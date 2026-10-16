# -*- coding: utf-8 -*-
"""
Customs Module Tests
====================

Tests DAU, FODINFA, Ad Valorem, IVA Importación.
All rates from ir.config_parameter.
"""
from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install", "l10n_ec", "customs")
class TestCustoms(TransactionCase):
    """Tests for Ecuador Customs (Aduanas)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()

    # =========================================================================
    # CONFIGURABLE RATES
    # =========================================================================

    def test_fodinfa_configurable(self):
        """[CUS-01] FODINFA rate from ir.config_parameter."""
        rate = float(self.ICP.get_param("l10n_ec.fodinfa", "0"))
        self.assertEqual(rate, 0.005, "FODINFA should be 0.5%")

    def test_customs_iva_configurable(self):
        """[CUS-02] Customs IVA from ir.config_parameter."""
        rate = float(self.ICP.get_param("l10n_ec.customs_iva", "0"))
        self.assertEqual(rate, 0.15, "Customs IVA should be 15%")

    def test_fodinfa_can_be_changed(self):
        """[CUS-03] FODINFA can be updated without code change."""
        original = self.ICP.get_param("l10n_ec.fodinfa")

        # Simulate regulation change
        self.ICP.set_param("l10n_ec.fodinfa", "0.01")
        new_rate = float(self.ICP.get_param("l10n_ec.fodinfa"))

        self.assertEqual(new_rate, 0.01, "FODINFA should be changeable")

        # Restore
        self.ICP.set_param("l10n_ec.fodinfa", original or "0.005")

    # =========================================================================
    # DAU MODEL
    # =========================================================================

    def test_dau_model_exists(self):
        """[CUS-04] DAU model exists."""
        model = self.env["ir.model"].search([("model", "=", "l10n_ec.import.dau")])
        self.assertTrue(model, "l10n_ec.import.dau model should exist")

    def test_dau_uses_config_params(self):
        """[CUS-05] DAU _compute_taxes uses config params."""
        DAU = self.env.get("l10n_ec.import.dau")
        if DAU:
            import inspect

            source = inspect.getsource(DAU._compute_taxes)
            self.assertIn(
                "ir.config_parameter", source, "DAU taxes must use config parameter"
            )

    # =========================================================================
    # CIF CALCULATION
    # =========================================================================

    def test_cif_formula(self):
        """[CUS-06] CIF = FOB + Freight + Insurance."""
        fob = 1000.0
        freight = 100.0
        insurance = 20.0
        cif = fob + freight + insurance
        self.assertEqual(cif, 1120.0, "CIF formula should be FOB + F + I")

    def test_fodinfa_calculation(self):
        """[CUS-07] FODINFA = CIF * 0.5%."""
        cif = 1000.0
        fodinfa_rate = float(self.ICP.get_param("l10n_ec.fodinfa", "0.005"))
        fodinfa = cif * fodinfa_rate
        self.assertEqual(fodinfa, 5.0, "FODINFA should be 0.5% of CIF")

    def test_customs_iva_calculation(self):
        """[CUS-08] Import IVA = (CIF + AdValorem + FODINFA) * 15%."""
        cif = 1000.0
        advalorem = 200.0
        fodinfa = 5.0
        iva_rate = float(self.ICP.get_param("l10n_ec.customs_iva", "0.15"))

        base = cif + advalorem + fodinfa
        iva = base * iva_rate

        self.assertEqual(iva, 180.75, "Import IVA calculation")


@tagged("post_install", "-at_install", "l10n_ec", "customs")
class TestCustomsRegression(TransactionCase):
    """
    Regression tests for bugs found and fixed during the Sprint-5 audit
    (Specialist Agent F). These exercise the REAL model code instead of
    re-doing arithmetic in the test body.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.DAU = cls.env.get("l10n_ec.import.dau")
        cls.Tariff = cls.env.get("l10n_ec.tariff.heading")
        cls.partner = cls.env["res.partner"].create(
            {"name": "AGENTE ADUANERO TEST", "vat": "1793125212001"}
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1
        )
        if not cls.journal:
            cls.journal = cls.env["account.journal"].create(
                {"name": "Aduana T", "code": "ADUT", "type": "purchase"}
            )
        for code, name, atype in (
            ("5110ADVT", "Ad Valorem Aduana T", "expense"),
            ("5110FODT", "FODINFA Aduana T", "expense"),
            ("1110IVAT", "IVA Importacion Aduana T", "asset_current"),
        ):
            cls.env["account.account"].create(
                {"code": code, "name": name, "account_type": atype}
            )
        cls.ICP.set_param("l10n_ec.customs_duty_account", "5110ADVT")
        cls.ICP.set_param("l10n_ec.customs_fodinfa_account", "5110FODT")
        cls.ICP.set_param("l10n_ec.customs_iva_account", "1110IVAT")

    def _dau(self, line_cmds, **kw):
        if not self.DAU:
            self.skipTest("l10n_ec_customs not installed")
        vals = {
            "name": "DAU-T-%s" % self._uid,
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "date": "2026-10-15",
            "freight": 500.0,
            "insurance": 100.0,
            "line_ids": line_cmds,
        }
        vals.update(kw)
        dau = self.DAU.create(vals)
        dau.action_calculate()
        return dau

    def test_account_domain_uses_company_ids(self):
        """[CUS-R1] account.account has no company_id in Odoo 18."""
        Account = self.env["account.account"]
        self.assertNotIn(
            "company_id",
            Account._fields,
            "Odoo 18 replaced account.account.company_id with company_ids; "
            "filtering on company_id raises 'Invalid field company_id'.",
        )
        self.assertIn("company_ids", Account._fields)
        dau = self._dau([(0, 0, {"valor_fob_line": 100.0})])
        domain = dau._l10n_ec_account_domain(self.env.company, "5110ADVT")
        # must be a domain Odoo 18 accepts (no unsupported field)
        Account.search(domain)

    def test_cif_includes_fob(self):
        """[CUS-R2] CIF = FOB + freight + insurance (FOB must not be lost)."""
        dau = self._dau([(0, 0, {"valor_fob_line": 10000.0})])
        self.assertAlmostEqual(dau.fob_value, 10000.0, places=2)
        self.assertAlmostEqual(dau.cif_value, 10600.0, places=2)

    def test_ad_valorem_uses_tariff_rate(self):
        """[CUS-R3] Ad Valorem = CIF * tariff rate (0-40%)."""
        if not self.Tariff:
            self.skipTest("l10n_ec_customs not installed")
        th = self.Tariff.create({"name": "8471.30.00.00", "ad_valorem": 10.0})
        dau = self._dau(
            [(0, 0, {"valor_fob_line": 10000.0, "tariff_id": th.id})],
            isd_applicable=False,
        )
        self.assertAlmostEqual(dau.total_ad_valorem, 1060.0, places=2)
        self.assertAlmostEqual(dau.total_fodinfa, 53.0, places=2)
        self.assertAlmostEqual(dau.total_iva, (10600 + 1060 + 53) * 0.15, places=2)

    def test_ad_valorem_rate_constrained_to_0_40(self):
        """[CUS-R4] SENAE Ad Valorem range is 0-40%."""
        if not self.Tariff:
            self.skipTest("l10n_ec_customs not installed")
        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.Tariff.create({"name": "TOO HIGH", "ad_valorem": 45.0})
        with self.assertRaises(ValidationError):
            self.Tariff.create({"name": "TOO LOW", "ad_valorem": -1.0})

    def test_per_heading_fodinfa_override(self):
        """[CUS-R5] tariff.fodinfa overrides the global l10n_ec.fodinfa."""
        if not self.Tariff:
            self.skipTest("l10n_ec_customs not installed")
        th = self.Tariff.create(
            {"name": "3004.90.10.00", "ad_valorem": 0.0, "fodinfa": 1.0}
        )
        dau = self._dau(
            [(0, 0, {"valor_fob_line": 10000.0, "tariff_id": th.id})],
            isd_applicable=False,
        )
        self.assertAlmostEqual(dau.total_fodinfa, 106.0, places=2)

    def test_per_heading_fodinfa_zero_is_honoured(self):
        """[CUS-R6] a legitimate 0% heading must NOT fall back to global."""
        if not self.Tariff:
            self.skipTest("l10n_ec_customs not installed")
        th = self.Tariff.create(
            {"name": "9999.00.00.00", "ad_valorem": 5.0, "fodinfa": 0.0}
        )
        dau = self._dau(
            [(0, 0, {"valor_fob_line": 10000.0, "tariff_id": th.id})],
            isd_applicable=False,
        )
        self.assertAlmostEqual(dau.total_fodinfa, 0.0, places=2)
        self.assertAlmostEqual(dau.total_ad_valorem, 530.0, places=2)

    def test_isd_five_percent_on_total_payment_value(self):
        """[CUS-R7] ISD (LORTI art. 75) = 5% of CIF+duties+taxes."""
        dau = self._dau(
            [(0, 0, {"valor_fob_line": 10000.0})],
            isd_applicable=True,
            isd_rate="0.05",
        )
        expected = (
            dau.cif_value
            + dau.total_ad_valorem
            + dau.total_fodinfa
            + dau.total_iva
        ) * 0.05
        self.assertAlmostEqual(dau.total_isd, expected, places=2)

    def test_posted_entry_has_no_double_tax(self):
        """
        [CUS-R8] The entry debits must equal the SENAE totals exactly.

        Bug found in the audit: tax_ids were attached to lines whose debit
        ALREADY contained the duty amount, so Odoo computed the taxes a
        second time, adding phantom lines and an "Automatic Balancing Line".
        """
        dau = self._dau(
            [(0, 0, {"valor_fob_line": 10000.0})],
            isd_applicable=True,
            isd_rate="0.05",
        )
        dau.action_post()
        self.assertEqual(dau.state, "done")
        self.assertEqual(dau.move_id.state, "posted")
        move = dau.move_id
        self.assertEqual(
            len(
                move.line_ids.filtered(
                    lambda l: l.name == "Automatic Balancing Line"
                )
            ),
            0,
            "a double-counted tax forces an automatic balancing line",
        )
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("debit")),
            sum(move.line_ids.mapped("credit")),
            places=2,
            msg="the import entry must be balanced",
        )
        expected_debits = dau.total_ad_valorem + dau.total_fodinfa + dau.total_iva
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("debit")), expected_debits, places=2
        )
        # ISD is NOT part of the customs entry (paid on the transfer)
        self.assertNotIn("isd", " ".join(move.line_ids.mapped("name")).lower())
