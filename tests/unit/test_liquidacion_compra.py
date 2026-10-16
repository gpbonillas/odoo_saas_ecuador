# -*- coding: utf-8 -*-
"""
Unit Tests: codDoc 03 (Liquidación de Compra) + codDoc 04/05 rendering
======================================================================

Requires the Odoo test runtime (TransactionCase), e.g.:
    docker compose run --rm odoo odoo -d test \\
        --test-tags /l10n_ec_edi --stop-after-init

Covers Sprint 1 P0 #3 (missing codDoc 03 implementation):
* detection: vendors NOT obligated to keep accounting get codDoc 03,
  obligated contributors keep codDoc 01
* XML rendering of LiquidacionCompra 1.1.0 (PROVEEDOR fields, codDoc 03)
* XML rendering of NotaCredito 1.1.0 with the modified-document block
* nota de débito template availability (SRI schema is 1.0.0, not 1.1.0)
"""
from datetime import date

from lxml import etree
from odoo.tests import tagged, TransactionCase

# Vats validated against l10n_ec_base's _validate_ec_document:
CEDULA = "1713488185"  # natural person (cédula) -> NOT obligated
RUC_NATURAL = "1713488185001"  # natural-person RUC (3rd digit 1) -> NOT obligated
RUC_COMPANY = "1793125212001"  # private-company RUC (3rd digit 9) -> obligated
COMPANY_RUC = "1793125212001"


@tagged("post_install", "-at_install", "l10n_ec")
class TestLiquidacionDeCompra(TransactionCase):
    """Document-type detection + XML rendering for codDoc 03/04/05."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ec = cls.env.ref("base.ec")
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test LC Company",
                "country_id": cls.ec.id,
                "currency_id": cls.env.ref("base.USD").id,
                "vat": COMPANY_RUC,
            }
        )
        cls.account_expense = cls.env["account.account"].create(
            {
                "name": "Test Expense EC",
                "code": "TEXPEC",
                "account_type": "expense",
                "company_id": cls.company.id,
            }
        )
        cls.account_income = cls.env["account.account"].create(
            {
                "name": "Test Income EC",
                "code": "TINEC2",
                "account_type": "income",
                "company_id": cls.company.id,
            }
        )
        cls.journal_purchase = cls.env["account.journal"].create(
            {
                "name": "Test Purchases EC",
                "code": "TPUEC",
                "type": "purchase",
                "company_id": cls.company.id,
            }
        )
        cls.journal_sale = cls.env["account.journal"].create(
            {
                "name": "Test Sales EC",
                "code": "TSUEC",
                "type": "sale",
                "company_id": cls.company.id,
            }
        )
        cls.tax_iva_15 = cls.env["account.tax"].create(
            {
                "name": "IVA 15%",
                "amount": 15.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
            }
        )

        def _partner(name, vat, id_type):
            return cls.env["res.partner"].create(
                {
                    "name": name,
                    "vat": vat,
                    "country_id": cls.ec.id,
                    "l10n_ec_identifier_type": id_type,
                }
            )

        cls.partner_person = _partner("Persona Cédula", CEDULA, "cedula")
        cls.partner_natural_ruc = _partner("Persona RUC", RUC_NATURAL, "ruc")
        cls.partner_company = _partner("Empresa RUC", RUC_COMPANY, "ruc")

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def test_forced_accounting_detection(self):
        self.assertFalse(self.partner_person._l10n_ec_is_forced_to_keep_accounting())
        self.assertFalse(
            self.partner_natural_ruc._l10n_ec_is_forced_to_keep_accounting()
        )
        self.assertTrue(self.partner_company._l10n_ec_is_forced_to_keep_accounting())

    def test_special_taxpayer_is_always_forced(self):
        self.partner_person.l10n_ec_taxpayer_type = "special"
        self.assertTrue(self.partner_person._l10n_ec_is_forced_to_keep_accounting())

    # ------------------------------------------------------------------
    # Document type selection
    # ------------------------------------------------------------------

    def _bill(self, partner):
        return (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "in_invoice",
                    "partner_id": partner.id,
                    "invoice_date": date(2026, 10, 15),
                    "journal_id": self.journal_purchase.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Servicio de prueba",
                                "quantity": 1,
                                "price_unit": 50.0,
                                "account_id": self.account_expense.id,
                            },
                        )
                    ],
                }
            )
        )

    def test_bill_for_person_selects_coddoc_03(self):
        bill = self._bill(self.partner_person)
        self.assertEqual(bill.l10n_latam_document_type_id.code, "03")

    def test_bill_for_natural_person_ruc_selects_coddoc_03(self):
        bill = self._bill(self.partner_natural_ruc)
        self.assertEqual(bill.l10n_latam_document_type_id.code, "03")

    def test_bill_for_company_selects_coddoc_01(self):
        bill = self._bill(self.partner_company)
        self.assertEqual(bill.l10n_latam_document_type_id.code, "01")

    def test_bill_for_special_taxpayer_selects_coddoc_01(self):
        self.partner_person.l10n_ec_taxpayer_type = "special"
        bill = self._bill(self.partner_person)
        self.assertEqual(bill.l10n_latam_document_type_id.code, "01")

    # ------------------------------------------------------------------
    # XML rendering
    # ------------------------------------------------------------------

    def _render(self, move):
        move._generate_access_key()
        xml_str = self.env["account.edi.format"]._export_l10n_ec_edi(move)
        return etree.fromstring(xml_str.encode("utf-8"))

    def test_liquidacion_compra_xml_structure(self):
        bill = self._bill(self.partner_person)
        self.assertEqual(bill.l10n_latam_document_type_id.code, "03")

        root = self._render(bill)
        self.assertEqual(root.tag, "liquidacionCompra")
        self.assertEqual(root.get("version"), "1.1.0")
        self.assertEqual(root.findtext("infoTributaria/codDoc"), "03")
        self.assertEqual(len(root.findtext("infoTributaria/claveAcceso")), 49)

        info = root.find("infoLiquidacionCompra")
        self.assertIsNotNone(info, "infoLiquidacionCompra missing")
        # LC declares PROVEEDOR (vendor) fields, not COMPRADOR
        self.assertIsNone(info.find("tipoIdentificacionComprador"))
        self.assertEqual(
            info.findtext("identificacionProveedor"), self.partner_person.vat
        )
        self.assertEqual(
            info.findtext("tipoIdentificacionProveedor"), "05"  # cédula
        )
        # totalDescuento is required in LC 1.1.0
        self.assertIsNotNone(info.find("totalDescuento"))
        self.assertIsNotNone(info.find("importeTotal"))

        # >= 1 totalImpuesto and >= 1 impuesto per detalle (XSD minOccurs=1)
        self.assertTrue(info.findall("totalConImpuestos/totalImpuesto"))
        detalle = root.find("detalles/detalle")
        self.assertIsNotNone(detalle)
        impuestos = detalle.findall("impuestos/impuesto")
        self.assertTrue(impuestos)
        for impuesto in impuestos:
            self.assertEqual(impuesto.findtext("codigo"), "2")

    def test_factura_xml_uses_sri_codigo_porcentaje(self):
        invoice = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner_company.id,
                    "invoice_date": date(2026, 10, 15),
                    "journal_id": self.journal_sale.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Producto",
                                "quantity": 1,
                                "price_unit": 100.0,
                                "account_id": self.account_income.id,
                                "tax_ids": [(6, 0, [self.tax_iva_15.id])],
                            },
                        )
                    ],
                }
            )
        )
        root = self._render(invoice)
        self.assertEqual(root.tag, "factura")
        self.assertEqual(root.findtext("infoTributaria/codDoc"), "01")

        total = root.find("infoFactura/totalConImpuestos/totalImpuesto")
        self.assertEqual(total.findtext("codigo"), "2")
        self.assertEqual(
            total.findtext("codigoPorcentaje"), "4"  # IVA 15% -> SRI code "4"
        )

        detalle_impuesto = root.find("detalles/detalle/impuestos/impuesto")
        self.assertEqual(detalle_impuesto.findtext("codigo"), "2")
        self.assertEqual(detalle_impuesto.findtext("codigoPorcentaje"), "4")

    def test_nota_credito_xml_structure(self):
        refund = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "out_refund",
                    "partner_id": self.partner_company.id,
                    "invoice_date": date(2026, 10, 15),
                    "narration": "Devolución de mercancía defectuosa",
                    "journal_id": self.journal_sale.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Producto devuelto",
                                "quantity": 1,
                                "price_unit": 30.0,
                                "account_id": self.account_income.id,
                            },
                        )
                    ],
                }
            )
        )
        self.assertEqual(refund.l10n_latam_document_type_id.code, "04")

        root = self._render(refund)
        self.assertEqual(root.tag, "notaCredito")
        self.assertEqual(root.get("version"), "1.1.0")
        self.assertEqual(root.findtext("infoTributaria/codDoc"), "04")

        info = root.find("infoNotaCredito")
        self.assertIsNotNone(info)
        # Fallbacks when the NC has no reversed_entry_id yet
        self.assertEqual(info.findtext("codDocModificado"), "01")
        self.assertEqual(info.findtext("numDocModificado"), "001-001-000000000")
        self.assertEqual(
            info.findtext("motivo"), "Devolución de mercancía defectuosa"
        )
        self.assertTrue(info.find("detalles/detalle"))

    def test_nota_debito_template_available(self):
        # ND is version 1.0.0 (the only schema published by the SRI).
        template = self.env.ref("l10n_ec_edi.l10n_ec_edi_nota_debito")
        self.assertTrue(template)
