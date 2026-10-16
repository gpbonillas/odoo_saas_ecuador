# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-05 — eventos de trazabilidad append-only (inmutabilidad AUD).

Verificación: SRS-VERT §6.2 (FR-AG-05) · CHG-2026-008.
"""
from odoo.exceptions import UserError
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestAgroEventsImmutable(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {"name": "Cacao en baba", "type": "consu", "is_storable": True, "tracking": "lot"}
        )
        cls.lot = cls.env["stock.lot"].create(
            {
                "name": "LOTE-CACAO-001",
                "product_id": cls.product.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.event = cls.env["l10n_ec.agro.trace_event"].create(
            {
                "lot_id": cls.lot.id,
                "stage": "harvest",
                "qty": 250.0,
                "comprobante": "2201202601179312521200120010010000000011",
            }
        )

    def test_event_created_with_stage_and_date(self):
        self.assertEqual(self.event.stage, "harvest")
        self.assertTrue(self.event.event_date)
        stages = dict(
            self.env["l10n_ec.agro.trace_event"]._fields["stage"]._description_selection(self.env)
        )
        self.assertIn("Cosecha", stages[self.event.stage])

    def test_write_is_blocked(self):
        with self.assertRaises(UserError):
            self.event.write({"qty": 999.0})

    def test_unlink_is_blocked(self):
        with self.assertRaises(UserError):
            self.event.unlink()
