# -*- coding: utf-8 -*-
"""
Unit Tests: Ecuador statutory reports + ATS (l10n_ec_reports)
=============================================================

PURE PYTHON (stdlib `unittest` only) - no Odoo runtime required, because
``l10n_ec_reports/report_lib.py`` is deliberately importable standalone:
it is the single source of truth for every number in the books, the SRI
forms and the ATS.

Run directly:
    python3 tests/unit/test_reports_ats.py
or via unittest/pytest from the repo root.

Covers (Sprint 3 - Definition of Done #5 "Books + Form 104 + ATS produce
real numbers"):
* Form 104 on a synthetic invoice set (IVA + ICE + retenciones, casilleros)
* Form 103 / 101 / 102 / 107 / 108 math
* Gastos personales caps + rebaja tributaria (configurable, no invented caps)
* Books (ventas / compras / retenciones / diario / mayor / bancos)
* Trial balance + estados financieros (cuadre contable)
* ATS structure + REQ-ATS-001 validation
"""
import os
import sys
import unittest
from datetime import date

# Make l10n_ec_reports/report_lib.py importable without Odoo.
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_MODULE_DIR = os.path.join(_REPO_ROOT, "l10n_ec_reports")
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

import report_lib as lib  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic invoice set (raw dicts as produced by
# l10n.ec.report.common._extract_invoice_row, consumed by invoice_report_row)
# ---------------------------------------------------------------------------
def raw_invoice(**overrides):
    """Minimal raw invoice dict; override per test."""
    row = {
        "id": 1,
        "fecha": "2026-01-15",
        "fecha_registro": "2026-01-15",
        "doc_code": "01",
        "doc_name": "FACTURA",
        "move_type": "out_invoice",
        "tp_id": "04",
        "identificacion": "1793125212001",
        "razon_social": "CLIENTE EJEMPLO S.A.",
        "clave_acceso": "1793125212001011010000000000000000000001234567891",
        "estab": "001",
        "pto": "001",
        "secuencial": "000000001",
        "autorizacion": "",
        "sustento": "01",
        "lines": [],
        "tax_lines": [],
        "total": 0.0,
        "state": "posted",
        "is_export": False,
        "is_import": False,
        "emision_linea": True,
        "forma_pago": "20",
        "retentions": [],
    }
    row.update(overrides)
    return row


def line(base, rates, no_objeto=False):
    return {"base": base, "rates": rates, "no_objeto": no_objeto}


# ---------------------------------------------------------------------------
# The synthetic set used by the Form 104 / ATS / books tests
# ---------------------------------------------------------------------------
def sales_set():
    """3 sales invoices + 1 credit note.

    * INV-1: 1000 @15% -> IVA 150, customer withholds 70% IVA (ret 105?) ->
      here ret_iva 105.00 is extracted from tax lines/retentions by the ORM
      layer; the test injects it directly (report_lib is ORM agnostic).
    * INV-2: 500 @5% (tarifa reducida) + 100 tarifa 0%
    * INV-3: export 2000 (excluded from domestic bases, Form 104 cas. 415)
    * NC-1: credit note - raw amounts are POSITIVE (that is how
      ``account.move`` stores them, see the report_lib raw invoice contract)
      and ``invoice_report_row`` makes the row negative (sign -1).
    """
    inv1 = raw_invoice(
        id=1,
        secuencial="000000001",
        lines=[line(1000.0, [15.0])],
        tax_lines=[
            {"group": "IVA 15%", "balance": 150.0, "ice": False, "ret_kind": None},
            {"group": "RET IVA 70%", "balance": 105.0, "ice": False,
             "ret_kind": "iva"},
            {"group": "RET RENTA 2%", "balance": 20.0, "ice": False,
             "ret_kind": "ir"},
        ],
        total=1150.0,
    )
    inv2 = raw_invoice(
        id=2,
        secuencial="000000002",
        lines=[line(500.0, [5.0]), line(100.0, [0.0])],
        tax_lines=[
            {"group": "IVA 5%", "balance": 25.0, "ice": False, "ret_kind": None},
        ],
        total=625.0,
    )
    inv3 = raw_invoice(
        id=3,
        secuencial="000000003",
        tp_id="07",
        identificacion="9999999999999",
        razon_social="EXPORTADORA LLC",
        lines=[line(2000.0, [0.0])],
        tax_lines=[],
        total=2000.0,
        is_export=True,
    )
    nc1 = raw_invoice(
        id=4,
        doc_code="04",
        doc_name="NOTA DE CREDITO",
        move_type="out_refund",
        secuencial="000000004",
        lines=[line(300.0, [15.0])],
        tax_lines=[
            {"group": "IVA 15%", "balance": 45.0, "ice": False, "ret_kind": None},
        ],
        total=345.0,
    )
    return [inv1, inv2, inv3, nc1]


def purchases_set():
    """2 purchase invoices, one of them with AIR + IVA withholdings."""
    pur1 = raw_invoice(
        id=10,
        move_type="in_invoice",
        tp_id="02",
        identificacion="1793125212001",
        razon_social="PROVEEDOR S.A.",
        doc_code="01",
        secuencial="000000101",
        lines=[line(1000.0, [15.0])],
        tax_lines=[
            {"group": "IVA 15%", "balance": 150.0, "ice": False, "ret_kind": None},
            {"group": "RET IVA 30%", "balance": 300.0, "ice": False,
             "ret_kind": "iva"},
        ],
        total=1150.0,
        retentions=[
            {"kind": "iva", "code": "721", "name": "Retencion IVA 30%",
             "base": 1000.0, "percent": 30.0, "amount": 300.0,
             "numero": "001-001-000000123", "fecha": "2026-01-20",
             "autorizacion": "1234567890", "partner": "PROVEEDOR S.A.",
             "identificacion": "1793125212001",
             "comprobante": "001-001-000000101",
             "fecha_factura": "2026-01-15"},
            {"kind": "ir", "code": "312", "name": "Transferencia de bienes",
             "base": 1000.0, "percent": 1.75, "amount": 17.5,
             "numero": "001-001-000000123", "fecha": "2026-01-20",
             "autorizacion": "1234567890", "partner": "PROVEEDOR S.A.",
             "identificacion": "1793125212001",
             "comprobante": "001-001-000000101",
             "fecha_factura": "2026-01-15"},
        ],
    )
    pur2 = raw_invoice(
        id=11,
        move_type="in_invoice",
        tp_id="02",
        identificacion="1713488185001",
        razon_social="SERVICIOS ECUA S.A.",
        doc_code="01",
        secuencial="000000102",
        lines=[line(400.0, [15.0]), line(200.0, [0.0])],
        tax_lines=[
            {"group": "IVA 15%", "balance": 60.0, "ice": False, "ret_kind": None},
        ],
        total=460.0,
    )
    return [pur1, pur2]


def retention_rows():
    """account.retention flattening (what _retention_flat_rows returns)."""
    return [
        {"kind": "ir", "code": "312", "name": "Transferencia de bienes",
         "base": 1000.0, "percent": 1.75, "amount": 17.5,
         "numero": "001-001-000000123", "fecha": "2026-01-20",
         "autorizacion": "1234567890", "partner": "PROVEEDOR S.A.",
         "identificacion": "1793125212001", "comprobante": "001-001-000000101",
         "fecha_factura": "2026-01-15"},
        {"kind": "ir", "code": "304", "name": "Servicios predomina el intelecto",
         "base": 2000.0, "percent": 11.5, "amount": 230.0,
         "numero": "001-001-000000124", "fecha": "2026-01-25",
         "autorizacion": "1234567890", "partner": "CONSULTORES CIA. LTDA.",
         "identificacion": "1713488185001", "comprobante": "001-001-000000102",
         "fecha_factura": "2026-01-22"},
        {"kind": "iva", "code": "723", "name": "Retencion IVA 70%",
         "base": 2000.0, "percent": 70.0, "amount": 1400.0,
         "numero": "001-001-000000124", "fecha": "2026-01-25",
         "autorizacion": "1234567890", "partner": "CONSULTORES CIA. LTDA.",
         "identificacion": "1713488185001", "comprobante": "001-001-000000102",
         "fecha_factura": "2026-01-22"},
    ]


# ===========================================================================
# Form 104 - IVA + ICE (the headline Sprint 3 requirement)
# ===========================================================================
class TestForm104(unittest.TestCase):
    """Casilleros per SRS_MODULE_09 section 3.2."""

    def setUp(self):
        self.result = lib.form104_calculate(sales_set(), purchases_set(),
                                             iva_rate=0.15)

    def _line(self, code):
        for section in self.result["sections"]:
            for line_ in section["lines"]:
                if line_["code"] == code:
                    return line_
        self.fail("casillero %s not found in Form 104" % code)

    def test_casillero_411_sales_15(self):
        # 1000 (inv1) - 300 (NC) = 700  -> 411
        self.assertAlmostEqual(self._line("411")["amount"], 700.0, places=2)

    def test_casillero_411b_sales_5(self):
        self.assertAlmostEqual(self._line("411b")["amount"], 500.0, places=2)

    def test_casillero_412_sales_0(self):
        self.assertAlmostEqual(self._line("412")["amount"], 100.0, places=2)

    def test_casillero_415_exports(self):
        self.assertAlmostEqual(self._line("415")["amount"], 2000.0, places=2)

    def test_casillero_480_iva_debito(self):
        # 150 (inv1) + 25 (inv2) - 45 (NC) = 130
        self.assertAlmostEqual(self._line("480")["amount"], 130.0, places=2)
        self.assertAlmostEqual(self.result["iva_ventas"], 130.0, places=2)

    def test_casillero_421_purchases_15(self):
        self.assertAlmostEqual(self._line("421")["amount"], 1400.0, places=2)

    def test_casillero_422_purchases_0(self):
        self.assertAlmostEqual(self._line("422")["amount"], 200.0, places=2)

    def test_casillero_520_iva_credito(self):
        # 150 + 60 = 210
        self.assertAlmostEqual(self._line("520")["amount"], 210.0, places=2)
        self.assertAlmostEqual(self.result["iva_compras"], 210.0, places=2)

    def test_casillero_601_retentions_received(self):
        # Retentions PRACTICADAS BY US on sales (customer withheld from us)
        # -> they reduce the 104 balance.  inv1 ret_iva = 105.
        self.assertAlmostEqual(self._line("601")["amount"], 105.0, places=2)
        self.assertAlmostEqual(self.result["ret_iva_recibidas"], 105.0,
                               places=2)

    def test_casillero_605_is_informativo_not_credit(self):
        # Retentions we withhold on purchases are informational only.
        line_ = self._line("605")
        self.assertAlmostEqual(line_["amount"], 300.0, places=2)
        credito_line_codes = [
            ln["code"]
            for sec in self.result["sections"]
            if sec["title"] == "CREDITO TRIBUTARIO"
            for ln in sec["lines"]
        ]
        self.assertNotIn("605", credito_line_codes)

    def test_debito_credito_saldo(self):
        debito = 130.0 + 0.0          # IVA ventas + ICE ventas
        credito = 210.0 + 0.0 + 105.0  # IVA compras + ICE compras + 601
        self.assertAlmostEqual(self.result["debito"], debito, places=2)
        self.assertAlmostEqual(self.result["credito"], credito, places=2)
        self.assertAlmostEqual(self.result["saldo"], debito - credito, places=2)
        # 130 - 315 < 0 -> the period is in credit (saldo a favor)
        self.assertEqual(self.result["saldo_tipo"], "A FAVOR")

    def test_casillero_699_is_the_saldo(self):
        self.assertAlmostEqual(
            self._line("699")["amount"],
            self.result["saldo"],
            places=2,
        )

    def test_credit_note_is_negative(self):
        # NC with -45 IVA must DEBIT (reduce) the sales side, never add.
        self.assertLess(self.result["iva_ventas"], 150.0 + 25.0)

    def test_saldo_a_favor_when_purchases_exceed(self):
        big_purchase = raw_invoice(
            id=99, move_type="in_invoice", tp_id="02",
            identificacion="1793125212001", razon_social="PROVEEDOR S.A.",
            secuencial="000000999", lines=[line(10000.0, [15.0])],
            tax_lines=[{"group": "IVA 15%", "balance": 1500.0,
                        "ice": False, "ret_kind": None}],
            total=11500.0,
        )
        result = lib.form104_calculate(sales_set(), purchases_set() + [big_purchase])
        self.assertEqual(result["saldo_tipo"], "A FAVOR")
        self.assertLess(result["saldo"], 0.0)

    def test_saldo_tipo_matches_the_sign_of_the_saldo(self):
        # debito 130 < credito 315 -> negative saldo -> A FAVOR
        self.assertLess(self.result["saldo"], 0.0)
        self.assertEqual(self.result["saldo_tipo"], "A FAVOR")


# ===========================================================================
# Form 103 / 101 / 102 / 107 / 108
# ===========================================================================
class TestForm103(unittest.TestCase):
    def test_groups_ir_by_code_and_totals(self):
        result = lib.form103_calculate(retention_rows())
        codes = [r["code"] for r in result["rows"]]
        self.assertIn("312", codes)
        self.assertIn("304", codes)
        # IVA retentions do not belong to Form 103 (they are Form 104/721-725)
        self.assertNotIn("723", codes)
        self.assertAlmostEqual(result["total_base"], 3000.0, places=2)
        self.assertAlmostEqual(result["total_amount"], 247.5, places=2)

    def test_percent_derived_when_missing(self):
        rows = [{"kind": "ir", "code": "303", "name": "Honorarios",
                 "base": 1000.0, "percent": 0.0, "amount": 10.0}]
        result = lib.form103_calculate(rows)
        self.assertAlmostEqual(result["rows"][0]["percent"], 1.0, places=4)

    def test_labels_from_spec(self):
        result = lib.form103_calculate(retention_rows())
        by_code = {r["code"]: r for r in result["rows"]}
        self.assertEqual(by_code["312"]["label"],
                         lib.FORM103_LABELS["312"])


class TestForm101(unittest.TestCase):
    def test_math_flat_25_percent(self):
        data = {
            "ingresos_gravados": 100000.0,
            "costos_ventas": 40000.0,
            "gastos_operacionales": 30000.0,
            "retenciones": 5000.0,
            "pagos_previos": 1000.0,
        }
        result = lib.form101_calculate(data, corporate_rate=0.25)
        self.assertAlmostEqual(result["base_imponible"], 30000.0, places=2)
        self.assertAlmostEqual(result["impuesto"], 7500.0, places=2)
        self.assertAlmostEqual(result["saldo"], 1500.0, places=2)
        self.assertEqual(result["saldo_tipo"], "A PAGAR")

    def test_negative_result_is_a_favor(self):
        data = {"ingresos_gravados": 10000.0, "costos_ventas": 9000.0,
                "gastos_operacionales": 2000.0, "retenciones": 100.0}
        result = lib.form101_calculate(data)
        self.assertEqual(result["saldo_tipo"], "A FAVOR")

    def test_no_tax_on_loss(self):
        data = {"ingresos_gravados": 10000.0, "costos_ventas": 9000.0,
                "gastos_operacionales": 5000.0}
        result = lib.form101_calculate(data)
        self.assertEqual(result["impuesto"], 0.0)


class TestForm102(unittest.TestCase):
    def test_uses_progressive_table(self):
        # base 15000 -> falls in the 12208.01-15549 bracket (5%)
        data = {"ingresos_gravados": 20000.0, "costos_ventas": 3000.0,
                "gastos_operacionales": 2000.0}
        result = lib.form102_calculate(data)
        expected = lib.progressive_tax(15000.0, lib.DEFAULT_TAX_BRACKETS_2026)
        self.assertAlmostEqual(result["base_imponible"], 15000.0, places=2)
        self.assertAlmostEqual(result["impuesto"], expected, places=2)

    def test_iess_reduces_base(self):
        data = {"ingresos_gravados": 20000.0, "costos_ventas": 0.0,
                "gastos_operacionales": 0.0, "aportes_iess": 2000.0}
        result = lib.form102_calculate(data)
        self.assertAlmostEqual(result["base_imponible"], 18000.0, places=2)


class TestForm107(unittest.TestCase):
    def test_math_with_rebaja(self):
        data = {
            "ingresos": {"trabajo": 0.0, "tercera": 30000.0, "cuarta": 0.0,
                         "capital": 0.0, "otros": 0.0},
            "aportes_iess": 3000.0,
            "gastos_personales": 5000.0,
            "retenciones": 0.0,
            "pagos_previos": 0.0,
            "rebaja": {"expenses": 5000.0, "n_baskets": 7.0,
                       "basket_cost": 808.95},
        }
        result = lib.form107_calculate(data)
        self.assertAlmostEqual(result["total_ingresos"], 30000.0, places=2)
        self.assertAlmostEqual(result["base_imponible"], 22000.0, places=2)
        expected_causado = lib.progressive_tax(
            22000.0, lib.DEFAULT_TAX_BRACKETS_2026)
        self.assertAlmostEqual(result["impuesto_causado"], expected_causado,
                               places=2)
        # rebaja = min(5000, 7 * 808.95) * 18%
        expected_rebaja = min(5000.0, 7 * 808.95) * 0.18
        self.assertAlmostEqual(result["rebaja"], expected_rebaja, places=2)
        self.assertAlmostEqual(result["impuesto"],
                               expected_causado - expected_rebaja, places=2)

    def test_no_rebaja_without_basket_cost(self):
        data = {"ingresos": {"tercera": 30000.0}, "rebaja": None}
        result = lib.form107_calculate(data)
        self.assertEqual(result["rebaja"], 0.0)


class TestForm108(unittest.TestCase):
    def test_credit_notes_totals(self):
        nc = [
            {"fecha": "2026-01-10", "identificacion": "1793125212001",
             "razon_social": "CLIENTE A", "doc_code": "04",
             "clave_acceso": "1" * 49, "total": -345.0},
            {"fecha": "2026-01-12", "identificacion": "1713488185001",
             "razon_social": "CLIENTE B", "doc_code": "04",
             "clave_acceso": "2" * 49, "total": -115.0},
        ]
        result = lib.form108_calculate(nc)
        self.assertEqual(result["count"], 2)
        # absolute values (the form reports the issued credit note value)
        self.assertAlmostEqual(result["total"], 460.0, places=2)
        self.assertAlmostEqual(result["rows"][0]["total"], 345.0, places=2)


# ===========================================================================
# Gastos personales + rebaja tributaria
# ===========================================================================
class TestGastosPersonales(unittest.TestCase):
    def test_caps_are_configurable_and_min_applied(self):
        gastos = {"vivienda": 6000.0, "salud": 1000.0, "educacion": 500.0,
                  "alimentacion": 800.0, "vestimenta": 300.0, "turismo": 0.0}
        # caps in SMMLV -> USD = cap * SBU.  NOT from docs: injected by test.
        caps = {"vivienda": 1.5, "salud": None, "educacion": None,
                "alimentacion": None, "vestimenta": None, "turismo": None}
        sbu = 482.0
        result = lib.gastos_personales_calculate(gastos, caps, sbu)
        by_code = {r["code"]: r for r in result["rows"]}
        # vivienda capped: 1.5 * 482 = 723 < 6000
        self.assertAlmostEqual(by_code["vivienda"]["deducible"], 723.0,
                               places=2)
        self.assertAlmostEqual(by_code["vivienda"]["cap_usd"], 723.0, places=2)
        # uncapped categories deduce fully but are flagged as unconfigured
        self.assertAlmostEqual(by_code["salud"]["deducible"], 1000.0, places=2)
        self.assertIn("salud", result["unconfigured"])
        self.assertNotIn("vivienda", result["unconfigured"])
        self.assertAlmostEqual(result["total_spent"], 8600.0, places=2)

    def test_unconfigured_caps_never_invent_numbers(self):
        gastos = {"vivienda": 6000.0}
        caps = {"vivienda": None}
        result = lib.gastos_personales_calculate(gastos, caps, sbu=482.0)
        self.assertIsNone(result["rows"][0]["cap_smmlv"])
        self.assertIsNone(result["rows"][0]["cap_usd"])
        self.assertAlmostEqual(result["total_deducible"], 6000.0, places=2)

    def test_cap_param_name(self):
        for key, _label in lib.GASTOS_PERSONALES_CATEGORIES:
            self.assertEqual(
                lib.GASTOS_CAP_PARAM % key,
                "l10n_ec.gastos_personales.cap.%s_smmlv" % key,
            )

    def test_rebaja_tributaria_formula(self):
        # min(expenses, baskets * basket_cost) * 18%
        self.assertAlmostEqual(
            lib.rebaja_tributaria(10000.0, 7.0, 808.95),
            min(10000.0, 7 * 808.95) * 0.18, places=2,
        )
        self.assertAlmostEqual(
            lib.rebaja_tributaria(1000.0, 7.0, 808.95),
            1000.0 * 0.18, places=2,
        )
        self.assertEqual(lib.rebaja_tributaria(1000.0, 7.0, 0.0), 0.0)

    def test_baskets_by_family_loads(self):
        self.assertEqual(lib.n_baskets_for_loads(0), 7.0)
        self.assertEqual(lib.n_baskets_for_loads(2), 11.0)
        self.assertEqual(lib.n_baskets_for_loads(99), lib.BASKETS_MAX)
        self.assertEqual(lib.n_baskets_for_loads(0, catastrophic=True), 20.0)


# ===========================================================================
# Books
# ===========================================================================
class TestBooks(unittest.TestCase):
    def test_libro_ventas_signs_and_totals(self):
        result = lib.libro_ventas_rows(sales_set())
        self.assertEqual(len(result["rows"]), 4)
        totals = result["totals"]
        # 1000 + 500 + 100 + 2000 - 300 = 3300 of bases (exenta incl.)
        expected_base = 1000.0 + 500.0 + 100.0 + 2000.0 - 300.0
        computed = (totals["base_15"] + totals["base_5"] + totals["base_0"] +
                    totals["base_exenta"])
        self.assertAlmostEqual(computed, expected_base, places=2)
        # credit note reduced the IVA collected
        self.assertAlmostEqual(totals["iva"], 130.0, places=2)

    def test_libro_compras_totals(self):
        result = lib.libro_compras_rows(purchases_set())
        totals = result["totals"]
        self.assertAlmostEqual(totals["base_15"], 1400.0, places=2)
        self.assertAlmostEqual(totals["base_0"], 200.0, places=2)
        self.assertAlmostEqual(totals["iva"], 210.0, places=2)
        self.assertAlmostEqual(totals["ret_iva"], 300.0, places=2)
        self.assertAlmostEqual(totals["ret_ir"], 17.5, places=2)

    def test_libro_retenciones(self):
        result = lib.libro_retenciones_rows(retention_rows())
        self.assertEqual(len(result["rows"]), 3)
        self.assertAlmostEqual(result["totals"]["amount"], 1647.5, places=2)
        self.assertAlmostEqual(result["totals"]["amount_ir"], 247.5, places=2)
        self.assertAlmostEqual(result["totals"]["amount_iva"], 1400.0, places=2)

    def test_libro_diario_balances(self):
        moves = [
            {"name": "BNK/0001", "date": "2026-01-05", "ref": "Cobro",
             "lines": [
                 {"account_code": "1020", "account_name": "Banco",
                  "label": "Cobro cliente", "debit": 1150.0, "credit": 0.0},
                 {"account_code": "1110", "account_name": "Clientes",
                  "label": "Cobro cliente", "debit": 0.0, "credit": 1150.0},
             ]},
        ]
        result = lib.libro_diario_rows(moves)
        self.assertAlmostEqual(result["totals"]["debe"], 1150.0, places=2)
        self.assertAlmostEqual(result["totals"]["haber"], 1150.0, places=2)
        self.assertAlmostEqual(result["totals"]["difference"], 0.0, places=2)

    def test_libro_bancos_running_balance(self):
        lines = [
            {"fecha": "2026-01-02", "documento": "AJ/1", "cuenta": "1020",
             "partner": "", "glosa": "Apertura", "debit": 1000.0,
             "credit": 0.0},
            {"fecha": "2026-01-10", "documento": "AJ/2", "cuenta": "1020",
             "partner": "", "glosa": "Pago", "debit": 0.0, "credit": 300.0},
        ]
        result = lib.libro_bancos_rows(lines, opening=500.0)
        self.assertAlmostEqual(result["rows"][0]["saldo"], 1500.0, places=2)
        self.assertAlmostEqual(result["rows"][1]["saldo"], 1200.0, places=2)
        self.assertAlmostEqual(result["totals"]["saldo"], 1200.0, places=2)
        self.assertAlmostEqual(result["opening"], 500.0, places=2)

    def test_libro_mayor_running_balance(self):
        moves = [
            {"name": "AJ/1", "date": "2026-01-05", "ref": "",
             "lines": [
                 {"account_code": "1020", "account_name": "Banco",
                  "label": "x", "debit": 100.0, "credit": 0.0},
                 {"account_code": "4100", "account_name": "Ventas",
                  "label": "x", "debit": 0.0, "credit": 100.0},
             ]},
            {"name": "AJ/2", "date": "2026-01-06", "ref": "",
             "lines": [
                 {"account_code": "1020", "account_name": "Banco",
                  "label": "y", "debit": 50.0, "credit": 0.0},
                 {"account_code": "4100", "account_name": "Ventas",
                  "label": "y", "debit": 0.0, "credit": 50.0},
             ]},
        ]
        result = lib.libro_mayor_rows(moves, openings={"1020": 20.0})
        banco = [a for a in result["accounts"] if a["code"] == "1020"][0]
        self.assertAlmostEqual(banco["rows"][0]["saldo"], 120.0, places=2)
        self.assertAlmostEqual(banco["rows"][1]["saldo"], 170.0, places=2)
        self.assertAlmostEqual(banco["balance"], 170.0, places=2)
        self.assertAlmostEqual(result["totals"]["debe"], 150.0, places=2)

    def test_trial_balance_and_inventarios_groups(self):
        raw = [
            {"code": "1020", "name": "Banco", "account_type": "asset_cash",
             "debit": 1000.0, "credit": 0.0},
            {"code": "1110", "name": "Clientes",
             "account_type": "asset_receivable", "debit": 500.0,
             "credit": 0.0},
            {"code": "2010", "name": "Proveedores",
             "account_type": "liability_payable", "debit": 0.0,
             "credit": 800.0},
            {"code": "3010", "name": "Capital", "account_type": "equity",
             "debit": 0.0, "credit": 700.0},
        ]
        trial = lib.trial_balance(raw)
        self.assertAlmostEqual(trial["totals"]["debit"], 1500.0, places=2)
        self.assertAlmostEqual(trial["totals"]["credit"], 1500.0, places=2)

        book = lib.inventarios_balances(trial, [
            {"name": "Producto A", "quantity": 10.0, "unit_cost": 5.0,
             "value": 50.0},
        ])
        groups = {g["group"]: g for g in book["groups"]}
        self.assertAlmostEqual(groups["1"]["balance"], 1500.0, places=2)
        self.assertEqual(groups["1"]["label"], "ACTIVO")
        self.assertAlmostEqual(book["valuation_total"], 50.0, places=2)


# ===========================================================================
# Estados financieros (SUPERCIAS)
# ===========================================================================
class TestEstadosFinancieros(unittest.TestCase):
    def _trial_rows(self):
        raw = [
            {"code": "1020", "name": "Banco", "account_type": "asset_cash",
             "debit": 5000.0, "credit": 0.0},
            {"code": "1110", "name": "Clientes",
             "account_type": "asset_receivable", "debit": 2000.0,
             "credit": 0.0},
            {"code": "1510", "name": "Equipos", "account_type": "asset_fixed",
             "debit": 3000.0, "credit": 0.0},
            {"code": "2010", "name": "Proveedores",
             "account_type": "liability_payable", "debit": 0.0,
             "credit": 4000.0},
            {"code": "2110", "name": "Prestamos",
             "account_type": "liability_non_current", "debit": 0.0,
             "credit": 2000.0},
            {"code": "3010", "name": "Capital", "account_type": "equity",
             "debit": 0.0, "credit": 4000.0},
        ]
        return lib.trial_balance(raw)["rows"]

    def test_balance_general_cuadra(self):
        result = lib.balance_general(self._trial_rows(), "2026")
        self.assertAlmostEqual(result["total_activo"], 10000.0, places=2)
        self.assertAlmostEqual(result["total_pasivo"], 6000.0, places=2)
        self.assertAlmostEqual(result["total_patrimonio"], 4000.0, places=2)
        self.assertAlmostEqual(result["total_pasivo_patrimonio"], 10000.0,
                               places=2)
        self.assertTrue(result["balanced"])
        self.assertAlmostEqual(result["difference"], 0.0, places=2)

    def test_balance_sections_match_groups(self):
        result = lib.balance_general(self._trial_rows())
        titles = [s["title"] for s in result["sections"]]
        self.assertIn("ACTIVO CORRIENTE", titles)
        self.assertIn("ACTIVO NO CORRIENTE", titles)
        self.assertIn("PASIVO CORRIENTE", titles)
        self.assertIn("PATRIMONIO", titles)

    def test_estado_resultados(self):
        raw = [
            {"code": "4100", "name": "Ventas", "account_type": "income",
             "debit": 0.0, "credit": 100000.0},
            {"code": "5100", "name": "Costo ventas",
             "account_type": "expense_direct_cost", "debit": 40000.0,
             "credit": 0.0},
            {"code": "6100", "name": "Gastos", "account_type": "expense",
             "debit": 30000.0, "credit": 0.0},
        ]
        rows = lib.trial_balance(raw)["rows"]
        result = lib.estado_resultados(rows, tax_rate=0.25)
        self.assertAlmostEqual(result["total_ingresos"], 100000.0, places=2)
        self.assertAlmostEqual(result["utilidad_bruta"], 60000.0, places=2)
        self.assertAlmostEqual(result["utilidad_operacional"], 30000.0,
                               places=2)
        self.assertAlmostEqual(result["impuesto_renta"], 7500.0, places=2)
        self.assertAlmostEqual(result["utilidad_neta"], 22500.0, places=2)

    def test_flujo_efectivo_reconciles(self):
        # trial_balance convention: balances are DEBIT POSITIVE, so equity
        # (credit balance) shows negative.  Scenario: cash +700, receivables
        # -200, equity +500 = net income 400 + depreciation 100 -> it
        # balances (assets 1500 -> 2000, equity 1500 -> 2000).
        open_rows = [
            {"code": "1020", "name": "Banco", "account_type": "asset_cash",
             "balance": 1000.0, "group": "1"},
            {"code": "1110", "name": "Clientes",
             "account_type": "asset_receivable", "balance": 500.0,
             "group": "1"},
            {"code": "3010", "name": "Capital", "account_type": "equity",
             "balance": -1500.0, "group": "3"},
        ]
        close_rows = [
            {"code": "1020", "name": "Banco", "account_type": "asset_cash",
             "balance": 1700.0, "group": "1"},
            {"code": "1110", "name": "Clientes",
             "account_type": "asset_receivable", "balance": 300.0,
             "group": "1"},
            {"code": "3010", "name": "Capital", "account_type": "equity",
             "balance": -2000.0, "group": "3"},
        ]
        result = lib.flujo_efectivo(open_rows, close_rows, net_income=400.0,
                                    depreciation=100.0)
        # cash went from 1000 -> 1700 = +700
        self.assertAlmostEqual(result["cash_delta"], 700.0, places=2)
        # net_change must equal cash_delta in this consistent scenario
        self.assertAlmostEqual(result["net_change"], 700.0, places=2)
        self.assertAlmostEqual(result["reconciliation_difference"], 0.0,
                               places=2)

    def test_cambios_patrimonio_identity(self):
        open_rows = [{"code": "3010", "name": "Capital",
                      "account_type": "equity", "balance": -1000.0,
                      "group": "3"}]
        close_rows = [{"code": "3010", "name": "Capital",
                       "account_type": "equity", "balance": -1500.0,
                       "group": "3"}]
        result = lib.cambios_patrimonio(open_rows, close_rows,
                                        net_income=400.0, distributions=100.0)
        self.assertAlmostEqual(result["check"], 0.0, places=2)
        self.assertAlmostEqual(
            result["saldo_inicial"] + result["otras_variaciones"] +
            result["utilidad"] - result["distribuciones"],
            result["saldo_final"], places=2,
        )

    def test_notas_stub_has_required_headings(self):
        notes = lib.notas_financieras_stub()
        numbers = [n["number"] for n in notes]
        self.assertEqual(numbers, [str(i) for i in range(1, 17)])
        self.assertEqual(len(notes), 16)
        for note in notes:
            self.assertTrue(note["title"])
            self.assertTrue(note["columns"])


# ===========================================================================
# ATS
# ===========================================================================
class TestATS(unittest.TestCase):
    def _payload(self, **kwargs):
        ventas = [lib.invoice_report_row(r) for r in sales_set()]
        compras = [lib.invoice_report_row(r) for r in purchases_set()]
        header = {"year": "2026", "month": "01", "entity": "001",
                  "company_name": "MI EMPRESA S.A.", "vat": "1793125212001"}
        return lib.ats_build(header, ventas, compras,
                             kwargs.get("cancelled", []),
                             kwargs.get("retentions", retention_rows()),
                             [v for v in ventas if v["is_export"]])

    def test_header(self):
        payload = self._payload()
        self.assertEqual(payload["header"]["year"], "2026")
        self.assertEqual(payload["header"]["month"], "01")
        self.assertEqual(payload["header"]["entity"], "001")

    def test_total_ventas_signed(self):
        payload = self._payload()
        # 1000 + 500 + 100 + 2000 - 300 = 3300
        self.assertAlmostEqual(payload["total_ventas"], 3300.0, places=2)

    def test_ventas_grouped_by_partner_and_doc(self):
        payload = self._payload()
        keys = {(v["tpIdCliente"], v["idCliente"], v["tipoComprobante"])
                for v in payload["ventas"]}
        # credit note (doc 04) is its own group
        self.assertIn(("04", "1793125212001", "01"), keys)
        self.assertIn(("04", "1793125212001", "04"), keys)
        nc = [v for v in payload["ventas"] if v["tipoComprobante"] == "04"][0]
        self.assertAlmostEqual(nc["montoIva"], -45.0, places=2)
        self.assertAlmostEqual(nc["baseImpGrav"], -300.0, places=2)

    def test_compras_structure(self):
        payload = self._payload()
        self.assertEqual(len(payload["compras"]), 2)
        first = payload["compras"][0]
        for key in ("codSustento", "tpIdProv", "idProv", "tipoComprobante",
                    "fechaRegistro", "establecimiento", "puntoEmision",
                    "secuencial", "fechaEmision", "autorizacion",
                    "baseNoGraIva", "baseImponible", "baseImpGrav",
                    "baseImpExe", "montoIce", "montoIva", "valorRetBienes",
                    "valorRetServicios", "valRetBien10", "valRetServ20",
                    "valRetServ50", "pagoExterior", "formasDePago", "air",
                    "estabRetencion1", "ptoEmiRetencion1", "secRetencion1",
                    "autRetencion1", "fechaEmiRet1"):
            self.assertIn(key, first, "ATS compras missing %s" % key)
        self.assertAlmostEqual(first["baseImpGrav"], 1000.0, places=2)
        self.assertAlmostEqual(first["montoIva"], 150.0, places=2)
        # IVA retention 30% -> valorRetBienes
        self.assertAlmostEqual(first["valorRetBienes"], 300.0, places=2)
        self.assertEqual(first["formasDePago"][0]["formaPago"], "20")
        self.assertEqual(first["pagoExterior"]["pagoLocExt"], "01")

    def test_compras_air_entries(self):
        payload = self._payload()
        air = payload["compras"][0]["air"]
        self.assertEqual(len(air), 1)
        self.assertEqual(air[0]["codRetAir"], "312")
        self.assertAlmostEqual(air[0]["baseImpAir"], 1000.0, places=2)
        self.assertAlmostEqual(air[0]["porcentajeAir"], 1.75, places=2)
        self.assertAlmostEqual(air[0]["valRetAir"], 17.5, places=2)

    def test_retention_voucher_reference_parsed(self):
        payload = self._payload()
        first = payload["compras"][0]
        self.assertEqual(first["estabRetencion1"], "001")
        self.assertEqual(first["ptoEmiRetencion1"], "001")
        self.assertEqual(first["secRetencion1"], "000000123")
        self.assertEqual(first["autRetencion1"], "1234567890")
        self.assertEqual(first["fechaEmiRet1"], "2026-01-20")

    def test_ventas_establecimiento(self):
        payload = self._payload()
        self.assertTrue(payload["ventas_establecimiento"])
        ve = payload["ventas_establecimiento"][0]
        self.assertEqual(ve["codEstab"], "001")
        self.assertAlmostEqual(ve["ventasEstab"], 3300.0, places=2)
        self.assertAlmostEqual(ve["ivaComp"], 130.0, places=2)

    def test_exportaciones_section(self):
        payload = self._payload()
        self.assertEqual(len(payload["exportaciones"]), 1)
        exp = payload["exportaciones"][0]
        self.assertAlmostEqual(exp["valorExport"], 2000.0, places=2)
        # codDoc of the export invoice, passed through (DM_07: tipoComprobante
        # = l10n_latam_document_type_id.code); no codDoc table in the repo
        # documents the SRS example value 18.
        self.assertEqual(exp["tipoComprobante"], "01")

    def test_retenciones_section(self):
        payload = self._payload()
        self.assertEqual(len(payload["retenciones"]), 3)
        codes = {r["codRetAir"] for r in payload["retenciones"]}
        self.assertEqual(codes, {"312", "304", "723"})
        total = sum(r["valRetAir"] for r in payload["retenciones"])
        self.assertAlmostEqual(total, 1647.5, places=2)

    def test_anulados_section(self):
        cancelled = [{"doc_code": "01", "numero": "001-001-000000050",
                      "autorizacion": "1234567890"}]
        payload = self._payload(cancelled=cancelled)
        self.assertEqual(len(payload["anulados"]), 1)
        entry = payload["anulados"][0]
        self.assertEqual(entry["establecimiento"], "001")
        self.assertEqual(entry["puntoEmision"], "001")
        self.assertEqual(entry["secuencialInicio"], "000000050")
        self.assertEqual(entry["secuencialFin"], "000000050")

    def test_empty_sections_are_empty_lists(self):
        payload = lib.ats_build(
            {"year": "2026", "month": "02", "entity": "001",
             "company_name": "X", "vat": "1793125212001"},
            [], [], [], [], [],
        )
        for key in ("ventas", "compras", "anulados", "exportaciones",
                    "retenciones"):
            self.assertEqual(payload[key], [], key)
        self.assertTrue(payload["ventas_establecimiento"])  # fallback row
        self.assertAlmostEqual(payload["total_ventas"], 0.0, places=2)


class TestATSValidation(unittest.TestCase):
    """REQ-ATS-001."""

    def test_ok_payload_has_no_errors(self):
        ventas = [lib.invoice_report_row(r) for r in sales_set()]
        compras = [lib.invoice_report_row(r) for r in purchases_set()]
        errors = lib.ats_validate(ventas, compras, [], retention_rows())
        self.assertEqual(errors, [])

    def test_missing_sustento_reported(self):
        compra = lib.invoice_report_row(raw_invoice(
            move_type="in_invoice", tp_id="02", identificacion="1793125212001",
            sustento="", secuencial="000000500",
            clave_acceso="", autorizacion="",
            lines=[line(100.0, [15.0])],
        ))
        errors = lib.ats_validate([], [compra], [], [])
        self.assertTrue(any("sustento" in e for e in errors))

    def test_missing_access_key_reported(self):
        compra = lib.invoice_report_row(raw_invoice(
            move_type="in_invoice", tp_id="02", identificacion="1793125212001",
            sustento="01", secuencial="000000501",
            clave_acceso="", autorizacion="",
            lines=[line(100.0, [15.0])],
        ))
        errors = lib.ats_validate([], [compra], [], [])
        self.assertTrue(any("clave de acceso" in e for e in errors))

    def test_missing_partner_id_reported(self):
        compra = lib.invoice_report_row(raw_invoice(
            move_type="in_invoice", tp_id="02", identificacion="",
            sustento="01", secuencial="000000502",
            clave_acceso="1" * 49,
            lines=[line(100.0, [15.0])],
        ))
        errors = lib.ats_validate([], [compra], [], [])
        self.assertTrue(any("identificacion" in e for e in errors))

    def test_missing_customer_id_reported(self):
        venta = lib.invoice_report_row(raw_invoice(identificacion="",
                                                   secuencial="000000503"))
        errors = lib.ats_validate([venta], [], [], [])
        self.assertTrue(any("cliente sin identificacion" in e for e in errors))

    def test_orphan_retention_reported(self):
        orphan = dict(retention_rows()[0], comprobante="")
        errors = lib.ats_validate([], [], [], [orphan])
        self.assertTrue(any("huerfano" in e for e in errors))


# ===========================================================================
# Shared helpers (invoice contract, formatters, exporters)
# ===========================================================================
class TestInvoiceContract(unittest.TestCase):
    def test_signs(self):
        self.assertEqual(lib.invoice_sign({"move_type": "out_invoice"}), 1.0)
        self.assertEqual(lib.invoice_sign({"move_type": "out_refund"}), -1.0)
        self.assertEqual(lib.invoice_sign({"move_type": "in_invoice"}), 1.0)
        self.assertEqual(lib.invoice_sign({"move_type": "in_refund"}), -1.0)

    def test_report_row_buckets(self):
        raw = raw_invoice(lines=[line(1000.0, [15.0]), line(200.0, [5.0]),
                                 line(50.0, [0.0])],
                          tax_lines=[{"group": "IVA 15%", "balance": 150.0,
                                      "ice": False, "ret_kind": None},
                                     {"group": "ICE", "balance": 10.0,
                                      "ice": True, "ret_kind": None},
                                     {"group": "RET IVA 30%", "balance": 60.0,
                                      "ice": False, "ret_kind": "iva"},
                                     {"group": "RET RENTA 2%", "balance": 20.0,
                                      "ice": False, "ret_kind": "ir"}])
        row = lib.invoice_report_row(raw)
        self.assertAlmostEqual(row["base_15"], 1000.0, places=2)
        self.assertAlmostEqual(row["base_5"], 200.0, places=2)
        self.assertAlmostEqual(row["base_0"], 50.0, places=2)
        self.assertAlmostEqual(row["iva"], 150.0, places=2)
        self.assertAlmostEqual(row["ice"], 10.0, places=2)
        self.assertAlmostEqual(row["ret_iva"], 60.0, places=2)
        self.assertAlmostEqual(row["ret_ir"], 20.0, places=2)

    def test_credit_note_row_is_negative(self):
        # raw amounts positive (account.move shape) -> signed row negative
        raw = raw_invoice(move_type="out_refund",
                          lines=[line(300.0, [15.0])],
                          tax_lines=[{"group": "IVA 15%", "balance": 45.0,
                                      "ice": False, "ret_kind": None}])
        row = lib.invoice_report_row(raw)
        self.assertAlmostEqual(row["base_15"], -300.0, places=2)
        self.assertAlmostEqual(row["iva"], -45.0, places=2)

    def test_split_document_number(self):
        self.assertEqual(lib.split_document_number("001-001-000000123"),
                         ("001", "001", "000000123"))
        self.assertEqual(lib.split_document_number("001001000000123"),
                         ("001", "001", "000000123"))
        self.assertEqual(lib.split_document_number("12345"), ("000", "000",
                                                              "12345"))


class TestFormatters(unittest.TestCase):
    def test_fmt_cell(self):
        self.assertEqual(lib.fmt_cell(1234.5), "1234.50")
        self.assertEqual(lib.fmt_cell(None), "")
        self.assertEqual(lib.fmt_cell(True), "SI")
        self.assertEqual(lib.fmt_cell(False), "NO")
        self.assertEqual(lib.fmt_cell("abc"), "abc")
        self.assertEqual(lib.fmt_cell(7), "7")

    def test_fmt_totals_includes_extra_keys(self):
        columns = [("base", "Base"), ("amount", "Valor")]
        totals = {"base": 100.0, "amount": 17.5, "amount_ir": 17.5,
                  "amount_iva": 0.0, "count": 2}
        rows = lib.fmt_totals(totals, columns)
        labels = [r[0] for r in rows]
        self.assertIn("Base", labels)
        self.assertIn("Valor", labels)
        self.assertIn("Total ret. IR", labels)
        self.assertIn("Registros", labels)
        self.assertEqual(dict(rows)["Valor"], "17.50")

    def test_write_csv_roundtrip(self):
        rows = [{"base": 100.0, "amount": 17.5, "fecha": "2026-01-01"}]
        columns = [("fecha", "Fecha"), ("base", "Base"), ("amount", "Valor")]
        content = lib.write_csv(rows, columns, totals={"base": 100.0,
                                                       "amount": 17.5})
        lines = [ln for ln in content.splitlines() if ln]
        self.assertEqual(lines[0], "Fecha,Base,Valor")
        self.assertIn("2026-01-01,100.00,17.50", lines[1])
        self.assertIn("100.00", lines[-1])

    def test_progressive_tax_brackets(self):
        brackets = lib.DEFAULT_TAX_BRACKETS_2026
        self.assertAlmostEqual(lib.progressive_tax(0.0, brackets), 0.0,
                               places=2)
        # exactly the first bracket limit
        self.assertAlmostEqual(lib.progressive_tax(12208.0, brackets), 0.0,
                               places=2)
        # inside second bracket: 0 + (15000-12208) * 5%
        self.assertAlmostEqual(lib.progressive_tax(15000.0, brackets),
                               (15000.0 - 12208.0) * 0.05, places=2)
        # top bracket: 24572 + (120000-109956) * 37%
        self.assertAlmostEqual(lib.progressive_tax(120000.0, brackets),
                               24572.0 + (120000.0 - 109956.0) * 0.37,
                               places=2)
        self.assertEqual(lib.progressive_tax(10.0, []), 0.0)

    def test_month_bounds(self):
        start, end = lib.month_bounds(2026, 2)
        self.assertEqual(start, date(2026, 2, 1))
        self.assertEqual(end, date(2026, 3, 1))

    def test_parse_date(self):
        self.assertEqual(lib.parse_date("2026-01-15"), date(2026, 1, 15))
        self.assertEqual(lib.parse_date(date(2026, 1, 15)), date(2026, 1, 15))
        self.assertEqual(lib.parse_date(False), date(1970, 1, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
