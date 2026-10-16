# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Catálogo de cultivos — D-05 (crop-agnóstico).

Regla de diseño: el tipo de cultivo son **datos de catálogo**, nunca columnas
de esquema ni variantes de módulo. Agregar un nuevo cultivo (café, cacao,
plátano, cáñamo…) es una fila en este modelo: cero cambio de esquema.
Origen de datos previsto: parámetro vertical `v.cultivos` (SRS-VERT §8, fase P2).
"""
from odoo import api, fields, models


class L10nEcAgroCrop(models.Model):
    _name = "l10n_ec.agro.crop"
    _description = "Catálogo de cultivos (crop-agnóstico, D-05)"
    _order = "name"
    _check_company_auto = True

    name = fields.Char(string="Cultivo", required=True, translate=True, index=True)
    code = fields.Char(string="Código", size=32, help="Código corto estable (ej. CAFE, CACAO).")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código de cultivo debe ser único."),
    ]

    @api.depends("name", "code")
    def _compute_display_name(self):
        for crop in self:
            crop.display_name = "[%s] %s" % (crop.code, crop.name) if crop.code else crop.name
