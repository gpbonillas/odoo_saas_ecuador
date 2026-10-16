# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RetentionWizard(models.TransientModel):
    _name = "l10n_ec.retention.wizard"
    _description = "Wizard to Create Withholding Document"

    invoice_id = fields.Many2one("account.move", string="Invoice", required=True)
    partner_id = fields.Many2one(related="invoice_id.partner_id", string="Vendor")
    date = fields.Date(string="Date", default=fields.Date.context_today)

    line_ids = fields.One2many(
        "l10n_ec.retention.wizard.line", "wizard_id", string="Withholding Lines"
    )

    @api.model
    def default_get(self, fields_list):
        res = super(RetentionWizard, self).default_get(fields_list)
        if (
            "active_id" in self.env.context
            and self.env.context.get("active_model") == "account.move"
        ):
            invoice = self.env["account.move"].browse(self.env.context["active_id"])
            res["invoice_id"] = invoice.id

            # Pre-fill with the automatically detected withholding
            # (product IR/IVA codes + SRI tariff table by RUC 4th digit /
            # activity). The user can edit rates/codes before creating.
            if invoice.move_type == "in_invoice":
                lines = []
                for vals in invoice._l10n_ec_calculate_withholding_vals():
                    line_vals = {
                        key: value
                        for key, value in vals.items()
                        if key in ("tax_type", "tax_id", "base", "percentage")
                    }
                    tax = self.env["l10n_ec.withholding.tax"].browse(
                        line_vals.get("tax_id")
                    )
                    line_vals["percentage"] = tax.percentage
                    lines.append((0, 0, line_vals))
                res["line_ids"] = lines

        return res

    def action_create_retention(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Please add at least one withholding line."))

        retention_vals = {
            "invoice_id": self.invoice_id.id,
            "partner_id": self.partner_id.id,
            "date": self.date,
            "company_id": self.invoice_id.company_id.id,
            "l10n_ec_sri_status": "draft",
            "retention_line_ids": [],
        }

        for line in self.line_ids:
            retention_vals["retention_line_ids"].append(
                (
                    0,
                    0,
                    {
                        "tax_type": line.tax_type,
                        "tax_id": line.tax_id.id,
                        "base": line.base,
                        "invoice_id": self.invoice_id.id,
                    },
                )
            )

        retention = self.env["account.retention"].create(retention_vals)

        # Link back to invoice for smart button (if we add one) or just return view
        return {
            "name": _("Withholding"),
            "type": "ir.actions.act_window",
            "res_model": "account.retention",
            "res_id": retention.id,
            "view_mode": "form",
            "target": "current",
        }


class RetentionWizardLine(models.TransientModel):
    _name = "l10n_ec.retention.wizard.line"
    _description = "Retention Wizard Line"

    wizard_id = fields.Many2one("l10n_ec.retention.wizard", required=True)
    tax_type = fields.Selection(
        [("1", "Renta"), ("2", "IVA"), ("6", "ISD")], string="Impuesto", required=True
    )
    withholding_type = fields.Char(compute="_compute_withholding_type")

    tax_id = fields.Many2one(
        "l10n_ec.withholding.tax",
        string="Tax Code",
        required=True,
        domain="[('type', '=', withholding_type)]",
    )
    tax_code = fields.Char(related="tax_id.code", string="Código", readonly=True)
    base = fields.Monetary(string="Base Imponible", required=True)
    percentage = fields.Float(string="Porcentaje %", readonly=True)
    amount = fields.Monetary(string="Valor Retenido", compute="_compute_amount")
    currency_id = fields.Many2one(related="wizard_id.invoice_id.currency_id")

    @api.depends("tax_type")
    def _compute_withholding_type(self):
        mapping = {"1": "renta", "2": "iva", "6": "isd"}
        for line in self:
            line.withholding_type = mapping.get(line.tax_type, "renta")

    @api.onchange("tax_id")
    def _onchange_tax_id(self):
        for line in self:
            line.percentage = line.tax_id.percentage
            if line.tax_id:
                line.tax_type = {
                    "renta": "1",
                    "iva": "2",
                    "isd": "6",
                }.get(line.tax_id.type, line.tax_type)

    @api.depends("base", "percentage")
    def _compute_amount(self):
        for line in self:
            line.amount = line.base * (line.percentage / 100.0)
