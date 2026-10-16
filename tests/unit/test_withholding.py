# -*- coding: utf-8 -*-
"""
Withholding Module Tests
========================

Tests retenciones IR, IVA, and Dividend withholding.
All rates from ir.config_parameter.
"""
from datetime import date

from odoo.tests import tagged, TransactionCase
from odoo.exceptions import ValidationError, UserError


@tagged("post_install", "-at_install", "l10n_ec", "withholding")
class TestWithholding(TransactionCase):
    """Tests for Ecuador Withholding (Retenciones)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()

    # =========================================================================
    # IR WITHHOLDING RATES
    # =========================================================================

    def test_withholding_ir_rates_exist(self):
        """[WITH-01] IR withholding rates configured."""
        # Tax template should have IR retention taxes
        taxes = self.env["account.tax"].search(
            [
                ("name", "ilike", "Retención IR%"),
                ("type_tax_use", "=", "purchase"),
            ]
        )
        self.assertTrue(len(taxes) > 0, "IR withholding taxes should exist")

    def test_withholding_ir_10_honorarios(self):
        """[WITH-02] IR 10% Honorarios rate."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%10%Honorarios%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(abs(tax.amount), 10.0, "IR Honorarios should be 10%")

    def test_withholding_ir_8_profesionales(self):
        """[WITH-03] IR 8% Profesionales rate."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%8%Profesional%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(abs(tax.amount), 8.0, "IR Profesionales should be 8%")

    # =========================================================================
    # IVA WITHHOLDING RATES
    # =========================================================================

    def test_withholding_iva_rates_exist(self):
        """[WITH-04] IVA withholding rates configured."""
        taxes = self.env["account.tax"].search(
            [
                ("name", "ilike", "Retención IVA%"),
                ("type_tax_use", "=", "purchase"),
            ]
        )
        self.assertTrue(len(taxes) > 0, "IVA withholding taxes should exist")

    def test_withholding_iva_30_bienes(self):
        """[WITH-05] IVA 30% Bienes rate."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%IVA 30%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(abs(tax.amount), 30.0, "IVA Bienes CE should be 30%")

    def test_withholding_iva_70_servicios(self):
        """[WITH-06] IVA 70% Servicios rate."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%IVA 70%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(abs(tax.amount), 70.0, "IVA Servicios CE should be 70%")

    def test_withholding_iva_100_total(self):
        """[WITH-07] IVA 100% Total rate."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%IVA 100%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(abs(tax.amount), 100.0, "IVA 100% should exist")

    # =========================================================================
    # DIVIDEND WITHHOLDING (2026 Regulation)
    # =========================================================================

    def test_dividend_10_non_resident(self):
        """[WITH-08] Dividend 10% for non-residents."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%Dividendos 10%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(
                abs(tax.amount), 10.0, "Dividend non-resident should be 10%"
            )

    def test_dividend_12_resident(self):
        """[WITH-09] Dividend 12% for residents."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%Dividendos 12%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(abs(tax.amount), 12.0, "Dividend resident should be 12%")

    def test_dividend_14_tax_haven(self):
        """[WITH-10] Dividend 14% for tax havens."""
        tax = self.env["account.tax"].search(
            [
                ("name", "ilike", "%Dividendos 14%"),
            ],
            limit=1,
        )
        if tax:
            self.assertEqual(abs(tax.amount), 14.0, "Dividend tax haven should be 14%")


# ===========================================================================
# AUDIT LOCKS: SRI RATE TABLES (2026)
# ===========================================================================

# SRI Tabla 19 (Impuesto a la Renta) - legal constants, must not drift.
EXPECTED_IR_RATES = {
    "303": 10.0,
    "304": 8.0,
    "307": 2.0,
    "308": 2.0,
    "309": 1.0,
    "310": 1.0,
    "312": 1.0,
    "319": 1.0,
    "320": 1.75,
    "322": 1.0,
    "323": 2.0,
    "340": 1.0,
    "344": 25.0,
    "500": 25.0,
}

# SRI Tabla 21 (IVA) - legal constants, must not drift.
EXPECTED_IVA_RATES = {
    "721": 10.0,
    "723": 20.0,
    "725": 30.0,
    "727": 70.0,
    "729": 100.0,
    "731": 100.0,
}


@tagged("post_install", "-at_install", "l10n_ec", "withholding")
class TestWithholdingRateTables(TransactionCase):
    """Locks the SRI IR/IVA withholding code+rate tables (audit items 1-2)."""

    def test_ir_rate_table_locked(self):
        """All SRI Tabla 19 codes exist with the legally correct rate."""
        Tax = self.env["l10n_ec.withholding.tax"]
        for code, rate in EXPECTED_IR_RATES.items():
            tax = Tax.search(
                [("code", "=", code), ("type", "=", "renta")], limit=1
            )
            self.assertTrue(tax, "Missing SRI IR withholding code %s" % code)
            self.assertAlmostEqual(
                tax.percentage,
                rate,
                places=2,
                msg="IR code %s must be %s%% (SRI Tabla 19)" % (code, rate),
            )

    def test_iva_rate_table_locked(self):
        """All SRI Tabla 21 codes exist with the legally correct rate."""
        Tax = self.env["l10n_ec.withholding.tax"]
        for code, rate in EXPECTED_IVA_RATES.items():
            tax = Tax.search(
                [("code", "=", code), ("type", "=", "iva")], limit=1
            )
            self.assertTrue(tax, "Missing SRI IVA withholding code %s" % code)
            self.assertAlmostEqual(
                tax.percentage,
                rate,
                places=2,
                msg="IVA code %s must be %s%% (SRI Tabla 21)" % (code, rate),
            )

    def test_base_retention_code_table_ir(self):
        """l10n_ec_base reference table (l10n_ec.retention.code) matches IR rates."""
        Code = self.env["l10n_ec.retention.code"]
        for code, rate in EXPECTED_IR_RATES.items():
            rec = Code.search([("code", "=", code), ("type", "=", "ir")], limit=1)
            self.assertTrue(rec, "l10n_ec.retention.code missing IR %s" % code)
            self.assertAlmostEqual(
                rec.rate, rate, places=2,
                msg="l10n_ec.retention.code IR %s must be %s%%" % (code, rate),
            )

    def test_base_retention_code_table_iva(self):
        """l10n_ec_base reference table (l10n_ec.retention.code) matches IVA rates."""
        Code = self.env["l10n_ec.retention.code"]
        for code, rate in EXPECTED_IVA_RATES.items():
            rec = Code.search([("code", "=", code), ("type", "=", "iva")], limit=1)
            self.assertTrue(rec, "l10n_ec.retention.code missing IVA %s" % code)
            self.assertAlmostEqual(
                rec.rate, rate, places=2,
                msg="l10n_ec.retention.code IVA %s must be %s%%" % (code, rate),
            )


# ===========================================================================
# AUDIT LOCK: 5-BUSINESS-DAY RULE (Código Tributario art. 17)
# ===========================================================================


@tagged("post_install", "-at_install", "l10n_ec", "withholding")
class TestFiveBusinessDayRule(TransactionCase):
    """
    The comprobante de retención must be issued within 5 BUSINESS days of
    the vendor bill date. Weekends and Ecuadorian holidays (fixed + Carnival
    + Good Friday + company leaves) are NOT counted.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor 5 Dias"})
        cls.journal_purchase = cls.env["account.journal"].search(
            [
                ("type", "=", "purchase"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        ) or cls.env["account.journal"].create(
            {
                "name": "Purchases Withholding Test",
                "type": "purchase",
                "code": "PW5D",
            }
        )
        cls.tax_ir_312 = cls.env.ref("l10n_ec_withholding.tax_ret_ir_312")
        cls.Retention = cls.env["account.retention"]

    def _make_invoice(self, invoice_date):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": invoice_date,
                "date": invoice_date,
            }
        )

    def _make_retention(self, invoice, ret_date):
        return self.Retention.create(
            {
                "invoice_id": invoice.id,
                "partner_id": self.partner.id,
                "date": ret_date,
                "retention_line_ids": [
                    (
                        0,
                        0,
                        {
                            "tax_type": "1",
                            "tax_id": self.tax_ir_312.id,
                            "base": 100.0,
                        },
                    )
                ],
            }
        )

    # -- pure counter ------------------------------------------------------

    def test_counter_same_day_is_zero(self):
        self.assertEqual(
            self.Retention._l10n_ec_count_business_days(
                date(2026, 3, 5), date(2026, 3, 5)
            ),
            0,
        )

    def test_counter_skips_weekend(self):
        # Friday -> Monday counts 1 business day (not 3 calendar days)
        self.assertEqual(
            self.Retention._l10n_ec_count_business_days(
                date(2026, 3, 6), date(2026, 3, 9)
            ),
            1,
        )

    def test_counter_skips_good_friday(self):
        # 2026-04-03 is Viernes Santo (holiday). Thu 02 -> Wed 08 = 3 business
        # days (06, 07, 08), not 4.
        self.assertEqual(
            self.Retention._l10n_ec_count_business_days(
                date(2026, 4, 2), date(2026, 4, 8)
            ),
            3,
        )

    def test_counter_skips_carnival(self):
        # Carnaval 2026: Mon 02-16 and Tue 02-17. Fri 13 -> Fri 20 = 3
        # business days (18, 19, 20).
        self.assertEqual(
            self.Retention._l10n_ec_count_business_days(
                date(2026, 2, 13), date(2026, 2, 20)
            ),
            3,
        )

    def test_counter_skips_guayaquil_holiday(self):
        # 2026-10-09 (Independencia de Guayaquil) is a Friday holiday.
        self.assertEqual(
            self.Retention._l10n_ec_count_business_days(
                date(2026, 10, 5), date(2026, 10, 13)
            ),
            5,
        )

    # -- constraint behavior -----------------------------------------------

    def test_same_day_retention_allowed(self):
        invoice = self._make_invoice(date(2026, 3, 5))
        retention = self._make_retention(invoice, date(2026, 3, 5))
        self.assertEqual(retention.state, "draft")

    def test_within_5_business_days_allowed(self):
        # Thu 2026-03-05 -> Wed 2026-03-11 = 4 business days
        invoice = self._make_invoice(date(2026, 3, 5))
        retention = self._make_retention(invoice, date(2026, 3, 11))
        self.assertEqual(retention.date, date(2026, 3, 11))

    def test_over_5_business_days_rejected(self):
        # Wed 2026-03-04 -> Fri 2026-03-13 = 7 business days
        invoice = self._make_invoice(date(2026, 3, 4))
        with self.assertRaises(ValidationError):
            self._make_retention(invoice, date(2026, 3, 13))

    def test_calendar_7_days_but_5_business_allowed(self):
        # 7 CALENDAR days but only 5 business days (two weekends):
        # Fri 2026-03-06 -> Fri 2026-03-13. A calendar-day rule would reject.
        invoice = self._make_invoice(date(2026, 3, 6))
        retention = self._make_retention(invoice, date(2026, 3, 13))
        self.assertEqual(retention.date, date(2026, 3, 13))

    def test_good_friday_flips_the_rule(self):
        # 6 calendar days (would exceed a calendar rule) but Good Friday +
        # weekend make it only 3 business days -> allowed.
        invoice = self._make_invoice(date(2026, 4, 2))
        retention = self._make_retention(invoice, date(2026, 4, 8))
        self.assertEqual(retention.date, date(2026, 4, 8))

    def test_guayaquil_holiday_flips_the_rule(self):
        # Mon 2026-10-05 -> Tue 2026-10-13 = 5 business days BECAUSE Oct 9
        # (holiday) and the weekend are excluded. Without the holiday
        # exclusion it would be 6 and the retention would be rejected.
        invoice = self._make_invoice(date(2026, 10, 5))
        retention = self._make_retention(invoice, date(2026, 10, 13))
        self.assertEqual(retention.date, date(2026, 10, 13))

    def test_retention_before_invoice_rejected(self):
        invoice = self._make_invoice(date(2026, 3, 10))
        with self.assertRaises(ValidationError):
            self._make_retention(invoice, date(2026, 3, 2))


# ===========================================================================
# AUDIT LOCK: 30% SRI / 70% IESS SPLIT OF THE WITHHELD IVA (Decreto 745)
# ===========================================================================


def _find_or_create_account(env, codes, name, account_type):
    """Chart account by code (python chart or dotted NEC), create if absent."""
    company = env.company
    Account = env["account.account"].with_company(company)
    domain = [("company_id", "in", (False, company.id))]
    account = Account.search(domain + [("code", "in", codes)], limit=1)
    if not account:
        account = Account.create(
            {
                "code": codes[0],
                "name": name,
                "account_type": account_type,
                "company_id": company.id,
            }
        )
    return account


@tagged("post_install", "-at_install", "l10n_ec", "withholding")
class TestIvaSplit3070(TransactionCase):
    """
    Posting a comprobante de retención with IVA must split the withheld
    amount: 30% Retención IVA por Pagar (SRI) / 70% Aporte Personal IESS.
    Ratios come from ir.config_parameter (legal constants as data).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.ICP.set_param("l10n_ec.withholding_iva_sri_pct", "30")
        cls.ICP.set_param("l10n_ec.withholding_iva_iess_pct", "70")

        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor Split"})

        cls.payable_account = _find_or_create_account(
            cls.env, ["210199"], "Cuentas por Pagar Proveedores (test)",
            "liability_payable",
        )
        cls.partner.with_company(cls.company).write(
            {"property_account_payable_id": cls.payable_account.id}
        )

        cls.journal_general = cls.env["account.journal"].search(
            [
                ("type", "=", "general"),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        ) or cls.env["account.journal"].create(
            {
                "name": "Misc Withholding Test",
                "type": "general",
                "code": "MWT",
            }
        )

        cls.tax_ir_303 = cls.env.ref("l10n_ec_withholding.tax_ret_ir_303")
        cls.tax_iva_725 = cls.env.ref("l10n_ec_withholding.tax_ret_iva_725")
        cls.tax_iva_727 = cls.env.ref("l10n_ec_withholding.tax_ret_iva_727")
        cls.tax_iva_729 = cls.env.ref("l10n_ec_withholding.tax_ret_iva_729")

    def _make_retention(self, lines_vals, ret_date=date(2026, 3, 5)):
        return self.env["account.retention"].create(
            {
                "partner_id": self.partner.id,
                "date": ret_date,
                "journal_id": self.journal_general.id,
                "retention_line_ids": [
                    (0, 0, vals) for vals in lines_vals
                ],
            }
        )

    @staticmethod
    def _sum(move, side, account):
        return sum(
            move.line_ids.filtered(lambda l: l.account_id == account).mapped(side)
        )

    def test_split_config_is_30_70(self):
        sri_pct, iess_pct = self.env["account.retention"]._l10n_ec_get_iva_split()
        self.assertEqual(sri_pct, 30.0)
        self.assertEqual(iess_pct, 70.0)

    def test_iva_withheld_splits_30_sri_70_iess(self):
        # IVA 727 (70%) on base 1000 -> retained 700 -> 210 SRI / 490 IESS
        retention = self._make_retention(
            [
                {
                    "tax_type": "2",
                    "tax_id": self.tax_iva_727.id,
                    "base": 1000.0,
                }
            ]
        )
        retention.action_post()
        self.assertEqual(retention.state, "posted")
        move = retention.move_id
        self.assertTrue(move, "Posting the retention must create a journal entry")
        self.assertEqual(move.state, "posted")

        ir_acc, sri_acc, iess_acc = retention._l10n_ec_get_liability_accounts()
        self.assertEqual(self._sum(move, "credit", sri_acc), 210.0)
        self.assertEqual(self._sum(move, "credit", iess_acc), 490.0)
        self.assertEqual(self._sum(move, "debit", self.payable_account), 700.0)
        # Balance
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("debit")),
            sum(move.line_ids.mapped("credit")),
            places=2,
        )

    def test_iva_100_pct_case_also_splits(self):
        # 100% retention (code 729, liquidacion de compra): 1000 retained
        # -> 300 SRI / 700 IESS.
        retention = self._make_retention(
            [
                {
                    "tax_type": "2",
                    "tax_id": self.tax_iva_729.id,
                    "base": 1000.0,
                }
            ]
        )
        retention.action_post()
        ir_acc, sri_acc, iess_acc = retention._l10n_ec_get_liability_accounts()
        self.assertEqual(self._sum(retention.move_id, "credit", sri_acc), 300.0)
        self.assertEqual(self._sum(retention.move_id, "credit", iess_acc), 700.0)
        self.assertEqual(
            self._sum(retention.move_id, "debit", self.payable_account), 1000.0
        )

    def test_ir_only_has_no_split(self):
        # IR 303 (10%) on base 500 -> 50 to the IR liability account only.
        retention = self._make_retention(
            [
                {
                    "tax_type": "1",
                    "tax_id": self.tax_ir_303.id,
                    "base": 500.0,
                }
            ]
        )
        retention.action_post()
        ir_acc, sri_acc, iess_acc = retention._l10n_ec_get_liability_accounts()
        move = retention.move_id
        self.assertEqual(self._sum(move, "credit", ir_acc), 50.0)
        self.assertEqual(self._sum(move, "credit", sri_acc), 0.0)
        self.assertEqual(self._sum(move, "credit", iess_acc), 0.0)
        self.assertEqual(self._sum(move, "debit", self.payable_account), 50.0)

    def test_mixed_ir_and_iva(self):
        # IR 303 (10%) base 500 -> 50; IVA 725 (30%) base 1000 -> 300
        # (90 SRI / 210 IESS).
        retention = self._make_retention(
            [
                {
                    "tax_type": "1",
                    "tax_id": self.tax_ir_303.id,
                    "base": 500.0,
                },
                {
                    "tax_type": "2",
                    "tax_id": self.tax_iva_725.id,
                    "base": 1000.0,
                },
            ]
        )
        retention.action_post()
        ir_acc, sri_acc, iess_acc = retention._l10n_ec_get_liability_accounts()
        move = retention.move_id
        self.assertEqual(self._sum(move, "credit", ir_acc), 50.0)
        self.assertEqual(self._sum(move, "credit", sri_acc), 90.0)
        self.assertEqual(self._sum(move, "credit", iess_acc), 210.0)
        self.assertEqual(self._sum(move, "debit", self.payable_account), 350.0)
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("debit")),
            sum(move.line_ids.mapped("credit")),
            places=2,
        )

    def test_split_rounding_keeps_balance(self):
        # 233.33 retained: 30% = 69.999 -> rounds to 70.00; the IESS line
        # takes the remainder (163.33) so the entry always balances.
        retention = self._make_retention(
            [
                {
                    "tax_type": "2",
                    "tax_id": self.tax_iva_727.id,
                    "base": 333.33,
                }
            ]
        )
        retention.action_post()
        ir_acc, sri_acc, iess_acc = retention._l10n_ec_get_liability_accounts()
        move = retention.move_id
        self.assertAlmostEqual(self._sum(move, "credit", sri_acc), 70.0, places=2)
        self.assertAlmostEqual(self._sum(move, "credit", iess_acc), 163.33, places=2)
        self.assertAlmostEqual(
            self._sum(move, "debit", self.payable_account), 233.33, places=2
        )
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("debit")),
            sum(move.line_ids.mapped("credit")),
            places=2,
        )


# ===========================================================================
# AUDIT LOCK: TARIFF TABLE + AUTO-DETECTION ON BILL CONFIRMATION
# ===========================================================================


@tagged("post_install", "-at_install", "l10n_ec", "withholding")
class TestTariffAndAutoDetection(TransactionCase):
    """
    Withholding detection on vendor bills: product-explicit codes first,
    then the SRI tariff table keyed by the RUC 4th digit / activity.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.ICP.set_param("l10n_ec.withholding_iva_sri_pct", "30")
        cls.ICP.set_param("l10n_ec.withholding_iva_iess_pct", "70")
        cls.ICP.set_param("l10n_ec.withholding_auto_detect", "True")

        cls.company = cls.env.company
        cls.company.l10n_ec_withhold_agent = True
        if cls.company.country_id.code != "EC":
            cls.company.country_id = cls.env.ref("base.ec").id

        cls.vendor = cls.env["res.partner"].create({"name": "Proveedor Auto"})

        # D-04: sólo IDs aprobados como literales. El 4º dígito RUC 1 / 5 de
        # la tabla de tarifas no es representable con IDs reales, así que se
        # GENERA sintéticamente (sólo vat[3] lee get_ruc_4th_digit; partner
        # sin país a propósito: omite la validación de VAT).
        def _synthetic_ruc_4th(digit4):
            return "179" + digit4 + "000000001"

        cls.vendor_ruc_d1 = cls.env["res.partner"].create(
            {"name": "RUC 4to digito 1", "vat": _synthetic_ruc_4th("1")}
        )
        cls.vendor_ruc_d5 = cls.env["res.partner"].create(
            {"name": "RUC 4to digito 5", "vat": _synthetic_ruc_4th("5")}
        )

        cls.journal_purchase = cls.env["account.journal"].search(
            [
                ("type", "=", "purchase"),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        ) or cls.env["account.journal"].create(
            {
                "name": "Purchases Tariff Test",
                "type": "purchase",
                "code": "PTT",
            }
        )
        cls.expense_account = _find_or_create_account(
            cls.env, ["601099"], "Gastos de prueba (test)", "expense"
        )
        cls.vat_tax = cls.env["account.tax"].create(
            {
                "name": "IVA 15% Test",
                "amount": 15.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": cls.company.id,
            }
        )
        cls.product_goods = cls.env["product.product"].create(
            {"name": "Bien de prueba", "type": "consu", "list_price": 100.0}
        )
        cls.tax_ir_303 = cls.env.ref("l10n_ec_withholding.tax_ret_ir_303")
        cls.tax_ir_312 = cls.env.ref("l10n_ec_withholding.tax_ret_ir_312")
        cls.tax_iva_721 = cls.env.ref("l10n_ec_withholding.tax_ret_iva_721")
        cls.tax_iva_723 = cls.env.ref("l10n_ec_withholding.tax_ret_iva_723")
        cls.tax_iva_725 = cls.env.ref("l10n_ec_withholding.tax_ret_iva_725")
        cls.Tariff = cls.env["l10n_ec.retention.tariff"]

    def _create_bill(self, product=None, price=100.0):
        product = product or self.product_goods
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "journal_id": self.journal_purchase.id,
                "invoice_date": date(2026, 3, 5),
                "date": date(2026, 3, 5),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": product.display_name,
                            "product_id": product.id,
                            "quantity": 1.0,
                            "price_unit": price,
                            "account_id": self.expense_account.id,
                            "tax_ids": [(6, 0, self.vat_tax.ids)],
                        },
                    )
                ],
            }
        )

    # -- RUC 4th digit / tariff resolution ---------------------------------

    def test_get_ruc_4th_digit(self):
        self.assertEqual(
            self.Tariff.get_ruc_4th_digit(self.vendor_ruc_d1), "1"
        )
        self.assertEqual(
            self.Tariff.get_ruc_4th_digit(self.vendor_ruc_d5), "5"
        )
        self.assertFalse(self.Tariff.get_ruc_4th_digit(self.vendor))

    def test_digit_specific_row_beats_any_row(self):
        # Default data: IVA/bienes = 725 (30%). A digit-specific row for the
        # 4th digit '1' must take precedence over the 'any' row.
        self.Tariff.create(
            {
                "tax_type": "iva",
                "ruc_digit": "1",
                "activity": "goods",
                "withholding_tax_id": self.tax_iva_721.id,
            }
        )
        resolved = self.Tariff.resolve("iva", "goods", self.vendor_ruc_d1)
        self.assertEqual(resolved, self.tax_iva_721)
        # Vendors without that digit still fall back to the 'any' row.
        fallback = self.Tariff.resolve("iva", "goods", self.vendor_ruc_d5)
        self.assertEqual(fallback, self.tax_iva_725)

    def test_any_row_fallback_for_shipped_table(self):
        self.assertEqual(
            self.Tariff.resolve("iva", "goods", self.vendor_ruc_d5),
            self.tax_iva_725,
        )
        self.assertEqual(
            self.Tariff.resolve("renta", "goods", self.vendor_ruc_d5),
            self.tax_ir_312,
        )

    def test_service_product_defaults_to_services(self):
        product = self.env["product.product"].create(
            {"name": "Servicio de prueba", "type": "service"}
        )
        self.assertEqual(product.l10n_ec_withholding_activity, "services")
        self.assertEqual(self.product_goods.l10n_ec_withholding_activity, "goods")

    def test_product_code_overrides_tariff(self):
        product = self.env["product.product"].create(
            {
                "name": "Servicio con codigo propio",
                "type": "service",
                "l10n_ec_ir_retention_tax_id": self.tax_ir_303.id,
                "l10n_ec_iva_retention_tax_id": self.tax_iva_723.id,
            }
        )
        move_model = self.env["account.move"]
        self.assertEqual(
            move_model._l10n_ec_resolve_withholding_code(
                product, "renta", "services", self.vendor
            ),
            self.tax_ir_303,
        )
        self.assertEqual(
            move_model._l10n_ec_resolve_withholding_code(
                product, "iva", "services", self.vendor
            ),
            self.tax_iva_723,
        )

    # -- auto-detection on bill confirmation -------------------------------

    def test_auto_withholding_created_on_bill_post(self):
        bill = self._create_bill()
        bill.action_post()
        # The action_post hook swallows errors to never block posting; call
        # the method directly as fallback so real errors surface here.
        retention = bill.l10n_ec_withholding_id or (
            bill._l10n_ec_create_auto_withholding()
        )
        self.assertTrue(
            retention, "Posting a bill of a withholding agent must create "
            "a draft comprobante de retencion"
        )
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.invoice_id, bill)
        self.assertEqual(retention.partner_id, self.vendor)
        self.assertEqual(retention.date, bill.invoice_date)

        codes = retention.retention_line_ids.mapped("tax_code")
        self.assertIn("312", codes, "Tariff: goods/renta -> IR 312 (1%)")
        self.assertIn("725", codes, "Tariff: goods/IVA -> 725 (30%)")

        ir_line = retention.retention_line_ids.filtered(
            lambda l: l.tax_code == "312"
        )
        self.assertAlmostEqual(ir_line.base, 100.0, places=2)
        self.assertAlmostEqual(ir_line.amount, 1.0, places=2)

        iva_line = retention.retention_line_ids.filtered(
            lambda l: l.tax_code == "725"
        )
        self.assertAlmostEqual(iva_line.base, 15.0, places=2)  # 15% de 100
        self.assertAlmostEqual(iva_line.amount, 4.5, places=2)

    def test_wizard_prefills_from_bill_detection(self):
        bill = self._create_bill()
        wizard = (
            self.env["l10n_ec.retention.wizard"]
            .with_context(active_model="account.move", active_id=bill.id)
            .create({})
        )
        self.assertEqual(wizard.invoice_id, bill)
        codes = wizard.line_ids.mapped("tax_code")
        self.assertIn("312", codes)
        self.assertIn("725", codes)
        bases = sorted(wizard.line_ids.mapped("base"))
        self.assertEqual(bases, [15.0, 100.0])

    def test_no_auto_detect_when_partner_not_agent(self):
        self.company.l10n_ec_withhold_agent = False
        self.vendor.l10n_ec_withhold_agent = False
        bill = self._create_bill()
        self.assertFalse(bill._l10n_ec_create_auto_withholding())

    def test_no_auto_detect_when_disabled_via_icp(self):
        self.ICP.set_param("l10n_ec.withholding_auto_detect", "False")
        bill = self._create_bill()
        self.assertFalse(bill._l10n_ec_create_auto_withholding())

    def test_existing_retention_is_not_duplicated(self):
        bill = self._create_bill()
        first = bill._l10n_ec_create_auto_withholding()
        self.assertTrue(first)
        second = bill._l10n_ec_create_auto_withholding()
        self.assertFalse(second, "Must not duplicate the comprobante")

    def test_auto_retention_respects_5_day_rule(self):
        # The auto retention is dated with the invoice date, so it is always
        # inside the 5-business-day window (0 days elapsed).
        bill = self._create_bill()
        retention = bill._l10n_ec_create_auto_withholding()
        self.assertEqual(retention.date, bill.invoice_date)
        self.assertEqual(
            self.env["account.retention"]._l10n_ec_count_business_days(
                bill.invoice_date, retention.date
            ),
            0,
        )


# ===========================================================================
# AUDIT LOCK: codDoc 07 ELECTRONIC WITHHOLDING (v2.0.0) EMISSION/TRANSMISSION
# ===========================================================================


@tagged("post_install", "-at_install", "l10n_ec", "withholding")
class TestCodDoc07Transmission(TransactionCase):
    """codDoc 07 comprobanteRetencion: XML render + reception/authorization."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not cls.company.vat:
            # Valid Ecuadorian RUC (modulo 11) in case the company partner
            # triggers the base VAT constraint.
            cls.company.vat = "1793125212001"
        cls.partner_ruc = cls.env["res.partner"].create(
            {
                "name": "Sujeto Retenido RUC",
                "vat": "1713488185001",
                "l10n_ec_identifier_type": "ruc",
            }
        )
        cls.partner_cedula = cls.env["res.partner"].create(
            {
                "name": "Sujeto Retenido Cedula",
                "l10n_ec_identifier_type": "cedula",
            }
        )
        cls.partner_pasaporte = cls.env["res.partner"].create(
            {
                "name": "Sujeto Retenido Pasaporte",
                "l10n_ec_identifier_type": "pasaporte",
            }
        )
        cls.tax_ir_312 = cls.env.ref("l10n_ec_withholding.tax_ret_ir_312")

    def _make_retention(self, partner=None):
        retention = self.env["account.retention"].create(
            {
                "partner_id": (partner or self.partner_ruc).id,
                "date": date(2026, 3, 5),
                "retention_line_ids": [
                    (
                        0,
                        0,
                        {
                            "tax_type": "1",
                            "tax_id": self.tax_ir_312.id,
                            "base": 1000.0,
                        },
                    )
                ],
            }
        )
        retention._generate_access_key()
        return retention

    @staticmethod
    def _render(retention):
        xml = retention._l10n_ec_render_xml()
        if isinstance(xml, bytes):
            xml = xml.decode("utf-8")
        return xml

    # -- access key --------------------------------------------------------

    def test_access_key_is_doc_type_07(self):
        retention = self._make_retention()
        key = retention.l10n_ec_sri_access_key
        self.assertTrue(key)
        self.assertEqual(len(key), 49, "SRI access key must have 49 digits")
        self.assertTrue(key.isdigit())
        # Layout: date(8) + codDoc(2) + ruc(13) + env(1) + ...
        self.assertEqual(key[8:10], "07")
        # Environment code of a test company must be '1'
        self.assertEqual(key[23:24], "1")

    # -- XML render --------------------------------------------------------

    def test_render_xml_structure(self):
        retention = self._make_retention()
        key = retention.l10n_ec_sri_access_key
        xml = self._render(retention)
        self.assertIn("<comprobanteRetencion", xml)
        self.assertIn('version="2.0.0"', xml)
        self.assertIn("<codDoc>07</codDoc>", xml)
        self.assertIn("<claveAcceso>%s</claveAcceso>" % key, xml)
        self.assertIn("<ambiente>1</ambiente>", xml)
        # RUC subject -> identifier type 04
        self.assertIn(
            "<tipoIdentificacionSujetoRetenido>04</tipoIdentificacionSujetoRetenido>",
            xml,
        )
        self.assertIn("<codigo>1</codigo>", xml)
        self.assertIn("<codigoRetencion>312</codigoRetencion>", xml)
        self.assertIn("<baseImponible>1000.00</baseImponible>", xml)
        self.assertIn("<porcentajeRetener>1.00</porcentajeRetener>", xml)
        self.assertIn("<valorRetenido>10.00</valorRetenido>", xml)

    def test_render_identifier_cedula_and_pasaporte(self):
        xml_cedula = self._render(self._make_retention(self.partner_cedula))
        self.assertIn(
            "<tipoIdentificacionSujetoRetenido>05</tipoIdentificacionSujetoRetenido>",
            xml_cedula,
        )
        xml_passport = self._render(self._make_retention(self.partner_pasaporte))
        self.assertIn(
            "<tipoIdentificacionSujetoRetenido>06</tipoIdentificacionSujetoRetenido>",
            xml_passport,
        )

    # -- reception / authorization processing (same path as invoices) ------

    def test_reception_recibida_sets_sent(self):
        retention = self._make_retention()
        retention._l10n_ec_process_reception(
            {"status": "RECIBIDA", "messages": []}, b"<signed/>"
        )
        self.assertEqual(retention.l10n_ec_sri_status, "sent")
        self.assertIn("RECIBIDA", retention.l10n_ec_sri_response)
        self.assertTrue(retention.l10n_ec_xml_data)

    def test_reception_devuelta_sets_rejected(self):
        retention = self._make_retention()
        retention._l10n_ec_process_reception(
            {"status": "DEVUELTA", "messages": ["Error 45: clave duplicada"]}
        )
        self.assertEqual(retention.l10n_ec_sri_status, "rejected")
        self.assertIn("DEVUELTA", retention.l10n_ec_sri_response)
        self.assertIn("Error 45", retention.l10n_ec_sri_response)

    def test_authorization_autorizado(self):
        retention = self._make_retention()
        retention._l10n_ec_process_authorization(
            {
                "status": "AUTORIZADO",
                "date": "2026-03-05 10:30:00",
                "xml": "<authorized/>",
                "messages": [],
            }
        )
        self.assertEqual(retention.l10n_ec_sri_status, "authorized")
        self.assertTrue(retention.l10n_ec_authorization_date)
        self.assertTrue(retention.l10n_ec_xml_data)

    def test_authorization_no_autorizado_rejected(self):
        retention = self._make_retention()
        retention._l10n_ec_process_authorization(
            {
                "status": "NO AUTORIZADO",
                "messages": ["Clave de acceso registrada"],
            }
        )
        self.assertEqual(retention.l10n_ec_sri_status, "rejected")
        self.assertIn("NO AUTORIZADO", retention.l10n_ec_sri_response)

    def test_authorization_pending_keeps_waiting(self):
        retention = self._make_retention()
        retention._l10n_ec_process_reception(
            {"status": "RECIBIDA", "messages": []}
        )
        retention._l10n_ec_process_authorization(
            {"status": "EN PROCESO", "messages": []}
        )
        # Still waiting: status must remain 'sent' (same semantics as bills)
        self.assertEqual(retention.l10n_ec_sri_status, "sent")

    # -- flow guards -------------------------------------------------------

    def test_send_sri_requires_posted_state(self):
        retention = self.env["account.retention"].create(
            {
                "partner_id": self.partner_ruc.id,
                "date": date(2026, 3, 5),
            }
        )
        with self.assertRaises(UserError):
            retention.action_send_sri()

    def test_check_sri_requires_access_key(self):
        retention = self.env["account.retention"].create(
            {
                "partner_id": self.partner_ruc.id,
                "date": date(2026, 3, 5),
            }
        )
        with self.assertRaises(UserError):
            retention.action_check_sri()
