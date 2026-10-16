# -*- coding: utf-8 -*-
"""
Layout configuration records (data-driven bank mapping).

Instead of a hardcoded bank list in the wizard, each supported bank is a
`l10n_ec.bank.layout` record pointing (via `bank_code`) to one generator
class in `file_formats/`. New banks can be enabled/disabled per company
without touching the wizard code; a new *format* still needs a new
generator class (see file_formats/__init__.py).
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.l10n_ec_bank_transfer.file_formats import (
    LAYOUTS,
    available_bank_codes,
    get_generator,
)


def _selection_bank_codes(self):
    """Selection sourced from the generator registry (single source of truth)."""
    return [(code, "%s [%s]" % (LAYOUTS[code].bank_name, code)) for code in available_bank_codes()]


class L10nEcBankLayout(models.Model):
    _name = "l10n_ec.bank.layout"
    _description = "Bank Cash-Management File Layout"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    bank_code = fields.Selection(
        selection=_selection_bank_codes,
        string="Generator",
        required=True,
        help="File-format generator used to build the TXT file "
        "(see l10n_ec_bank_transfer/file_formats/).",
    )
    sequence = fields.Integer(default=10)
    default_concept = fields.Char(
        string="Default Batch Concept",
        default="PAGO",
        help="Concept/reference written into the file header when the "
        "wizard description is empty.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "bank_code_company_uniq",
            "unique(bank_code, company_id)",
            "Each bank layout can only be configured once per company.",
        ),
    ]

    @api.constrains("bank_code")
    def _check_bank_code_known(self):
        for rec in self:
            if rec.bank_code not in LAYOUTS:
                raise ValidationError(
                    _("Unknown bank generator: %s") % rec.bank_code
                )

    def get_generator(self):
        """Return the pure-python generator instance for this layout."""
        self.ensure_one()
        return get_generator(self.bank_code)
