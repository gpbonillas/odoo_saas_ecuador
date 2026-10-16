# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-01 — el lote porta atributos agro genéricos; sustancias SOLO en análisis.

Verificación: SRS-VERT §6.2 (FR-AG-01) · CHG-2026-008.
"""
from odoo import fields
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestAgroLotFields(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.crop_cafe = cls.env["l10n_ec.agro.crop"].create({"name": "Café", "code": "CAFE"})
        cls.crop_cacao = cls.env["l10n_ec.agro.crop"].create({"name": "Cacao", "code": "CACAO"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto agro de prueba",
                "type": "consu",
                "is_storable": True,
                "tracking": "lot",
            }
        )
        cls.lot = cls.env["stock.lot"].create(
            {
                "name": "LOTE-AGRO-001",
                "product_id": cls.product.id,
                "company_id": cls.env.company.id,
                "l10n_ec_crop_type": cls.crop_cafe.id,
                "l10n_ec_variety": "Typica",
                "l10n_ec_harvest_date": fields.Date.today(),
                "l10n_ec_sanitary_reg": "REG-SAN-001",
            }
        )

    def test_lot_stores_agro_fields(self):
        """El lote conserva cultivo, variedad, cosecha y registro sanitario."""
        self.assertEqual(self.lot.l10n_ec_crop_type, self.crop_cafe)
        self.assertEqual(self.lot.l10n_ec_variety, "Typica")
        self.assertEqual(self.lot.l10n_ec_harvest_date, fields.Date.today())
        self.assertEqual(self.lot.l10n_ec_sanitary_reg, "REG-SAN-001")
        self.assertEqual(self.lot.l10n_ec_lab_state, "none")

    def test_new_crop_is_catalog_row_only(self):
        """D-05: un nuevo cultivo = fila de catálogo, cero cambio de esquema."""
        lot2 = self.env["stock.lot"].create(
            {
                "name": "LOTE-AGRO-002",
                "product_id": self.product.id,
                "company_id": self.env.company.id,
                "l10n_ec_crop_type": self.crop_cacao.id,
            }
        )
        self.assertEqual(lot2.l10n_ec_crop_type.code, "CACAO")
        self.assertEqual(lot2.l10n_ec_crop_type.display_name, "[CACAO] Cacao")

    def test_no_crop_specific_columns(self):
        """D-05: ninguna columna por especie en stock.lot; sustancias sólo en análisis."""
        lot_fields = self.env["stock.lot"]._fields
        for forbidden in ("l10n_ec_thc", "l10n_ec_cbd", "l10n_ec_humidity"):
            self.assertNotIn(forbidden, lot_fields)

        analysis = self.env["l10n_ec.agro.analysis"].create(
            {
                "lot_id": self.lot.id,
                "analyte": "THC",
                "value": 0.5,
                "unit": "%",
                "limit": 1.0,
                "lab_name": "LAB-PRUEBA",
            }
        )
        self.assertTrue(analysis.passed)
        self.assertEqual(self.lot.l10n_ec_lab_state, "passed")

    def test_lab_state_derived_from_analyses(self):
        """El estado de laboratorio se deriva: failed si algún análisis no conforme."""
        self.env["l10n_ec.agro.analysis"].create(
            {"lot_id": self.lot.id, "analyte": "Humedad", "value": 18.0, "limit": 12.0, "unit": "%"}
        )
        self.assertEqual(self.lot.l10n_ec_lab_state, "failed")
