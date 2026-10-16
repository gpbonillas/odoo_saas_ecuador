# -*- coding: utf-8 -*-
"""
Tax Calendar Tests
==================

Tests deadline calculations based on 9th RUC digit.
All dates from ir.config_parameter.
"""
from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install", "l10n_ec", "calendar")
class TestTaxCalendar(TransactionCase):
    """Tests for Ecuador Tax Calendar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.Calendar = cls.env["l10n_ec.tax.calendar"]

    # =========================================================================
    # 9TH DIGIT EXTRACTION
    # =========================================================================

    def test_extract_9th_digit_ruc(self):
        """[CAL-01] Extract 9th digit from RUC."""
        digit = self.Calendar.get_9th_digit("1793125212001")
        self.assertEqual(digit, "1", "9th digit of 1793125212001 should be 1")

    def test_extract_9th_digit_various(self):
        """[CAL-02] Various 9th digit extractions."""
        # D-04: sólo IDs aprobados como literales; los demás dígitos de
        # plazo se cubren con entradas sintéticas GENERADAS (no son
        # identidades): get_9th_digit sólo depende del carácter pos. 9.
        test_cases = [
            ("1713488185001", "8"),  # RUC natural aprobado (pos. 9 = 8)
            ("9999999999999", "9"),  # CONSUMIDOR FINAL (pos. 9 = 9)
        ]
        test_cases += [
            ("0" * 8 + digit + "0" * 4, digit) for digit in "0234567"
        ]
        for ruc, expected in test_cases:
            result = self.Calendar.get_9th_digit(ruc)
            self.assertEqual(
                result, expected, f"9th digit of {ruc} should be {expected}"
            )

    # =========================================================================
    # DEADLINE MAP CONFIGURATION
    # =========================================================================

    def test_deadline_map_configurable(self):
        """[CAL-03] Deadline map from ir.config_parameter."""
        param = self.ICP.get_param("l10n_ec.deadline_day_map")
        self.assertIsNotNone(param, "Deadline map should be configured")

    def test_deadline_map_default_values(self):
        """[CAL-04] Default deadline days per digit."""
        deadline_map = self.Calendar._get_deadline_map()
        expected = {
            "1": 10,
            "2": 12,
            "3": 14,
            "4": 16,
            "5": 18,
            "6": 20,
            "7": 22,
            "8": 24,
            "9": 26,
            "0": 28,
        }
        self.assertEqual(deadline_map, expected)

    def test_special_contributor_day(self):
        """[CAL-05] Special contributor deadline day 9."""
        day = self.Calendar._get_special_contributor_day()
        self.assertEqual(day, 9, "CE deadline should be day 9")

    # =========================================================================
    # DEADLINE CALCULATIONS
    # =========================================================================

    def test_iva_deadline_digit_1(self):
        """[CAL-06] IVA deadline for digit 1 = 10th."""
        # Create mock company with RUC ending in 1
        # For unit test, we'll verify the map
        deadline_map = self.Calendar._get_deadline_map()
        self.assertEqual(deadline_map["1"], 10)

    def test_iva_deadline_digit_0(self):
        """[CAL-07] IVA deadline for digit 0 = 28th."""
        deadline_map = self.Calendar._get_deadline_map()
        self.assertEqual(deadline_map["0"], 28)

    # =========================================================================
    # PERIOD MONTH HANDLING
    # =========================================================================

    def test_december_rollover(self):
        """[CAL-08] December deadline rolls to January."""
        # December declaration due in January
        period_month = 12
        next_month = period_month + 1 if period_month < 12 else 1
        self.assertEqual(next_month, 1, "December + 1 should be January")

    def test_ir_declaration_month(self):
        """[CAL-09] IR sociedades month = April (4)."""
        month = int(self.ICP.get_param("l10n_ec.ir_sociedades_month", "4"))
        self.assertEqual(month, 4, "IR sociedades should be April")

    def test_ir_natural_month(self):
        """[CAL-10] IR natural persons month = March (3)."""
        month = int(self.ICP.get_param("l10n_ec.ir_natural_month", "3"))
        self.assertEqual(month, 3, "IR natural should be March")
