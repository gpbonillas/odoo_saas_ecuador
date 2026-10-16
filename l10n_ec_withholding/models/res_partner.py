# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ec_withhold_agent = fields.Boolean(
        string="Agente de Retención (SRI)",
        help="The partner is an SRI withholding agent. Purchase invoices from "
             "(or of) a partner flagged as withholding agent are "
             "automatically checked for IR/IVA withholding on confirmation.",
    )
    l10n_ec_withhold_resolution = fields.Char(
        string="Withholding Agent Resolution",
        help="SRI resolution number that grants the withholding-agent status.",
    )
