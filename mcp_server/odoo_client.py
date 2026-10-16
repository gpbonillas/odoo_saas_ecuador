# -*- coding: utf-8 -*-
"""
Odoo JSON-RPC 2.0 client (stdlib only — no `requests`).

Endpoints used (all under `<ODOO_URL>/jsonrpc`):
  * service "common"  -> version          (connectivity check)
  * service "common"  -> login            (auth; captures session_id cookie)
  * service "object"  -> execute_kw       (model method dispatch)

Works with Odoo in Docker (http://odoo:8069) or local (http://localhost:8069)
via the ODOO_URL env var.  If Odoo is unreachable the client raises
OdooConnectionError; tool handlers convert that into structured errors so
the MCP server still starts and answers cleanly.
"""
import json
import logging
import os
import urllib.error
import urllib.request

_log = logging.getLogger("mcp.odoo")


class OdooError(Exception):
    """Base class for client errors."""

    def __init__(self, message, hint=None, data=None):
        super().__init__(message)
        self.hint = hint
        self.data = data


class OdooConnectionError(OdooError):
    pass


class OdooRPCError(OdooError):
    pass


class OdooClient:
    def __init__(self, url=None, db=None, user=None, password=None, timeout=None):
        self.url = (url or os.environ.get("ODOO_URL", "http://odoo:8069")).rstrip("/")
        self.db = db or os.environ.get("ODOO_DB", "odooec")
        self.user = user or os.environ.get("ODOO_USER", "admin")
        self.password = password or os.environ.get("ODOO_PASSWORD", "admin")
        self.timeout = float(timeout or os.environ.get("ODOO_TIMEOUT", "30"))
        self.uid = None
        self.session_id = None
        self._req_id = 0
        # Cookie jar so common.login session_id is reused on execute_kw
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor())

    # ------------------------------------------------------------------
    # Low-level JSON-RPC
    # ------------------------------------------------------------------
    def _rpc(self, service, method, params):
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": params},
            "id": self._req_id,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/jsonrpc",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise OdooConnectionError(
                "Odoo devolvió HTTP %s en %s" % (exc.code, self.url),
                hint="Revise que el servidor Odoo esté levantado y que la "
                     "URL ODOO_URL sea correcta.",
            )
        except urllib.error.URLError as exc:
            raise OdooConnectionError(
                "No se pudo conectar con Odoo en %s (%s)" % (self.url, exc.reason),
                hint="Levante el clúster con `docker compose up -d odoo db` o "
                     "ajuste ODOO_URL (ej. http://localhost:8069).",
            )
        except TimeoutError:
            raise OdooConnectionError(
                "Timeout conectando a Odoo (%s)" % self.url,
                hint="Odoo puede estar arrancando; reintente en unos segundos.")
        try:
            data = json.loads(raw)
        except ValueError:
            raise OdooRPCError("Respuesta no-JSON de Odoo: %s" % raw[:200])
        if data.get("error"):
            err = data["error"] or {}
            msg = err.get("message") or "error desconocido"
            data_obj = err.get("data") or {}
            if isinstance(data_obj, dict) and data_obj.get("debug"):
                msg = "%s: %s" % (msg, str(data_obj.get("debug"))[-400:])
            raise OdooRPCError(msg, data=err)
        return data.get("result")

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def login(self):
        """Authenticate via service=db login; cache uid + session_id."""
        try:
            self._rpc("common", "version", [])
        except OdooError:
            raise  # connectivity failure — propagate structured
        # Odoo 18: auth lives on the "common" service (exp_login ->
        # exp_authenticate). The "db" service no longer exposes login.
        result = self._rpc("common", "login",
                           [self.db, self.user, self.password])
        if not result:
            raise OdooRPCError(
                "Login falló para usuario %s en BD %s" % (self.user, self.db),
                hint="Verifique ODOO_USER / ODOO_PASSWORD / ODOO_DB.")
        self.uid = int(result)
        for cookie in getattr(self._opener, "cookiejar", []):
            if cookie.name == "session_id":
                self.session_id = cookie.value
        _log.info("autenticado uid=%s db=%s session=%s",
                  self.uid, self.db, "yes" if self.session_id else "no")
        return self.uid

    def _ensure_session(self):
        if self.uid is None:
            self.login()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute(self, model, method, args=None, kwargs=None):
        """
        execute_kw wrapper: env[model].<method>(*args, **kwargs).
        Auth uses the cached session_id (falls back to password).
        """
        self._ensure_session()
        args = args or []
        kwargs = kwargs or {}
        auth = self.session_id or self.password
        params = [self.db, self.uid, auth, model, method, args, kwargs]
        try:
            return self._rpc("object", "execute_kw", params)
        except OdooRPCError as exc:
            text = str(exc).lower()
            if any(s in text for s in ("access denied", "session", "token",
                                       "expired", "accesserror")):
                # Session went stale or session_id auth unsupported -> retry
                # once with the real password.
                if auth != self.password:
                    _log.warning("session rechazada, reintento con password")
                    self.session_id = None
                    params[2] = self.password
                    return self._rpc("object", "execute_kw", params)
            raise

    def search_read(self, model, domain=None, fields=None, limit=None, order=None):
        kwargs = {"domain": domain or [], "fields": fields or []}
        if limit:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return self.execute(model, "search_read", [], kwargs)

    def read(self, model, ids, fields=None):
        return self.execute(model, "read", [ids, fields or []])

    def create(self, model, vals):
        return self.execute(model, "create", [vals])

    def write(self, model, ids, vals):
        return self.execute(model, "write", [ids, vals])

    def call_kw(self, model, method, args=None, kwargs=None):
        return self.execute(model, method, args or [], kwargs or {})

    def config_param(self, key, default=None):
        rows = self.search_read("ir.config_parameter",
                                [("key", "=", key)], ["value"], limit=1)
        if rows and rows[0].get("value") not in (None, ""):
            return rows[0]["value"]
        return default

    def status(self):
        """Non-raising connectivity probe for tools/resources."""
        try:
            version = self._rpc("common", "version", [])
        except OdooError as exc:
            return {"reachable": False, "url": self.url, "db": self.db,
                    "error": str(exc), "hint": exc.hint}
        out = {"reachable": True, "url": self.url, "db": self.db,
               "server_version": (version or {}).get("server_version"),
               "authenticated": self.uid is not None}
        if self.uid is None:
            try:
                self.login()
                out["authenticated"] = True
            except OdooError as exc:
                out["authenticated"] = False
                out["auth_error"] = str(exc)
                out["hint"] = exc.hint
        return out
