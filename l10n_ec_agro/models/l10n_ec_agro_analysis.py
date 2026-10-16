# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Análisis de laboratorio por lote — FR-AG-01/FR-AG-03.

Analito **genérico** (humedad, THC, CBD, residuos…): los valores de
sustancia viven SOLO como filas de análisis, jamás como columnas del lote
(D-05). El gate de laboratorio (FR-AG-03) usa `passed = False`.
`limit = 0.0` significa "sin límite documentado" (el wiring con el parámetro
vertical `v.analisis_limites` llega en fase P2).
"""
from odoo import api, fields, models


class L10nEcAgroAnalysis(models.Model):
    _name = "l10n_ec.agro.analysis"
    _description = "Análisis de laboratorio por lote"
    _order = "analysis_date desc, id desc"
    _check_company_auto = True

    lot_id = fields.Many2one(
        "stock.lot", string="Lote", required=True, ondelete="cascade", index=True
    )
    product_id = fields.Many2one(related="lot_id.product_id", store=True, index=True)
    analyte = fields.Char(string="Analito", required=True, index=True)
    value = fields.Float(string="Valor", required=True)
    unit = fields.Char(string="Unidad", help="%, mg/kg, ppm…")
    limit = fields.Float(string="Límite legal/configurado", help="0.0 = sin límite documentado.")
    passed = fields.Boolean(
        string="Conforme",
        compute="_compute_passed",
        store=True,
        help="False cuando el valor excede el límite: bloquea la salida del lote (FR-AG-03).",
    )
    lab_name = fields.Char(string="Laboratorio")
    certificate = fields.Binary(string="Certificado", attachment=True)
    analysis_date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(related="lot_id.company_id", store=True, index=True)
    display_name = fields.Char(compute="_compute_display_name")

    @api.depends("value", "limit")
    def _compute_passed(self):
        for analysis in self:
            analysis.passed = not analysis.limit or analysis.value <= analysis.limit

    @api.depends("lot_id", "analyte", "analysis_date")
    def _compute_display_name(self):
        for analysis in self:
            analysis.display_name = "%s · %s · %s" % (
                analysis.lot_id.display_name,
                analysis.analyte,
                analysis.analysis_date or "",
            )
