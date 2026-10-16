# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Extensión de producto para la vertical AGRO.

FR-AG-14: productos **regulados** (p.ej. línea CBD de CANNACHAIN, ARCSA) —
agnóstico de cultivo (D-05): el flag es genérico; qué producto es regulado lo
decide el tenant en su wizard/import, nunca el código.
"""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_ec_regulated = fields.Boolean(
        string="Producto regulado (registro sanitario)",
        help="FR-AG-14: la venta de este producto exige el parámetro "
             "v.registro_sanitario configurado (guardrail del wizard agro).",
    )
