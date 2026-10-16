# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Libro de Socios - share / quota register required by the mercantile code
(actas societarias bookkeeping).  Kept intentionally lean: one row per
share/quota emission or transfer, printed as a register report.
"""

from odoo import api, fields, models, _


class L10nEcPartnerShare(models.Model):
    _name = "l10n_ec.partner.share"
    _description = "Libro de Socios - Registro de Acciones / Cuotas"
    _order = "date, id"
    _inherit = ["mail.thread"]

    name = fields.Char(
        string="Numero",
        default="/",
        readonly=True,
        copy=False,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True
    )
    partner_id = fields.Many2one(
        "res.partner", string="Socio / Accionista", required=True,
        tracking=True,
    )
    share_type = fields.Selection(
        [
            ("accion", "Accion"),
            ("cuota", "Cuota social"),
            ("otro", "Otro titulo"),
        ],
        required=True,
        default="cuota",
    )
    share_count = fields.Float(string="Numero de titulos", default=1.0)
    nominal_value = fields.Monetary(
        string="Valor nominal", currency_field="currency_id", default=0.0
    )
    total_value = fields.Monetary(
        string="Valor total",
        compute="_compute_total_value",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", string="Moneda"
    )
    operation = fields.Selection(
        [
            ("emision", "Emision / Suscripcion"),
            ("transferencia", "Transferencia"),
            ("amortizacion", "Amortizacion / Repurchase"),
        ],
        default="emision",
        required=True,
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("posted", "Registrado")],
        default="draft",
        required=True,
        tracking=True,
    )
    notes = fields.Text("Observaciones")

    @api.depends("share_count", "nominal_value")
    def _compute_total_value(self):
        for record in self:
            record.total_value = record.share_count * record.nominal_value

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") in ("/", False):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "l10n_ec.partner.share"
                    )
                    or "SOC/%s" % fields.Date.context_today(self)
                )
        return super().create(vals_list)

    def action_post(self):
        self.write({"state": "posted"})

    def action_draft(self):
        self.write({"state": "draft"})
