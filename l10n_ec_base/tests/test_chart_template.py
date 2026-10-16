# -*- coding: utf-8 -*-
"""
Test Odoo de carga del plan de cuentas NEC (l10n_ec_base).

Valida en base real que el template 'ec' se puede instalar en una empresa y
que las cuentas/grupos/impuestos oficiales quedan creados con códigos punteados.
"""
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestEcChartTemplate(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.ChartTemplate = cls.env["account.chart.template"]
        # Odoo 18 auto-instala `generic_coa` con el módulo account; el plan
        # NEC sólo se carga si la empresa no lo tiene YA.
        if cls.company.chart_template != "ec":
            cls.ChartTemplate.sudo().try_loading("ec", cls.company)

    def _account(self, code):
        return self.env["account.account"].sudo().search(
            [("code", "=", code)], limit=1
        )

    def test_chart_loaded(self):
        self.assertTrue(
            self.company.chart_template,
            "El template 'ec' no quedó registrado en la empresa",
        )

    def test_required_accounts_exist(self):
        for code in (
            "1.01.01.01", "1.01.01.02", "1.01.04.01", "1.01.04.02",
            "1.01.04.03", "2.01.04", "2.01.05", "2.01.06.01", "2.01.06.02",
            "2.01.06.03", "2.01.07.01", "2.01.07.02", "2.01.07.03",
            "2.01.08", "4.01.01", "4.01.02", "4.01.03", "4.01.04",
            "6.01.01.01",
        ):
            account = self._account(code)
            self.assertTrue(account, f"Cuenta NEC oficial no creada: {code}")

    def test_six_groups_loaded(self):
        groups = self.env["account.group"].sudo().search(
            [("code_prefix_start", "in", list("123456"))]
        )
        prefixes = set(groups.mapped("code_prefix_start"))
        for digit in "123456":
            self.assertIn(digit, prefixes, f"Grupo NEC clase {digit} no creado")

    def test_property_accounts_point_to_nec(self):
        receivable = self.company.partner_id.property_account_receivable_id
        payable = self.company.partner_id.property_account_payable_id
        self.assertEqual(receivable.code, "1.01.02.02")
        self.assertEqual(payable.code, "2.01.01.02")

    def test_taxes_loaded_with_groups(self):
        tax = self.env["account.tax"].sudo().search(
            [("name", "=", "IVA 15% (Ventas)"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        self.assertTrue(tax, "Impuesto IVA 15% (Ventas) no creado")
        self.assertEqual(tax.tax_group_id.name, "IVA 15%")
        # la repartition de impuesto apunta a 2.01.04 IVA por Pagar
        tax_line = tax.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
        )
        self.assertEqual(tax_line.account_id.code, "2.01.04")

    def test_unaffected_earnings_account(self):
        account = self.company.get_unaffected_earnings_account()
        self.assertTrue(account, "No existe cuenta equity_unaffected (3.01.03.01)")
        self.assertEqual(account.code, "3.01.03.01")
