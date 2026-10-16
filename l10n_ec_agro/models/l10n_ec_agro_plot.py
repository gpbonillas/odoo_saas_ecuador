# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Predio / cultivo (plot). Fr-AG-02 (junto a ciclo)."""
from odoo import fields, models


class L10nEcAgroPlot(models.Model):
    _name = "l10n_ec.agro.plot"
    _description = "Predio agroalimentario"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True)
    code = fields.Char(string="Código")
    hectares = fields.Float(string="Hectáreas", digits=(10, 2))
    location = fields.Char(string="Ubicación", help="Dirección/descripción del predio.")
    responsible_id = fields.Many2one(
        "res.users", string="Responsable", default=lambda self: self.env.user
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)
    cycle_ids = fields.One2many("l10n_ec.agro.cycle", "plot_id", string="Ciclos")
