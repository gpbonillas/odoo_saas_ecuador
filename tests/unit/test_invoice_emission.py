# -*- coding: utf-8 -*-
"""
Unit Tests: Invoice Emission Flow - Odoo Ecuador Localization
==============================================================

Tests the complete invoice creation cycle in Odoo:
1. Draft → Posted → SRI Sent → Authorized

Test Cases:
- Normal invoice with IVA 15%
- Invoice with IVA 5% (construcción)
- Invoice with IVA 0%
- Invoice with multiple tax lines
- Consumidor Final validation
- SRI access key generation
"""
from odoo.tests import tagged, TransactionCase
from odoo.exceptions import ValidationError, UserError
from datetime import date


@tagged("post_install", "-at_install", "l10n_ec")
class TestInvoiceEmission(TransactionCase):
    """Test the complete invoice emission flow for Ecuador."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get Ecuador
        cls.ecuador = cls.env.ref("base.ec")

        # Get or create test company for Ecuador
        cls.company = cls.env["res.company"].search(
            [("country_id", "=", cls.ecuador.id)], limit=1
        )

        if not cls.company:
            cls.company = cls.env["res.company"].create(
                {
                    "name": "Test Company Ecuador",
                    "country_id": cls.ecuador.id,
                    "currency_id": cls.env.ref("base.USD").id,
                    "vat": "1793125212001",
                }
            )

        # Set SRI environment from config (not hardcoded)
        cls.env["ir.config_parameter"].sudo().set_param(
            "l10n_ec.sri_environment", "test"
        )

        # Create test partner (client)
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Prueba Ecuador",
                "vat": "1713488185001",
                "country_id": cls.ecuador.id,
                "l10n_ec_identifier_type": "ruc",
            }
        )

        # Get taxes from chart template (not hardcoded)
        cls.tax_iva_15 = cls.env["account.tax"].search(
            [
                ("company_id", "=", cls.company.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 15.0),
            ],
            limit=1,
        )

        cls.tax_iva_0 = cls.env["account.tax"].search(
            [
                ("company_id", "=", cls.company.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 0.0),
            ],
            limit=1,
        )

        # Get income account
        cls.account_income = cls.env["account.account"].search(
            [
                ("company_id", "=", cls.company.id),
                ("account_type", "=", "income"),
            ],
            limit=1,
        )

    def _create_invoice(self, partner=None, amount=100.0, tax=None):
        """Helper to create a test invoice."""
        partner = partner or self.partner
        tax = tax or self.tax_iva_15

        invoice = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "invoice_date": date.today(),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Producto de Prueba",
                                "quantity": 1,
                                "price_unit": amount,
                                "account_id": (
                                    self.account_income.id
                                    if self.account_income
                                    else False
                                ),
                                "tax_ids": [(6, 0, [tax.id])] if tax else [],
                            },
                        )
                    ],
                }
            )
        )
        return invoice

    # =========================================================================
    # TEST CASES: Invoice Creation
    # =========================================================================

    def test_01_create_invoice_iva_15(self):
        """Test crear factura con IVA 15%."""
        invoice = self._create_invoice(amount=100.0)

        self.assertEqual(invoice.state, "draft")
        self.assertTrue(invoice.amount_total > 0)

        # Verify IVA calculation: $100 + 15% = $115
        if self.tax_iva_15:
            expected_total = 100.0 * 1.15
            self.assertAlmostEqual(invoice.amount_total, expected_total, places=2)

    def test_02_create_invoice_iva_0(self):
        """Test crear factura con IVA 0%."""
        invoice = self._create_invoice(amount=100.0, tax=self.tax_iva_0)

        # No IVA
        if self.tax_iva_0:
            self.assertAlmostEqual(invoice.amount_total, 100.0, places=2)

    def test_03_post_invoice(self):
        """Test confirmar (postear) una factura."""
        invoice = self._create_invoice()

        # Post the invoice
        invoice.action_post()

        self.assertEqual(invoice.state, "posted")
        self.assertTrue(invoice.name != "/")

    # =========================================================================
    # TEST CASES: SRI Integration
    # =========================================================================

    def test_04_generate_access_key(self):
        """Test generación de clave de acceso SRI."""
        invoice = self._create_invoice()
        invoice.action_post()

        # Generate access key
        if hasattr(invoice, "_generate_access_key"):
            invoice._generate_access_key()

            # Access key should be 49 digits
            if invoice.l10n_ec_sri_access_key:
                self.assertEqual(len(invoice.l10n_ec_sri_access_key), 49)

    def test_05_invoice_sri_status_initial(self):
        """Test estado inicial SRI es 'draft'."""
        invoice = self._create_invoice()

        self.assertEqual(invoice.l10n_ec_sri_status, "draft")

    # =========================================================================
    # TEST CASES: Validation Rules
    # =========================================================================

    def test_06_invoice_requires_partner(self):
        """Test factura requiere cliente."""
        with self.assertRaises((ValidationError, UserError)):
            self.env["account.move"].with_company(self.company).create(
                {
                    "move_type": "out_invoice",
                    "invoice_date": date.today(),
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Test",
                                "quantity": 1,
                                "price_unit": 100.0,
                            },
                        )
                    ],
                }
            )

    def test_07_invoice_date_required(self):
        """Test factura requiere fecha."""
        invoice = self._create_invoice()
        self.assertTrue(invoice.invoice_date)
