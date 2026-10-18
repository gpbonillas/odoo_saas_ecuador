# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""SOMATECH-ODOO-BRIDGE — núcleo P1 (SRS-BRIDGE, Option A).

Capa L1: sesiones, RBAC y lecturas tipadas ``kpis/list/detail`` sobre Odoo.

Contratos (SRS-BRIDGE §4):
* FR-BR-01: autenticación VÍA Odoo (``common.login``) — sin store de usuarios paralelo.
* FR-BR-02: RBAC Odoo groups → rol → entidades; **deny-by-default** (rol sin
  permisos = ningún acceso, no "todo lo no prohibido").
* FR-BR-03: el token porta el ``db`` (tenant); TODA lectura va a ese db.
* FR-BR-04: lecturas con drill-down ``kpis → list → detail`` por entidad.
* FR-BR-07: datos legales faltantes ⇒ bloque ``needs_data`` (pregunta), nunca fallo.

Seguridad (SEC-01/02): secreto SÓLO por env ``BRIDGE_TOKEN_SECRET``; tokens
HMAC-SHA256 (stdlib), payload json+base64url, comparación constante.

Este módulo es puro (sin red): el conector se inyecta — en producción
``OdooJsonRpcConnector`` (bridge_http), en tests un fake. Sin dependencias
nuevas: sólo stdlib.
"""
import base64
import hashlib
import hmac
import json
import re
import time

__all__ = [
    "BridgeError", "BridgeAuthError", "BridgeRbacError", "BridgeNotFound",
    "BridgeConfigError", "BridgeUpstreamError",
    "TokenService", "BridgeCore", "ENTITIES", "ROLE_ENTITIES", "DEFAULT_ROLE_MAP",
    "NAV", "nav_for_role", "MAX_LIMIT", "DEFAULT_TTL",
]

MAX_LIMIT = 100
DEFAULT_LIMIT = 20
DEFAULT_TTL = 8 * 3600  # 8 h — sesión de operación diaria


# ---------------------------------------------------------------------------
# Errores (mapeados a HTTP en bridge_http)
# ---------------------------------------------------------------------------
class BridgeError(Exception):
    code = "bridge_error"
    http_status = 500

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_dict(self):
        out = {"code": self.code, "message": self.message}
        if self.hint:
            out["hint"] = self.hint
        return {"error": out}


class BridgeAuthError(BridgeError):
    code = "auth_error"
    http_status = 401


class BridgeRbacError(BridgeError):
    code = "rbac_denied"
    http_status = 403


class BridgeNotFound(BridgeError):
    code = "not_found"
    http_status = 404


class BridgeConfigError(BridgeError):
    code = "config_error"
    http_status = 500


class BridgeUpstreamError(BridgeError):
    code = "upstream_unreachable"
    http_status = 502


# ---------------------------------------------------------------------------
# RBAC — Odoo groups → rol → entidades (deny-by-default)
# ---------------------------------------------------------------------------
# Mapa base (per-tenant sobreescribible en P2 vía config):
DEFAULT_ROLE_MAP = {
    "base.group_system": "admin",
    "base.group_user": "operario",
    "mrp.group_mrp_user": "produccion",
    "mrp.group_mrp_manager": "gerente",
    "stock.group_stock_user": "bodega",
}

# Entidades legibles por rol (vacío = nada; nada implícito fuera de esta tabla):
# P3 (CHG-2026-013): predios (agro piso) y eventos (auditoría append-only).
ROLE_ENTITIES = {
    "admin": {"lotes", "ciclos", "analisis", "predios", "eventos"},
    "gerente": {"lotes", "ciclos", "analisis", "predios", "eventos"},
    "produccion": {"lotes", "ciclos", "predios"},
    "bodega": {"lotes"},
    "operario": set(),
}

# Jerarquía (mayor = más privilegio; decide cuando un usuario tiene varios roles)
ROLE_RANK = ["operario", "bodega", "produccion", "gerente", "admin"]


def role_for_groups(group_xmlids, role_map=None):
    """Devuelve el rol de mayor privilegio del usuario (deny-by-default: None)."""
    role_map = role_map or DEFAULT_ROLE_MAP
    best, best_i = None, -1
    for xmlid in group_xmlids:
        role = role_map.get(xmlid)
        if not role:
            continue
        i = ROLE_RANK.index(role) if role in ROLE_RANK else -1
        if i > best_i:
            best, best_i = role, i
    return best


def entities_for_role(role):
    return set(ROLE_ENTITIES.get(role, set()))


# ---------------------------------------------------------------------------
# Entidades P1 (vertical AGRO) — registry = añadir entidad es configuración
# ---------------------------------------------------------------------------
ENTITIES = {
    "lotes": {
        "model": "stock.lot",
        "fields": [
            "id", "name", "product_id", "l10n_ec_crop_type", "l10n_ec_variety",
            "l10n_ec_cycle_id", "l10n_ec_harvest_date", "l10n_ec_lab_state",
            "l10n_ec_sanitary_reg", "product_qty",
        ],
        "filters": {"lab_state": "l10n_ec_lab_state", "cycle": "l10n_ec_cycle_id",
                    "crop": "l10n_ec_crop_type"},
        "groupby": "l10n_ec_lab_state",
        "order": "id desc",
    },
    "ciclos": {
        "model": "l10n_ec.agro.cycle",
        "fields": [
            "id", "display_name", "plot_id", "crop_id", "variety", "sow_date",
            "expected_harvest_date", "actual_harvest_date", "state",
        ],
        "filters": {"state": "state"},
        "groupby": "state",
        "order": "id desc",
    },
    "analisis": {
        "model": "l10n_ec.agro.analysis",
        "fields": [
            "id", "lot_id", "analyte", "value", "unit", "limit", "passed",
            "lab_name", "analysis_date",
        ],
        "filters": {"passed": "passed", "analyte": "analyte"},
        "groupby": None,
        "order": "id desc",
    },
    "predios": {
        "model": "l10n_ec.agro.plot",
        "fields": [
            "id", "name", "code", "hectares", "location",
            "responsible_id", "active",
        ],
        "filters": {"active": "active"},
        "groupby": None,
        "order": "id desc",
    },
    "eventos": {
        "model": "l10n_ec.agro.trace_event",
        "fields": [
            "id", "lot_id", "stage", "qty", "partner_id", "comprobante",
            "event_date",
        ],
        "filters": {"stage": "stage"},
        "groupby": "stage",
        "order": "event_date desc, id desc",
    },
}

# ---------------------------------------------------------------------------
# Nav (SRS-BRIDGE §5.2) — el bridge sirve el árbol filtrado por rol; la UI
# sólo renderiza lo que llega aquí. Cada item exige TODAS sus entidades.
# ---------------------------------------------------------------------------
NAV = [
    {"key": "operacion", "label": "Operación", "entities": ["lotes"]},
    {"key": "gestion", "label": "Gestión", "entities": ["ciclos", "analisis"]},
    {"key": "lotes", "label": "Lotes", "entities": ["lotes"]},
    {"key": "predios", "label": "Predios", "entities": ["predios"]},
    {"key": "trazabilidad", "label": "Trazabilidad", "entities": ["lotes"]},
    {"key": "eventos", "label": "Eventos", "entities": ["eventos"]},
    {"key": "wizard", "label": "Wizard", "entities": [], "roles": ["admin", "gerente"]},
    {"key": "chat", "label": "Agente", "entities": [], "roles": None},
]


def nav_for_role(role):
    """Árbol de navegación permitido para el rol (deny-by-default)."""
    allowed = entities_for_role(role)
    out = []
    for item in NAV:
        roles = item.get("roles")
        if roles is not None and role not in roles:
            continue
        if not set(item["entities"]) <= allowed:
            continue
        out.append({"key": item["key"], "label": item["label"]})
    return out


def _entity(name):
    spec = ENTITIES.get(name)
    if not spec:
        raise BridgeNotFound(
            "Entidad desconocida: %s" % name,
            hint="Entidades P1: %s" % ", ".join(sorted(ENTITIES)),
        )
    return spec


def _m2o(value):
    """Extrae el id de un many2one de Odoo (viene como [id, name] o escalar)."""
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


# -- chat helpers (P3, CHG-2026-013) ------------------------------------------
_DIGIT_RE = re.compile(r"\b(\d{10,13})\b")
_LOT_RE = re.compile(r"lote\s+(\S+)")
_ID_KEYWORDS = (
    "ruc", "cedula", "cédula", "validar", "valida", "valido",
    "identificacion", "identificación", "contribuyente", "cliente",
)


# ---------------------------------------------------------------------------
# Tokens HMAC-SHA256 (stdlib)
# ---------------------------------------------------------------------------
class TokenService:
    def __init__(self, secret, ttl_seconds=DEFAULT_TTL):
        if not secret:
            raise BridgeConfigError(
                "Falta BRIDGE_TOKEN_SECRET (SEC-01: secretos sólo por env).")
        self._key = secret.encode("utf-8")
        self.ttl = int(ttl_seconds)

    def issue(self, db, uid, login, role, now=None):
        payload = {
            "db": db, "uid": int(uid), "login": login, "role": role,
            "exp": int(now or time.time()) + self.ttl,
        }
        body = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).decode("ascii")
        return "%s.%s" % (body, self._sign(body))

    def _sign(self, body):
        mac = hmac.new(self._key, body.encode("ascii"), hashlib.sha256)
        return base64.urlsafe_b64encode(mac.digest()).decode("ascii")

    def verify(self, token, now=None):
        try:
            body, sig = token.rsplit(".", 1)
        except ValueError:
            raise BridgeAuthError("Token malformado.")
        expected = self._sign(body)
        if not hmac.compare_digest(sig, expected):
            raise BridgeAuthError("Firma de token inválida.")
        try:
            payload = json.loads(base64.urlsafe_b64decode(body).decode("utf-8"))
        except (ValueError, TypeError):
            raise BridgeAuthError("Payload de token inválido.")
        if int(payload.get("exp", 0)) < int(now or time.time()):
            raise BridgeAuthError("Sesión expirada; ingrese de nuevo.",
                                  hint="Vuelva a llamar POST /auth/login.")
        return payload


# ---------------------------------------------------------------------------
# Núcleo
# ---------------------------------------------------------------------------
class BridgeCore:
    """Fachada del bridge. El conector (Odoo real o fake) se inyecta.

    Interfaz del conector:
      authenticate(db, login, password) -> uid (int) o falsy
      execute(db, model, method, args, kwargs=None) -> resultado Odoo
      group_xmlids(db, group_ids) -> [xmlid]
    """

    def __init__(self, connector, tokens, role_map=None):
        self.connector = connector
        self.tokens = tokens
        self.role_map = role_map or DEFAULT_ROLE_MAP

    # -- auth (FR-BR-01) --------------------------------------------------
    def login(self, db, login, password):
        uid = self.connector.authenticate(db, login, password)
        if not uid:
            raise BridgeAuthError("Credenciales inválidas para %s@%s." % (login, db),
                                  hint="Verifique usuario/contraseña Odoo.")
        user = self.connector.execute(
            db, "res.users", "read", [int(uid)],
            {"fields": ["name", "login", "groups_id"]})
        if not user:
            raise BridgeAuthError("Usuario no encontrado tras autenticar.")
        user = user[0]
        xmlids = self.connector.group_xmlids(db, user.get("groups_id") or [])
        role = role_for_groups(xmlids, self.role_map)
        out = {
            "token": self.tokens.issue(db, uid, user.get("login") or login, role),
            "db": db,
            "uid": int(uid),
            "name": user.get("name"),
            "role": role,
            "entities": sorted(entities_for_role(role)),
        }
        needs = self._needs_data(db)
        if needs:
            out["needs_data"] = needs  # FR-BR-07: pregunta, nunca fallo
        return out

    def _needs_data(self, db):
        """Chequeo legal mínimo P1: tenant sin RUC ⇒ pregunta."""
        try:
            company = self.connector.execute(
                db, "res.company", "search_read", [[]],
                {"fields": ["name", "vat"], "limit": 1})
        except BridgeError:
            return None
        if company and not company[0].get("vat"):
            return [{
                "scope": "company",
                "question": "La empresa %s no tiene RUC registrado. "
                            "¿Cuál es el RUC de la empresa (13 dígitos)?"
                            % company[0].get("name", "(sin nombre)"),
                "field": "vat",
            }]
        return None

    # -- autoridad de acceso ----------------------------------------------
    def _authz(self, token, entity):
        payload = self.tokens.verify(token)
        role = payload.get("role")
        if entity not in entities_for_role(role):
            raise BridgeRbacError(
                "El rol '%s' no tiene acceso a la entidad '%s'." % (role, entity),
                hint="Accesos del rol: %s" % (", ".join(sorted(entities_for_role(role))) or "ninguno"))
        return payload

    # -- lecturas (FR-BR-04) ----------------------------------------------
    def kpis(self, token, entity):
        spec = _entity(entity)
        payload = self._authz(token, entity)
        db = payload["db"]
        if entity == "lotes":
            groups = self.connector.execute(
                db, spec["model"], "read_group", [[]],
                {"fields": [spec["groupby"]], "groupby": [spec["groupby"]],
                 "lazy": False})
            por_estado = {str(g.get(spec["groupby"]) or "sin_estado"): g.get("__count", 0)
                          for g in groups}
            return {
                "entity": entity,
                "total": sum(por_estado.values()),
                "por_estado_lab": por_estado,
                "bloqueados": por_estado.get("failed", 0),
            }
        if entity == "ciclos":
            groups = self.connector.execute(
                db, spec["model"], "read_group", [[]],
                {"fields": [spec["groupby"]], "groupby": [spec["groupby"]],
                 "lazy": False})
            por_estado = {str(g.get(spec["groupby"]) or "sin_estado"): g.get("__count", 0)
                          for g in groups}
            return {"entity": entity,
                    "total": sum(por_estado.values()),
                    "por_estado": por_estado}
        if entity == "eventos":
            groups = self.connector.execute(
                db, spec["model"], "read_group", [[]],
                {"fields": [spec["groupby"]], "groupby": [spec["groupby"]],
                 "lazy": False})
            por_etapa = {str(g.get(spec["groupby"]) or "sin_etapa"): g.get("__count", 0)
                         for g in groups}
            return {"entity": entity,
                    "total": sum(por_etapa.values()),
                    "por_etapa": por_etapa}
        if entity == "predios":
            total = self.connector.execute(db, spec["model"], "search_count", [[]])
            activos = self.connector.execute(
                db, spec["model"], "search_count", [[("active", "=", True)]])
            return {"entity": entity, "total": total, "activos": activos}
        # analisis: total + no conformes
        total = self.connector.execute(db, spec["model"], "search_count", [[]])
        fallidos = self.connector.execute(
            db, spec["model"], "search_count", [[("passed", "=", False)]])
        return {"entity": entity, "total": total, "no_conformes": fallidos}

    def list(self, token, entity, limit=DEFAULT_LIMIT, offset=0, filters=None):
        spec = _entity(entity)
        payload = self._authz(token, entity)
        db = payload["db"]
        try:
            limit = max(1, min(int(limit), MAX_LIMIT))
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            raise BridgeError("limit/offset inválidos.")
        domain = []
        for key, value in (filters or {}).items():
            field = spec["filters"].get(key)
            if not field:
                raise BridgeNotFound(
                    "Filtro '%s' no soportado para %s." % (key, entity),
                    hint="Filtros: %s" % ", ".join(sorted(spec["filters"])))
            domain.append((field, "=", value))
        rows = self.connector.execute(
            db, spec["model"], "search_read", [domain],
            {"fields": spec["fields"], "limit": limit, "offset": offset,
             "order": spec["order"]})
        total = self.connector.execute(db, spec["model"], "search_count", [domain])
        return {"entity": entity, "items": rows, "total": total,
                "limit": limit, "offset": offset}

    def detail(self, token, entity, res_id):
        spec = _entity(entity)
        payload = self._authz(token, entity)
        db = payload["db"]
        rows = self.connector.execute(
            db, spec["model"], "search_read", [[("id", "=", int(res_id))]],
            {"fields": spec["fields"], "limit": 1})
        if not rows:
            raise BridgeNotFound("%s %s no existe en %s." % (entity, res_id, db))
        row = rows[0]
        if entity == "lotes":
            # drill-down: análisis del lote (escenario de aceptación 2)
            row["analisis"] = self.connector.execute(
                db, "l10n_ec.agro.analysis", "search_read",
                [[("lot_id", "=", int(res_id))]],
                {"fields": ENTITIES["analisis"]["fields"], "order": "id desc"})
            row["trace"] = "/api/trace/lote/%d" % int(res_id)
        return {"entity": entity, "record": row}

    # -- P3: nav por rol (SRS-BRIDGE §5.2) --------------------------------
    def nav(self, token):
        payload = self.tokens.verify(token)
        role = payload.get("role")
        return {"role": role, "items": nav_for_role(role)}

    # -- P3: trazabilidad genealogía + recall (FR-AG-06/07) ----------------
    def trace(self, token, lot_id):
        """Genealogía up (ciclo→predio) + down (análisis/eventos/movimientos)
        + recall (facturas del producto desde cosecha)."""
        payload = self._authz(token, "lotes")
        db = payload["db"]
        spec = _entity("lotes")
        try:
            lot_pk = int(lot_id)
        except (TypeError, ValueError):
            raise BridgeError("lot_id inválido.")
        rows = self.connector.execute(
            db, spec["model"], "search_read", [[("id", "=", lot_pk)]],
            {"fields": spec["fields"], "limit": 1})
        if not rows:
            raise BridgeNotFound("Lote %s no existe en %s." % (lot_pk, db))
        lot = rows[0]

        # -- up: ciclo → predio
        cycle = plot = None
        cycle_id = _m2o(lot.get("l10n_ec_cycle_id"))
        if cycle_id:
            cyc = self.connector.execute(
                db, "l10n_ec.agro.cycle", "search_read", [[("id", "=", cycle_id)]],
                {"fields": ENTITIES["ciclos"]["fields"], "limit": 1})
            if cyc:
                cycle = cyc[0]
                plot_id = _m2o(cycle.get("plot_id"))
                if plot_id:
                    pl = self.connector.execute(
                        db, "l10n_ec.agro.plot", "search_read",
                        [[("id", "=", plot_id)]],
                        {"fields": ENTITIES["predios"]["fields"], "limit": 1})
                    plot = pl[0] if pl else None

        # -- down: análisis + eventos + movimientos
        analisis = self.connector.execute(
            db, "l10n_ec.agro.analysis", "search_read",
            [[("lot_id", "=", lot_pk)]],
            {"fields": ENTITIES["analisis"]["fields"], "order": "id desc"})
        eventos = self.connector.execute(
            db, "l10n_ec.agro.trace_event", "search_read",
            [[("lot_id", "=", lot_pk)]],
            {"fields": ENTITIES["eventos"]["fields"], "limit": 50,
             "order": ENTITIES["eventos"]["order"]})
        movimientos = self.connector.execute(
            db, "stock.move", "search_read", [[("lot_ids", "in", [lot_pk])]],
            {"fields": ["id", "state", "date", "picking_id", "location_dest_id",
                        "product_uom_qty"], "limit": 50,
             "order": "date desc, id desc"})

        # -- recall: facturas del producto desde la cosecha (FR-AG-06)
        recall = {"invoices": [], "harvest_date": lot.get("l10n_ec_harvest_date")}
        product_id = _m2o(lot.get("product_id"))
        if product_id and lot.get("l10n_ec_harvest_date"):
            domain = [("invoice_line_ids.product_id", "=", product_id),
                      ("invoice_date", ">=", lot["l10n_ec_harvest_date"])]
            try:
                recall["invoices"] = self.connector.execute(
                    db, "account.move", "search_read", [domain],
                    {"fields": ["id", "name", "invoice_date", "amount_total",
                                "state"], "limit": 50,
                     "order": "invoice_date desc, id desc"})
            except BridgeError:
                recall["invoices"] = []

        return {"entity": "lote_trace", "lot": lot,
                "up": {"cycle": cycle, "plot": plot},
                "down": {"analisis": analisis, "eventos": eventos,
                         "movimientos": movimientos},
                "recall": recall}

    # -- P3: wizard (FR-AG-10/12 vía bridge; apply = acción ⚠ admin) -------
    def wizard_templates(self, token):
        payload = self._authz_roles(token, {"admin", "gerente"})
        db = payload["db"]
        rows = self.connector.execute(
            db, "l10n_ec.vertical.template", "catalog_json", [])
        return {"templates": rows}

    def wizard_params(self, token):
        payload = self._authz_roles(token, {"admin", "gerente"})
        db = payload["db"]
        rows = self.connector.execute(
            db, "l10n_ec.vertical.param", "search_read", [[]],
            {"fields": ["key", "value", "value_type", "source", "vertical"],
             "limit": 200, "order": "key asc"})
        return {"params": rows}

    def wizard_preview(self, token, vertical, size="medium"):
        payload = self._authz_roles(token, {"admin", "gerente"})
        db = payload["db"]
        plan = self.connector.execute(
            db, "l10n_ec.vertical.template", "preview", [vertical, size])
        return {"vertical": vertical, "size": size, "plan": plan}

    def wizard_apply(self, token, vertical, size="medium"):
        # AGT-01: apply muta el tenant ⇒ sólo admin (acciones ⚠)
        payload = self._authz_roles(token, {"admin"})
        db = payload["db"]
        result = self.connector.execute(
            db, "l10n_ec.vertical.template", "apply", [vertical, size])
        return {"vertical": vertical, "size": size, "applied": result}

    def _authz_roles(self, token, roles):
        payload = self.tokens.verify(token)
        role = payload.get("role")
        if role not in roles:
            raise BridgeRbacError(
                "Requiere rol %s; su rol '%s' no puede ejecutar esta acción."
                % ("|".join(sorted(roles)), role),
                hint="Acciones wizard: preview/params=gerente+admin, apply=admin")
        return payload

    # -- P3: chat con tools reales (escenario 3, AGT-03) ------------------
    def chat(self, token, message, context=None):
        """Determinista: valida ID (rules) o ejecuta tools reales con el
        MISMO token del usuario ⇒ el agente respeta el RBAC (AGT-03).
        Siempre con pie de atribución; nada inventado."""
        import rules as _rules  # stdlib puro, import perezoso
        payload = self.tokens.verify(token)
        db = payload["db"]
        text = (message or "").strip()
        low = text.lower()
        attribution = "puente directo Odoo (sin LLM)"
        tools_used = []

        # tool 1: validar identificación (RUC/cédula) — rules deterministas
        match = _DIGIT_RE.search(text)
        if match and (text == match.group(1)
                      or any(k in low for k in _ID_KEYWORDS)):
            vat = match.group(1)
            res = _rules.validate_vat(vat)
            if res["valid"]:
                kind = (res["id_type"] or "").upper()
                formula = "mod-10" if res["id_type"] == "cedula" else "mod-11/mod-10"
                reply = "%s %s: dígito verificador VÁLIDO (%s del SRI)." % (
                    kind, vat, formula)
            else:
                reply = "%s: NO válido — %s." % (vat, "; ".join(res["errors"]))
            return {"reply": reply, "engine": "rules",
                    "attribution": "via validate_vat · bridge → rules",
                    "context": context}

        # tool 2: stock real de un lote (escenario 3)
        lot_match = _LOT_RE.search(low)
        if lot_match:
            lot_name = lot_match.group(1)
            ent = "lotes"
            if ent not in entities_for_role(payload.get("role")):
                return {"reply": "Su rol '%s' no tiene acceso a la entidad "
                                 "'%s'; no puedo leer stock de lotes."
                                 % (payload.get("role"), ent),
                        "engine": "tools", "attribution": "RBAC denegado (deny-by-default)",
                        "context": context}
            rows = self.connector.execute(
                db, "stock.lot", "search_read", [[("name", "ilike", lot_name)]],
                {"fields": ["id", "name", "product_qty", "l10n_ec_lab_state",
                            "l10n_ec_harvest_date"], "limit": 10,
                 "order": "id desc"})
            tools_used.append("stock.lot.search_read(ilike=%s)" % lot_name)
            if not rows:
                return {"reply": "No encontré lotes que coincidan con '%s' en "
                                 "el tenant %s." % (lot_name, db),
                        "engine": "tools", "attribution": attribution,
                        "context": context, "tools": tools_used}
            lines = ["%s: %.2f uds (%s)" % (
                r.get("name"), r.get("product_qty") or 0.0,
                r.get("l10n_ec_lab_state") or "sin estado") for r in rows]
            return {"reply": "Stock real de lotes que coinciden con '%s':\n%s"
                             % (lot_name, "\n".join(lines)),
                    "engine": "tools", "attribution": attribution,
                    "context": context, "tools": tools_used}

        # sin tool aplicable: nunca inventar
        return {"reply": "Puedo validar RUC/cédula o leer stock real de un "
                         "lote. Ej: «validar RUC 1793125212001» o «stock lote "
                         "CAF-SMOKE-01».",
                "engine": "rules", "attribution": "sin tool aplicable",
                "context": context}
