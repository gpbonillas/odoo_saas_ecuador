# -*- coding: utf-8 -*-
"""
Bank Cash-Management file wizard (generalized).

Generates the TXT batch file for THREE payment modes:

  * payroll  — Nómina: payslips (l10n_ec.payslip) with net_wage > 0
  * advance  — Adelantos de suelda: payslips with advances > 0
  * supplier — Pago a Proveedores: posted vendor bills (account.move)

The file format comes from a `l10n_ec.bank.layout` config record which
points to one generator class per bank in `file_formats/` (pure-python,
standalone-testable).

FIXES vs previous implementation:
  * `slip.number` (nonexistent field -> AttributeError on the first
    positive payslip) replaced by `slip.name` / period reference.
  * Beneficiaries without a bank account now ABORT the generation with a
    clear list; the old code silently emitted account '0000000000'.
  * Account type (ahorro/corriente) now comes from the partner bank
    account field `l10n_ec_account_type` instead of hardcoded 'AHO'.
"""
import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_ec_bank_transfer.file_formats import (
    BatchHeader,
    BankFileError,
    PaymentLine,
)

_logger = logging.getLogger(__name__)


class L10nEcBankTransferWizard(models.TransientModel):
    _name = "l10n_ec.bank.transfer.wizard"
    _description = "Generate Bank Cash Management Files"

    payment_mode = fields.Selection(
        [
            ("payroll", "Nómina (Planilla de pagos)"),
            ("advance", "Adelantos de Sueldo"),
            ("supplier", "Pago a Proveedores"),
        ],
        string="Payment Mode",
        required=True,
        default="payroll",
    )
    layout_id = fields.Many2one(
        "l10n_ec.bank.layout",
        string="Bank Layout",
        required=True,
        domain="[('active', '=', True)]",
        help="Bank file layout to use (config records, one per bank).",
    )
    payment_date = fields.Date(
        string="Payment Date", default=fields.Date.context_today, required=True
    )
    description = fields.Char(string="Batch Description", default="PAGO MENSUAL")

    payslip_ids = fields.Many2many(
        "l10n_ec.payslip",
        string="Payslips",
        help="Payslips to pay (payroll mode) or to advance (advance mode).",
    )
    invoice_ids = fields.Many2many(
        "account.move",
        string="Vendor Bills",
        help="Posted vendor bills to pay (supplier mode).",
    )

    # Output
    filename = fields.Char()
    file_data = fields.Binary(readonly=True)

    # ------------------------------------------------------------------
    # Defaults from launch context (list-view bindings)
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if active_model == "l10n_ec.payslip" and active_ids:
            res.setdefault("payment_mode", "payroll")
            res["payslip_ids"] = [(6, 0, active_ids)]
        elif active_model == "account.move" and active_ids:
            res.setdefault("payment_mode", "supplier")
            res["invoice_ids"] = [(6, 0, active_ids)]
        if "layout_id" in fields_list and not res.get("layout_id"):
            layout = self.env["l10n_ec.bank.layout"].search(
                [("active", "=", True)], limit=1
            )
            if layout:
                res["layout_id"] = layout.id
        return res

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def action_generate(self):
        """Generate the TXT file for the selected payment mode."""
        self.ensure_one()
        if not self.layout_id:
            raise UserError(_("Select a bank layout first."))

        if self.payment_mode in ("payroll", "advance"):
            lines, missing = self._collect_payslip_lines()
        elif self.payment_mode == "supplier":
            lines, missing = self._collect_supplier_lines()
        else:  # pragma: no cover - selection is enforced by Odoo
            raise UserError(_("Unknown payment mode: %s") % self.payment_mode)

        # FIX (audit 1b): never emit placeholder accounts; abort listing
        # every beneficiary missing a bank account.
        if missing:
            raise UserError(
                _(
                    "Cannot generate the bank file: the following "
                    "beneficiaries have NO bank account registered:\n\n%s\n\n"
                    "Add their bank account (and Tipo de Cuenta EC) and run "
                    "the wizard again."
                )
                % "\n".join("• %s" % m for m in missing)
            )
        if not lines:
            raise UserError(
                _(
                    "Nothing to pay in '%s' mode with the selected records "
                    "(amounts must be greater than zero)."
                )
                % dict(self._fields["payment_mode"].selection)[self.payment_mode]
            )

        header = BatchHeader(
            company_name=self.env.company.name,
            company_vat=self.env.company.vat or "",
            payment_date=self.payment_date,
            batch_reference=self.description
            or self.layout_id.default_concept
            or "PAGO",
        )

        generator = self.layout_id.get_generator()
        try:
            content = generator.generate(header, lines)
        except BankFileError as err:
            raise UserError(str(err))

        stamp = self.payment_date.strftime("%Y%m%d") if self.payment_date else ""
        self.filename = "%s_%s_%s%s" % (
            self.layout_id.bank_code.upper(),
            self.payment_mode.upper(),
            stamp,
            generator.file_extension,
        )
        self.file_data = base64.b64encode(content.encode(generator.encoding))

        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.bank.transfer.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Payment-line collection per mode
    # ------------------------------------------------------------------
    def _collect_payslip_lines(self):
        """
        Build lines from payslips.

        payroll mode -> amount = net_wage
        advance mode -> amount = advances (salary advances)
        FIX (audit 1a): uses `slip.name`/period — `slip.number` does NOT
        exist on l10n_ec.payslip.
        FIX (audit 1c): account type from `bank.l10n_ec_account_type`.
        """
        lines = []
        missing = []
        for slip in self.payslip_ids:
            if slip.state == "cancel":
                continue
            emp = slip.employee_id
            amount = slip.net_wage if self.payment_mode == "payroll" else slip.advances
            if not amount or amount <= 0:
                continue

            bank = emp.bank_account_id
            if not bank or not bank.acc_number:
                period = (
                    slip.date_end.strftime("%m/%Y") if slip.date_end else "?"
                )
                missing.append(
                    _("%s (cedula/RUC %s, periodo %s)")
                    % (emp.name, emp.identification_id or "S/I", period)
                )
                continue

            period = slip.date_end.strftime("%m/%Y") if slip.date_end else ""
            if self.payment_mode == "payroll":
                concept = _("NOMINA %s") % period
            else:
                concept = _("ANTICIPO %s") % period

            lines.append(
                PaymentLine(
                    beneficiary_name=emp.name,
                    beneficiary_id=emp.identification_id or "",
                    account_number=bank.acc_number,
                    amount=amount,
                    account_type=bank.l10n_ec_account_type or "ahorro",
                    reference=slip.name or "",
                    concept=concept,
                )
            )
        return lines, missing

    def _collect_supplier_lines(self):
        """Build lines from posted vendor bills (Pago a Proveedores)."""
        lines = []
        missing = []
        wrong_state = []
        for move in self.invoice_ids:
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            if move.state != "posted":
                wrong_state.append(move.display_name)
                continue
            amount = abs(move.amount_residual)
            if amount <= 0:
                continue

            bank = move.partner_bank_id or move.partner_id.bank_ids[:1]
            if not bank or not bank.acc_number:
                missing.append(
                    _("%s (RUC/cedula %s, factura %s, saldo %.2f)")
                    % (
                        move.partner_id.name,
                        move.partner_id.vat or "S/I",
                        move.display_name,
                        amount,
                    )
                )
                continue

            lines.append(
                PaymentLine(
                    beneficiary_name=move.partner_id.name,
                    beneficiary_id=move.partner_id.vat or "",
                    account_number=bank.acc_number,
                    amount=amount,
                    account_type=bank.l10n_ec_account_type or "ahorro",
                    reference=move.payment_reference or move.ref or move.name,
                    concept=move.partner_id.name[:40],
                )
            )
        if wrong_state:
            raise UserError(
                _(
                    "Only posted vendor bills can be paid. "
                    "Post first: %s"
                )
                % ", ".join(wrong_state)
            )
        return lines, missing
