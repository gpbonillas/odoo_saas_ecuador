# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-14 — guardrail de registro sanitario en ventas.

Verificación: SRS-VERT §6.2 FR-AG-14 + §8 · CHG-2026-011.
Producto regulado sin `v.registro_sanitario` ⇒ bloquea la confirmación;
con el parámetro ⇒ pasa; producto NO regulado ⇒ nunca interviene.
"""
from odoo.exceptions import UserError
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestAgroSanitaryGuardrail(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Param = cls.env["l10n_ec.vertical.param"]
        cls.partner = cls.env["res.partner"].create({"name": "Cliente AGRO"})
        cls.product_regulated = cls.env["product.product"].create({
            "name": "CBD Flores",
            "type": "consu",
            "l10n_ec_regulated": True,
        })
        cls.product_free = cls.env["product.product"].create({
            "name": "Café pergamino",
            "type": "consu",
        })

    def _order(self, product):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1})],
        })

    def test_blocks_regulated_sale_without_registry(self):
        order = self._order(self.product_regulated)
        with self.assertRaises(UserError) as ctx:
            order.action_confirm()
        self.assertIn("registro sanitario", str(ctx.exception).lower())
        self.assertNotEqual(order.state, "sale")

    def test_passes_with_registry_configured(self):
        self.Param.set_value("v.registro_sanitario", "REG-EC-001", value_type="text",
                             source="USER")
        order = self._order(self.product_regulated)
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_unregulated_sale_unaffected(self):
        order = self._order(self.product_free)
        order.action_confirm()
        self.assertEqual(order.state, "sale")
