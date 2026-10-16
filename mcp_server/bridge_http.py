# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""SOMATECH-ODOO-BRIDGE — API HTTP/JSON (stdlib), P1 (Option A).

Endpoints (SRS-BRIDGE §9 P1):
  POST /auth/login                  → {token, role, entities, ...}   (FR-BR-01)
  GET  /api/kpis/<entidad>          → KPIs de la entidad             (FR-BR-04)
  GET  /api/list/<entidad>          → listado paginado (limit/offset/filtros)
  GET  /api/detail/<entidad>/<id>   → detalle (+analisis para lotes)
  GET  /healthz                     → estado

Auth: ``Authorization: Bearer <token>``. Token HMAC firmado por BRIDGE_TOKEN_SECRET
(SEC-01/02: sólo env; nunca en repo). El token porta el tenant (db) — FR-BR-03.

Conector Odoo: JSON-RPC sobre /jsonrpc reutilizando ``odoo_client.OdooClient``
(cuenta servicio ODOO_USER para lecturas; el login del usuario final valida con
``common.login`` en SU db — sin store de usuarios paralelo).

Todo el log va a STDERR (stdout queda reservado para el canal MCP).
"""
import argparse
import json
import logging
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bridge import (  # noqa: E402
    BridgeAuthError, BridgeCore, BridgeError, TokenService,
)
import odoo_client  # noqa: E402
import rules  # noqa: E402 — motor legal determinista del chat (AGT-03)

# -- UI estática (Option A, CHG-2026-012): servida por la propia puerta ------
WEB_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
# Lista blanca: cero riesgo de path-traversal, cero archivos fuera de web/.
STATIC_FILES = {
    "": ("index.html", "text/html; charset=utf-8"),          # raíz = login
    "index.html": ("index.html", "text/html; charset=utf-8"),
    "app.html": ("app.html", "text/html; charset=utf-8"),
    "app.css": ("app.css", "text/css; charset=utf-8"),
    "app.js": ("app.js", "application/javascript; charset=utf-8"),
}

# -- Chat (P2 semilla): motor de reglas; LLM llega en P3 ---------------------
_DIGIT_RE = re.compile(r"\b(\d{10,13})\b")
_ID_KEYWORDS = (
    "ruc", "cedula", "cédula", "validar", "valida", "valido",
    "identificacion", "identificación", "contribuyente", "cliente",
)


def chat_reply(message):
    """Respuesta determinista del panel de chat (AGT-03: no inventa)."""
    text = (message or "").strip()
    low = text.lower()
    match = _DIGIT_RE.search(text)
    if match and (text == match.group(1)
                  or any(k in low for k in _ID_KEYWORDS)):
        vat = match.group(1)
        res = rules.validate_vat(vat)
        if res["valid"]:
            kind = (res["id_type"] or "").upper()
            formula = "mod-10" if res["id_type"] == "cedula" else "mod-11/mod-10"
            reply = "%s %s: dígito verificador VÁLIDO (%s del SRI)." % (
                kind, vat, formula)
        else:
            reply = "%s: NO válido — %s." % (vat, "; ".join(res["errors"]))
        return {
            "reply": reply,
            "engine": "rules",
            "attribution": "via validate_vat · bridge → rules",
        }
    return {
        "reply": "Puedo validar RUC y cédulas del SRI con el motor de reglas "
                 "(ej: «validar RUC 1793125212001»). En P3 se conecta el agente "
                 "con las herramientas del ERP. Si falta un dato legal, "
                 "pregunto — nunca invento.",
        "engine": "rules",
        "attribution": "via help · bridge → rules",
    }

_log = logging.getLogger("bridge")
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# ---------------------------------------------------------------------------
# Conector Odoo real (JSON-RPC)
# ---------------------------------------------------------------------------
class OdooJsonRpcConnector:
    """Implementa la interfaz de BridgeCore sobre el Odoo del tenant."""

    def __init__(self, client=None):
        self.client = client or odoo_client.OdooClient()

    def authenticate(self, db, login, password):
        # common.login devuelve uid o False (credenciales malas = False,
        # no excepción). Un error de red sí truena (OdooRPCError → upstream).
        try:
            result = self.client._rpc("common", "login", [db, login, password])
        except odoo_client.OdooError as exc:
            raise BridgeError("Odoo no disponible: %s" % exc, hint="Revise ODOO_URL/db.")
        return int(result) if result else 0

    def execute(self, db, model, method, args, kwargs=None):
        self.client._ensure_session()
        auth = self.client.session_id or self.client.password
        params = [db, self.client.uid, auth, model, method, args or [], kwargs or {}]
        try:
            return self.client._rpc("object", "execute_kw", params)
        except odoo_client.OdooRPCError as exc:
            if self.client.session_id and auth != self.client.password:
                params[2] = self.client.password
                try:
                    return self.client._rpc("object", "execute_kw", params)
                except odoo_client.OdooRPCError as exc2:
                    raise BridgeError("Odoo rechazó la operación: %s" % exc2)
            raise BridgeError("Odoo rechazó la operación: %s" % exc)

    def group_xmlids(self, db, group_ids):
        if not group_ids:
            return []
        rows = self.execute(
            db, "ir.model.data", "search_read", [],
            {"domain": [["model", "=", "res.groups"],
                        ["res_id", "in", list(group_ids)]],
             "fields": ["module", "name", "res_id"], "limit": 500})
        return ["%s.%s" % (r["module"], r["name"]) for r in rows]


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "SomatechBridge/1.0"
    protocol_version = "HTTP/1.1"

    # inyectado por main(): core = BridgeCore
    core = None

    # -- utilidades --------------------------------------------------------
    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, exc):
        status = getattr(exc, "http_status", 500)
        if not isinstance(exc, BridgeError):
            _log.exception("error interno")
            payload = {"error": {"code": "internal", "message": "Error interno del bridge."}}
            status = 500
        else:
            payload = exc.to_dict()
        self._send(status, payload)

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            raise BridgeError("Body JSON inválido.")

    def _token(self):
        header = self.headers.get("Authorization") or ""
        if not header.startswith("Bearer "):
            raise BridgeAuthError("Falta header Authorization: Bearer <token>.")
        return header[len("Bearer "):].strip()

    def log_message(self, fmt, *args):  # log propio a stderr, sin ruido de access-log
        _log.info("%s %s", self.address_string(), fmt % args)

    # -- ruteo -------------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        try:
            # -- UI estática (whitelist: sin traversal, Option A P2) ------
            if parsed.path in ("/", "/index.html", "/app.html",
                               "/app.css", "/app.js"):
                return self._serve_static(parsed.path)
            if parts == ["healthz"]:
                return self._send(200, {"status": "ok", "service": "somatech-odoo-bridge"})
            if len(parts) == 3 and parts[:2] == ["api", "kpis"]:
                return self._send(200, self.core.kpis(self._token(), parts[2]))
            if len(parts) == 3 and parts[:2] == ["api", "list"]:
                return self._send(200, self.core.list(
                    self._token(), parts[2],
                    limit=query.get("limit", 20), offset=query.get("offset", 0),
                    filters={k: v for k, v in query.items() if k not in ("limit", "offset")}))
            if len(parts) == 4 and parts[:2] == ["api", "detail"]:
                return self._send(200, self.core.detail(self._token(), parts[2], parts[3]))
            return self._not_found(parsed.path)
        except BridgeError as exc:
            self._error(exc)
        except Exception as exc:  # pragma: no cover - red
            self._error(exc)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        try:
            if parts == ["auth", "login"]:
                body = self._json_body()
                missing = [f for f in ("db", "login", "password") if not body.get(f)]
                if missing:
                    return self._bad_request("Faltan campos: %s." % ", ".join(missing))
                return self._send(200, self.core.login(
                    body["db"], body["login"], body["password"]))
            if parts == ["api", "chat"]:
                # Cualquier rol autenticado usa el chat (contexto de rol se
                # inyecta en P3 con el agente LLM); el token sólo autentica.
                self._token()  # valida Bearer (401 si falta/malformado)
                body = self._json_body()
                if not str(body.get("message") or "").strip():
                    return self._bad_request("Falta 'message'.")
                return self._send(200, chat_reply(body["message"]))
            self._not_found(parsed.path)
        except BridgeError as exc:
            self._error(exc)
        except Exception as exc:  # pragma: no cover - red
            self._error(exc)

    def _serve_static(self, path):
        """Sirve un archivo de la lista blanca STATIC_FILES (sin traversal)."""
        name, content_type = STATIC_FILES[path.lstrip("/") or ""]
        full = os.path.realpath(os.path.join(WEB_ROOT, name))
        if not full.startswith(os.path.realpath(WEB_ROOT) + os.sep):
            return self._not_found(path)  # defensa en profundidad
        try:
            with open(full, "rb") as fh:
                payload = fh.read()
        except OSError:
            return self._not_found(path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(payload)

    def _not_found(self, path):
        self._send(404, {"error": {"code": "not_found",
                                   "message": "Ruta no encontrada: %s" % path}})

    def _bad_request(self, message):
        self._send(400, {"error": {"code": "bad_request", "message": message}})


def make_server(host, port, core):
    handler = type("BoundBridgeHandler", (BridgeHandler,), {"core": core})
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="SOMATECH-ODOO-BRIDGE HTTP/JSON (P1)")
    parser.add_argument("--host", default=os.environ.get("BRIDGE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("BRIDGE_PORT", "8090")))
    args = parser.parse_args(argv)

    secret = os.environ.get("BRIDGE_TOKEN_SECRET", "")
    tokens = TokenService(secret)  # sin secreto ⇒ BridgeConfigError (SEC-01)
    connector = OdooJsonRpcConnector()
    core = BridgeCore(connector, tokens)
    server = make_server(args.host, args.port, core)
    _log.info("bridge escuchando en http://%s:%s (tenant db=%s)",
              args.host, args.port, connector.client.db)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log.info("bridge detenido")
        server.server_close()


if __name__ == "__main__":
    main()
