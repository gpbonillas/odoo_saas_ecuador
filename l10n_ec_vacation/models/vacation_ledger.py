# -*- coding: utf-8 -*-
"""Vacation ledger — Ecuadorian accrued/paid vacation control.

Accrual math follows KB_LABOR_SBU_DECIMOS / CT art. 69:
  * base: 15 days/year → 1.25 days/month
  * seniority: +1 day per completed year after year 5, capped at +15
    (total never exceeds 30 days).
The seniority/cap constants live in ``l10n_ec_payroll_calc`` so the
payslip engine, the liquidación wizard and this ledger share them.
"""
from odoo import models, fields, api

from odoo.addons.l10n_ec_hr_payroll.models import l10n_ec_payroll_calc as calc


class L10nEcVacationLedger(models.Model):
    _name = "l10n_ec.vacation.ledger"
    _description = "Ecuadorian Vacation Ledger"
    _order = "date desc"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    contract_id = fields.Many2one("hr.contract", string="Contract", required=True)

    date = fields.Date("Date", default=fields.Date.today, required=True)
    description = fields.Char("Description", required=True)

    # Ledger columns
    days_earned = fields.Float(
        "Days Earned (+)", default=0.0, help="Accrual (1.25/month + seniority)"
    )
    days_taken = fields.Float(
        "Days Taken (-)", default=0.0, help="Vacation days enjoyed"
    )
    days_paid = fields.Float(
        "Days Paid (-)", default=0.0, help="Liquidated days (cash)"
    )

    balance = fields.Float("Balance", compute="_compute_balance", store=True)

    @api.depends("employee_id")
    def _compute_balance(self):
        # Rolling balance calculation is tricky in stored compute without strict ordering.
        # For simplicity in V1, we verify balance per employee.
        # A better approach for Ledger is usually on-the-fly or sequential triggers.
        # Here we will just sum for the employee.
        for rec in self:
            domain = [("employee_id", "=", rec.employee_id.id)]
            ledgers = self.search(domain)
            earned = sum(l.days_earned for l in ledgers)
            taken = sum(l.days_taken for l in ledgers)
            paid = sum(l.days_paid for l in ledgers)
            rec.balance = earned - taken - paid

    @api.model
    def run_monthly_accrual(self, reference_date=None):
        """
        Scheduled Action to run accruals (CT art. 69 / KB §3):

        1. Find active contracts.
        2. Seniority = completed years of service (calc.years_of_service).
        3. Base = 1.25 days/month (15 days/year).
        4. Seniority bonus = +1 day/year after year 5, capped at +15
           extra days (total never exceeds 30); monthly portion =
           bonus / 12.
        """
        if not reference_date:
            reference_date = fields.Date.today()

        contracts = self.env["hr.contract"].search([("state", "=", "open")])

        for contract in contracts:
            # Check if accrual already ran for this month? (Omitted for MVP simplicity, would be a unique constraint)

            # 1. Base Accrual (15 days / 12 months)
            base_monthly = calc.VACATION_BASE_DAYS / 12.0

            # 2. Seniority Bonus, shared logic with payslip/wizard:
            #    +1 day per completed year after year 5, capped at +15.
            years_service = calc.years_of_service(
                contract.date_start, reference_date
            )
            seniority_days_yearly = 0.0
            if years_service > 5:
                seniority_days_yearly = min(
                    years_service - 5, calc.VACATION_MAX_EXTRA_DAYS
                )

            seniority_monthly = seniority_days_yearly / 12.0
            total_earned = base_monthly + seniority_monthly

            self.create(
                {
                    "employee_id": contract.employee_id.id,
                    "contract_id": contract.id,
                    "date": reference_date,
                    "description": f"Monthly Accrual ({reference_date.strftime('%B %Y')}) - Base: {base_monthly:.2f}, Seniority: {seniority_monthly:.2f}",
                    "days_earned": total_earned,
                }
            )
