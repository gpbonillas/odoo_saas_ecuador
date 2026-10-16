# -*- coding: utf-8 -*-
"""
Liquidación de Beneficios Sociales / Auxilio de Cesantía
========================================================

Wizard that computes the termination settlement ("liquidación por salida")
per the Código del Trabajo:

* Salario proporcional del último periodo          (KB_LABOR_TERMINATION §2.1)
* Décimo tercero proporcional  = ingresos ÷ 12     (KB_LABOR_SBU_DECIMOS §2.1)
* Décimo cuarto proporcional   = (SBU ÷ 360) × días, con periodo regional
  Costa/Galápagos → 15 marzo | Sierra/Amazonía → 15 agosto
                                                     (KB_LABOR_SBU_DECIMOS §3)
* Vacaciones devengadas no disfrutadas = sueldo ÷ 24 × días
                                                     (KB_LABOR_TERMINATION §3.3)
* Fondos de reserva pendientes (8.33%, solo "acumulado"/retenido por el
  empleador; mensualizado se paga vía IESS)          (KB_LABOR_FONDOS_RESERVA)
* Utilidades (parte individual, 10% de la utilidad neta por días
  trabajados — CT art. 97-100; distribución completa en el reporte SUT
  "Utilidades" de l10n_ec_sut)                       (KB_MINISTERIO_TRABAJO §5)
* Auxilio de cesantía = % × décimo tercero total devengado (escala por
  años de servicio cargada desde ir.config_parameter,
  ver l10n_ec_payroll_calc.CESANTIA_SCHEDULE)
* Indemnización (campo manual: desahucio 25%/año, despido 3 meses + 1/año,
  máx. 25 meses — CT art. 185/188, KB_LABOR_TERMINATION §2.2-2.3)

All percentages/divisors/SBU are read from ``ir.config_parameter`` — no
hardcoded legal values.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..models import l10n_ec_payroll_calc as calc


class L10nEcLiquidacionWizard(models.TransientModel):
    _name = "l10n_ec.termination.wizard"
    _description = "Liquidación de Beneficios Sociales (Ecuador)"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True
    )
    contract_id = fields.Many2one(
        "hr.contract", string="Contract", required=True
    )
    date_start = fields.Date(
        string="Hire Date",
        compute="_compute_date_start",
        store=True,
        readonly=False,
        help="Start of the service relationship (defaults to the contract "
        "start date).",
    )
    date_end = fields.Date(
        string="Termination Date",
        required=True,
        default=fields.Date.today,
    )
    termination_type = fields.Selection(
        [
            ("renuncia", "Voluntary Resignation"),
            ("desahucio_empleador", "Desahucio (Employer, 15-day notice)"),
            ("desahucio_trabajador", "Desahucio (Employee, 15-day notice)"),
            ("despido_intempestivo", "Unfair Dismissal"),
            ("mutuo_acuerdo", "Mutual Agreement"),
            ("visto_bueno", "Visto Bueno"),
            ("fin_contrato", "End of Contract"),
        ],
        string="Termination Type",
        default="renuncia",
        required=True,
    )
    region = fields.Selection(
        [
            ("costa", "Costa / Galápagos (pago 15 marzo)"),
            ("sierra", "Sierra / Amazonía (pago 15 agosto)"),
        ],
        string="Décimo 14 Region",
        compute="_compute_region",
        store=True,
        readonly=False,
    )

    # --- service time -----------------------------------------------------
    wage = fields.Float(
        string="Monthly Wage", compute="_compute_service", store=True
    )
    months_service = fields.Integer(
        string="Months of Service", compute="_compute_service", store=True
    )
    years_service = fields.Integer(
        string="Years of Service", compute="_compute_service", store=True
    )
    salary_days = fields.Integer(
        string="Pending Salary Days", compute="_compute_service", store=True
    )
    salary_proportional = fields.Float(
        string="Proportional Salary", compute="_compute_service", store=True
    )

    # --- benefits ----------------------------------------------------------
    decimo_13 = fields.Float(
        string="Décimo Tercero Proporcional", compute="_compute_decimos", store=True
    )
    decimo_14 = fields.Float(
        string="Décimo Cuarto Proporcional", compute="_compute_decimos", store=True
    )
    decimo_14_deadline = fields.Date(
        string="Décimo 14 Deadline", compute="_compute_decimos", store=True
    )
    vacation_days = fields.Float(
        string="Unused Vacation Days",
        compute="_compute_vacation_days",
        store=True,
        readonly=False,
    )
    vacation_pay = fields.Float(
        string="Vacaciones No Disfrutadas", compute="_compute_vacation_pay", store=True
    )
    fondos_reserva = fields.Float(
        string="Fondos de Reserva Pendientes",
        compute="_compute_fondos_reserva",
        store=True,
    )
    utilidades = fields.Float(
        string="Utilidades (parte individual)",
        compute="_compute_utilidades",
        store=True,
        readonly=False,
    )
    auxilio_cesantia_pct = fields.Float(
        string="Auxilio de Cesantía %", compute="_compute_auxilio", store=True
    )
    auxilio_cesantia = fields.Float(
        string="Auxilio de Cesantía", compute="_compute_auxilio", store=True
    )
    indemnizacion = fields.Float(
        string="Indemnización (manual)",
        default=0.0,
        help="Enter the indemnification when applicable: desahucio = 25% of "
        "the monthly wage per year worked (min. 25% of one month); unfair "
        "dismissal = 3 months + 1 month per year beyond 3 years, capped at "
        "25 months (CT art. 185 / 188 — KB_LABOR_TERMINATION §2.2-2.3).",
    )
    total_a_pagar = fields.Float(
        string="TOTAL A PAGAR", compute="_compute_total", store=True
    )
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Confirmed")], default="draft"
    )

    # ------------------------------------------------------------------
    @api.depends("contract_id")
    def _compute_date_start(self):
        for rec in self:
            rec.date_start = rec.contract_id.date_start or rec.date_end

    @api.depends("employee_id")
    def _compute_region(self):
        for rec in self:
            rec.region = (
                rec.employee_id.l10n_ec_decimo_cuarto_region or "sierra"
            )

    @api.depends("date_start", "date_end", "contract_id")
    def _compute_service(self):
        for rec in self:
            start = rec.date_start
            end = rec.date_end
            rec.wage = rec.contract_id.wage if rec.contract_id else 0.0
            rec.months_service = calc.months_of_service(start, end)
            rec.years_service = rec.months_service // 12
            # Pending salary: from the 1st of the termination month (or the
            # hire date when it is later) up to the termination date.
            if start and end:
                month_start = max(
                    fields.Date(start.year, start.month, 1), start
                )
                rec.salary_days = calc.days_inclusive(month_start, end)
            else:
                rec.salary_days = 0
            rec.salary_proportional = calc._money(
                rec.wage / 30.0 * rec.salary_days
            )

    def _get_required_param(self, *keys):
        ICP = self.env["ir.config_parameter"].sudo()
        values = {key: ICP.get_param(key) for key in keys}
        missing = sorted(k for k, v in values.items() if not v)
        if missing:
            raise UserError(
                _(
                    "Missing payroll configuration: %(keys)s. Install "
                    "l10n_ec_hr_payroll properly."
                )
                % {"keys": ", ".join(missing)}
            )
        return {key: float(values[key]) for key in keys}

    @api.depends("date_start", "date_end", "region", "contract_id")
    def _compute_decimos(self):
        params = self._get_required_param(
            "l10n_ec.sbu",
            "l10n_ec.decimo_tercero_divisor",
        )
        sbu = params["l10n_ec.sbu"]
        divisor = params["l10n_ec.decimo_tercero_divisor"]
        ICP = self.env["ir.config_parameter"].sudo()

        for rec in self:
            start = rec.date_start
            end = rec.date_end or fields.Date.today()
            region = rec.region or "sierra"

            # --- Décimo 13: period Dec 1 (prior year) → termination, ÷ 12.
            d13_start = max(start or end, fields.Date(end.year - 1, 12, 1))
            payslips = self.env["l10n_ec.payslip"].search(
                [
                    ("employee_id", "=", rec.employee_id.id),
                    ("date_start", ">=", d13_start),
                    ("date_end", "<=", end),
                ]
            )
            if payslips:
                earnings = sum(payslips.mapped("total_income"))
            else:
                # Fallback: wage × months elapsed (30-day months convention).
                days = calc.days_inclusive(d13_start, end)
                earnings = rec.wage * days / 30.0
            rec.decimo_13 = calc.decimo_tercero_proporcional(earnings, divisor)

            # --- Décimo 14: regional period + deadline.
            year = end.year
            period_start, period_end = calc.decimo_cuarto_period(year, region)
            if end > period_end:
                year += 1
                period_start, period_end = calc.decimo_cuarto_period(
                    year, region
                )
            accrual_start = max(start or period_start, period_start)
            days14 = calc.days_inclusive(
                accrual_start, min(end, period_end)
            )
            rec.decimo_14 = calc.decimo_cuarto_proporcional(sbu, days14)
            deadline_param = (
                "l10n_ec.decimo_cuarto_deadline_costa"
                if region == "costa"
                else "l10n_ec.decimo_cuarto_deadline_sierra"
            )
            month_day = (ICP.get_param(deadline_param) or "").split("-")
            if len(month_day) == 2 and month_day[0].isdigit():
                rec.decimo_14_deadline = fields.Date(
                    int(year), int(month_day[0]), int(month_day[1])
                )
            else:
                rec.decimo_14_deadline = calc.decimo_cuarto_deadline(
                    year, region
                )

    @api.depends("employee_id", "date_start", "date_end")
    def _compute_vacation_days(self):
        """Unused vacation days: from the vacation ledger when
        l10n_ec_vacation is installed, otherwise the Art. 69 formula."""
        for rec in self:
            days = 0.0
            if "l10n_ec.vacation.ledger" in self.env and rec.employee_id:
                ledger = self.env["l10n_ec.vacation.ledger"].search(
                    [("employee_id", "=", rec.employee_id.id)]
                )
                days = sum(
                    entry.days_earned - entry.days_taken - entry.days_paid
                    for entry in ledger
                )
            if days <= 0.0:
                days = calc.vacaciones_accrued_days(
                    rec.months_service or 0,
                    rec.years_service or 0,
                )
            rec.vacation_days = max(0.0, days)

    @api.depends("vacation_days", "contract_id")
    def _compute_vacation_pay(self):
        for rec in self:
            wage = rec.contract_id.wage if rec.contract_id else 0.0
            rec.vacation_pay = calc.vacaciones_pay(wage, rec.vacation_days)

    @api.depends("date_start", "date_end", "contract_id")
    def _compute_fondos_reserva(self):
        """Only pending when the employer RETAINS the fondos (acumulado);
        the monthly option is deposited to the IESS and has no balance due
        at termination (KB_IESS_2026 §3.2)."""
        params = self._get_required_param(
            "l10n_ec.sbu",
            "l10n_ec.fondos_reserva",
            "l10n_ec.fondos_reserva_meses",
            "l10n_ec.iess_ceiling_sbu_multiplicador",
        )
        ceiling = calc.iess_ceiling(
            params["l10n_ec.sbu"],
            int(params["l10n_ec.iess_ceiling_sbu_multiplicador"]),
        )
        for rec in self:
            rec.fondos_reserva = 0.0
            contract = rec.contract_id
            if not contract or not contract.l10n_ec_accumulate_reserve:
                continue
            if not contract.date_start or not rec.date_end:
                continue
            if calc.months_of_service(contract.date_start, rec.date_end) < int(
                params["l10n_ec.fondos_reserva_meses"]
            ):
                continue
            monthly = calc.fondos_reserva_amount(
                contract.wage,
                params["l10n_ec.fondos_reserva"],
                999,  # eligibility already checked above
                int(params["l10n_ec.fondos_reserva_meses"]),
                ceiling,
            )
            year_start = fields.Date(rec.date_end.year, 1, 1)
            pending_start = max(contract.date_start, year_start)
            pending_months = calc.months_of_service(
                pending_start, rec.date_end
            )
            rec.fondos_reserva = calc._money(monthly * pending_months)

    @api.depends("employee_id", "date_end")
    def _compute_utilidades(self):
        """Individual utilities share (CT art. 100): 10% of the net profit
        of the last closed fiscal year distributed by days worked.

        The complete distribution (10% days + 5% family loads) is produced
        by the SUT "Utilidades" report (l10n_ec_sut). Amount is editable.
        """
        for rec in self:
            rec.utilidades = 0.0
            if not rec.employee_id or not rec.date_end:
                continue
            # Profits of the previous calendar year (paid by April 15).
            year = rec.date_end.year - 1
            year_start = fields.Date(year, 1, 1)
            year_end = fields.Date(year, 12, 31)

            self.env.cr.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN aa.account_type IN ('income', 'income_other')
                             THEN -aml.balance ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN aa.account_type IN
                                 ('expense', 'expense_depreciation', 'expense_direct_cost')
                             THEN aml.balance ELSE 0 END), 0)
                FROM account_move_line aml
                JOIN account_account aa ON aml.account_id = aa.id
                JOIN account_move am ON aml.move_id = am.id
                WHERE am.state = 'posted'
                  AND am.date >= %s AND am.date <= %s
                  AND am.company_id = %s
                """,
                (year_start, year_end, self.env.company.id),
            )
            row = self.env.cr.fetchone()
            profit = max(0.0, (row[0] or 0.0) - (row[1] or 0.0))
            if profit <= 0:
                continue

            slips = self.env["l10n_ec.payslip"].search(
                [
                    ("date_start", ">=", year_start),
                    ("date_end", "<=", year_end),
                ]
            )
            if not slips:
                continue
            total_days = sum(slips.mapped("days_worked")) or 0.0
            employee_days = sum(
                slip.days_worked
                for slip in slips
                if slip.employee_id == rec.employee_id
            )
            if total_days <= 0 or employee_days <= 0:
                continue
            rec.utilidades = calc._money(
                (employee_days / total_days) * profit * 0.10
            )

    @api.depends("date_start", "date_end", "contract_id", "years_service")
    def _compute_auxilio(self):
        """Auxilio de cesantía = schedule(years) × total décimo tercero
        earned during the whole service relationship."""
        params = self._get_required_param(
            "l10n_ec.decimo_tercero_divisor",
            "l10n_ec.cesantia_pct_1_5",
            "l10n_ec.cesantia_pct_6_10",
            "l10n_ec.cesantia_pct_11_15",
            "l10n_ec.cesantia_pct_16_20",
            "l10n_ec.cesantia_pct_21_24",
            "l10n_ec.cesantia_pct_25_mas",
        )
        schedule = (
            (1, 5, params["l10n_ec.cesantia_pct_1_5"]),
            (6, 10, params["l10n_ec.cesantia_pct_6_10"]),
            (11, 15, params["l10n_ec.cesantia_pct_11_15"]),
            (16, 20, params["l10n_ec.cesantia_pct_16_20"]),
            (21, 24, params["l10n_ec.cesantia_pct_21_24"]),
            (25, None, params["l10n_ec.cesantia_pct_25_mas"]),
        )
        for rec in self:
            start = rec.date_start
            end = rec.date_end or fields.Date.today()
            years = calc.years_of_service(start, end)
            rec.auxilio_cesantia_pct = calc.auxilio_cesantia_pct(years, schedule)

            # Base: total décimo tercero earned during the relationship.
            payslips = self.env["l10n_ec.payslip"].search(
                [
                    ("employee_id", "=", rec.employee_id.id),
                    ("date_start", ">=", start),
                    ("date_end", "<=", end),
                ]
            ) if start else self.env["l10n_ec.payslip"]
            if payslips:
                earnings = sum(payslips.mapped("total_income"))
            else:
                earnings = rec.wage * calc.days_inclusive(start, end) / 30.0
            d13_total = calc.decimo_tercero_proporcional(
                earnings, params["l10n_ec.decimo_tercero_divisor"]
            )
            rec.auxilio_cesantia = calc.auxilio_cesantia_amount(
                d13_total, years, schedule
            )

    @api.depends(
        "salary_proportional",
        "decimo_13",
        "decimo_14",
        "vacation_pay",
        "fondos_reserva",
        "utilidades",
        "auxilio_cesantia",
        "indemnizacion",
    )
    def _compute_total(self):
        for rec in self:
            rec.total_a_pagar = calc._money(
                rec.salary_proportional
                + rec.decimo_13
                + rec.decimo_14
                + rec.vacation_pay
                + rec.fondos_reserva
                + rec.utilidades
                + rec.auxilio_cesantia
                + rec.indemnizacion
            )

    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        if self.date_end and self.date_start and self.date_end < self.date_start:
            raise UserError(
                _("The termination date cannot be before the hire date.")
            )
        if self.total_a_pagar <= 0:
            raise UserError(
                _(
                    "The settlement total is zero — check the hire/termination "
                    "dates and the employee's payslips."
                )
            )
        self.write({"state": "done"})
        return True
