#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) server — stdio transport, pure Python 3 stdlib.

JSON-RPC 2.0 over newline-delimited JSON on stdin/stdout.  Implements:
  initialize, notifications/initialized, tools/list, tools/call,
  resources/list, resources/read, ping.

Registered by OpenCode as:
  {"type": "local", "command": ["python3", "<abs>/mcp_server/server.py"],
   "environment": {"ODOO_URL": "http://localhost:8069", ...}}

STDOUT is reserved for the MCP channel.  All logging goes to stderr.
"""
import datetime
import json
import logging
import os
import sys
import traceback

# Allow running as a plain script: python3 mcp_server/server.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import odoo_client  # noqa: E402
import rules        # noqa: E402
import tools        # noqa: E402

SERVER_NAME = "odoo-ecuador-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

_log = logging.getLogger(SERVER_NAME)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _client_singleton():
    """Build the Odoo client lazily (Odoo may be down — server must still start)."""
    if not hasattr(_client_singleton, "_inst"):
        _client_singleton._inst = odoo_client.OdooClient()
    return _client_singleton._inst


# ---------------------------------------------------------------------------
# Static resources exposed over MCP resources/*
# ---------------------------------------------------------------------------
def _resources():
    return [
        {"uri": "ec://rules",
         "name": "Reglas fiscales ecuatorianas",
         "description": "Límites y constantes que aplica el motor de reglas "
                        "(CF $50, día 7 anulación, 5 días hábiles retención, "
                        "tablas IR/IVA, feriados).",
         "mimeType": "application/json"},
        {"uri": "ec://holidays",
         "name": "Feriados ecuatorianos",
         "description": "Feriados nacionales del año en curso (incluye "
                        "Carnaval y Viernes Santo vía computus gregoriano).",
         "mimeType": "application/json"},
        {"uri": "odoo://status",
         "name": "Estado del backend Odoo",
         "description": "Alcanzabilidad y autenticación contra el Odoo "
                        "configurado (ODOO_URL/ODOO_DB).",
         "mimeType": "application/json"},
    ]


def _read_resource(uri):
    if uri == "ec://rules":
        payload = {
            "cf_ruc": rules.CF_RUC_DEFAULT,
            "cf_limit_usd": rules.CF_LIMIT_DEFAULT,
            "annulment_day_limit": rules.ANNULMENT_DAY_DEFAULT,
            "retention_business_days": rules.RETENTION_BUSINESS_DAYS,
            "iva_retention_casilleros": {"721": 10.0, "723": 20.0,
                                         "725": 30.0, "727": 50.0,
                                         "729": 70.0, "731": 100.0},
            "ir_tabla19": {"servicios": list(rules.VALID_IR_SERVICIOS),
                           "bienes": list(rules.VALID_IR_BIENES)},
            "iva_rates": list(rules.IVA_RATES),
            "doc_types": rules.DOC_TYPES,
            "iess": {"personal": rules.IESS_PERSONAL_RATE,
                     "patronal": rules.IESS_PATRONAL_RATE,
                     "techo_sbu_mult": rules.IESS_BASE_MULTIPLIER_CAP},
        }
    elif uri == "ec://holidays":
        year = datetime.date.today().year
        payload = {"year": year,
                   "holidays": sorted(d.isoformat()
                                      for d in rules.ec_holidays(year))}
    elif uri == "odoo://status":
        payload = _client_singleton().status()
    else:
        return None
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# JSON-RPC dispatch
# ---------------------------------------------------------------------------
def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def handle_request(msg):
    """Return a JSON-RPC response dict, or None for notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _error(None, INVALID_REQUEST, "invalid request")
    method = msg.get("method")
    req_id = msg.get("id", None)
    params = msg.get("params") or {}
    is_notification = "id" not in msg

    _log.info("-> %s (id=%s)", method, req_id)

    if method == "initialize":
        client_proto = params.get("protocolVersion")
        return _result(req_id, {
            "protocolVersion": client_proto or PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False},
                             "resources": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions":
                "Gateway MCP para Odoo con localización ecuatoriana. Use "
                "detect_taxpayer/get_client_data antes de create_invoice; si "
                "responde status=needs_data, responda la 'question' al usuario "
                "y vuelva a llamar con los datos faltantes.",
        })

    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None  # notification — no response

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": tools.list_tools()})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            return _error(req_id, INVALID_PARAMS, "missing tool name")
        result = tools.call_tool(_client_singleton(), name, arguments)
        is_error = result.get("status") == "error"
        return _result(req_id, {
            "content": [{"type": "text",
                         "text": json.dumps(result, ensure_ascii=False,
                                            default=str)}],
            "isError": is_error,
        })

    if method == "resources/list":
        return _result(req_id, {"resources": _resources()})

    if method == "resources/read":
        uri = params.get("uri")
        text = _read_resource(uri) if uri else None
        if text is None:
            return _error(req_id, INVALID_PARAMS, "unknown resource: %s" % uri)
        return _result(req_id, {"contents": [{"uri": uri,
                                             "mimeType": "application/json",
                                             "text": text}]})

    if is_notification:
        _log.warning("notificación no soportada ignorada: %s", method)
        return None
    return _error(req_id, METHOD_NOT_FOUND, "method not found: %s" % method)


def main():
    _log.info("%s v%s iniciando (transporte stdio). ODOO_URL=%s db=%s",
              SERVER_NAME, SERVER_VERSION,
              os.environ.get("ODOO_URL", "http://odoo:8069"),
              os.environ.get("ODOO_DB", "odooec"))
    stdout = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = _error(None, PARSE_ERROR, "parse error")
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()
            continue
        try:
            resp = handle_request(msg)
        except Exception as exc:  # noqa: BLE001
            _log.error("error interno: %s\n%s", exc, traceback.format_exc())
            req_id = msg.get("id") if isinstance(msg, dict) else None
            resp = _error(req_id, INTERNAL_ERROR, "internal error: %s" % exc)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
            stdout.flush()
    _log.info("stdin cerrado; terminando")


if __name__ == "__main__":
    main()
