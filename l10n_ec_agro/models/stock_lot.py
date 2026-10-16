# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Extensión de `stock.lot` con atributos agro genéricos — FR-AG-01.

Crop-agnóstico (D-05): ningún campo específico de especie. Sustancias
(THC/CBD/humedad…) viven SOLO en `l10n_ec.agro.analysis`. El estado de
laboratorio se deriva de los análisis (passed).
"""
from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    l10n_ec_crop_type = fields.Many2one(
        "l10n_ec.agro.crop", string="Cultivo", ondelete="restrict", index=True
    )
    l10n_ec_variety = fields.Char(string="Variedad")
    l10n_ec_cycle_id = fields.Many2one(
        "l10n_ec.agro.cycle", string="Ciclo de cultivo", ondelete="restrict", index=True
    )
    l10n_ec_harvest_date = fields.Date(string="Fecha de cosecha")
    l10n_ec_lab_state = fields.Selection(
        [
            ("none", "Sin análisis"),
            ("passed", "Aprobado"),
            ("failed", "Reprobado"),
        ],
        string="Estado de laboratorio",
        compute="_compute_l10n_ec_lab_state",
        store=True,
        help="Derivado de l10n_ec.agro.analysis: 'failed' si algún análisis no es conforme.",
    )
    l10n_ec_sanitary_reg = fields.Char(string="Registro sanitario")
    l10n_ec_analysis_ids = fields.One2many(
        "l10n_ec.agro.analysis", "lot_id", string="Análisis de laboratorio"
    )

    @api.depends("l10n_ec_analysis_ids.passed")
    def _compute_l10n_ec_lab_state(self):
        for lot in self:
            if not lot.l10n_ec_analysis_ids:
                lot.l10n_ec_lab_state = "none"
            elif all(lot.l10n_ec_analysis_ids.mapped("passed")):
                lot.l10n_ec_lab_state = "passed"
            else:
                lot.l10n_ec_lab_state = "failed"

    @api.onchange("l10n_ec_cycle_id")
    def _onchange_l10n_ec_cycle_id(self):
        """Arrastra cultivo y variedad del ciclo seleccionado (si los tiene)."""
        if self.l10n_ec_cycle_id:
            self.l10n_ec_crop_type = self.l10n_ec_cycle_id.crop_id
            if self.l10n_ec_cycle_id.variety and not self.l10n_ec_variety:
                self.l10n_ec_variety = self.l10n_ec_cycle_id.variety
