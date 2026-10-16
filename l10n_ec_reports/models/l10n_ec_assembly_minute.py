# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Libro de Actas - register of assemblies / board minutes (juntas generales,
asambleas, directorio).  Lean model: date, type, attendees, agreements.
"""

from odoo import api, fields, models, _


class L10nEcAssemblyMinute(models.Model):
    _name = "l10n_ec.assembly.minute"
    _description = "Libro de Actas - Juntas y Asambleas"
    _order = "date desc, id"
    _inherit = ["mail.thread"]

    name = fields.Char(
        string="Acta No.",
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
    assembly_type = fields.Selection(
        [
            ("junta_general", "Junta General de Accionistas"),
            ("asamblea_general", "Asamblea General"),
            ("directorio", "Directorio / Consejo de Administracion"),
            ("comite", "Comite de Auditoria"),
            ("accionista_unico", "Accionista Unico"),
        ],
        required=True,
        default="junta_general",
    )
    place = fields.Char("Lugar")
    president = fields.Char("Presidente")
    secretary = fields.Char("Secretario")
    attendees = fields.Text(
        "Asistentes", help="One name per line (socios / directores)."
    )
    agreements = fields.Text(
        "Acuerdos y decisiones",
        help="Minute body: points discussed and agreed resolutions.",
    )
    document_count = fields.Integer(compute="_compute_document_count")
    state = fields.Selection(
        [("draft", "Borrador"), ("posted", "Aprobada")],
        default="draft",
        required=True,
        tracking=True,
    )

    def _compute_document_count(self):
        for record in self:
            record.document_count = 1 if record.agreements else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") in ("/", False):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "l10n_ec.assembly.minute"
                    )
                    or "ACTA/%s" % fields.Date.context_today(self)
                )
        return super().create(vals_list)

    def action_post(self):
        self.write({"state": "posted"})

    def action_draft(self):
        self.write({"state": "draft"})
