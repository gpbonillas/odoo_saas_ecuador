# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-03 — gate de laboratorio: lote con análisis NO conforme no sale
del stock interno; movimientos internos y lotes conformes/ sin análisis
sí pueden moverse.

Cobertura de los DOS puntos de gate:
* `_action_confirm` (flujo draft → confirm, con reserva en línea qty=0)
* `_action_done` (salida real; cubre movimientos que nacen 'assigned')

Verificación: SRS-VERT §6.2 (FR-AG-03) · CHG-2026-008.
"""
from odoo.exceptions import UserError
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestAgroLabGate(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wh = cls.env.ref("stock.warehouse0")
        cls.stock_loc = cls.wh.lot_stock_id
        cls.customers_loc = cls.env.ref("stock.stock_location_customers")
        cls.internal_loc = cls.env["stock.location"].create(
            {"name": "AGRO-INTERNO", "location_id": cls.stock_loc.id, "usage": "internal"}
        )
        Quant = cls.env["stock.quant"]

        def _lot_flow(name, analyte=None, value=None, limit=None):
            """Producto PROPIO con 1 lote en stock: aislamiento total por test
            (evita que la reserva automática de Odoo adjunte lotes ajenos)."""
            product = cls.env["product.product"].create(
                {"name": name, "type": "consu", "is_storable": True, "tracking": "lot"}
            )
            lot = cls.env["stock.lot"].create(
                {"name": name, "product_id": product.id, "company_id": cls.env.company.id}
            )
            if analyte:
                cls.env["l10n_ec.agro.analysis"].create(
                    {"lot_id": lot.id, "analyte": analyte, "value": value, "limit": limit, "unit": "%"}
                )
            Quant._update_available_quantity(product, cls.stock_loc, 10.0, lot_id=lot)
            return product, lot

        cls.product_bad, cls.lot_bad = _lot_flow("LOTE-BAD", "Humedad", 18.0, 12.0)
        cls.product_good, cls.lot_good = _lot_flow("LOTE-GOOD", "Humedad", 9.0, 12.0)
        cls.product_none, cls.lot_none = _lot_flow("LOTE-NONE")

    def _make_picking(self, product, lot, dest, picking_type=None, qty=1.0):
        line_vals = {
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "location_id": self.stock_loc.id,
            "location_dest_id": dest.id,
            "lot_id": lot.id,
        }
        if qty:
            # Cantidad explícita: la línea nace reservada (movimiento
            # 'assigned' — no pasa por _action_confirm; lo cubre _action_done).
            line_vals["quantity"] = qty
        return self.env["stock.picking"].create(
            {
                "picking_type_id": (picking_type or self.env.ref("stock.picking_type_out")).id,
                "location_id": self.stock_loc.id,
                "location_dest_id": dest.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": product.display_name,
                            "product_id": product.id,
                            "product_uom_qty": 1.0,
                            "product_uom": product.uom_id.id,
                            "location_id": self.stock_loc.id,
                            "location_dest_id": dest.id,
                            "move_line_ids": [(0, 0, line_vals)],
                        },
                    )
                ],
            }
        )

    def test_failing_lot_is_blocked_on_outgoing_validate(self):
        """Salida con lote reprobado: bloqueada en _action_done (backstop)."""
        self.assertEqual(self.lot_bad.l10n_ec_lab_state, "failed")
        picking = self._make_picking(self.product_bad, self.lot_bad, self.customers_loc)
        self.assertEqual(picking.move_ids.state, "assigned")  # nace reservado
        with self.assertRaises(UserError):
            picking.button_validate()
        self.assertNotEqual(picking.state, "done")

    def test_failing_lot_is_blocked_at_confirm_when_reserved(self):
        """Salida draft (línea sin cantidad): la reserva adjunta el lote
        disponible y _action_confirm lo bloquea antes de reservar."""
        picking = self._make_picking(
            self.product_bad, self.lot_bad, self.customers_loc, qty=0.0
        )
        self.assertEqual(picking.move_ids.state, "draft")
        with self.assertRaises(UserError):
            picking.action_confirm()

    def test_passing_lot_validates(self):
        self.assertEqual(self.lot_good.l10n_ec_lab_state, "passed")
        picking = self._make_picking(self.product_good, self.lot_good, self.customers_loc)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_lot_without_analysis_validates(self):
        self.assertEqual(self.lot_none.l10n_ec_lab_state, "none")
        picking = self._make_picking(self.product_none, self.lot_none, self.customers_loc)
        picking.button_validate()
        self.assertEqual(picking.state, "done")

    def test_internal_transfer_of_failing_lot_allowed(self):
        """El gate bloquea SALIDAS; los traspasos internos no."""
        picking = self._make_picking(
            self.product_bad, self.lot_bad, self.internal_loc, picking_type=self.wh.int_type_id
        )
        picking.button_validate()
        self.assertEqual(picking.state, "done")
