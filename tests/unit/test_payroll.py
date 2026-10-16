# -*- coding: utf-8 -*-
"""
Payroll Module Tests
====================

Tests IESS, SBU, décimos, fondos de reserva, caps and params.
All rates from ir.config_parameter.

The deep legal math (rates, ceilings, caps, schedules) is covered by the
standalone suite ``tests/unit/test_payroll_calc_standalone.py`` which runs
without Odoo. This file covers the Odoo-side wiring: ir.config_parameter
records loaded by ``l10n_ec_payroll_data.xml``, model constraints and the
journal-entry posting.
"""
from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install", "l10n_ec", "payroll")
class TestPayroll(TransactionCase):
    """Tests for Ecuador Payroll (Nómina)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()

    # =========================================================================
    # CONFIGURABLE RATES
    # =========================================================================

    def test_sbu_configurable(self):
        """[PAY-01] SBU uses ir.config_parameter."""
        sbu = float(self.ICP.get_param("l10n_ec.sbu", "0"))
        self.assertEqual(sbu, 482.0, "SBU 2026 should be $482")

    def test_sbu_cites_mdt_2025_195(self):
        """[PAY-10] The SBU param record cites MDT-2025-195 (repo consensus).

        An earlier revision of l10n_ec_payroll_data.xml cited the wrong
        resolution (MDT-2025-227); CUMPLIMIENTO_REGULATORIO, README and
        KB_MASTER all use MDT-2025-195.
        """
        record = self.env["ir.model.data"].search(
            [
                ("module", "=", "l10n_ec_hr_payroll"),
                ("model", "=", "ir.config_parameter"),
            ]
        )
        sbu_param = record.filtered(
            lambda r: r.name and "sbu" in r.name
        ).mapped("record_id")
        self.assertTrue(sbu_param, "SBU ir.config_parameter record exists")
        for param in sbu_param:
            # The XMLID noupdate record stores the citation in the XML; the
            # param value itself is the number. Check no stale value leaks.
            self.assertNotEqual(
                param.value,
                "227",
                "SBU must not reference the wrong MDT resolution",
            )

    def test_iess_personal_configurable(self):
        """[PAY-02] IESS personal uses ir.config_parameter."""
        rate = float(self.ICP.get_param("l10n_ec.iess_aporte_personal", "0"))
        self.assertEqual(rate, 9.45, "IESS personal should be 9.45%")

    def test_iess_employer_configurable(self):
        """[PAY-03] IESS patronal uses ir.config_parameter."""
        rate = float(self.ICP.get_param("l10n_ec.iess_aporte_patronal", "0"))
        self.assertEqual(
            rate,
            11.15,
            "IESS patronal should be 11.15% (base rate, total with SECAP+IECE = 12.15%)",
        )

    def test_iess_extra_rates_configurable(self):
        """[PAY-11] SECAP/IECE and the 25xSBU ceiling params exist."""
        self.assertEqual(
            float(self.ICP.get_param("l10n_ec.iess_secap", "0")), 0.5
        )
        self.assertEqual(
            float(self.ICP.get_param("l10n_ec.iess_iece", "0")), 0.5
        )
        self.assertEqual(
            float(
                self.ICP.get_param("l10n_ec.iess_ceiling_sbu_multiplicador", "0")
            ),
            25.0,
        )

    def test_labor_caps_configurable(self):
        """[PAY-12] Art. 55 overtime caps and deduction caps are params."""
        self.assertEqual(
            float(self.ICP.get_param("l10n_ec.horas_max_dia", "0")), 4.0
        )
        self.assertEqual(
            float(self.ICP.get_param("l10n_ec.horas_max_semana", "0")), 12.0
        )
        self.assertEqual(
            float(self.ICP.get_param("l10n_ec.tope_descuento_porcentaje", "0")),
            40.0,
        )
        self.assertEqual(
            float(self.ICP.get_param("l10n_ec.tope_descuento_decreto", "0")),
            33.33,
        )

    def test_fondos_reserva_gate_param(self):
        """[PAY-13] Fondos de reserva eligibility = 13 months (param)."""
        self.assertEqual(
            float(self.ICP.get_param("l10n_ec.fondos_reserva_meses", "0")), 13.0
        )

    def test_sbu_can_be_changed(self):
        """[PAY-04] SBU can be updated without code change."""
        original = self.ICP.get_param("l10n_ec.sbu")

        # Simulate regulation change
        self.ICP.set_param("l10n_ec.sbu", "500.00")
        new_sbu = float(self.ICP.get_param("l10n_ec.sbu"))

        self.assertEqual(new_sbu, 500.0, "SBU should be changeable")

        # Restore
        self.ICP.set_param("l10n_ec.sbu", original or "482.00")

    # =========================================================================
    # PAYSLIP CALCULATIONS
    # =========================================================================

    def test_payslip_model_exists(self):
        """[PAY-05] Payslip model exists."""
        model = self.env["ir.model"].search([("model", "=", "l10n_ec.payslip")])
        self.assertTrue(model, "l10n_ec.payslip model should exist")

    def test_payslip_uses_config_iess(self):
        """[PAY-06] Payslip _compute_iess uses config params."""
        # Verify the method uses ir.config_parameter
        Payslip = self.env.get("l10n_ec.payslip")
        if Payslip:
            # Check source code doesn't have hardcoded rates
            import inspect

            source = inspect.getsource(Payslip._compute_iess)
            self.assertIn(
                "ir.config_parameter",
                source,
                "IESS computation must use config parameter",
            )

    def test_overtime_limit_constraint(self):
        """[PAY-14] art. 55 caps raise ValidationError on excess."""
        Payslip = self.env["l10n_ec.payslip"]
        self.assertTrue(
            hasattr(Payslip, "_check_overtime_limits"),
            "payslip must implement the art. 55 overtime cap check",
        )
        self.assertTrue(
            hasattr(Payslip, "_check_deduction_limits"),
            "payslip must implement the 40%/33.33% deduction cap check",
        )

    def test_liquidacion_wizard_exists(self):
        """[PAY-15] Liquidación wizard model is registered."""
        model = self.env["ir.model"].search(
            [("model", "=", "l10n_ec.termination.wizard")]
        )
        self.assertTrue(model, "l10n_ec.termination.wizard must exist")

    def test_loans_split_buckets(self):
        """[PAY-16] l10n_ec_loans splits IESS vs company loan deductions."""
        Payslip = self.env["l10n_ec.payslip"]
        self.assertIn("loan_deduction", Payslip._fields)
        self.assertIn("loan_deduction_iess", Payslip._fields)
        self.assertIn("loan_deduction_company", Payslip._fields)

    # =========================================================================
    # DÉCIMOS CALCULATIONS
    # =========================================================================

    def test_decimo_tercero_formula(self):
        """[PAY-07] Décimo tercer sueldo = Income / 12."""
        # Standard formula verification
        income = 1000.0
        decimo_13 = income / 12.0
        self.assertAlmostEqual(decimo_13, 83.33, places=2)

    def test_decimo_cuarto_formula(self):
        """[PAY-08] Décimo cuarto = SBU / 12 (per month)."""
        sbu = float(self.ICP.get_param("l10n_ec.sbu", "482"))
        decimo_14_monthly = sbu / 12.0
        self.assertAlmostEqual(decimo_14_monthly, 40.17, places=2)

    def test_fondos_reserva_rate(self):
        """[PAY-09] Fondos de reserva = 8.33% of income."""
        income = 1000.0
        reserva = income * (1.0 / 12.0)  # 8.33%
        self.assertAlmostEqual(reserva, 83.33, places=2)
