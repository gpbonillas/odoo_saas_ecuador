# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Store de parámetros del wizard (N-01) — 1 fila por clave.

Fuentes (convención N-01):
* ``TEMPLATE`` — lo pone la plantilla vertical (re-aplicar puede actualizarlo).
* ``USER``     — lo ingresó el usuario en el wizard; **nunca lo pisa** el loader.
* ``DEFAULT``  — constantes de la capa legal (no editable, DES-01/CAP-05).

Lectura tipada: ``get_value('v.lotes')`` devuelve bool/int/str según
``value_type``. Los guardrails (FR-AG-12/14) y el wizard leen por aquí.
"""
from odoo import api, fields, models

SOURCE = [("TEMPLATE", "Plantilla"), ("USER", "Usuario"), ("DEFAULT", "Defecto")]
VALUE_TYPES = [
    ("bool", "Booleano"),
    ("int", "Entero"),
    ("float", "Decimal"),
    ("text", "Texto"),
    ("select", "Selección"),
    ("multi", "Multi (CSV)"),
]

_TRUTHY = {"1", "true", "t", "yes", "y", "si", "sí", "on"}


class L10nEcVerticalParam(models.Model):
    _name = "l10n_ec.vertical.param"
    _description = "Parámetro de configuración vertical (catálogo N-01)"
    _order = "key"

    key = fields.Char("Clave", required=True, index=True, help="Ej: v.lotes, cap.inv.stock")
    value = fields.Text("Valor")
    value_type = fields.Selection(VALUE_TYPES, string="Tipo", default="text", required=True)
    source = fields.Selection(SOURCE, string="Fuente", default="TEMPLATE", required=True)
    vertical = fields.Char("Vertical", index=True, help="Vacío = aplica a todas")

    _sql_constraints = [("key_uniq", "unique(key)", "La clave de parámetro debe ser única.")]

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    @api.model
    def get_value(self, key, default=None):
        """Valor tipado del parámetro (o ``default`` si no existe)."""
        rec = self.sudo().search([("key", "=", key)], limit=1)
        if not rec:
            return default
        return rec.typed_value(default)

    def typed_value(self, default=None):
        self.ensure_one()
        raw = self.value
        if raw in (None, ""):
            return default
        if self.value_type == "bool":
            return str(raw).strip().lower() in _TRUTHY
        if self.value_type == "int":
            try:
                return int(raw)
            except ValueError:
                return default
        if self.value_type == "float":
            try:
                return float(raw)
            except ValueError:
                return default
        if self.value_type == "multi":
            return [v.strip() for v in str(raw).split(",") if v.strip()]
        return raw

    @api.model
    def set_value(self, key, value, value_type="text", source="USER", vertical=None):
        """Escritura del wizard (source=USER ganda sobre TEMPLATE)."""
        rec = self.sudo().search([("key", "=", key)], limit=1)
        vals = {
            "key": key,
            "value": "" if value is None else str(value),
            "value_type": value_type,
            "source": source,
            "vertical": vertical or False,
        }
        if rec:
            rec.write(vals)
        else:
            rec = self.sudo().create(vals)
        return rec
