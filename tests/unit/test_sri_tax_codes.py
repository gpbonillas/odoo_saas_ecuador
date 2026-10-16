# -*- coding: utf-8 -*-
"""
Unit Tests: SRI tax code resolution (codigo / codigoPorcentaje)
===============================================================

Requires the Odoo test runtime (TransactionCase), e.g.:
    docker compose run --rm odoo odoo -d test \\
        --test-tags /l10n_ec_edi --stop-after-init

Regression for Sprint 1 P0 #1: codigoPorcentaje must come from the SRI
catalogs (Table 16/17) and NOT from the Odoo tax amount. IVA 15% is
codigoPorcentaje "4", IVA 5% is "5", No Objeto is "6", Exento is "7".
"""
from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install", "l10n_ec")
class TestSriTaxCodes(TransactionCase):
    """_get_sri_tax_codes / _compute_tax_aggregates mapping tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.edi_format = cls.env["account.edi.format"]

        def _tax(name, amount):
            return cls.env["account.tax"].create(
                {
                    "name": name,
                    "amount": amount,
                    "amount_type": "percent",
                    "type_tax_use": "sale",
                }
            )

        cls.tax_iva_15 = _tax("IVA 15%", 15.0)
        cls.tax_iva_5 = _tax("IVA 5% Construcción", 5.0)
        cls.tax_iva_0 = _tax("IVA 0%", 0.0)
        cls.tax_no_objeto = _tax("IVA No Objeto", 0.0)
        cls.tax_exento = _tax("IVA Exento", 0.0)
        cls.tax_ice = _tax("ICE Cigarrillos", 10.0)
        cls.tax_iva_12 = _tax("IVA 12%", 12.0)
        cls.tax_weird = _tax("IVA Raro 33%", 33.0)

    def test_iva_15_maps_to_codigo_porcentaje_4(self):
        """IVA 15% must be codigoPorcentaje '4', never '15'."""
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_iva_15), ("2", "4")
        )

    def test_iva_5_maps_to_codigo_porcentaje_5(self):
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_iva_5), ("2", "5")
        )

    def test_iva_0_maps_to_codigo_porcentaje_0(self):
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_iva_0), ("2", "0")
        )

    def test_no_objeto_maps_to_codigo_porcentaje_6(self):
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_no_objeto), ("2", "6")
        )

    def test_exento_maps_to_codigo_porcentaje_7(self):
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_exento), ("2", "7")
        )

    def test_ice_keeps_legacy_catalog_code(self):
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_ice), ("3", "3023")
        )

    def test_iva_12_uses_rate_fallback(self):
        # No 12% record in the seeded catalog: the rate fallback must
        # return the SRI code "2" (not "12").
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_iva_12), ("2", "2")
        )

    def test_unknown_rate_falls_back_to_zero(self):
        # 33% is not an SRI rate: fail safe to 0% instead of emitting 33.
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_weird), ("2", "0")
        )

    def test_explicit_catalog_link_wins(self):
        # A manual tax -> l10n_ec.tax.code link takes priority.
        catalog = self.env["l10n_ec.tax.code"].search(
            [("code", "=", "4"), ("tax_type", "=", "iva")], limit=1
        )
        if not catalog:
            self.skipTest("l10n_ec.tax.code catalog not loaded")
        catalog.tax_id = self.tax_iva_12
        self.assertEqual(
            self.edi_format._get_sri_tax_codes(self.tax_iva_12), ("2", "4")
        )


@tagged("post_install", "-at_install", "l10n_ec")
class TestSriTaxAggregates(TransactionCase):
    """Aggregation + untaxed fallbacks used by the totalImpuesto blocks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "country_id": cls.env.ref("base.ec").id,
                "vat": "1790017045001",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Aggregates",
                "vat": "1312345679",
                "country_id": cls.env.ref("base.ec").id,
                "l10n_ec_identifier_type": "cedula",
            }
        )
        cls.tax_iva_15 = cls.env["account.tax"].create(
            {
                "name": "IVA 15%",
                "amount": 15.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )
        cls.account_income = cls.env["account.account"].search(
            [
                ("company_id", "=", cls.company.id),
                ("account_type", "=", "income"),
            ],
            limit=1,
        )
        if not cls.account_income:
            cls.account_income = cls.env["account.account"].create(
                {
                    "name": "Test Income Agg",
                    "code": "TINCAGG",
                    "account_type": "income",
                    "company_id": cls.company.id,
                }
            )
        cls.journal = cls.env["account.journal"].search(
            [
                ("type", "=", "sale"),
                ("company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        if not cls.journal:
            cls.journal = cls.env["account.journal"].create(
                {
                    "name": "Test Sales Agg",
                    "code": "TAGG",
                    "type": "sale",
                    "company_id": cls.company.id,
                }
            )

    def _invoice(self, taxed):
        taxes = [(6, 0, [self.tax_iva_15.id])] if taxed else []
        return (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "invoice_date": "2026-10-15",
                    "journal_id": self.journal.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Producto",
                                "quantity": 1,
                                "price_unit": 100.0,
                                "account_id": self.account_income.id,
                                "tax_ids": taxes,
                            },
                        )
                    ],
                }
            )
        )

    def test_taxed_invoice_aggregates_codigo_porcentaje_4(self):
        invoice = self._invoice(taxed=True)
        aggregates = self.env["account.edi.format"]._compute_tax_aggregates(invoice)
        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0]["codigo"], "2")
        self.assertEqual(aggregates[0]["codigo_porcentaje"], "4")
        self.assertAlmostEqual(aggregates[0]["base"], 100.0, places=2)
        self.assertAlmostEqual(aggregates[0]["amount"], 15.0, places=2)

    def test_untaxed_invoice_gets_zero_rated_fallback(self):
        # SRI XSDs require >= 1 <totalImpuesto>: untaxed documents must
        # declare IVA 0% over the full untaxed base.
        invoice = self._invoice(taxed=False)
        aggregates = self.env["account.edi.format"]._compute_tax_aggregates(invoice)
        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0]["codigo"], "2")
        self.assertEqual(aggregates[0]["codigo_porcentaje"], "0")
        self.assertAlmostEqual(aggregates[0]["base"], 100.0, places=2)
        self.assertAlmostEqual(aggregates[0]["amount"], 0.0, places=2)

    def test_untaxed_line_gets_detail_level_fallback(self):
        invoice = self._invoice(taxed=False)
        line_taxes = self.env["account.edi.format"]._get_l10n_ec_line_taxes(invoice)
        line = invoice.invoice_line_ids.filtered(lambda l: not l.display_type)
        self.assertEqual(len(line_taxes[line.id]), 1)
        self.assertEqual(line_taxes[line.id][0]["codigo_porcentaje"], "0")

    def test_tax_map_populated_with_sri_codes(self):
        invoice = self._invoice(taxed=True)
        values = self.env["account.edi.format"]._get_l10n_ec_edi_values(invoice)
        self.assertEqual(
            values["tax_map"].get(self.tax_iva_15.id), "4"
        )  # was always '' before the fix
