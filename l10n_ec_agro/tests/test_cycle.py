# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-02 — ciclos por predio con fechas y estado.

Verificación: SRS-VERT §6.2 (FR-AG-02) · CHG-2026-008.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestAgroCycle(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.crop = cls.env["l10n_ec.agro.crop"].create({"name": "Plátano", "code": "PLAT"})
        cls.plot = cls.env["l10n_ec.agro.plot"].create(
            {"name": "Predio Norte", "hectares": 3.5, "location": "Pichincha"}
        )
        cls.today = fields.Date.today()
        cls.cycle = cls.env["l10n_ec.agro.cycle"].create(
            {
                "plot_id": cls.plot.id,
                "crop_id": cls.crop.id,
                "variety": "Dominico",
                "sow_date": cls.today,
                "expected_harvest_date": cls.today + timedelta(days=90),
            }
        )

    def test_cycle_defaults_and_state_flow(self):
        """Ciclo nace planificado y transita planned→growing→harvested→closed."""
        self.assertEqual(self.cycle.state, "planned")
        self.cycle.action_growing()
        self.assertEqual(self.cycle.state, "growing")
        self.cycle.action_harvested()
        self.assertEqual(self.cycle.state, "harvested")
        self.cycle.action_closed()
        self.assertEqual(self.cycle.state, "closed")

    def test_cycle_links_lots(self):
        """El lote apunta al ciclo y el ciclo lista sus lotes."""
        product = self.env["product.product"].create(
            {"name": "Plátano granel", "type": "consu", "is_storable": True, "tracking": "lot"}
        )
        lot = self.env["stock.lot"].create(
            {
                "name": "LOTE-PLAT-001",
                "product_id": product.id,
                "company_id": self.env.company.id,
                "l10n_ec_cycle_id": self.cycle.id,
            }
        )
        self.assertIn(lot, self.cycle.lot_ids)
        self.assertEqual(lot.l10n_ec_cycle_id, self.cycle)

    def test_expected_harvest_before_sow_raises(self):
        with self.assertRaises(ValidationError):
            self.cycle.write({"expected_harvest_date": self.today - timedelta(days=1)})

    def test_actual_harvest_before_sow_raises(self):
        with self.assertRaises(ValidationError):
            self.cycle.write({"actual_harvest_date": self.today - timedelta(days=1)})

    def test_actual_harvest_after_sow_ok(self):
        self.cycle.write({"actual_harvest_date": self.today + timedelta(days=88)})
        self.assertEqual(self.cycle.state, "planned")
