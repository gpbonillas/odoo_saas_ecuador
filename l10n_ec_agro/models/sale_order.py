# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-14 — guardrail: venta de producto regulado sin registro sanitario.

Verificación: SRS-VERT §6.2 FR-AG-14 + §8 (`v.registro_sanitario`) ·
CHG-2026-011. El parámetro vive en el store `l10n_ec.vertical.param`
(wizard `USER`); leerlo aquí NO duplica lógica (una sola fuente, DES-01).
"""
from odoo import models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        Param = self.env["l10n_ec.vertical.param"]
        for order in self:
            regulated = order.order_line.filtered(
                lambda line: line.product_id.l10n_ec_regulated)
            if regulated and not Param.get_value("v.registro_sanitario"):
                raise UserError(
                    "Producto regulado sin registro sanitario: '%s'. "
                    "Configure el parámetro v.registro_sanitario (wizard/ajustes "
                    "agro) antes de confirmar esta venta. — FR-AG-14."
                    % regulated[0].product_id.display_name)
        return super().action_confirm()
