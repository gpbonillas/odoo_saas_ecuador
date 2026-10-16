# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Evento de trazabilidad append-only — FR-AG-05 (inmutabilidad AUD).

Auditoría de la traza seed-to-sale (SRS-VERT §5, etapas A–I). Una vez
creado el evento NO puede modificarse ni eliminarse (ni siquiera por
superusuario vía ORM; el ACL también lo prohíbe). La corrección de un
evento se hace agregando un evento nuevo (estilo AUD/ATS del SRI).
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nEcAgroTraceEvent(models.Model):
    _name = "l10n_ec.agro.trace_event"
    _description = "Evento de trazabilidad (append-only)"
    _order = "event_date desc, id desc"
    _rec_name = "display_name"
    _check_company_auto = True

    STAGES = [
        ("inputs", "A · Compra de insumos"),
        ("cultivation", "B · Cultivo"),
        ("harvest", "C · Cosecha"),
        ("processing", "D · Procesamiento"),
        ("analysis", "E · Análisis de laboratorio"),
        ("storage", "F · Almacenamiento"),
        ("sale", "G · Venta"),
        ("delivery", "H · Entrega"),
        ("recall", "I · Retiro (recall)"),
    ]

    lot_id = fields.Many2one(
        "stock.lot", string="Lote", required=True, ondelete="restrict", index=True
    )
    stage = fields.Selection(STAGES, string="Etapa", required=True, index=True)
    qty = fields.Float(string="Cantidad")
    partner_id = fields.Many2one("res.partner", string="Tercero")
    comprobante = fields.Char(
        string="Comprobante", help="Clave de acceso / referencia del comprobante SRI."
    )
    event_date = fields.Datetime(string="Fecha/hora", required=True, default=fields.Datetime.now)
    company_id = fields.Many2one(
        related="lot_id.company_id", store=True, index=True
    )
    display_name = fields.Char(compute="_compute_display_name")

    @api.depends("lot_id", "stage", "event_date")
    def _compute_display_name(self):
        stages = dict(self._fields["stage"]._description_selection(self.env))
        for event in self:
            event.display_name = "%s · %s · %s" % (
                event.lot_id.display_name,
                stages.get(event.stage, event.stage),
                event.event_date,
            )

    def write(self, vals):
        raise UserError(_("Los eventos de trazabilidad son inmutables (FR-AG-05); cree un evento nuevo."))

    def unlink(self):
        raise UserError(_("Los eventos de trazabilidad no pueden eliminarse (FR-AG-05)."))
