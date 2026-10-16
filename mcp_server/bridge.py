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
import time

__all__ = [
    "BridgeError", "BridgeAuthError", "BridgeRbacError", "BridgeNotFound",
    "BridgeConfigError", "BridgeUpstreamError",
    "TokenService", "BridgeCore", "ENTITIES", "ROLE_ENTITIES", "DEFAULT_ROLE_MAP",
    "MAX_LIMIT", "DEFAULT_TTL",
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
ROLE_ENTITIES = {
    "admin": {"lotes", "ciclos", "analisis"},
    "gerente": {"lotes", "ciclos", "analisis"},
    "produccion": {"lotes", "ciclos"},
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
        "filters": {"lab_state": "l10n_ec_lab_state", "cycle": "l10n_ec_cycle_id"},
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
}


def _entity(name):
    spec = ENTITIES.get(name)
    if not spec:
        raise BridgeNotFound(
            "Entidad desconocida: %s" % name,
            hint="Entidades P1: %s" % ", ".join(sorted(ENTITIES)),
        )
    return spec


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
        return {"entity": entity, "record": row}
