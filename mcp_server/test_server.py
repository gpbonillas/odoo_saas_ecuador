#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests del gateway MCP (stdlib unittest, sin Odoo ni pytest).

  python3 mcp_server/test_server.py

Cubre:
  1. Handshake MCP real por stdio (subprocess): initialize, initialized,
     tools/list, ping, resources/*, tools/call con Odoo caído -> error
     estructurado, y la ausencia de ruido no-JSON en stdout.
  2. Dispatch JSON-RPC directo (parse error, método inexistente).
  3. Motor de reglas ecuatoriano: mod-10/mod-11, tipo de persona, clave de
     49 dígitos, límite CF $50, anulación día 7, feriados + 5 días hábiles,
     tablas de retención, liquidación y campos faltantes.
  4. Normalización de errores de tools sin Odoo.
"""
import datetime
import json
import os
import random
import subprocess
import sys
import unittest

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import rules            # noqa: E402
import tools            # noqa: E402
import server           # noqa: E402


# Identificadores REALES — únicos aceptados (nada inventado):
#   cédula 1713488185      -> persona natural (stdnum.ec.ci OK)
#   RUC    1793125212001   -> persona jurídica (SRI: CANNACHAIN S.A.S.)
# RUC natural derivado de la cédula real (cédula + "001"); el SRI lo confirma
# como 1713488185001 (CADENA PEÑA ADRIAN RAFAEL). RUC_BAD muta el dígito
# verificador jurídico (índice 9) del RUC real para casos negativos.
CEDULA_OK = "1713488185"
RUC_OK = "1793125212001"
RUC_JURIDICA = RUC_OK                 # alias: persona jurídica real
RUC_NATURAL = CEDULA_OK + "001"       # 1713488185001 (natural)
RUC_BAD = RUC_OK[:9] + "9" + RUC_OK[10:]   # check digit jurídico inválido


class TestVatRules(unittest.TestCase):
    def test_cedula_mod10_ok(self):
        v = rules.validate_vat(CEDULA_OK)
        self.assertEqual(v["id_type"], "cedula")
        self.assertTrue(v["valid"])

    def test_cedula_mod10_bad(self):
        # cédula real con el dígito verificador corrompido
        v = rules.validate_vat(CEDULA_OK[:-1] + "4")
        self.assertFalse(v["valid"])

    def test_ruc_mod11_natural(self):
        v = rules.validate_vat(RUC_NATURAL)
        self.assertEqual(v["id_type"], "ruc")
        self.assertTrue(v["valid"])
        self.assertEqual(rules.classify_ruc(RUC_NATURAL)["person_type"],
                         "natural")

    def test_ruc_mod11_juridica(self):
        v = rules.validate_vat(RUC_JURIDICA)
        self.assertTrue(v["valid"])
        self.assertEqual(rules.classify_ruc(RUC_JURIDICA)["person_type"],
                         "juridica")

    def test_ruc_bad_province(self):
        # RUC real con provincia inválida (99)
        v = rules.validate_vat("99" + RUC_OK[2:])
        self.assertFalse(v["valid"])

    def test_ruc_bad_checksum(self):
        # dígito verificador jurídico (índice 9) corrompido
        v = rules.validate_vat(RUC_BAD)
        self.assertFalse(v["valid"])

    def test_ruc_bad_establishment_zero(self):
        # establecimiento 000 nunca es válido (stdnum lo rechaza)
        v = rules.validate_vat(RUC_OK[:-3] + "000")
        self.assertFalse(v["valid"])

    def test_ruc_third_digit_78_invalid(self):
        # 3er dígito 7/8 no existe en la fórmula SRI
        self.assertFalse(rules.ruc_check_digit_ok("177" + RUC_OK[3:]))
        self.assertFalse(rules.ruc_check_digit_ok("178" + RUC_OK[3:]))

    def test_short_vat_rejected(self):
        self.assertFalse(rules.validate_vat("12345")["valid"])

    def test_pasaporte_accepted(self):
        v = rules.validate_vat("AB123456")
        self.assertEqual(v["id_type"], "pasaporte")
        self.assertTrue(v["valid"])


class TestAccessKey(unittest.TestCase):
    def _key(self):
        return rules.generate_access_key(
            datetime.date(2026, 10, 15), "01", RUC_JURIDICA, "test",
            "001", "001", "1", numeric_code="12345678")

    def test_generate_and_validate(self):
        key = self._key()
        self.assertEqual(len(key), 49)
        res = rules.validate_access_key(key)
        self.assertTrue(res["valid"], res["errors"])
        self.assertEqual(res["doc_type"], "01")
        self.assertEqual(res["ruc_emisor"], RUC_JURIDICA)

    def test_tampered_key_fails(self):
        key = self._key()
        bad = key[:48] + ("0" if key[48] != "0" else "1")
        self.assertFalse(rules.validate_access_key(bad)["valid"])

    def test_wrong_length_fails(self):
        self.assertFalse(rules.validate_access_key("123")["valid"])


class TestCfAndAnnulment(unittest.TestCase):
    def test_consumidor_final_detection(self):
        self.assertTrue(rules.is_consumidor_final("9999999999999"))
        self.assertFalse(rules.is_consumidor_final(RUC_JURIDICA))

    def test_cf_limit(self):
        self.assertTrue(rules.cf_limit_check(50.0)["ok"])
        self.assertFalse(rules.cf_limit_check(50.01)["ok"])

    def test_annulment_deadline_day7(self):
        d = rules.annulment_deadline(datetime.date(2026, 1, 31))
        self.assertEqual(d, datetime.date(2026, 2, 7))

    def test_annulment_december_rolls_to_january(self):
        d = rules.annulment_deadline(datetime.date(2026, 12, 31))
        self.assertEqual(d, datetime.date(2027, 1, 7))

    def test_annulment_allowed_within_window(self):
        res = rules.check_annul_allowed(datetime.date(2026, 10, 1),
                                        today=datetime.date(2026, 10, 5))
        self.assertTrue(res["allowed"])

    def test_annulment_expired(self):
        res = rules.check_annul_allowed(datetime.date(2026, 8, 1),
                                        today=datetime.date(2026, 10, 5))
        self.assertFalse(res["allowed"])

    def test_cf_never_annulable(self):
        res = rules.check_annul_allowed(datetime.date(2026, 10, 1),
                                        today=datetime.date(2026, 10, 2),
                                        is_cf=True)
        self.assertFalse(res["allowed"])


class TestBusinessDays(unittest.TestCase):
    def test_easter_2026(self):
        self.assertEqual(rules.easter_sunday(2026), datetime.date(2026, 4, 5))

    def test_holidays_2026(self):
        hol = rules.ec_holidays(2026)
        self.assertIn(datetime.date(2026, 1, 1), hol)     # Año Nuevo
        self.assertIn(datetime.date(2026, 2, 16), hol)    # Carnaval lunes
        self.assertIn(datetime.date(2026, 2, 17), hol)    # Carnaval martes
        self.assertIn(datetime.date(2026, 4, 3), hol)     # Viernes Santo
        self.assertIn(datetime.date(2026, 5, 1), hol)     # Trabajo
        self.assertIn(datetime.date(2026, 12, 25), hol)   # Navidad

    def test_five_business_days_skips_weekend_and_holiday(self):
        # lunes 2026-10-05 + 5 días hábiles: mar 6, mié 7, jue 8,
        # vie 9 = Independencia de Guayaquil (feriado), lun 12, mar 13
        res = rules.add_business_days(datetime.date(2026, 10, 5), 5)
        self.assertEqual(res, datetime.date(2026, 10, 13))

    def test_retention_deadline_not_overdue(self):
        res = rules.retention_deadline(datetime.date(2026, 10, 5),
                                       today=datetime.date(2026, 10, 13))
        self.assertFalse(res["overdue"])
        self.assertEqual(res["due_date"], "2026-10-13")

    def test_retention_deadline_overdue_warns(self):
        res = rules.retention_deadline(datetime.date(2026, 10, 5),
                                       today=datetime.date(2026, 10, 14))
        self.assertTrue(res["overdue"])
        self.assertIn("fuera de plazo", res["warning"])


class TestWithholdingMath(unittest.TestCase):
    def test_ir_default_servicios(self):
        # Res. NAC-DGERCGC26-00000009: honorarios (cod. 303) = 10%.
        self.assertEqual(
            rules.ir_retention_pct(1000, "servicios")["percentage"], 10.0)

    def test_ir_override_valid(self):
        # 2.75% fue ELIMINADO por Res. NAC-DGERCGC26-00000009; usamos un
        # porcentaje vigente (2.0%) que sí está en la Tabla 19.
        res = rules.ir_retention_pct(1000, "servicios", override=2.0)
        self.assertTrue(res["valid"])

    def test_ir_override_eliminated_rate(self):
        # La tarifa 2.75% ya no es válida (eliminada en 2026).
        res = rules.ir_retention_pct(1000, "servicios", override=2.75)
        self.assertFalse(res["valid"])

    def test_ir_override_invalid(self):
        res = rules.ir_retention_pct(1000, "servicios", override=3.3)
        self.assertFalse(res["valid"])

    def test_iva_full_to_sri_no_iess_split(self):
        # Res. NAC-DGERCGC20-00000061: la retención de IVA se entrega
        # ÍNTEGRAMENTE al SRI (casillero 104). NO existe split IESS/SECE.
        res = rules.iva_retention_amount(100.0)
        self.assertEqual(res["retained"], 30.0)
        self.assertEqual(res["sri_share"], 30.0)
        self.assertEqual(res["iess_share"], 0.0)

    def test_iva_bucket_dual_scale(self):
        # Escala doble Res. 61: especial->especial bienes = 10% (721);
        # general bienes = 30% (725); servicios general = 70% (729).
        self.assertEqual(
            rules.iva_retention_bucket(
                "bienes", agent_especial=True,
                counterparty_especial=True)["casillero"], "721")
        self.assertEqual(
            rules.iva_retention_bucket("bienes")["casillero"], "725")
        self.assertEqual(
            rules.iva_retention_bucket("servicios")["casillero"], "729")
        self.assertEqual(
            rules.iva_retention_bucket("honorarios")["casillero"], "731")


class TestPayrollMath(unittest.TestCase):
    def test_progressive_tax(self):
        rows = [{"basic_fraction": 0, "excess_until": 11310,
                 "basic_tax": 0, "marginal_rate": 0},
                {"basic_fraction": 11310, "excess_until": 14410,
                 "basic_tax": 200, "marginal_rate": 5}]
        self.assertEqual(rules.progressive_tax(12000, rows), 234.5)
        self.assertEqual(rules.progressive_tax(5000, rows), 0.0)

    def test_liquidation_core(self):
        liq = rules.calculate_liquidation(482.0, days_worked=30, sbu=482.0)
        self.assertEqual(liq["decimo_tercero"], 40.17)
        self.assertEqual(liq["decimo_cuarto"], 40.17)
        self.assertEqual(liq["fondos_reserva"], 40.17)
        self.assertEqual(liq["iess_personal"], 45.55)

    def test_iess_ceiling_25_sbu(self):
        res = rules.iess_amounts(20000.0, sbu=482.0)
        self.assertEqual(res["base"], 482.0 * 25)
        self.assertTrue(res["warnings"])


class TestMissingData(unittest.TestCase):
    COMPANY = {"vat": RUC_OK, "ambiente": "test",
               "establishment": "001", "emission_point": "001",
               "certificate_active": True}

    def test_complete_partner_no_blockers(self):
        partner = {"vat": RUC_JURIDICA, "id_type": "ruc",
                   "valid_checksum": True, "name": "ACME SA",
                   "street": "Av. Amazonas 100"}
        missing = rules.missing_invoice_data(partner, self.COMPANY)
        self.assertFalse([m for m in missing if m["severity"] == "blocker"])

    def test_ruc_without_street_is_blocker(self):
        partner = {"vat": RUC_JURIDICA, "id_type": "ruc",
                   "valid_checksum": True, "name": "ACME SA"}
        missing = rules.missing_invoice_data(partner, self.COMPANY)
        fields = [m["field"] for m in missing if m["severity"] == "blocker"]
        self.assertIn("street", fields)

    def test_bad_ruc_is_blocker(self):
        partner = {"vat": RUC_BAD, "id_type": "ruc",
                   "valid_checksum": False, "name": "X", "street": "Y"}
        missing = rules.missing_invoice_data(partner, self.COMPANY)
        self.assertTrue(any(m["field"] == "vat" for m in missing))

    def test_no_partner_short_circuits(self):
        missing = rules.missing_invoice_data(None, self.COMPANY)
        self.assertEqual(missing[0]["field"], "partner")

    def test_question_is_built(self):
        q = rules.build_question([{"severity": "blocker", "question": "¿RUC?"}])
        self.assertEqual(q, "¿RUC?")


class TestToolNormalizationNoOdoo(unittest.TestCase):
    def test_unknown_tool(self):
        res = tools.call_tool(None, "no_existe", {})
        self.assertEqual(res["status"], "error")

    def test_create_invoice_without_partner_asks(self):
        res = tools.call_tool(None, "create_invoice", {})
        self.assertEqual(res["status"], "needs_data")
        self.assertTrue(res["question"])

    def test_create_invoice_cf_over_limit(self):
        res = tools.call_tool(None, "create_invoice",
                              {"vat": "9999999999999",
                               "lines": [{"description": "x", "unit_price": 60}]})
        # La regla CF ≤ $50 se aplica incluso sin Odoo y sin traceback.
        self.assertEqual(res["status"], "error")
        self.assertEqual(res.get("rule"), "cf_limit_50")

    def test_create_invoice_cf_under_limit_passes_cf_gate(self):
        res = tools.call_tool(None, "create_invoice",
                              {"vat": "9999999999999",
                               "lines": [{"description": "x", "unit_price": 10}]})
        # La regla CF NO bloquea; sin Odoo se devuelve error estructurado
        # (no traceback) al intentar resolver el partner.
        self.assertEqual(res["status"], "error")
        self.assertNotIn("rule", res)

    def test_detect_taxpayer_offline_degrades(self):
        # client=None -> la consulta SRI degrada y la detección local sigue
        # funcionando (reglas puras), jamás un traceback.
        res = tools.call_tool(None, "detect_taxpayer", {"vat": RUC_JURIDICA})
        self.assertEqual(res["status"], "ok")
        self.assertFalse(res["sri"]["available"])
        self.assertEqual(res["profile"]["person_type"], "juridica")
        self.assertNotIn("Traceback", json.dumps(res))

    def test_all_handlers_return_dicts(self):
        for tool in tools.TOOLS:
            self.assertIn("name", tool)
            self.assertIn("inputSchema", tool)
            self.assertIn("handler", tool)


class TestJsonRpcDispatch(unittest.TestCase):
    def test_initialize_shape(self):
        resp = server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "odoo-ecuador-mcp")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_notification_returns_none(self):
        self.assertIsNone(server.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_tools_list_shape(self):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 2,
                                      "method": "tools/list"})
        names = [t["name"] for t in resp["result"]["tools"]]
        for expected in ("detect_taxpayer", "create_invoice", "post_invoice",
                         "create_credit_note", "create_withholding",
                         "calculate_withholding", "validate_ruc",
                         "generate_payslips", "generate_iess_planilla",
                         "calculate_liquidation", "generate_ats",
                         "get_sales_summary", "get_ar_aging", "record_payment",
                         "send_ride", "get_stock_level", "get_client_data",
                         "create_partner"):
            self.assertIn(expected, names)

    def test_unknown_method(self):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 3,
                                      "method": "bogus/method"})
        self.assertEqual(resp["error"]["code"], -32601)

    def test_ping(self):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 4, "method": "ping"})
        self.assertEqual(resp["result"], {})


class TestStdioHandshake(unittest.TestCase):
    """End-to-end: spawn server.py and speak real MCP over stdio."""

    def test_full_handshake_with_odoo_down(self):
        env = dict(os.environ)
        env.update({
            "ODOO_URL": "http://127.0.0.1:9",   # puerto cerrado a propósito
            "ODOO_DB": "odooec",
            "ODOO_USER": "admin",
            "ODOO_PASSWORD": "admin",
            "ODOO_TIMEOUT": "2",
        })
        lines = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05",
                                   "capabilities": {}}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}),
            json.dumps({"jsonrpc": "2.0", "id": 4, "method": "resources/list"}),
            json.dumps({"jsonrpc": "2.0", "id": 5, "method": "resources/read",
                        "params": {"uri": "ec://holidays"}}),
            json.dumps({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                        "params": {"name": "detect_taxpayer",
                                   "arguments": {"vat": RUC_JURIDICA}}}),
            "{corrupt json",
        ]
        proc = subprocess.run(
            [sys.executable, os.path.join(BASE, "server.py")],
            input="\n".join(lines) + "\n",
            capture_output=True, text=True, timeout=60, env=env,
            cwd=os.path.dirname(BASE))
        out_lines = [l for l in proc.stdout.splitlines() if l.strip()]
        # stdout puro: cada línea debe ser JSON válido (el log va a stderr)
        responses = [json.loads(l) for l in out_lines]
        by_id = {r.get("id"): r for r in responses}

        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"],
                         "odoo-ecuador-mcp")
        self.assertEqual(len(by_id[2]["result"]["tools"]), len(tools.TOOLS))
        self.assertEqual(by_id[3]["result"], {})
        self.assertGreaterEqual(len(by_id[4]["result"]["resources"]), 3)
        holidays = json.loads(by_id[5]["result"]["contents"][0]["text"])
        self.assertIn("2026-01-01", holidays["holidays"])
        # tools/call con Odoo caído -> degradación controlada (detección local
        # por reglas + meta SRI no disponible), nunca un traceback.
        call = by_id[6]["result"]
        payload = json.loads(call["content"][0]["text"])
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["sri"]["available"])
        self.assertIn("error", payload["sri"])
        # el parse error genera respuesta -32700 con id null
        self.assertTrue(any(r.get("error", {}).get("code") == -32700
                            for r in responses))
        self.assertNotIn("Traceback (most recent call last)", proc.stderr)


try:  # stdnum solo existe dentro del contenedor Odoo (dependencia oficial)
    from stdnum.ec import ci as _std_ci
    from stdnum.ec import ruc as _std_ruc
    HAVE_STDNUM = True
except ImportError:  # pragma: no cover
    _std_ci = _std_ruc = None
    HAVE_STDNUM = False


@unittest.skipUnless(HAVE_STDNUM,
                     "stdnum no instalado en este host "
                     "(ejecutar dentro del contenedor Odoo)")
class TestStdnumEquivalence(unittest.TestCase):
    """CHG-2026-005: rules.py == stdnum.ec.ci / stdnum.ec.ruc.

    stdnum es la fuente oficial (regla de oro ISO-04). Esta suite reproduce
    de forma permanente el cross-check que dio 20.195 casos / 0 diferencias
    (evidencia ISO-EC-11 §3.1): IDs aprobados + todas sus mutaciones de un
    dígito + barrido sistemático determinista (seed fija) de provincias
    (01-24, 30, 50, 00, 99) × 3er dígito 0-9 × cuerpos aleatorios, en
    longitudes 10 y 13.

    Nota: los números sintéticos del barrido son SOLO material de prueba del
    dígito verificador; nunca se usan como datos de contribuyentes (D-04).
    """

    PROVINCIAS = ["%02d" % p for p in range(1, 25)] + ["30", "50", "00", "99"]

    @classmethod
    def _corpus(cls):
        # 1) IDs aprobados + todas sus mutaciones de UN dígito
        for base in (CEDULA_OK, RUC_NATURAL, RUC_OK):
            yield base
            for pos in range(len(base)):
                for digit in "0123456789":
                    if digit != base[pos]:
                        yield base[:pos] + digit + base[pos + 1:]
        # 2) Barrido sistemático determinista
        rnd = random.Random(20261016)
        for length in (10, 13):
            for prov in cls.PROVINCIAS:
                for third in "0123456789":
                    for _ in range(40):
                        body = "".join(
                            rnd.choice("0123456789")
                            for _ in range(length - 3))
                        yield prov + third + body

    @staticmethod
    def _ours(number):
        if len(number) == 10:
            return rules.cedula_check_digit_ok(number)
        if len(number) == 13:
            return rules.ruc_check_digit_ok(number)
        return False

    @staticmethod
    def _stdnum(number):
        if len(number) == 10:
            return _std_ci.is_valid(number)
        if len(number) == 13:
            return _std_ruc.is_valid(number)
        return False

    def test_approved_ids_valid_in_both(self):
        for number in (CEDULA_OK, RUC_NATURAL, RUC_OK):
            self.assertTrue(self._ours(number), number)
            self.assertTrue(self._stdnum(number), number)

    def test_corpus_matches_stdnum(self):
        checked = 0
        diffs = []
        for number in self._corpus():
            ours, theirs = self._ours(number), self._stdnum(number)
            if ours != theirs:
                diffs.append("%s rules=%s stdnum=%s" % (number, ours, theirs))
            checked += 1
        self.assertGreaterEqual(checked, 20000,
                                "corpus demasiado pequeño")
        self.assertEqual(diffs, [], "diferencias vs stdnum: %s"
                         % diffs[:10])

    def test_validate_vat_agrees_on_corpus_sample(self):
        # validate_vat es la fachada usada por las tools: misma respuesta.
        for i, number in enumerate(self._corpus()):
            if i % 97:            # muestra determinista (~1%)
                continue
            result = rules.validate_vat(number)
            self.assertEqual(bool(result["checksum_ok"]),
                             self._stdnum(number), number)


if __name__ == "__main__":
    unittest.main(verbosity=2)
