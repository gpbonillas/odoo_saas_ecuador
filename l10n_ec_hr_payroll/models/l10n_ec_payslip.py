# -*- coding: utf-8 -*-
import logging
import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

from . import l10n_ec_payroll_calc as calc

_logger = logging.getLogger(__name__)


class L10nEcPayslip(models.Model):
    _name = "l10n_ec.payslip"
    _description = "Ecuadorian Payslip"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(readonly=True)  # e.g. "Cedula - Month/Year"
    employee_id = fields.Many2one("hr.employee", required=True)
    contract_id = fields.Many2one("hr.contract", required=True)

    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)

    days_worked = fields.Float(default=30.0)

    # Earnings
    wage = fields.Float(
        "Base Wage", compute="_compute_wage", store=True, readonly=False
    )
    # Legal surcharges are applied to the ordinary hour rate (SBU/240):
    #   overtime_hours      -> suplementaria   +50%  (CT art. 55)
    #   supplementary_hours -> extraordinaria  +100% (CT art. 55)
    #   night_hours         -> nocturna        +25%
    overtime_hours = fields.Float("Suplementary (50%) Hours")
    supplementary_hours = fields.Float("Extraordinary (100%) Hours")
    night_hours = fields.Float("Night (25%) Hours")
    commission = fields.Float("Commissions")
    bonus = fields.Float("Bonuses")

    # Computations
    total_income = fields.Float("Total Income", compute="_compute_totals", store=True)

    # Deductions
    iess_personal = fields.Float(
        "IESS Personal (9.45%)", compute="_compute_iess", store=True
    )
    income_tax = fields.Float("Impuesto Renta", default=0.0)
    advances = fields.Float("Salary Advances")
    pension_alimenticia = fields.Float(
        "Pensión Alimenticia",
        default=0.0,
        help="Court-ordered alimony. Legally priority deduction: deducted "
        "first and EXEMPT from the 40% monthly deduction cap.",
    )

    # Employer Costs / IESS breakdown
    iess_contribution_base = fields.Float(
        "IESS Contribution Base (techo 25×SBU)",
        compute="_compute_iess",
        store=True,
        help="min(Total Income, 25 × SBU). The ceiling caps the contribution "
        "base, never the salary itself.",
    )
    iess_employer = fields.Float(
        "IESS Patronal (11.15%)", compute="_compute_iess", store=True
    )
    iess_secap = fields.Float(
        "IESS SECAP (0.5%)", compute="_compute_iess", store=True
    )
    iess_iece = fields.Float(
        "IESS IECE (0.5%)", compute="_compute_iess", store=True
    )
    iess_employer_total = fields.Float(
        "IESS Employer Total (12.15%)", compute="_compute_iess", store=True
    )

    # Benefits (Provisions)
    thirteenth = fields.Float("13th Salary", compute="_compute_benefits", store=True)
    fourteenth = fields.Float("14th Salary", compute="_compute_benefits", store=True)
    reserve_funds = fields.Float(
        "Reserve Funds (IESS)", compute="_compute_benefits", store=True
    )

    net_wage = fields.Float("Net Wage", compute="_compute_totals", store=True)
    total_benefits_cash = fields.Float(
        "Benefits (Cash)", compute="_compute_benefits", store=True
    )

    # Accounting
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    journal_entry = fields.Char(
        "Journal Entry Number", readonly=True, copy=False
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("verify", "Verification"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Parameter helpers — ALL legal values come from ir.config_parameter
    # (data/l10n_ec_payroll_data.xml). No hardcoded fallbacks.
    # ------------------------------------------------------------------
    def _get_required_param(self, *keys):
        """Read float-able params; raise when any is missing."""
        ICP = self.env["ir.config_parameter"].sudo()
        values = {key: ICP.get_param(key) for key in keys}
        missing = sorted(key for key, value in values.items() if not value)
        if missing:
            raise ValueError(
                "Missing payroll configuration: %s. "
                "Install l10n_ec_hr_payroll properly "
                "(data/l10n_ec_payroll_data.xml) or set the parameters in "
                "Settings > Technical > Parameters." % ", ".join(missing)
            )
        return {key: float(values[key]) for key in keys}

    @api.depends("contract_id")
    def _compute_wage(self):
        for rec in self:
            rec.wage = rec.contract_id.wage if rec.contract_id else 0.0

    # ------------------------------------------------------------------
    # TOTALS / NET
    # ------------------------------------------------------------------
    @api.depends(
        "wage",
        "overtime_hours",
        "supplementary_hours",
        "night_hours",
        "commission",
        "bonus",
    )
    def _compute_totals(self):
        for rec in self:
            # Superiority Feature: Auto-calculate Overtime from Attendance
            rec._compute_overtime_from_attendance()

            # Recargos from parameters (50 / 100 / 25) applied to the
            # ordinary hour rate = wage / 240 (KB_MINISTERIO_TRABAJO §6).
            recargos = rec._get_required_param(
                "l10n_ec.horas_suplementarias_recargo",
                "l10n_ec.horas_extraordinarias_recargo",
                "l10n_ec.trabajo_nocturno_recargo",
            )
            ot_pay = calc.overtime_amount(
                rec.overtime_hours, rec.wage,
                recargos["l10n_ec.horas_suplementarias_recargo"],
            )
            supp_pay = calc.overtime_amount(
                rec.supplementary_hours, rec.wage,
                recargos["l10n_ec.horas_extraordinarias_recargo"],
            )
            night_pay = calc.overtime_amount(
                rec.night_hours, rec.wage,
                recargos["l10n_ec.trabajo_nocturno_recargo"],
            )

            rec.total_income = (
                rec.wage
                + ot_pay
                + supp_pay
                + night_pay
                + rec.commission
                + rec.bonus
            )
            # Income Tax Calculation (SRI 2026 Progressive)
            rec.income_tax = rec._compute_income_tax_2026(
                rec.total_income, rec.iess_personal
            )

            # Mandatory deductions contributed by other modules
            # (l10n_ec_loans adds loan_deduction through getattr).
            optional_deductions = float(getattr(rec, "loan_deduction", 0.0) or 0.0)

            rec.net_wage = (
                (rec.total_income + rec.total_benefits_cash)
                - rec.iess_personal
                - rec.income_tax
                - rec.pension_alimenticia
                - rec.advances
                - optional_deductions
            )

    def _compute_overtime_from_attendance(self):
        """
        PacERP Killer: Auto-calculate overtime from Biometric/Kiosk data.
        Logic:
        1. Fetch Attendance records within Payslip Period.
        2. Sum hours worked.
        3. Compare vs Contract Hours (e.g. 8h/day).
        4. Split Excess:
           - Weekdays > 8h -> +50% (Suplementaria)   -> overtime_hours
           - Weekends       -> +100% (Extraordinaria) -> supplementary_hours
        """
        for rec in self:
            try:
                attendances = self.env["hr.attendance"].search(
                    [
                        ("employee_id", "=", rec.employee_id.id),
                        ("check_in", ">=", rec.date_start),
                        ("check_out", "<=", rec.date_end),
                    ]
                )
            except (KeyError, Exception):
                continue

            total_supp_50 = 0.0
            total_extra_100 = 0.0

            for att in attendances:
                if not att.check_out:
                    continue

                # Calculate Duration
                delta = att.check_out - att.check_in
                hours = delta.total_seconds() / 3600.0

                # Check Day of Week (0=Mon, 6=Sun)
                # Odoo Datetime is UTC, need conversion to local typically?
                # For MVP we assume server time matches or is handled.
                weekday = att.check_in.weekday()

                if weekday >= 5:
                    # Weekend / holiday -> Extraordinaria (+100%)
                    total_extra_100 += hours
                elif hours > 8.0:
                    # Weekday excess -> Suplementaria (+50%)
                    total_supp_50 += hours - 8.0

            # Write to fields (recalculated on every totals recompute)
            rec.overtime_hours = total_supp_50  # +50% suplementaria
            rec.supplementary_hours = total_extra_100  # +100% extraordinaria

    def _compute_income_tax_2026(self, monthly_income, monthly_iess):
        """
        Implementation of Resolution NAC-DGERCGC25-00000043.
        1. Project Annual Income (Income * 12).
        2. Deduct IESS Personal (Income * 0.0945 * 12).
        3. Determine Tax Base.
        4. Calculate Impuesto Causado (Progressive Table).
        5. Calculate Rebaja Tributaria (Family Loads).
        6. Result: Annual Tax / 12.
        """
        # A. Projection
        # Note: Decimals and Reserve Funds are EXEMPT from Income Tax.
        annual_gross = monthly_income * 12.0
        annual_deductible_iess = monthly_iess * 12.0

        taxable_base = max(0.0, annual_gross - annual_deductible_iess)

        # B. Impuesto Causado
        # Get tax from l10n_ec.tax.table
        tax_table = self.env["l10n_ec.tax.table"]
        annual_caused_tax = tax_table.get_tax_for_base(taxable_base, year=2026)

        # If no tax caused, return 0 early
        if annual_caused_tax <= 0:
            return 0.0

        # C. Rebaja Tributaria (Tax Credit)
        # Needs Employee Family Loads and Contract Projected Expenses
        basket_model = self.env["l10n_ec.family.basket"]

        # Get Projected Expenses from Contract
        projected_expenses = 0.0
        if self.contract_id:
            projected_expenses = self.contract_id.l10n_ec_projected_expenses

        # Get Family Loads from Employee
        loads = 0
        catastrophic_disease = False
        if self.employee_id:
            loads = self.employee_id.l10n_ec_family_loads
            catastrophic_disease = self.employee_id.l10n_ec_catastrophic_disease

        rebate = basket_model.calculate_rebate(
            projected_expenses, loads, catastrophic_disease, year=2026
        )

        # D. Final Tax
        final_annual_tax = max(0.0, annual_caused_tax - rebate)

        return final_annual_tax / 12.0

    # ------------------------------------------------------------------
    # IESS — KB_IESS_2026 §1-2 / CUMPLIMIENTO §5.3
    #   personal 9.45% | patronal 11.15% + SECAP 0.5% + IECE 0.5% = 12.15%
    #   techo = 25 × SBU ($12,050 for SBU $482) applied to the BASE
    # ------------------------------------------------------------------
    @api.depends("total_income")
    def _compute_iess(self):
        """Compute every IESS contribution on the capped contribution base."""
        params = self._get_required_param(
            "l10n_ec.iess_aporte_personal",
            "l10n_ec.iess_aporte_patronal",
            "l10n_ec.iess_secap",
            "l10n_ec.iess_iece",
            "l10n_ec.sbu",
            "l10n_ec.iess_ceiling_sbu_multiplicador",
        )
        ceiling = calc.iess_ceiling(
            params["l10n_ec.sbu"],
            int(params["l10n_ec.iess_ceiling_sbu_multiplicador"]),
        )

        for rec in self:
            contrib = calc.iess_contributions(
                rec.total_income,
                ceiling,
                params["l10n_ec.iess_aporte_personal"],
                params["l10n_ec.iess_aporte_patronal"],
                params["l10n_ec.iess_secap"],
                params["l10n_ec.iess_iece"],
            )
            rec.iess_contribution_base = contrib["base"]
            rec.iess_personal = contrib["personal"]
            rec.iess_employer = contrib["patronal"]
            rec.iess_secap = contrib["secap"]
            rec.iess_iece = contrib["iece"]
            rec.iess_employer_total = contrib["employer_total"]

    # ------------------------------------------------------------------
    # BENEFITS — décimos, fondos de reserva (KB_LABOR_SBU_DECIMOS /
    # KB_LABOR_FONDOS_RESERVA)
    # ------------------------------------------------------------------
    @api.depends(
        "total_income",
        "days_worked",
        "date_start",
        "date_end",
        "contract_id.l10n_ec_accumulate_13",
        "contract_id.l10n_ec_accumulate_14",
        "contract_id.l10n_ec_accumulate_reserve",
        "contract_id.date_start",
    )
    def _compute_benefits(self):
        params = self._get_required_param(
            "l10n_ec.sbu",
            "l10n_ec.decimo_tercero_divisor",
            "l10n_ec.fondos_reserva",
            "l10n_ec.fondos_reserva_meses",
            "l10n_ec.iess_ceiling_sbu_multiplicador",
        )
        sbu = params["l10n_ec.sbu"]
        ceiling = calc.iess_ceiling(
            sbu, int(params["l10n_ec.iess_ceiling_sbu_multiplicador"])
        )
        divisor = params["l10n_ec.decimo_tercero_divisor"]
        fondos_rate = params["l10n_ec.fondos_reserva"]
        fondos_months = int(params["l10n_ec.fondos_reserva_meses"])

        for rec in self:
            # Décimo Tercero: Total Income / 12 (KB §2.1)
            rec.thirteenth = calc.decimo_tercero_proporcional(
                rec.total_income, divisor
            )

            # Décimo Cuarto: SBU / 360 × days worked (KB §3.4)
            rec.fourteenth = calc.decimo_cuarto_proporcional(
                sbu, rec.days_worked
            )

            # Fondos de Reserva: 8.33% from month 13 onwards, on the same
            # base as the IESS contributions (KB_LABOR_FONDOS_RESERVA §2-3).
            months = 0
            contract = rec.contract_id
            if contract and contract.date_start:
                months = calc.months_of_service(
                    contract.date_start, rec.date_end or fields.Date.today()
                )
            rec.reserve_funds = calc.fondos_reserva_amount(
                rec.total_income,
                fondos_rate,
                months,
                fondos_months,
                ceiling,
            )

            # Cash payout (Mensualizado) for décimos only.
            cash_total = 0.0
            if contract and not contract.l10n_ec_accumulate_13:
                cash_total += rec.thirteenth
            if contract and not contract.l10n_ec_accumulate_14:
                cash_total += rec.fourteenth

            # Fondos de Reserva are NEVER paid as cash in the rol de pagos:
            # since the 2009 monthly-payment reform they are deposited to the
            # IESS with the monthly planilla (KB_IESS_2026 §3.2 — "Mensualizado
            # (IESS): paid monthly through IESS (default)"; CUMPLIMIENTO §5.4
            # "Mensual vía IESS"). The amount is an employer obligation, not
            # part of the employee's net wage.
            rec.total_benefits_cash = cash_total

    # ------------------------------------------------------------------
    # OVERTIME CAPS — Código del Trabajo art. 55
    #   * max 4 supplementary+extraordinary hours per 24h day
    #   * max 12 supplementary+extraordinary hours per week
    # ------------------------------------------------------------------
    @api.constrains(
        "overtime_hours",
        "supplementary_hours",
        "days_worked",
        "date_start",
        "date_end",
    )
    def _check_overtime_limits(self):
        for rec in self:
            message = rec._overtime_limit_error()
            if message:
                raise ValidationError(message)

    def _overtime_limit_error(self):
        """Hard validation of both art. 55 caps.

        Layer 1 — attendance based (precise): per calendar day and per ISO
        week built from the attendance records of the period.
        Layer 2 — prorated period validation for manually entered hours
        (daily = 4 h × days, weekly = 12 h × days / 7).
        """
        self.ensure_one()
        params = self._get_required_param(
            "l10n_ec.horas_max_dia", "l10n_ec.horas_max_semana"
        )
        max_day = params["l10n_ec.horas_max_dia"]
        max_week = params["l10n_ec.horas_max_semana"]

        messages = []

        # Layer 1: precise daily/weekly buckets from attendance.
        daily, weekly = self._attendance_overtime_buckets()
        bad_days = sorted(
            (day, hours)
            for day, hours in daily.items()
            if hours > max_day + 1e-9
        )
        if bad_days:
            detail = ", ".join(
                "%s (%.1f h)" % (day.strftime("%d/%m/%Y"), hours)
                for day, hours in bad_days[:5]
            )
            extra = "" if len(bad_days) <= 5 else " …"
            messages.append(
                "Días que exceden las %.0f horas suplementarias+"
                "extraordinarias en 24 horas:\n  %s%s" % (max_day, detail, extra)
            )

        bad_weeks = sorted(
            (key, hours)
            for key, hours in weekly.items()
            if hours > max_week + 1e-9
        )
        if bad_weeks:
            detail = ", ".join(
                "semana ISO %s/%02d (%.1f h)" % (key[0], key[1], hours)
                for key, hours in bad_weeks[:5]
            )
            extra = "" if len(bad_weeks) <= 5 else " …"
            messages.append(
                "Semanas que exceden las %.0f horas suplementarias+"
                "extraordinarias por semana consecutiva:\n  %s%s"
                % (max_week, detail, extra)
            )

        # Layer 2: prorated period limits (manual entries / no attendance).
        period_message = calc.check_overtime_caps(
            self.overtime_hours + self.supplementary_hours,
            self.days_worked
            or calc.days_inclusive(self.date_start, self.date_end),
            max_day,
            max_week,
        )
        if period_message:
            messages.append(period_message)

        if not messages:
            return None
        return (
            "LÍMITE LEGAL DE HORAS EXTRAS EXCEDIDO "
            "(art. 55 Código del Trabajo)\n\n" + "\n\n".join(messages)
        )

    def _attendance_overtime_buckets(self):
        """Overtime hours aggregated per day and per ISO week.

        Weekday hours above 8 count as suplementarias; weekend hours count
        as extraordinarias. Only suplementarias+extraordinarias are subject
        to the art. 55 caps (the nocturna +25% surcharge applies to regular
        night shift hours, not to overtime).
        """
        self.ensure_one()
        daily = {}
        weekly = {}
        if not (self.employee_id and self.date_start and self.date_end):
            return daily, weekly

        attendances = self.env["hr.attendance"].search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("check_in", ">=", self.date_start),
                ("check_out", "<=", self.date_end),
            ]
        )
        for att in attendances:
            if not att.check_out:
                continue
            hours = (att.check_out - att.check_in).total_seconds() / 3600.0
            weekday = att.check_in.weekday()
            overtime = hours if weekday >= 5 else max(0.0, hours - 8.0)
            if overtime <= 0:
                continue
            day = att.check_in.date()
            iso = day.isocalendar()
            week_key = (iso[0], iso[1])
            daily[day] = daily.get(day, 0.0) + overtime
            weekly[week_key] = weekly.get(week_key, 0.0) + overtime
        return daily, weekly

    # ------------------------------------------------------------------
    # DEDUCTION CAPS — 40% of the liquid salary (IESS + other obligations)
    # and 33.33% for general assets/credit cases (Decreto);
    # pensiones alimenticias are legally priority and EXEMPT.
    # ------------------------------------------------------------------
    @api.constrains(
        "advances",
        "pension_alimenticia",
        "total_income",
        "income_tax",
        "iess_personal",
    )
    def _check_deduction_limits(self):
        for rec in self:
            message = rec._deduction_limit_error()
            if message:
                raise ValidationError(message)

    def _deduction_limit_error(self):
        """Validate the monthly deduction caps against the liquid salary.

        Liquid salary (salario líquido) = total income − IESS personal −
        income tax. ``loan_deduction`` (l10n_ec_loans) is included through
        getattr and is re-validated in ``action_confirm`` because a computed
        field of another module cannot be declared in ``@api.constrains``.
        """
        self.ensure_one()
        params = self._get_required_param(
            "l10n_ec.tope_descuento_porcentaje",
            "l10n_ec.tope_descuento_decreto",
        )
        liquid = max(
            0.0, self.total_income - self.iess_personal - self.income_tax
        )
        loans = float(getattr(self, "loan_deduction", 0.0) or 0.0)
        credit_deductions = loans + self.advances
        total_deductions = (
            self.iess_personal
            + self.income_tax
            + credit_deductions
        )
        violations = calc.check_deduction_caps(
            liquid,
            total_deductions,
            credit_deductions,
            cap_pct=params["l10n_ec.tope_descuento_porcentaje"],
            decreto_pct=params["l10n_ec.tope_descuento_decreto"],
            priority_deductions=self.pension_alimenticia,
        )
        if not violations:
            return None
        return (
            "LÍMITE LEGAL DE DESCUENTOS EXCEDIDO (Código del Trabajo / "
            "Decreto — topes 40% y 33.33% del salario líquido)\n\n"
            + "\n\n".join(violations)
            + "\n\nLas pensiones alimenticias tienen derecho preferente: se "
            "descuentan primero y no consumen el tope. Reduzca los préstamos/"
            "anticipos o programe su descuento en otro periodo."
        )

    # ------------------------------------------------------------------
    # POSTING — journal entry on confirmation.
    #
    # The aporte personal is credited to the SAME "IESS Aporte Personal por
    # Pagar" account (see l10n_ec_payroll_calc.ACCOUNT_CODES) that the 70%
    # of the IVA retention destined to the IESS must use (l10n_ec_withholding,
    # owned by another agent — coordinate through those constants only).
    # ------------------------------------------------------------------
    def _resolve_account(self, key):
        """Resolve an account by ordered candidate codes + name pattern."""
        codes = list(calc.ACCOUNT_CODES[key])
        pattern = calc.ACCOUNT_NAME_PATTERNS[key]
        company = self.contract_id.company_id or self.env.company
        candidates = self.env["account.account"].sudo().search(
            [("code", "in", codes), ("company_id", "in", [False, company.id])],
            order="code",
        )
        for account in candidates:
            if re.search(pattern, account.name or "", re.IGNORECASE):
                return account
        if len(candidates) == 1:
            # Single candidate with a different name (custom CoA): accept it
            # but make it visible in the log for the accountants.
            _logger.warning(
                "l10n_ec payroll: using account %s (%s) for '%s' — name does "
                "not match the expected pattern %r.",
                candidates.code, candidates.name, key, pattern,
            )
            return candidates[0]
        return self.env["account.account"]

    def _resolve_payroll_accounts(self):
        """Resolve every account needed for the payslip journal entry.

        Returns ``None`` when the chart of accounts is not installed yet
        (nothing to post against), otherwise a dict ``key -> record``.
        """
        keys = (
            "gasto_sueldos",
            "gasto_decimo_13",
            "gasto_decimo_14",
            "gasto_aporte_patronal",
            "gasto_fondos_reserva",
            "iess_aporte_personal",
            "iess_aporte_patronal",
            "iess_fondos_reserva",
            "iess_prestamos",
            "impuesto_renta",
            "otras_cuentas_por_cobrar",
            "decimo_13_por_pagar",
            "decimo_14_por_pagar",
            "sueldos_por_pagar",
        )
        accounts = {key: self._resolve_account(key) for key in keys}
        core = ("gasto_sueldos", "iess_aporte_personal", "sueldos_por_pagar")
        if all(not accounts[key] for key in core):
            return None
        return accounts

    def _get_payroll_journal(self):
        company = self.contract_id.company_id or self.env.company
        code = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.payroll_journal_code", "")
        )
        domain = [("company_id", "=", company.id), ("type", "=", "general")]
        if code:
            journal = self.env["account.journal"].sudo().search(
                domain + [("code", "=", code.strip())], limit=1
            )
            if journal:
                return journal
        return self.env["account.journal"].sudo().search(domain, limit=1)

    def _create_account_move(self):
        """Create/post the payroll journal entry (NEC chart of accounts)."""
        self.ensure_one()
        if self.move_id:
            return
        accounts = self._resolve_payroll_accounts()
        if accounts is None:
            _logger.warning(
                "l10n_ec.payslip '%s': Ecuador payroll accounts not found in "
                "the chart of accounts — journal entry skipped. Install/"
                "configure the EC chart (l10n_ec_base) to post payroll.",
                self.name,
            )
            return

        contract = self.contract_id
        d13_cash = self.thirteenth if (
            contract and not contract.l10n_ec_accumulate_13
        ) else 0.0
        d14_cash = self.fourteenth if (
            contract and not contract.l10n_ec_accumulate_14
        ) else 0.0
        loans_iess = 0.0
        loans_company = 0.0
        if "loan_deduction_iess" in self._fields:
            loans_iess = float(self.loan_deduction_iess or 0.0)
            loans_company = float(self.loan_deduction_company or 0.0)
        elif "loan_deduction" in self._fields:
            # Fallback: whole loan deduction treated as credit/asset case.
            loans_company = float(self.loan_deduction or 0.0)

        # (account key, debit, credit) — amounts must balance exactly:
        #   gross + accrued décimos + employer IESS + reserve    (debits)
        #   = IESS withholdings + tax + loans + advances + net payable
        #     + un-paid décimo provisions                        (credits)
        raw_lines = [
            ("gasto_sueldos", self.total_income, 0.0),
            ("gasto_decimo_13", self.thirteenth, 0.0),
            ("gasto_decimo_14", self.fourteenth, 0.0),
            ("gasto_aporte_patronal", self.iess_employer_total, 0.0),
            ("gasto_fondos_reserva", self.reserve_funds, 0.0),
            ("iess_aporte_personal", 0.0, self.iess_personal),
            ("iess_aporte_patronal", 0.0, self.iess_employer_total),
            ("iess_fondos_reserva", 0.0, self.reserve_funds),
            ("impuesto_renta", 0.0, self.income_tax),
            ("iess_prestamos", 0.0, loans_iess),
            (
                "otras_cuentas_por_cobrar",
                0.0,
                loans_company + self.advances,
            ),
            # Provision of the décimos NOT paid in cash this period
            # (acumulado mode); the cash part flows through net_wage.
            ("decimo_13_por_pagar", 0.0, self.thirteenth - d13_cash),
            ("decimo_14_por_pagar", 0.0, self.fourteenth - d14_cash),
            (
                "sueldos_por_pagar",
                0.0,
                self.net_wage + self.pension_alimenticia,
            ),
        ]

        missing = sorted(
            key
            for key, debit, credit in raw_lines
            if (debit or credit) and not accounts.get(key)
        )
        if missing:
            raise UserError(
                _(
                    "Cannot post the payroll journal entry: missing account(s) "
                    "%(keys)s in the chart of accounts. Expected codes: "
                    "%(codes)s."
                )
                % {
                    "keys": ", ".join(missing),
                    "codes": "; ".join(
                        "%s=%s"
                        % (key, "/".join(calc.ACCOUNT_CODES[key]))
                        for key in missing
                    ),
                }
            )

        journal = self._get_payroll_journal()
        if not journal:
            raise UserError(
                _(
                    "No 'Miscellaneous' (general) journal found for company "
                    "%(company)s. Create one so the payroll can be posted."
                )
                % {"company": (self.contract_id.company_id or self.env.company).display_name}
            )

        label = _("Payroll %(name)s") % {"name": self.name or ""}
        line_ids = []
        total_debit = 0.0
        total_credit = 0.0
        wages_line_index = None
        for key, debit, credit in raw_lines:
            debit = round(debit or 0.0, 2)
            credit = round(credit or 0.0, 2)
            if debit == 0.0 and credit == 0.0:
                continue
            if key == "sueldos_por_pagar":
                wages_line_index = len(line_ids)
            total_debit = round(total_debit + debit, 2)
            total_credit = round(total_credit + credit, 2)
            line_ids.append(
                (
                    0,
                    0,
                    {
                        "name": label,
                        "account_id": accounts[key].id,
                        "debit": debit,
                        "credit": credit,
                    },
                )
            )

        # Rounding residual goes to the wages-payable (balancing) line.
        residual = round(total_debit - total_credit, 2)
        if residual and wages_line_index is not None:
            vals = line_ids[wages_line_index][2]
            new_credit = round(vals["credit"] + residual, 2)
            if new_credit >= 0:
                vals["credit"] = new_credit
            else:
                vals["credit"] = 0.0
                vals["debit"] = round(-new_credit, 2)
        elif residual:
            # No payable line to absorb it: create one.
            line_ids.append(
                (
                    0,
                    0,
                    {
                        "name": label,
                        "account_id": accounts["sueldos_por_pagar"].id,
                        "debit": round(-residual, 2) if residual < 0 else 0.0,
                        "credit": round(residual, 2) if residual > 0 else 0.0,
                    },
                )
            )

        move = (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "journal_id": journal.id,
                    "date": self.date_end or fields.Date.today(),
                    "ref": self.name or "",
                    "line_ids": line_ids,
                }
            )
        )
        try:
            move.action_post()
        except Exception:
            _logger.exception(
                "l10n_ec.payslip '%s': could not post journal entry %s "
                "(kept as draft).", self.name, move.name,
            )
        self.write({"move_id": move.id, "journal_entry": move.name})
        _logger.info(
            "l10n_ec.payslip '%s': journal entry %s created (aporte personal "
            "$%.2f → %s).",
            self.name,
            move.name,
            self.iess_personal,
            accounts["iess_aporte_personal"].display_name,
        )

    # ------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            # Hard validations (art. 55 caps + deduction caps incl. loans)
            rec._check_overtime_limits()
            rec._check_deduction_limits()
            rec._create_account_move()
        self.write({"state": "done"})

    @api.model
    def create(self, vals):
        res = super(L10nEcPayslip, self).create(vals)
        res.name = f"{res.employee_id.name} - {res.date_start}"
        return res
