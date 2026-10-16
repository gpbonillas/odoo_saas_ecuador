# -*- coding: utf-8 -*-
from odoo import models, fields, api

# loan_type values defined in l10n_ec.loan (see loan.py)
IESS_LOAN_TYPES = ("iess_qui", "iess_hip")
COMPANY_LOAN_TYPES = ("company",)


class L10nEcPayslip(models.Model):
    _inherit = "l10n_ec.payslip"

    # Aggregate loan deduction for this period (kept for backward compat,
    # views and the base net_wage computation read it via getattr).
    loan_deduction = fields.Float(
        "IESS/Company Loans", compute="_compute_loans", store=True
    )
    # Bucket split required by the journal-entry posting in
    # l10n_ec_hr_payroll: IESS quirografario/hipotecario installments are
    # paid to the IESS (a different liability account than company loans).
    loan_deduction_iess = fields.Float(
        "IESS Loan Deduction", compute="_compute_loans", store=True
    )
    loan_deduction_company = fields.Float(
        "Company Loan Deduction", compute="_compute_loans", store=True
    )

    @api.depends("employee_id", "date_start", "date_end")
    def _compute_loans(self):
        Line = self.env["l10n_ec.loan.line"]
        for rec in self:
            # Find unpaid loan installments due in this period
            installments = Line.search(
                [
                    ("loan_id.employee_id", "=", rec.employee_id.id),
                    ("loan_id.state", "=", "active"),
                    ("is_paid", "=", False),
                    ("date_due", ">=", rec.date_start),
                    ("date_due", "<=", rec.date_end),
                ]
            )
            iess = sum(
                installments.filtered(
                    lambda l: l.loan_id.loan_type in IESS_LOAN_TYPES
                ).mapped("amount")
            )
            company = sum(
                installments.filtered(
                    lambda l: l.loan_id.loan_type in COMPANY_LOAN_TYPES
                ).mapped("amount")
            )
            rec.loan_deduction_iess = iess
            rec.loan_deduction_company = company
            rec.loan_deduction = iess + company

    @api.depends("loan_deduction")
    def _compute_totals(self):
        # The base implementation (l10n_ec_hr_payroll) already subtracts
        # loan_deduction from net_wage via getattr; here we only extend the
        # recompute trigger so net_wage refreshes when loans change.
        # @api.depends accumulates across the model inheritance chain.
        super()._compute_totals()

    def action_confirm(self):
        # Mark installments as paid
        for rec in self:
            installments = self.env["l10n_ec.loan.line"].search(
                [
                    ("loan_id.employee_id", "=", rec.employee_id.id),
                    ("loan_id.state", "=", "active"),
                    ("is_paid", "=", False),
                    ("date_due", ">=", rec.date_start),
                    ("date_due", "<=", rec.date_end),
                ]
            )
            installments.write({"is_paid": True, "payslip_id": rec.id})

        return super(L10nEcPayslip, self).action_confirm()
