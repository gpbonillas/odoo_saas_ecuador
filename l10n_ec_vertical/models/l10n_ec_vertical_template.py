# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Catálogo + loader idempotente de plantillas verticales.

Contratos (ISO-EC-09):
* DES-02: la plantilla son **datos versionados en git** — un JSON por
  vertical/tamaño en ``<modulo>/templates/<vertical>_<size>.json``; el código
  sólo tiene el loader genérico (nunca condicionales por vertical).
* DES-03: cada plantilla declara ``version`` + ``checksum`` (sha256) +
  ``changelog``; la aplicación es **idempotente por XML-ID**: re-cargar
  = update, jamás duplicar.
* DES-04: ``preview()`` = **dry-run obligatorio** con diff create/update/skip
  antes de ``apply()``.
* FR-AG-10: re-corrida ⇒ 0 creates (verificado por test).
* FR-AG-12 / N-01: al aplicar se activan caps + params; guardrails
  (``cap.inv.stock`` auto-enable + explicación, ``agro``+``simple`` ⇒ warning,
  ``v.cultivos`` vacío ⇒ ``needs_data``).

El loader es agnóstico: las reglas por vertical viven en ``RULES`` como datos
(agregar un vertical = agregar una entrada, cero código nuevo — DES-06).
"""
import hashlib
import json
import os

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError

TEMPLATES_SUBDIR = "templates"
XMLID_PREFIX = "tmpl"  # ids: l10n_ec_vertical.tmpl_<codigo>_<modelo>_<clave>

# Reglas de guardrail por vertical (datos, no código — DES-06/D-05)
RULES = {
    "agro": {
        "required_caps": ("cap.inv.stock", "cap.mrp"),
        "required_caps_reason": "agro requiere inventario y producción (SRS-VERT §8)",
        "simple_warn": "agro + size=simple: se recomienda size=medium "
                       "(requiere inventario/producción)",
        "needs_data_param": "v.cultivos",
        "needs_data_question": "Vertical agro: indique al menos un cultivo "
                               "(p.ej. café, cacao, plátano, lino, cáñamo) — D-05.",
    },
}


def _norm(value):
    """Normaliza para comparar vals de Odoo (False ≈ '' ≈ None)."""
    if value in (None, False, ""):
        return False
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return value[0]
    return value


def _slug(text):
    return "".join(c if c.isalnum() else "_" for c in str(text)).strip("_").lower()


class L10nEcVerticalTemplate(models.Model):
    _name = "l10n_ec.vertical.template"
    _description = "Plantilla vertical publicada (catálogo DES-03)"
    _order = "vertical, size"

    code = fields.Char("Código", required=True, index=True, help="Ej: agro/medium")
    name = fields.Char(string="Nombre", compute="_compute_name", store=True)
    vertical = fields.Char(required=True, index=True)
    size = fields.Char(required=True)
    version = fields.Char(required=True)
    checksum = fields.Char(readonly=True, help="sha256 del archivo de especificación")
    changelog = fields.Text()
    data_path = fields.Char(readonly=True)
    active = fields.Boolean(default=True)
    applied_version = fields.Char(readonly=True, help="Versión aplicada por última vez")
    applied_at = fields.Datetime(readonly=True)

    _sql_constraints = [("code_uniq", "unique(code)", "El código de plantilla debe ser único.")]

    @api.depends("vertical", "size")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s / %s" % (rec.vertical or "?", rec.size or "?")

    # ------------------------------------------------------------------
    # Descubrimiento de especificaciones (DES-02)
    # ------------------------------------------------------------------
    @api.model
    def _spec_files(self):
        """Rutas absolutas de ``<mod>/templates/*.json`` de módulos instalados."""
        Mod = self.env["ir.module.module"].sudo()
        installed = Mod.search([("state", "=", "installed")]).mapped("name")
        found = []
        from odoo.modules import module as odoo_module

        for mod_name in installed:
            base = odoo_module.get_module_path(mod_name)
            if not base:
                continue
            folder = os.path.join(base, TEMPLATES_SUBDIR)
            if not os.path.isdir(folder):
                continue
            for fname in sorted(os.listdir(folder)):
                if fname.endswith(".json"):
                    found.append(os.path.join(folder, fname))
        return found

    @api.model
    def sync_catalog(self):
        """Idempotente: crea/actualiza la fila de catálogo por cada spec."""
        ids = []
        for path in self._spec_files():
            with open(path, "rb") as fh:
                raw = fh.read()
            try:
                spec = json.loads(raw.decode("utf-8"))
            except ValueError as exc:
                raise UserError("Spec inválida %s: %s" % (path, exc))
            for field_name in ("code", "vertical", "size", "version"):
                if not spec.get(field_name):
                    raise UserError("Spec %s sin campo obligatorio '%s' (DES-03)."
                                    % (path, field_name))
            checksum = hashlib.sha256(raw).hexdigest()
            row = self.sudo().search([("code", "=", spec["code"])], limit=1)
            vals = {
                "code": spec["code"],
                "vertical": spec["vertical"],
                "size": spec["size"],
                "version": spec["version"],
                "checksum": checksum,
                "changelog": spec.get("changelog") or "",
                "data_path": path,
            }
            if row:
                row.write(vals)
            else:
                row = self.sudo().create(vals)
            ids.append(row.id)
        return self.sudo().browse(ids)

    # ------------------------------------------------------------------
    # Carga de spec
    # ------------------------------------------------------------------
    @api.model
    def _load_spec(self, vertical, size):
        self.sync_catalog()
        row = self.sudo().search([("vertical", "=", vertical), ("size", "=", size),
                                  ("active", "=", True)], limit=1)
        if not row or not row.data_path:
            raise UserError("No existe plantilla para vertical='%s' size='%s'. "
                            "Available: %s" % (vertical, size,
                                               ", ".join(self.sudo().search([]).mapped("code")) or "ninguna"))
        with open(row.data_path, "rb") as fh:
            raw = fh.read()
        checksum = hashlib.sha256(raw).hexdigest()
        checksum_ok = checksum == row.checksum
        spec = json.loads(raw.decode("utf-8"))
        return spec, row, checksum, checksum_ok

    # ------------------------------------------------------------------
    # Dry-run (DES-04) — el corazón del loader
    # ------------------------------------------------------------------
    @api.model
    def preview(self, vertical, size):
        spec, row, checksum, checksum_ok = self._load_spec(vertical, size)
        plan = self._plan_from_spec(spec)
        plan["template"] = {
            "code": row.code, "version": row.version, "checksum": checksum,
            "checksum_ok": checksum_ok, "changelog": row.changelog,
        }
        plan["dry_run"] = True
        return plan

    @api.model
    def apply(self, vertical, size, dry_run=False):
        spec, row, checksum, checksum_ok = self._load_spec(vertical, size)
        plan = self._plan_from_spec(spec)
        plan["template"] = {
            "code": row.code, "version": row.version, "checksum": checksum,
            "checksum_ok": checksum_ok, "changelog": row.changelog,
        }
        plan["dry_run"] = bool(dry_run)
        if dry_run:
            return plan
        sudo = self.env(user=SUPERUSER_ID)
        # 1) registros (idempotente por XML-ID, DES-03)
        for item in plan["records"]:
            if item["action"] == "skip":
                continue
            Model = sudo[item["model"]]
            xmlid_tail = "%s_%s_%s" % (_slug(spec["code"]), _slug(item["model"]), item["key"])
            full_xmlid = "l10n_ec_vertical.%s_%s" % (XMLID_PREFIX, xmlid_tail)
            res_id = sudo["ir.model.data"]._xmlid_to_res_id(full_xmlid,
                                                           raise_if_not_found=False)
            if res_id:
                Model.browse(res_id).write(item["vals"])
            else:
                rec = Model.create(item["vals"])
                sudo["ir.model.data"].create({
                    "module": "l10n_ec_vertical",
                    "name": "%s_%s" % (XMLID_PREFIX, xmlid_tail),
                    "model": item["model"],
                    "res_id": rec.id,
                })
        # 2) params + caps (nunca pisa USER — FR-AG-12)
        Param = sudo["l10n_ec.vertical.param"]
        for item in plan["params"]:
            if item["action"] == "skip":
                continue
            Param.set_value(item["key"], item["value"],
                            value_type=item["value_type"], source="TEMPLATE",
                            vertical=spec["vertical"])
        row.write({"applied_version": spec["version"], "applied_at": fields.Datetime.now()})
        plan["applied"] = True
        return plan

    # ------------------------------------------------------------------
    # Plan (puro: spec + estado actual ⇒ diff) — testeable con specs inline
    # ------------------------------------------------------------------
    @api.model
    def _plan_from_spec(self, spec):
        sudo = self.env(user=SUPERUSER_ID)
        rule = RULES.get(spec.get("vertical"), {})
        records, params = [], []
        summary = {"create": 0, "update": 0, "skip": 0}

        def bump(action):
            summary[action] += 1

        # --- registros de datos (DES-02/03) -----------------------------
        for model, entries in (spec.get("data") or {}).items():
            if model not in sudo.registry:
                raise UserError("Spec %s: modelo desconocido '%s'." % (spec.get("code"), model))
            Model = sudo[model]
            for entry in entries:
                key = entry.get("key")
                if not key:
                    raise UserError("Spec %s: entrada de '%s' sin 'key'."
                                    % (spec.get("code"), model))
                vals = {k: v for k, v in entry.items() if k != "key"}
                xmlid_tail = "%s_%s_%s" % (_slug(spec["code"]), _slug(model), key)
                res_id = sudo["ir.model.data"]._xmlid_to_res_id(
                    "l10n_ec_vertical.%s_%s" % (XMLID_PREFIX, xmlid_tail),
                    raise_if_not_found=False)
                action = "create"
                if res_id:
                    rec = Model.browse(res_id)
                    current = {f: rec[f] for f in vals}
                    same = all(_norm(current[f]) == _norm(vals[f]) for f in vals)
                    action = "skip" if same else "update"
                bump(action)
                records.append({"action": action, "model": model, "key": key,
                                "xmlid": "l10n_ec_vertical.%s_%s" % (XMLID_PREFIX, xmlid_tail),
                                "vals": vals})

        # --- caps (auto-enable + explicación, FR-AG-12) -----------------
        caps = dict(spec.get("caps") or {})
        auto_enable = []
        for cap in rule.get("required_caps", ()):
            if not caps.get(cap):
                caps[cap] = True
                auto_enable.append({"key": cap, "reason": rule.get("required_caps_reason")})

        # --- params de plantilla (USER gana, nunca se pisa) -------------
        Param = sudo["l10n_ec.vertical.param"]
        for key, meta in list((spec.get("params") or {}).items()) + [
                (k, {"type": "bool", "value": v}) for k, v in caps.items()]:
            existing = Param.search([("key", "=", key)], limit=1)
            if existing and existing.source == "USER":
                action = "skip"  # FR-AG-12: el usuario manda
            elif existing and str(existing.value or "") == str(meta.get("value", "")):
                action = "skip"
            else:
                action = "update" if existing else "create"
            bump(action)
            params.append({"action": action, "key": key,
                           "value": meta.get("value"), "value_type": meta.get("type", "bool")})

        # --- guardrails verticales (N-01) -------------------------------
        warnings = []
        needs_data = []
        if spec.get("vertical") == "agro" and spec.get("size") == "simple":
            warnings.append(rule.get("simple_warn"))
        if rule.get("needs_data_param"):
            if not Param.search([("key", "=", rule["needs_data_param"])]):
                needs_data.append({
                    "scope": "wizard",
                    "field": rule["needs_data_param"],
                    "question": rule["needs_data_question"],
                })

        return {"records": records, "params": params, "summary": summary,
                "warnings": [w for w in warnings if w], "auto_enable": auto_enable,
                "needs_data": needs_data, "caps": caps}
