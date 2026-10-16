# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Ciclo de cultivo — FR-AG-02 (ciclos por predio con fechas y estado).

El cultivo y la variedad viven aquí (y en el lote) como datos genéricos:
nunca columnas específicas de especie (D-05).
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nEcAgroCycle(models.Model):
    _name = "l10n_ec.agro.cycle"
    _description = "Ciclo de cultivo"
    _order = "sow_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Referencia")
    display_name = fields.Char(compute="_compute_display_name", store=True)
    plot_id = fields.Many2one(
        "l10n_ec.agro.plot", string="Predio", required=True, ondelete="cascade", index=True
    )
    crop_id = fields.Many2one(
        "l10n_ec.agro.crop", string="Cultivo", required=True, ondelete="restrict", index=True
    )
    variety = fields.Char(string="Variedad")
    sow_date = fields.Date(string="Fecha de siembra")
    expected_harvest_date = fields.Date(string="Cosecha esperada")
    actual_harvest_date = fields.Date(string="Cosecha real")
    state = fields.Selection(
        [
            ("planned", "Planificado"),
            ("growing", "En cultivo"),
            ("harvested", "Cosechado"),
            ("closed", "Cerrado"),
        ],
        string="Estado",
        default="planned",
        required=True,
    )
    lot_ids = fields.One2many("stock.lot", "l10n_ec_cycle_id", string="Lotes")
    company_id = fields.Many2one(
        related="plot_id.company_id", store=True, index=True
    )

    @api.depends("plot_id", "crop_id", "sow_date", "name")
    def _compute_display_name(self):
        for cycle in self:
            parts = [cycle.plot_id.display_name, cycle.crop_id.display_name]
            if cycle.sow_date:
                parts.append(cycle.sow_date.isoformat())
            cycle.display_name = " / ".join(p for p in parts if p) or cycle.name or "/"

    @api.constrains("sow_date", "expected_harvest_date")
    def _check_expected_after_sow(self):
        for cycle in self:
            if cycle.sow_date and cycle.expected_harvest_date and cycle.expected_harvest_date < cycle.sow_date:
                raise ValidationError(_("La cosecha esperada no puede ser anterior a la siembra."))

    @api.constrains("sow_date", "actual_harvest_date")
    def _check_actual_after_sow(self):
        for cycle in self:
            if cycle.sow_date and cycle.actual_harvest_date and cycle.actual_harvest_date < cycle.sow_date:
                raise ValidationError(_("La cosecha real no puede ser anterior a la siembra."))

    def action_growing(self):
        self.write({"state": "growing"})

    def action_harvested(self):
        self.write({"state": "harvested"})

    def action_closed(self):
        self.write({"state": "closed"})
