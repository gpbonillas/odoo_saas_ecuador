# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Contract tests SOMATECH-ODOO-BRIDGE P1 (SRS-BRIDGE §4/§9, CHG-2026-010).

Cobertura: tokens HMAC (FR-BR-01), matriz RBAC con negativos (FR-BR-02),
aislamiento de tenant (FR-BR-03), contratos kpis/list/detail (FR-BR-04),
needs_data (FR-BR-07) y la capa HTTP real sobre puerto efímero.

Todo con stdlib: fake de conector + http.server + urllib.
"""
import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import bridge  # noqa: E402
import bridge_http  # noqa: E402
from bridge import (  # noqa: E402
    BridgeAuthError, BridgeCore, BridgeNotFound, BridgeRbacError, TokenService,
)

SECRET = "test-secret-para-la-suite"

GID = {"system": 10, "user": 20, "mrp_user": 30, "mrp_manager": 40, "stock_user": 50}
GXML = {10: "base.group_system", 20: "base.group_user", 30: "mrp.group_mrp_user",
        40: "mrp.group_mrp_manager", 50: "stock.group_stock_user"}


class FakeOdoo:
    """Conector falso multi-tenant con la interfaz de BridgeCore."""

    def __init__(self):
        self.calls = []  # (db, model, method)
        self.users = {
            1: {"id": 1, "name": "Ada Admin", "login": "admin",
                "groups_id": [GID["system"]], "password": "pw-admin"},
            2: {"id": 2, "name": "Gera Gerente", "login": "gerente",
                "groups_id": [GID["mrp_manager"], GID["user"]], "password": "pw-gerente"},
            3: {"id": 3, "name": "Pro Produccion", "login": "produccion",
                "groups_id": [GID["mrp_user"], GID["user"]], "password": "pw-produccion"},
            4: {"id": 4, "name": "Bo Bodega", "login": "bodega",
                "groups_id": [GID["stock_user"], GID["user"]], "password": "pw-bodega"},
            5: {"id": 5, "name": "Ola Operario", "login": "operario",
                "groups_id": [GID["user"]], "password": "pw-operario"},
        }
        lot_fields = ("id", "name", "l10n_ec_lab_state")
        self.dbs = {
            "odooec": {
                "res.company": [{"name": "CANNACHAIN S.A.S.", "vat": "1793125212001"}],
                "stock.lot": [
                    {"id": 1, "name": "LOTE-1", "l10n_ec_lab_state": "none",
                     "product_id": "Cafe", "l10n_ec_variety": "Typica",
                     "l10n_ec_crop_type": "CAFE", "l10n_ec_cycle_id": 1,
                     "l10n_ec_harvest_date": "2026-09-01", "l10n_ec_sanitary_reg": "",
                     "product_qty": 100.0},
                    {"id": 2, "name": "LOTE-2", "l10n_ec_lab_state": "passed",
                     "product_id": "Cafe", "l10n_ec_variety": "Typica",
                     "l10n_ec_crop_type": "CAFE", "l10n_ec_cycle_id": 1,
                     "l10n_ec_harvest_date": "2026-09-02", "l10n_ec_sanitary_reg": "",
                     "product_qty": 50.0},
                    {"id": 3, "name": "LOTE-3", "l10n_ec_lab_state": "failed",
                     "product_id": "Cacao", "l10n_ec_variety": "CCN-51",
                     "l10n_ec_crop_type": "CACAO", "l10n_ec_cycle_id": 2,
                     "l10n_ec_harvest_date": "2026-09-03", "l10n_ec_sanitary_reg": "",
                     "product_qty": 0.0},
                ],
                "l10n_ec.agro.cycle": [
                    {"id": 1, "display_name": "Norte/CAFE/2026-08-01", "plot_id": "Norte",
                     "crop_id": "CAFE", "variety": "Typica", "sow_date": "2026-08-01",
                     "expected_harvest_date": "2026-11-01", "actual_harvest_date": False,
                     "state": "growing"},
                    {"id": 2, "display_name": "Sur/CACAO/2026-03-01", "plot_id": "Sur",
                     "crop_id": "CACAO", "variety": "CCN-51", "sow_date": "2026-03-01",
                     "expected_harvest_date": "2026-08-01", "actual_harvest_date": "2026-08-05",
                     "state": "closed"},
                ],
                "l10n_ec.agro.analysis": [
                    {"id": 1, "lot_id": 2, "analyte": "Humedad", "value": 9.0,
                     "unit": "%", "limit": 12.0, "passed": True, "lab_name": "LAB-1",
                     "analysis_date": "2026-09-05"},
                    {"id": 2, "lot_id": 3, "analyte": "Humedad", "value": 18.0,
                     "unit": "%", "limit": 12.0, "passed": False, "lab_name": "LAB-1",
                     "analysis_date": "2026-09-06"},
                ],
            },
            # tenant B: empresa SIN RUC => login debe incluir needs_data (FR-BR-07)
            "tenantb": {
                "res.company": [{"name": "Tenant B Agro", "vat": ""}],
                "stock.lot": [{"id": 9, "name": "TB-UNICO", "l10n_ec_lab_state": "none"}],
                "l10n_ec.agro.cycle": [],
                "l10n_ec.agro.analysis": [],
            },
        }
        self._lot_fields = lot_fields

    # interfaz del conector --------------------------------------------
    def authenticate(self, db, login, password):
        table = self.dbs.get(db)
        if not table:
            return 0
        for user in self.users.values():
            if user["login"] == login and user["password"] == password:
                return user["id"]
        return 0

    def group_xmlids(self, db, group_ids):
        return [GXML[g] for g in group_ids if g in GXML]

    def execute(self, db, model, method, args, kwargs=None):
        kwargs = kwargs or {}
        self.calls.append((db, model, method))
        table = self.dbs.get(db)
        if table is None:
            raise AssertionError("¡consulta a tenant desconocido: %s!" % db)
        if model == "res.users":
            uid = args[0]
            user = self.users[uid]
            return [{k: user.get(k) for k in kwargs.get("fields", [])} or dict(user)]
        rows = table.get(model, [])
        if method == "search_read":
            matched = _apply_domain(rows, args[0] if args else [])
            order = kwargs.get("order") or ""
            if order.endswith("desc"):
                matched = sorted(matched, key=lambda r: r.get("id") or 0, reverse=True)
            fields = kwargs.get("fields")
            if fields:
                matched = [{k: r.get(k) for k in fields} for r in matched]
            offset = int(kwargs.get("offset") or 0)
            limit = kwargs.get("limit")
            matched = matched[offset:]
            if limit is not None:
                matched = matched[: int(limit)]
            return matched
        if method == "search_count":
            return len(_apply_domain(rows, args[0] if args else []))
        if method == "read_group":
            field = (kwargs.get("groupby") or [None])[0]
            counts = {}
            for r in rows:
                key = r.get(field)
                counts[key] = counts.get(key, 0) + 1
            return [{field: k, "__count": v} for k, v in counts.items()]
        raise AssertionError("método fake no soportado: %s" % method)


def _apply_domain(rows, domain):
    out = rows
    for clause in domain or []:
        field, op, value = clause
        if op == "=":
            out = [r for r in out if r.get(field) == value]
        else:
            raise AssertionError("operador fake no soportado: %s" % op)
    return out


def make_core(fake=None):
    fake = fake or FakeOdoo()
    return BridgeCore(fake, TokenService(SECRET)), fake


def login_token(core, login="admin", db="odooec", password=None):
    password = password or ("pw-" + login)
    return core.login(db, login, password)["token"]


class TestTokenService(unittest.TestCase):
    def test_roundtrip(self):
        tokens = TokenService(SECRET)
        token = tokens.issue("odooec", 1, "admin", "admin")
        payload = tokens.verify(token)
        self.assertEqual(payload["db"], "odooec")
        self.assertEqual(payload["uid"], 1)
        self.assertEqual(payload["role"], "admin")

    def test_tampered_signature_rejected(self):
        tokens = TokenService(SECRET)
        token = tokens.issue("odooec", 1, "admin", "admin")
        body, sig = token.rsplit(".", 1)
        with self.assertRaises(BridgeAuthError):
            tokens.verify(body + "x." + sig)

    def test_expired_rejected(self):
        tokens = TokenService(SECRET, ttl_seconds=1)
        token = tokens.issue("odooec", 1, "admin", "admin", now=time.time() - 10)
        with self.assertRaises(BridgeAuthError):
            tokens.verify(token)

    def test_wrong_secret_rejected(self):
        token = TokenService(SECRET).issue("odooec", 1, "admin", "admin")
        with self.assertRaises(BridgeAuthError):
            TokenService("otro-secreto").verify(token)

    def test_missing_secret_is_config_error(self):
        with self.assertRaises(bridge.BridgeConfigError):
            TokenService("")


class TestAuthAndNeedsData(unittest.TestCase):
    def test_login_shape_and_role(self):
        core, _ = make_core()
        out = core.login("odooec", "gerente", "pw-gerente")
        self.assertIn("token", out)
        self.assertEqual(out["role"], "gerente")
        self.assertEqual(out["entities"], ["analisis", "ciclos", "lotes"])
        self.assertNotIn("needs_data", out)  # odooec tiene RUC

    def test_bad_credentials_401(self):
        core, _ = make_core()
        with self.assertRaises(BridgeAuthError):
            core.login("odooec", "admin", "mala")

    def test_needs_data_question_when_company_has_no_ruc(self):
        core, _ = make_core()
        out = core.login("tenantb", "admin", "pw-admin")
        self.assertIn("needs_data", out)
        self.assertIn("RUC", out["needs_data"][0]["question"])
        self.assertEqual(out["needs_data"][0]["field"], "vat")


class TestRbacMatrix(unittest.TestCase):
    def setUp(self):
        self.core, self.fake = make_core()

    def _token(self, login):
        return login_token(self.core, login)

    def test_admin_reads_everything(self):
        for ent in ("lotes", "ciclos", "analisis"):
            self.core.kpis(self._token("admin"), ent)

    def test_gerente_reads_everything(self):
        for ent in ("lotes", "ciclos", "analisis"):
            self.core.list(self._token("gerente"), ent, limit=5)

    def test_produccion_cannot_read_analisis(self):
        token = self._token("produccion")
        self.core.list(token, "lotes", limit=5)  # sí
        with self.assertRaises(BridgeRbacError):
            self.core.kpis(token, "analisis")    # no

    def test_bodega_only_lotes(self):
        token = self._token("bodega")
        self.core.detail(token, "lotes", 1)
        with self.assertRaises(BridgeRbacError):
            self.core.list(token, "ciclos")
        with self.assertRaises(BridgeRbacError):
            self.core.list(token, "analisis")

    def test_operario_denied_everything(self):
        token = self._token("operario")
        for ent in ("lotes", "ciclos", "analisis"):
            with self.assertRaises(BridgeRbacError):
                self.core.kpis(token, ent)

    def test_rank_highest_role_wins(self):
        # gerente también es operario (base.group_user) => gerente gana
        out = self.core.login("odooec", "gerente", "pw-gerente")
        self.assertEqual(out["role"], "gerente")


class TestTenantIsolation(unittest.TestCase):
    def test_reads_use_token_db_only(self):
        core, fake = make_core()
        token = login_token(core, db="tenantb")
        core.kpis(token, "lotes")
        core.list(token, "lotes", limit=5)
        read_calls = [c for c in fake.calls if c[1] in (
            "stock.lot", "l10n_ec.agro.cycle", "l10n_ec.agro.analysis")]
        self.assertTrue(read_calls)
        self.assertEqual({c[0] for c in read_calls}, {"tenantb"})


class TestReadContracts(unittest.TestCase):
    def setUp(self):
        self.core, self.fake = make_core()
        self.token = login_token(self.core)

    def test_kpis_lotes_contract(self):
        out = self.core.kpis(self.token, "lotes")
        self.assertEqual(out["entity"], "lotes")
        self.assertEqual(out["total"], 3)
        self.assertEqual(out["bloqueados"], 1)
        self.assertEqual(out["por_estado_lab"],
                         {"none": 1, "passed": 1, "failed": 1})

    def test_kpis_ciclos_contract(self):
        out = self.core.kpis(self.token, "ciclos")
        self.assertEqual(out["total"], 2)
        self.assertEqual(out["por_estado"], {"growing": 1, "closed": 1})

    def test_kpis_analisis_contract(self):
        out = self.core.kpis(self.token, "analisis")
        self.assertEqual(out, {"entity": "analisis", "total": 2, "no_conformes": 1})

    def test_list_whitelist_and_pagination(self):
        out = self.core.list(self.token, "lotes", limit=2, offset=1)
        self.assertEqual(out["total"], 3)
        self.assertEqual(len(out["items"]), 2)
        self.assertEqual(out["limit"], 2)
        allowed = set(bridge.ENTITIES["lotes"]["fields"])
        for row in out["items"]:
            self.assertTrue(set(row).issubset(allowed),
                            "campos fuera de whitelist: %s" % (set(row) - allowed))
        self.assertEqual([r["id"] for r in out["items"]], [2, 1])  # id desc

    def test_list_limit_is_capped(self):
        out = self.core.list(self.token, "lotes", limit=999)
        self.assertEqual(out["limit"], bridge.MAX_LIMIT)

    def test_list_filter(self):
        out = self.core.list(self.token, "lotes", filters={"lab_state": "failed"})
        self.assertEqual([r["id"] for r in out["items"]], [3])

    def test_unknown_filter_404(self):
        with self.assertRaises(BridgeNotFound):
            self.core.list(self.token, "lotes", filters={"otro": 1})

    def test_unknown_entity_404(self):
        with self.assertRaises(BridgeNotFound):
            self.core.kpis(self.token, "facturas")

    def test_detail_lot_includes_analisis(self):
        out = self.core.detail(self.token, "lotes", 3)
        self.assertEqual(out["record"]["name"], "LOTE-3")
        self.assertEqual(len(out["record"]["analisis"]), 1)
        self.assertFalse(out["record"]["analisis"][0]["passed"])

    def test_detail_missing_404(self):
        with self.assertRaises(BridgeNotFound):
            self.core.detail(self.token, "lotes", 999)


class TestHttpLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core, cls.fake = make_core()
        cls.server = bridge_http.make_server("127.0.0.1", 0, cls.core)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _req(self, path, token=None, body=None, method=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data,
            method=method or ("POST" if data else "GET"))
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def _login(self, login="admin", db="odooec"):
        status, out = self._req("/auth/login", body={
            "db": db, "login": login, "password": "pw-" + login})
        self.assertEqual(status, 200, out)
        return out["token"]

    def _req_raw(self, path):
        """GET crudo: devuelve (status, content_type, body_text) para la
        UI estática (que no es JSON)."""
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as resp:
                ctype = resp.headers.get("Content-Type", "")
                return resp.status, ctype, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type", ""), ""

    def test_healthz(self):
        status, out = self._req("/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(out["status"], "ok")

    def test_login_and_kpis_over_http(self):
        token = self._login()
        status, out = self._req("/api/kpis/lotes", token=token)
        self.assertEqual(status, 200, out)
        self.assertEqual(out["total"], 3)

    def test_list_and_detail_over_http(self):
        token = self._login("gerente")
        status, out = self._req("/api/list/ciclos?state=growing", token=token)
        self.assertEqual(status, 200, out)
        self.assertEqual([r["id"] for r in out["items"]], [1])
        status, out = self._req("/api/detail/lotes/2", token=token)
        self.assertEqual(status, 200, out)
        self.assertEqual(out["record"]["name"], "LOTE-2")

    def test_missing_token_401(self):
        status, out = self._req("/api/kpis/lotes")
        self.assertEqual(status, 401)
        self.assertEqual(out["error"]["code"], "auth_error")

    def test_operario_403_over_http(self):
        token = self._login("operario")
        status, out = self._req("/api/kpis/lotes", token=token)
        self.assertEqual(status, 403)
        self.assertEqual(out["error"]["code"], "rbac_denied")

    def test_login_missing_fields_400(self):
        status, out = self._req("/auth/login", body={"db": "odooec"})
        self.assertEqual(status, 400)

    def test_unknown_route_404(self):
        status, out = self._req("/api/nope/lotes", token=self._login())
        self.assertEqual(status, 404)

    def test_needs_data_over_http(self):
        status, out = self._req("/auth/login", body={
            "db": "tenantb", "login": "admin", "password": "pw-admin"})
        self.assertEqual(status, 200)
        self.assertIn("needs_data", out)

    # -- UI estática (Option A, CHG-2026-012) ----------------------------
    def test_root_serves_login_html(self):
        status, ctype, body = self._req_raw("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("SOMATECH", body)
        self.assertIn("login-form", body)

    def test_static_assets_served_with_types(self):
        status, ctype, body = self._req_raw("/app.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", ctype)
        self.assertIn("--brand: #ff4d00", body)  # tokens D-10
        status, ctype, body = self._req_raw("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)
        self.assertIn("BridgeApp", body)
        status, ctype, body = self._req_raw("/app.html")
        self.assertEqual(status, 200)
        self.assertIn("view-chat", body)

    def test_static_traversal_blocked(self):
        for path in ("/../../etc/passwd", "/app.css/../bridge.py",
                     "/%2e%2e/%2e%2e/etc/passwd", "/bridge.py", "/test_bridge.py"):
            status, _, _ = self._req_raw(path)
            self.assertEqual(status, 404, "traversal/no-whitelist pasó: %s" % path)

    # -- Chat (P2 semilla, motor rules) ----------------------------------
    def test_chat_requires_auth(self):
        status, out = self._req("/api/chat", body={"message": "hola"})
        self.assertEqual(status, 401)

    def test_chat_missing_message_400(self):
        status, out = self._req("/api/chat", token=self._login(),
                                body={"message": "  "})
        self.assertEqual(status, 400)

    def test_chat_validates_ruc(self):
        status, out = self._req("/api/chat", token=self._login(), body={
            "message": "validar RUC 1793125212001"})
        self.assertEqual(status, 200, out)
        self.assertIn("VÁLIDO", out["reply"])
        self.assertIn("1793125212001", out["reply"])
        self.assertIn("validate_vat", out["attribution"])

    def test_chat_validates_cedula_bare_number(self):
        status, out = self._req("/api/chat", token=self._login(), body={
            "message": "1713488185"})
        self.assertEqual(status, 200, out)
        self.assertIn("CEDULA", out["reply"])
        self.assertIn("VÁLIDO", out["reply"])

    def test_chat_rejects_bad_checksum(self):
        # mutación sintética de un ID aprobado (práctica D-04: los tests
        # usan mutaciones programáticas, no identidades reales). El dígito
        # mutado va DENTRO de los 10 primeros (los últimos 3 son establecimiento
        # y no entran al módulo 11 de la jurídica).
        status, out = self._req("/api/chat", token=self._login(), body={
            "message": "validar RUC 1893125212001"})
        self.assertEqual(status, 200, out)
        self.assertIn("NO válido", out["reply"])

    def test_chat_help_when_no_id(self):
        status, out = self._req("/api/chat", token=self._login(), body={
            "message": "hola, ¿qué puedes hacer?"})
        self.assertEqual(status, 200, out)
        self.assertEqual(out["engine"], "rules")
        self.assertIn("RUC", out["reply"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
