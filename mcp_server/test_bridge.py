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
                    {"id": 1, "display_name": "Norte/CAFE/2026-08-01", "plot_id": [1, "Norte"],
                     "crop_id": "CAFE", "variety": "Typica", "sow_date": "2026-08-01",
                     "expected_harvest_date": "2026-11-01", "actual_harvest_date": False,
                     "state": "growing"},
                    {"id": 2, "display_name": "Sur/CACAO/2026-03-01", "plot_id": [2, "Sur"],
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
                # P3 (CHG-2026-013): predios + eventos + movimientos + recall
                "l10n_ec.agro.plot": [
                    {"id": 1, "name": "Norte", "code": "PN-01", "hectares": 5.5,
                     "location": "Pichincha", "responsible_id": "Ada", "active": True},
                    {"id": 2, "name": "Sur", "code": "PS-01", "hectares": 3.0,
                     "location": "Los Ríos", "responsible_id": "Bo", "active": True},
                ],
                "l10n_ec.agro.trace_event": [
                    {"id": 1, "lot_id": 2, "stage": "harvest", "qty": 120.0,
                     "partner_id": "Camp", "comprobante": "GR-001",
                     "event_date": "2026-09-02 08:00:00"},
                    {"id": 2, "lot_id": 2, "stage": "analysis", "qty": 0.0,
                     "partner_id": False, "comprobante": "LAB-001",
                     "event_date": "2026-09-05 10:00:00"},
                    {"id": 3, "lot_id": 3, "stage": "harvest", "qty": 80.0,
                     "partner_id": "Camp", "comprobante": "GR-002",
                     "event_date": "2026-09-03 09:00:00"},
                ],
                "stock.move": [
                    {"id": 1, "state": "done", "date": "2026-09-03 12:00:00",
                     "picking_id": "Pick-1", "location_dest_id": "Stock",
                     "product_uom_qty": 100.0, "lot_ids": [1]},
                    {"id": 2, "state": "done", "date": "2026-09-06 14:00:00",
                     "picking_id": "Pick-2", "location_dest_id": "Stock",
                     "product_uom_qty": 50.0, "lot_ids": [2]},
                ],
                "account.move": [
                    {"id": 1, "name": "INV/2026/0001", "invoice_date": "2026-09-10",
                     "amount_total": 1200.0, "state": "posted",
                     "invoice_line_ids_product_id": "Cafe"},
                    {"id": 2, "name": "INV/2026/0002", "invoice_date": "2026-09-12",
                     "amount_total": 600.0, "state": "posted",
                     "invoice_line_ids_product_id": "Cacao"},
                ],
                "l10n_ec.vertical.template": [],
                "l10n_ec.vertical.param": [],
            },
            # tenant B: empresa SIN RUC => login debe incluir needs_data (FR-BR-07)
            "tenantb": {
                "res.company": [{"name": "Tenant B Agro", "vat": ""}],
                "stock.lot": [{"id": 9, "name": "TB-UNICO", "l10n_ec_lab_state": "none"}],
                "l10n_ec.agro.cycle": [],
                "l10n_ec.agro.analysis": [],
                "l10n_ec.agro.plot": [],
                "l10n_ec.agro.trace_event": [],
                "stock.move": [],
                "account.move": [],
                "l10n_ec.vertical.template": [],
                "l10n_ec.vertical.param": [],
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
        # P3: métodos del loader de plantillas (wizard vía bridge)
        if model == "l10n_ec.vertical.template" and method == "catalog_json":
            return [{"id": 1, "code": "agro/medium", "name": "agro / medium",
                     "vertical": "agro", "size": "medium", "version": "1.0.0",
                     "checksum": "abc123", "changelog": "alta inicial",
                     "applied_version": "", "applied_at": None}]
        if model == "l10n_ec.vertical.template" and method == "preview":
            return {"dry_run": True, "summary": {"create": 16, "update": 0, "skip": 0},
                    "records": [], "params": [], "warnings": [], "auto_enable": [],
                    "needs_data": [], "caps": {}, "template": {"code": "agro/medium"}}
        if model == "l10n_ec.vertical.template" and method == "apply":
            return {"applied": True, "summary": {"create": 16, "update": 0, "skip": 0},
                    "records": [], "params": [], "warnings": [], "auto_enable": [],
                    "needs_data": [], "caps": {}, "template": {"code": "agro/medium"}}
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
        # campo anidado (invoice_line_ids.product_id) ⇒ fake lo aplana con _
        lookup = field.replace(".", "_")
        if op == "=":
            out = [r for r in out if r.get(lookup) == value]
        elif op == "ilike":
            needle = str(value or "").lower()
            out = [r for r in out if needle in str(r.get(lookup) or "").lower()]
        elif op == "in":
            keep = []
            for r in out:
                row_val = r.get(lookup)
                if isinstance(row_val, (list, tuple)):
                    if set(row_val) & set(value):
                        keep.append(r)
                elif row_val in value:
                    keep.append(r)
            out = keep
        elif op == ">=":
            out = [r for r in out if str(r.get(lookup) or "") >= str(value)]
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
        self.assertEqual(out["entities"], ["analisis", "ciclos", "eventos", "lotes", "predios"])
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

    # -- P3: nav / trace / wizard / chat-tools sobre HTTP (CHG-2026-013) --
    def test_nav_over_http(self):
        token = self._login("gerente")
        status, out = self._req("/api/nav", token=token)
        self.assertEqual(status, 200, out)
        keys = {i["key"] for i in out["items"]}
        self.assertIn("predios", keys)
        self.assertIn("wizard", keys)

    def test_nav_operario_over_http(self):
        token = self._login("operario")
        status, out = self._req("/api/nav", token=token)
        self.assertEqual(status, 200, out)
        keys = {i["key"] for i in out["items"]}
        self.assertEqual(keys, {"chat"})

    def test_trace_over_http(self):
        token = self._login()
        status, out = self._req("/api/trace/lote/2", token=token)
        self.assertEqual(status, 200, out)
        self.assertEqual(out["lot"]["name"], "LOTE-2")
        self.assertEqual(out["up"]["plot"]["name"], "Norte")
        self.assertEqual(len(out["recall"]["invoices"]), 1)

    def test_trace_missing_over_http_404(self):
        token = self._login()
        status, out = self._req("/api/trace/lote/999", token=token)
        self.assertEqual(status, 404)

    def test_wizard_templates_over_http(self):
        token = self._login()
        status, out = self._req("/api/wizard/templates", token=token)
        self.assertEqual(status, 200, out)
        self.assertEqual(out["templates"][0]["code"], "agro/medium")

    def test_wizard_params_over_http(self):
        token = self._login()
        status, out = self._req("/api/wizard/params", token=token)
        self.assertEqual(status, 200, out)
        self.assertIn("params", out)

    def test_wizard_preview_over_http(self):
        token = self._login()
        status, out = self._req("/api/wizard/preview", token=token,
                                body={"vertical": "agro", "size": "medium"})
        self.assertEqual(status, 200, out)
        self.assertIn("plan", out)

    def test_wizard_preview_missing_vertical_400(self):
        token = self._login()
        status, out = self._req("/api/wizard/preview", token=token, body={})
        self.assertEqual(status, 400)

    def test_wizard_apply_admin_over_http(self):
        token = self._login()
        status, out = self._req("/api/wizard/apply", token=token,
                                body={"vertical": "agro", "size": "medium"})
        self.assertEqual(status, 200, out)
        self.assertTrue(out["applied"]["applied"])

    def test_wizard_apply_gerente_403_over_http(self):
        token = self._login("gerente")
        status, out = self._req("/api/wizard/apply", token=token,
                                body={"vertical": "agro", "size": "medium"})
        self.assertEqual(status, 403)
        self.assertEqual(out["error"]["code"], "rbac_denied")

    def test_chat_stock_tool_over_http(self):
        status, out = self._req("/api/chat", token=self._login(), body={
            "message": "stock lote LOTE-2"})
        self.assertEqual(status, 200, out)
        self.assertEqual(out["engine"], "tools")
        self.assertIn("LOTE-2", out["reply"])
        self.assertIn("50.00", out["reply"])

    def test_chat_stock_tool_operario_denied_over_http(self):
        status, out = self._req("/api/chat", token=self._login("operario"), body={
            "message": "stock lote LOTE-2"})
        self.assertEqual(status, 200, out)
        self.assertIn("no tiene acceso", out["reply"])

    def test_chat_context_echo_over_http(self):
        status, out = self._req("/api/chat", token=self._login(), body={
            "message": "stock lote LOTE-1",
            "context": {"view": "trazabilidad", "entity": "lotes"}})
        self.assertEqual(status, 200, out)
        self.assertEqual(out["context"], {"view": "trazabilidad", "entity": "lotes"})


class TestNavByRole(unittest.TestCase):
    """P3 (CHG-2026-013): nav por rol, deny-by-default (SRS-BRIDGE §5.2)."""

    def setUp(self):
        self.core, _ = make_core()

    def _token(self, login):
        return login_token(self.core, login)

    def test_admin_nav_has_all_items(self):
        out = self.core.nav(self._token("admin"))
        keys = {i["key"] for i in out["items"]}
        self.assertIn("operacion", keys)
        self.assertIn("predios", keys)
        self.assertIn("trazabilidad", keys)
        self.assertIn("eventos", keys)
        self.assertIn("wizard", keys)
        self.assertIn("chat", keys)

    def test_gerente_nav_has_wizard(self):
        out = self.core.nav(self._token("gerente"))
        keys = {i["key"] for i in out["items"]}
        self.assertIn("wizard", keys)

    def test_produccion_nav_no_wizard_no_analisis(self):
        out = self.core.nav(self._token("produccion"))
        keys = {i["key"] for i in out["items"]}
        self.assertNotIn("wizard", keys)        # roles=[admin,gerente]
        self.assertNotIn("gestion", keys)       # gestion exige analisis
        self.assertIn("lotes", keys)
        self.assertIn("predios", keys)

    def test_bodega_nav_only_lotes(self):
        out = self.core.nav(self._token("bodega"))
        keys = {i["key"] for i in out["items"]}
        self.assertIn("lotes", keys)
        self.assertNotIn("predios", keys)       # bodega sin predios
        self.assertNotIn("eventos", keys)
        self.assertNotIn("wizard", keys)

    def test_operario_nav_empty_except_chat(self):
        out = self.core.nav(self._token("operario"))
        keys = {i["key"] for i in out["items"]}
        self.assertEqual(keys, {"chat"})  # sólo chat (sin entidades)


class TestNewEntities(unittest.TestCase):
    """P3: predios + eventos en el registry con contrato kpis/list."""

    def setUp(self):
        self.core, self.fake = make_core()
        self.token = login_token(self.core)

    def test_predios_list_contract(self):
        out = self.core.list(self.token, "predios", limit=10)
        self.assertEqual(out["entity"], "predios")
        self.assertEqual(out["total"], 2)
        self.assertEqual([r["id"] for r in out["items"]], [2, 1])  # id desc
        row = out["items"][0]
        self.assertIn("name", row)
        self.assertIn("hectares", row)

    def test_eventos_list_contract(self):
        out = self.core.list(self.token, "eventos", limit=10)
        self.assertEqual(out["entity"], "eventos")
        self.assertEqual(out["total"], 3)
        row = out["items"][0]
        self.assertIn("stage", row)
        self.assertIn("event_date", row)

    def test_eventos_kpis_por_etapa(self):
        out = self.core.kpis(self.token, "eventos")
        self.assertEqual(out["total"], 3)
        self.assertEqual(out["por_etapa"], {"harvest": 2, "analysis": 1})

    def test_predios_kpis(self):
        out = self.core.kpis(self.token, "predios")
        self.assertEqual(out["total"], 2)
        self.assertEqual(out["activos"], 2)

    def test_bodega_cannot_read_predios_or_eventos(self):
        token = login_token(self.core, "bodega")
        with self.assertRaises(BridgeRbacError):
            self.core.list(token, "predios")
        with self.assertRaises(BridgeRbacError):
            self.core.list(token, "eventos")

    def test_operario_cannot_read_new_entities(self):
        token = login_token(self.core, "operario")
        with self.assertRaises(BridgeRbacError):
            self.core.list(token, "predios")
        with self.assertRaises(BridgeRbacError):
            self.core.list(token, "eventos")


class TestTrace(unittest.TestCase):
    """P3: trazabilidad genealogía up/down + recall (FR-AG-06/07)."""

    def setUp(self):
        self.core, self.fake = make_core()
        self.token = login_token(self.core)

    def test_trace_lot_2_up_down_recall(self):
        out = self.core.trace(self.token, 2)
        self.assertEqual(out["entity"], "lote_trace")
        self.assertEqual(out["lot"]["name"], "LOTE-2")
        # up: cycle → plot
        self.assertEqual(out["up"]["cycle"]["id"], 1)
        self.assertEqual(out["up"]["plot"]["name"], "Norte")
        # down: analisis + eventos + movimientos
        self.assertEqual(len(out["down"]["analisis"]), 1)
        self.assertEqual(out["down"]["analisis"][0]["analyte"], "Humedad")
        self.assertEqual(len(out["down"]["eventos"]), 2)
        self.assertEqual(len(out["down"]["movimientos"]), 1)
        # recall: facturas del producto (Cafe) desde cosecha (2026-09-02)
        self.assertEqual(out["recall"]["harvest_date"], "2026-09-02")
        self.assertEqual(len(out["recall"]["invoices"]), 1)
        self.assertEqual(out["recall"]["invoices"][0]["name"], "INV/2026/0001")

    def test_trace_missing_lot_404(self):
        with self.assertRaises(BridgeNotFound):
            self.core.trace(self.token, 999)

    def test_trace_bodega_allowed(self):
        token = login_token(self.core, "bodega")
        out = self.core.trace(token, 1)
        self.assertEqual(out["lot"]["name"], "LOTE-1")
        # LOTE-1 tiene cycle_id=1 ⇒ cycle + plot deben venir
        self.assertEqual(out["up"]["cycle"]["id"], 1)
        self.assertEqual(out["up"]["plot"]["name"], "Norte")
        self.assertEqual(len(out["down"]["movimientos"]), 1)  # move id=1 (lot_ids=[1])

    def test_trace_operario_denied(self):
        token = login_token(self.core, "operario")
        with self.assertRaises(BridgeRbacError):
            self.core.trace(token, 1)


class TestWizard(unittest.TestCase):
    """P3: wizard vía bridge; apply=admin-only (AGT-01)."""

    def setUp(self):
        self.core, self.fake = make_core()
        self.token = login_token(self.core)

    def test_templates_admin_ok(self):
        out = self.core.wizard_templates(self.token)
        self.assertEqual(len(out["templates"]), 1)
        self.assertEqual(out["templates"][0]["code"], "agro/medium")

    def test_templates_gerente_ok(self):
        token = login_token(self.core, "gerente")
        out = self.core.wizard_templates(token)
        self.assertEqual(len(out["templates"]), 1)

    def test_templates_produccion_denied(self):
        token = login_token(self.core, "produccion")
        with self.assertRaises(BridgeRbacError):
            self.core.wizard_templates(token)

    def test_params_admin_ok(self):
        out = self.core.wizard_params(self.token)
        self.assertIn("params", out)

    def test_preview_admin_ok(self):
        out = self.core.wizard_preview(self.token, "agro", "medium")
        self.assertEqual(out["vertical"], "agro")
        self.assertIn("plan", out)

    def test_preview_gerente_ok(self):
        token = login_token(self.core, "gerente")
        out = self.core.wizard_preview(token, "agro", "medium")
        self.assertIn("plan", out)

    def test_apply_admin_ok(self):
        out = self.core.wizard_apply(self.token, "agro", "medium")
        self.assertTrue(out["applied"]["applied"])

    def test_apply_gerente_denied(self):
        # AGT-01: apply muta el tenant ⇒ sólo admin, gerente NO
        token = login_token(self.core, "gerente")
        with self.assertRaises(BridgeRbacError):
            self.core.wizard_apply(token, "agro", "medium")


class TestChatTools(unittest.TestCase):
    """P3 (escenario 3): chat con tools reales; RBAC del agente."""

    def setUp(self):
        self.core, self.fake = make_core()
        self.token = login_token(self.core)

    def test_stock_lot_tool_returns_real_qty(self):
        out = self.core.chat(self.token, "stock lote LOTE-2")
        self.assertEqual(out["engine"], "tools")
        self.assertIn("LOTE-2", out["reply"])
        self.assertIn("50.00", out["reply"])
        self.assertIn("stock.lot.search_read", out["tools"][0])

    def test_stock_lot_tool_context_echo(self):
        ctx = {"view": "lotes", "entity": "lotes"}
        out = self.core.chat(self.token, "stock lote LOTE-2", context=ctx)
        self.assertEqual(out["context"], ctx)

    def test_stock_lot_tool_no_match(self):
        out = self.core.chat(self.token, "stock lote NOEXISTE")
        self.assertEqual(out["engine"], "tools")
        self.assertIn("No encontré", out["reply"])

    def test_operario_stock_tool_rbac_denied(self):
        token = login_token(self.core, "operario")
        out = self.core.chat(token, "stock lote LOTE-2")
        self.assertEqual(out["engine"], "tools")
        self.assertIn("no tiene acceso", out["reply"])

    def test_bodega_stock_tool_allowed(self):
        token = login_token(self.core, "bodega")
        out = self.core.chat(token, "stock lote LOTE-1")
        self.assertIn("LOTE-1", out["reply"])

    def test_id_validation_still_works(self):
        out = self.core.chat(self.token, "validar RUC 1793125212001")
        self.assertEqual(out["engine"], "rules")
        self.assertIn("VÁLIDO", out["reply"])

    def test_help_when_no_tool(self):
        out = self.core.chat(self.token, "hola")
        self.assertEqual(out["engine"], "rules")
        self.assertIn("Puedo", out["reply"])

    def test_chat_context_over_http_with_tool(self):
        # smoke: chat con contexto vía HTTP respeta tools + contexto
        pass  # cubierto por TestHttpLayer.test_chat_stock_tool_over_http


class TestScenario7Independence(unittest.TestCase):
    """Escenario 7: chat caído ⇒ dashboards siguen leyendo (FR-BR-08)."""

    def test_kpis_work_regardless_of_chat_state(self):
        core, fake = make_core()
        token = login_token(core)
        # chat con mensaje sin tool (no toca Odoo) — el core no lanza
        core.chat(token, "hola, ¿qué puedes hacer?")
        # dashboards siguen leyendo normal
        out = core.kpis(token, "lotes")
        self.assertEqual(out["total"], 3)
        out = core.list(token, "predios", limit=5)
        self.assertEqual(out["total"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
