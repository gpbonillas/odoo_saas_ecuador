# -*- coding: utf-8 -*-
from odoo import models, fields, api


class L10nEcRetentionTariff(models.Model):
    """
    SRI Withholding Tariff Table.

    Maps (tax type, RUC 4th digit, product/activity nature) to the SRI
    withholding code + rate that must be applied automatically when a
    purchase invoice is confirmed (agents of retention: Código Tributario
    art. 29; withholding obligations: LRTI art. 50 - agents of retention
    must withhold on purchases of goods/services).

    Lookup order for a given (tax_type, activity):
      1. Row whose ``ruc_digit`` matches the 4th digit of the partner RUC.
      2. Row with ``ruc_digit = 'any'`` (default table shipped as data).

    The table is data-driven (legal constants), not hardcoded in Python.
    """

    _name = "l10n_ec.retention.tariff"
    _description = "SRI Withholding Tariff (RUC 4th digit / activity)"
    _order = "sequence, id"

    tax_type = fields.Selection(
        [
            ("renta", "Impuesto a la Renta (Table 19)"),
            ("iva", "IVA (Table 21)"),
            ("isd", "ISD"),
        ],
        string="Tax Type",
        required=True,
        index=True,
    )
    ruc_digit = fields.Selection(
        [("any", "All (default)")]
        + [(str(d), str(d)) for d in range(10)],
        string="RUC 4th Digit",
        required=True,
        default="any",
        help="4th digit of the withholding subject's RUC. Rows with a "
             "specific digit take precedence over the 'any' row.",
    )
    activity = fields.Selection(
        [
            ("goods", "Bienes (goods)"),
            ("services", "Servicios (services)"),
            ("professional", "Honorarios profesionales"),
            ("transport", "Transporte"),
            ("liquidacion", "Liquidación de compra"),
        ],
        string="Activity / Nature",
        required=True,
        default="goods",
    )
    sequence = fields.Integer(default=10)
    withholding_tax_id = fields.Many2one(
        "l10n_ec.withholding.tax",
        string="Withholding Code",
        required=True,
        ondelete="restrict",
    )
    rate = fields.Float(
        related="withholding_tax_id.percentage",
        string="Rate %",
        store=True,
    )

    _sql_constraints = [
        (
            "tariff_uniq",
            "unique(tax_type, ruc_digit, activity)",
            "A tariff row already exists for this tax type / RUC digit / activity!",
        ),
    ]

    @api.model
    def get_ruc_4th_digit(self, partner):
        """Return the 4th digit of the partner RUC, or False."""
        vat = (partner and partner.vat or "").strip()
        if len(vat) >= 4 and vat[3].isdigit():
            return vat[3]
        return False

    @api.model
    def resolve(self, tax_type, activity, partner):
        """
        Resolve the withholding code for a purchase line.

        :param tax_type: 'renta' or 'iva'
        :param activity: 'goods', 'services', 'professional', ...
        :param partner: vendor being withheld
        :return: l10n_ec.withholding.tax recordset (empty if no tariff)
        """
        base_domain = [("tax_type", "=", tax_type), ("activity", "=", activity)]
        digit = self.get_ruc_4th_digit(partner)
        row = self.browse()
        if digit:
            row = self.search(base_domain + [("ruc_digit", "=", digit)], limit=1)
        if not row:
            row = self.search(base_domain + [("ruc_digit", "=", "any")], limit=1)
        return row.withholding_tax_id
