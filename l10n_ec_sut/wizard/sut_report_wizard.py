# -*- coding: utf-8 -*-
"""
SUT Report Generator - MDT Integration.

Scope: TXT/csv helpers for the three MDT "SUT" (Sistema Único de
Trabajo) style reporting extracts that this repo supports:
  * Décimo Tercero (13th)   — earnings ÷ 12 (KB_LABOR_SBU_DECIMOS §2.1)
  * Décimo Cuarto (14th)    — SBU/360 × days, region-dependent window
                              (KB_LABOR_SBU_DECIMOS §3)
  * Utilidades (art. 97-104) — 15% of net profit: 10% equal +
                              5% by cargas familiares, filed by April 15.

Legal basis:
- Código Trabajo Art. 97-104: 15% Utilidades
  - 10% repartición directa (igual para todos)
  - 5% por cargas familiares
- Filing: April 15 each year
- Décimo Cuarto deadlines (KB §3.1): Costa/Galápagos → 15 marzo;
  Sierra/Amazonía → 15 agosto. NOT Sept 15 — the old comment here was
  wrong. Calculation periods (KB §3.2): Costa 1 mar prev → 28/29 feb;
  Sierra 1 ago prev → 31 jul.
"""
import base64
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict

try:
    from odoo.addons.l10n_ec_hr_payroll.models import (
        l10n_ec_payroll_calc as calc,
    )
except ImportError:  # pragma: no cover - standalone lint environments
    calc = None


class L10nEcSutReportWizard(models.TransientModel):
    _name = "l10n_ec.sut.report.wizard"
    _description = "MDT SUT Report Generator"

    report_type = fields.Selection(
        [
            ("13th", "Décimo Tercero"),
            ("14th", "Décimo Cuarto"),
            ("utilidades", "Utilidades"),
        ],
        string="Report Type",
        required=True,
    )

    date_start = fields.Date("Start Date", required=True)
    date_end = fields.Date("End Date", required=True)

    # For utilidades - AUTO-CALCULATED from accounting P&L
    fiscal_year_profit = fields.Float(
        "Utilidad Neta del Ejercicio",
        compute="_compute_fiscal_profit",
        help="Auto-calculado desde cuentas de Ingresos - Gastos del período",
    )
    company_profit = fields.Float(
        "Utilidad a Repartir (15%)",
        compute="_compute_fiscal_profit",
        help="Código Trabajo Art. 97: 15% de utilidad neta, auto-calculado",
    )

    # Generated File
    filename = fields.Char("Filename")
    file_data = fields.Binary("Report File")

    @api.depends("date_start", "date_end")
    def _compute_fiscal_profit(self):
        """
        Auto-calculate company profit from accounting:
        - Income accounts (type: income, income_other)
        - Expense accounts (type: expense, expense_depreciation, expense_direct_cost)
        """
        for rec in self:
            if not rec.date_start or not rec.date_end:
                rec.fiscal_year_profit = 0.0
                rec.company_profit = 0.0
                continue

            # Get income and expense totals from account.move.line
            self.env.cr.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN aa.account_type IN ('income', 'income_other')
                             THEN -aml.balance ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN aa.account_type IN ('expense', 'expense_depreciation', 'expense_direct_cost')
                             THEN aml.balance ELSE 0 END), 0) as total_expense
                FROM account_move_line aml
                JOIN account_account aa ON aml.account_id = aa.id
                JOIN account_move am ON aml.move_id = am.id
                WHERE am.state = 'posted'
                  AND am.date >= %s AND am.date <= %s
                  AND am.company_id = %s
            """,
                (rec.date_start, rec.date_end, self.env.company.id),
            )

            result = self.env.cr.fetchone()
            total_income = result[0] if result else 0
            total_expense = result[1] if result else 0

            # Net profit = Income - Expenses
            net_profit = total_income - total_expense
            rec.fiscal_year_profit = max(net_profit, 0)  # Only distribute if profit
            rec.company_profit = (
                rec.fiscal_year_profit * 0.15
            )  # 15% per Código Trabajo Art. 97

    def action_generate(self):
        self.ensure_one()

        # 1. Fetch relevant Payslips
        domain = [
            ("state", "=", "done"),
            ("date_end", ">=", self.date_start),
            ("date_start", "<=", self.date_end),
        ]
        payslips = self.env["l10n_ec.payslip"].search(domain)

        if not payslips:
            raise UserError(_("No payslips found for the selected period."))

        content = ""

        if self.report_type == "13th":
            content = self._generate_13th_report(payslips)

        elif self.report_type == "14th":
            content = self._generate_14th_report(payslips)

        elif self.report_type == "utilidades":
            content = self._generate_utilidades_report(payslips)

        self.filename = f"SUT_{self.report_type}_{self.date_end}.txt"
        self.file_data = base64.b64encode(content.encode("utf-8"))

        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.sut.report.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def _generate_13th_report(self, payslips):
        """Décimo Tercero report for SUT."""
        content = "Cedula,Nombres,Dias_Trabajados,Total_Ganado,Valor_Decimo\n"
        for p in payslips:
            content += f"{p.employee_id.identification_id},{p.employee_id.name},{p.days_worked},{p.total_income},{p.thirteenth}\n"
        return content

    def _generate_14th_report(self, payslips):
        """Décimo Cuarto report for SUT.

        Region + deadlines come from the shared calc library
        (KB_LABOR_SBU_DECIMOS §3.1/§3.2): Costa/Galápagos pays by
        15 marzo (period 1 mar prev → 28/29 feb); Sierra/Amazonía pays
        by 15 agosto (period 1 ago prev → 31 jul).
        """
        content = (
            "Cedula,Nombres,Region,Dias_Trabajados,"
            "Valor_Decimo,Fecha_Limite_Pago\n"
        )
        payment_year = (self.date_end or date.today()).year
        for p in payslips:
            emp = p.employee_id
            # Prefer the computed employee field (province-based, see
            # l10n_ec_hr_payroll/models/hr_employee_ec.py); fall back to
            # the home address state name; "sierra" is the legal default.
            region = (
                getattr(emp, "l10n_ec_decimo_cuarto_region", False)
                or emp.private_state_id.name
                or "sierra"
            )
            region_key = (
                calc.normalize_decimo_cuarto_region(region)
                if calc
                else "sierra"
            )
            deadline = (
                calc.decimo_cuarto_deadline(payment_year, region_key).isoformat()
                if calc
                else ""
            )
            content += (
                f"{emp.identification_id},{emp.name},{region_key},"
                f"{p.days_worked},{p.fourteenth},{deadline}\n"
            )
        return content

    def _generate_utilidades_report(self, payslips):
        """
        Utilidades report per Código Trabajo Art. 97-104 and
        KB_LABOR_UTILIDADES §3:

        - 10% component: proportional to DAYS WORKED
          (Factor A = days worked by employee; Factor B = total days).
        - 5% component: proportional to DAYS WORKED × FAMILY LOADS
          (Factor 1 = days × cargas; Factor 2 = sum of Factor 1).

        Profit is AUTO-CALCULATED from accounting (15% of net profit).
        """
        if self.company_profit <= 0:
            raise UserError(
                _(
                    "No hay utilidad a repartir. La utilidad neta del ejercicio es: $%.2f"
                )
                % self.fiscal_year_profit
            )

        # Calculate 10% (days) and 5% (days × cargas)
        total_profit = self.company_profit
        equal_portion = total_profit * (10 / 15)  # 10% of 15% = 2/3
        cargas_portion = total_profit * (5 / 15)  # 5% of 15% = 1/3

        # Aggregate by employee
        employee_data = defaultdict(
            lambda: {"name": "", "cedula": "", "days": 0, "cargas": 0}
        )

        for p in payslips:
            emp_id = p.employee_id.id
            employee_data[emp_id]["name"] = p.employee_id.name
            employee_data[emp_id]["cedula"] = p.employee_id.identification_id or ""
            employee_data[emp_id]["days"] += p.days_worked or 0
            # Get cargas familiares from employee or contract
            employee_data[emp_id]["cargas"] = (
                getattr(p.employee_id, "l10n_ec_family_loads", 0) or 0
            )

        total_days = sum(emp["days"] for emp in employee_data.values())
        # KB §3.2 Factor 2 = Σ (days worked × cargas)
        total_days_cargas = sum(
            emp["days"] * emp["cargas"] for emp in employee_data.values()
        )

        # Calculate per employee
        content = "Cedula,Nombres,Dias_Trabajados,Cargas_Familiares,Utilidad_10pct,Utilidad_5pct,Total_Utilidad\n"

        for emp_id, emp in employee_data.items():
            # 10% portion: proportional to days worked (KB §3.1)
            if total_days > 0:
                utilidad_10 = (emp["days"] / total_days) * equal_portion
            else:
                utilidad_10 = 0

            # 5% portion: proportional to days × cargas (KB §3.2)
            factor_1 = emp["days"] * emp["cargas"]
            if total_days_cargas > 0 and factor_1 > 0:
                utilidad_5 = (factor_1 / total_days_cargas) * cargas_portion
            else:
                utilidad_5 = 0

            total_util = utilidad_10 + utilidad_5

            content += (
                f"{emp['cedula']},"
                f"{emp['name']},"
                f"{emp['days']},"
                f"{emp['cargas']},"
                f"{utilidad_10:.2f},"
                f"{utilidad_5:.2f},"
                f"{total_util:.2f}\n"
            )

        return content
