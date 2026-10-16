# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_ec_ir_retention_tax_id = fields.Many2one(
        "l10n_ec.withholding.tax",
        string="IR Withholding Code",
        domain="[('type', '=', 'renta')]",
        help="SRI income-tax withholding code applied to purchases of this "
             "product (Tabla 19). Leave empty to use the tariff table "
             "(RUC 4th digit / activity).",
    )
    l10n_ec_iva_retention_tax_id = fields.Many2one(
        "l10n_ec.withholding.tax",
        string="IVA Withholding Code",
        domain="[('type', '=', 'iva')]",
        help="SRI VAT withholding code applied to purchases of this product "
             "(Tabla 21). Leave empty to use the tariff table "
             "(RUC 4th digit / activity).",
    )
    l10n_ec_withholding_activity = fields.Selection(
        [
            ("goods", "Bienes (goods)"),
            ("services", "Servicios (services)"),
            ("professional", "Honorarios profesionales"),
            ("transport", "Transporte"),
            ("liquidacion", "Liquidación de compra"),
        ],
        string="Withholding Nature",
        compute="_compute_l10n_ec_withholding_activity",
        store=True,
        readonly=False,
        default="goods",
        help="Nature used to pick the withholding tariff when no explicit "
             "IR/IVA code is set on the product.",
    )

    @api.depends("type")
    def _compute_l10n_ec_withholding_activity(self):
        for product in self:
            product.l10n_ec_withholding_activity = (
                "services" if product.type == "service" else "goods"
            )
