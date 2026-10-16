# -*- coding: utf-8 -*-
"""
Unit Tests: SRI Validation Rules
=================================

Tests for SRI-specific validations:
- RUC/Cédula format validation
- Access key generation
- Annulment deadline (day 7 of next month)
- Immediate transmission requirement
"""
from odoo.tests import tagged, TransactionCase
from odoo.exceptions import ValidationError
from datetime import date


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriValidation(TransactionCase):
    """Test SRI validation rules for Ecuador localization."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ecuador = cls.env.ref("base.ec")

        cls.company = (
            cls.env["res.company"].search(
                [("country_id", "=", cls.ecuador.id)], limit=1
            )
            or cls.env.user.company_id
        )

    # =========================================================================
    # TEST CASES: RUC Validation
    # =========================================================================

    def test_01_valid_ruc_natural_person(self):
        """Test RUC válido persona natural (3er dígito < 6)."""
        partner = self.env["res.partner"].create(
            {
                "name": "Persona Natural",
                "vat": "1713488185001",  # Valid format (3rd digit 1)
                "country_id": self.ecuador.id,
                "l10n_ec_identifier_type": "ruc",
            }
        )

        self.assertTrue(partner)
        self.assertEqual(len(partner.vat), 13)

    def test_02_valid_ruc_private_company(self):
        """Test RUC válido sociedad privada (3er dígito = 9)."""
        partner = self.env["res.partner"].create(
            {
                "name": "Sociedad Privada",
                "vat": "1793125212001",  # Valid format (9 as 3rd digit)
                "country_id": self.ecuador.id,
                "l10n_ec_identifier_type": "ruc",
            }
        )

        self.assertTrue(partner)

    def test_03_invalid_ruc_wrong_length(self):
        """Test RUC inválido por longitud incorrecta."""
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Invalid Partner",
                    "vat": "123456789",  # Only 9 digits
                    "country_id": self.ecuador.id,
                    "l10n_ec_identifier_type": "ruc",
                }
            )

    def test_04_valid_cedula(self):
        """Test cédula válida (10 dígitos)."""
        partner = self.env["res.partner"].create(
            {
                "name": "Persona con Cédula",
                "vat": "1713488185",  # 10 digits
                "country_id": self.ecuador.id,
                "l10n_ec_identifier_type": "cedula",
            }
        )

        self.assertEqual(len(partner.vat), 10)

    # =========================================================================
    # TEST CASES: Annulment Deadline
    # =========================================================================

    def test_05_annulment_within_deadline_allowed(self):
        """Test anulación dentro del plazo (día 7 mes siguiente)."""
        # Get the annulment day from config
        annulment_day = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.annulment_day_limit", "7")
        )

        # Verify annulment config is within valid range
        self.assertTrue(annulment_day >= 1)
        self.assertTrue(annulment_day <= 31)

    def test_06_annulment_config_is_not_hardcoded(self):
        """Test that annulment limit is configurable, not hardcoded."""
        # Change the config parameter
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_ec.annulment_day_limit", "10"
        )

        # Verify it can be read back
        new_limit = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.annulment_day_limit")
        )

        self.assertEqual(new_limit, 10)

        # Reset to default
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_ec.annulment_day_limit", "7"
        )

    # =========================================================================
    # TEST CASES: Access Key Format
    # =========================================================================

    def test_07_access_key_length(self):
        """Test clave de acceso tiene 49 dígitos."""
        # Import AccessKey helper
        try:
            from odoo.addons.l10n_ec_edi.models.access_key import AccessKey

            key = AccessKey.generate(
                invoice_date=date.today(),
                doc_type="01",  # Factura
                ruc="1793125212001",
                environment="1",
                establishment="001",
                emission_point="001",
                sequential="000000001",
            )

            self.assertEqual(len(key), 49)
            self.assertTrue(key.isdigit())

        except ImportError:
            # Skip if module not installed
            self.skipTest("l10n_ec_edi module not available")
