# -*- coding: utf-8 -*-
"""
Ecuadorian account type on bank accounts.

Banks distinguish "cuenta de ahorros" (AHO) from "cuenta corriente"
(CTA/CTE) on every payment file. Odoo's `res.partner.bank` has no such
field, so the bank-transfer generators used to hardcode "AHO". This adds
the field per bank account; each layout maps the value to its own code
(see `account_type_map` in each generator class).
"""
from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    l10n_ec_account_type = fields.Selection(
        [
            ("ahorro", "Cuenta de Ahorros"),
            ("corriente", "Cuenta Corriente"),
        ],
        string="Tipo de Cuenta (EC)",
        default="ahorro",
        help="Ecuadorian account type used when generating bank "
        "Cash-Management files (each bank maps this to its own code, "
        "e.g. AHO/CTA for Pichincha).",
    )
