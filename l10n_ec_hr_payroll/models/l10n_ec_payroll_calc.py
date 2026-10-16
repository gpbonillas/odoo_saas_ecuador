# -*- coding: utf-8 -*-
"""
Ecuador payroll — pure calculation library (NO Odoo imports).

Every legal number used by ``l10n_ec_hr_payroll`` / ``l10n_ec_loans`` /
``l10n_ec_sut`` lives here so it can be unit-tested standalone::

    python3 -m pytest tests/unit/test_payroll_calc_standalone.py

Legal sources (repo knowledge base, all figures re-verified against them):

===============================  ==========================================
Function group                   Source
===============================  ==========================================
IESS rates + 25xSBU ceiling      KB_IESS_2026.md §1-2,
                                 KB_IESS_CONTRIBUTIONS.md §1-2,
                                 docs/CUMPLIMIENTO_REGULATORIO.md §5.3
Overtime rates/topes (art. 55)   KB_MINISTERIO_TRABAJO_2026.md §6,
                                 CUMPLIMIENTO §5.5
Deduction caps 40% / 33.33%      DEVELOPMENT_PLAN.md (Min. Trabajo row)
Décimo 13 / 14                   KB_LABOR_SBU_DECIMOS.md §2-4,
                                 KB_MINISTERIO_TRABAJO_2026.md §4
Fondos de reserva 8.33%/13m      KB_LABOR_FONDOS_RESERVA.md §2-3,
                                 KB_IESS_2026.md §3
Liquidación components           KB_LABOR_TERMINATION.md §2-3
Auxilio de cesantía schedule     Sprint requirement (see CESANTIA_SCHEDULE —
                                 NOT present in the knowledge base,
                                 see report/README note in this module)
===============================  ==========================================
"""
from datetime import date

__all__ = [
    "iess_ceiling",
    "iess_contributions",
    "hour_rate",
    "overtime_amount",
    "check_overtime_caps",
    "check_daily_overtime",
    "check_weekly_overtime",
    "check_deduction_caps",
    "auxilio_cesantia_pct",
    "auxilio_cesantia_amount",
    "CESANTIA_SCHEDULE",
    "decimo_tercero_proporcional",
    "decimo_cuarto_proporcional",
    "decimo_cuarto_deadline",
    "decimo_cuarto_period",
    "normalize_decimo_cuarto_region",
    "fondos_reserva_amount",
    "vacaciones_pay",
    "vacaciones_accrued_days",
    "months_of_service",
    "years_of_service",
    "days_inclusive",
    "ACCOUNT_CODES",
    "ACCOUNT_NAME_PATTERNS",
    "APORTE_PERSONAL_ACCOUNT_CODES",
]

MONEY_EPS = 1e-9


def _money(amount):
    """Round to cents (half away from zero for the magnitudes we handle)."""
    return float(round(amount + (1e-9 if amount >= 0 else -1e-9), 2))


# ===========================================================================
# 1. IESS CONTRIBUTIONS (KB_IESS_2026.md §1-2)
#    Employee 9.45% | Employer 11.15% + SECAP 0.5% + IECE 0.5% = 12.15%
#    Ceiling 25 x SBU = $12,050 (SBU 2026 = $482)
# ===========================================================================

def iess_ceiling(sbu, multiplier=25):
    """Contribution ceiling: ``multiplier`` x SBU (25 x 482 = 12,050)."""
    if sbu <= 0 or multiplier <= 0:
        raise ValueError("SBU and ceiling multiplier must be positive")
    return float(sbu) * float(multiplier)


def iess_contributions(
    gross_income,
    ceiling,
    personal_pct,
    patronal_pct,
    secap_pct=0.0,
    iece_pct=0.0,
):
    """Compute every IESS contribution on the *contribution base*.

    The ceiling is applied to the base used for the contributions — the
    gross salary itself is never reduced by it::

        base      = min(gross_income, ceiling)
        personal  = base * 9.45%
        patronal  = base * 11.15%
        SECAP     = base * 0.5%
        IECE      = base * 0.5%
        employer  = base * 12.15%
    """
    if ceiling <= 0:
        raise ValueError("IESS contribution ceiling must be positive")
    base = max(0.0, min(float(gross_income), float(ceiling)))
    personal = _money(base * personal_pct / 100.0)
    patronal = _money(base * patronal_pct / 100.0)
    secap = _money(base * secap_pct / 100.0)
    icep = _money(base * iece_pct / 100.0)
    employer_total = _money(base * (patronal_pct + secap_pct + iece_pct) / 100.0)
    return {
        "base": base,
        "personal": personal,
        "patronal": patronal,
        "secap": secap,
        "iece": icep,
        "employee_total": personal,
        "employer_total": employer_total,
        "total_to_iess": _money(personal + employer_total),
    }


# ===========================================================================
# 2. OVERTIME (KB_MINISTERIO_TRABAJO_2026.md §6 / CT art. 55)
#    Hora = Sueldo mensual / 240 ($482 / 240 = $2.01)
#    Suplementaria +50% | Extraordinaria +100% | Nocturna +25%
#    Topes: 4 h suplementarias+extraordinarias por cada 24 h,
#           12 h suplementarias+extraordinarias por semana
# ===========================================================================

def hour_rate(monthly_wage):
    """KB §6: ``Hora = Sueldo mensual / 240`` (SBU 482 → $2.01/hora)."""
    if monthly_wage < 0:
        raise ValueError("Wage cannot be negative")
    return float(monthly_wage) / 240.0


def overtime_amount(hours, monthly_wage, recargo_pct):
    """Pay for ``hours`` at the ordinary hour rate plus ``recargo_pct``.

    ``recargo_pct`` is the legal surcharge: 50 (suplementaria),
    100 (extraordinaria) or 25 (nocturna).
    """
    if hours < 0:
        raise ValueError("Hours cannot be negative")
    return _money(hours * hour_rate(monthly_wage) * (1.0 + recargo_pct / 100.0))


def check_daily_overtime(day_hours, max_per_day=4.0, label=""):
    """CT art. 55: max 4 supplementary+extraordinary hours per 24h day."""
    if day_hours > max_per_day + MONEY_EPS:
        return (
            "%s: %.2f h de horas suplementarias/extraordinarias en un mismo "
            "día. El Código del Trabajo (art. 55) limita el trabajo en día "
            "consecutivo a 4 horas suplementarias y extraordinarias cada "
            "24 horas (máximo: %.0f h)."
            % (label or "Día", day_hours, max_per_day)
        )
    return None


def check_weekly_overtime(week_hours, max_per_week=12.0, label=""):
    """CT art. 55: max 12 supplementary+extraordinary hours per week."""
    if week_hours > max_per_week + MONEY_EPS:
        return (
            "%s: %.2f h de horas suplementarias/extraordinarias acumuladas. "
            "El Código del Trabajo (art. 55) limita el trabajo en semana "
            "consecutiva a 12 horas suplementarias y extraordinarias "
            "(máximo: %.0f h/semana)."
            % (label or "Semana", week_hours, max_per_week)
        )
    return None


def check_overtime_caps(total_hours, days, max_per_day=4.0, max_per_week=12.0):
    """Period-level (prorated) validation of both art. 55 caps.

    Without a daily timesheet the legal limits are prorated over the
    payslip period::

        daily  limit = max_per_day    x days
        weekly limit = max_per_week x days / 7

    Returns an error message (str) when exceeded, ``None`` otherwise.
    """
    if total_hours <= 0:
        return None
    days = float(days) if days and days > 0 else 1.0
    violations = []

    daily_avg = total_hours / days
    if daily_avg > max_per_day + MONEY_EPS:
        violations.append(
            "  - Promedio diario: %.2f h/día (máximo legal: %.0f horas "
            "suplementarias+extraordinarias por cada 24 horas)"
            % (daily_avg, max_per_day)
        )

    weekly_equiv = total_hours * 7.0 / days
    if weekly_equiv > max_per_week + MONEY_EPS:
        violations.append(
            "  - Promedio semanal: %.2f h/semana (máximo legal: %.0f horas "
            "suplementarias+extraordinarias por semana consecutiva)"
            % (weekly_equiv, max_per_week)
        )

    if not violations:
        return None
    return (
        "LÍMITE LEGAL DE HORAS EXTRAS EXCEDIDO (art. 55 Código del Trabajo)\n\n"
        + "\n".join(violations)
        + "\n\nHoras registradas en el periodo: %.2f sobre %d días.\n"
        "Reduzca las horas suplementarias/extraordinarias o divida el "
        "periodo antes de confirmar la planilla." % (total_hours, days)
    )


# ===========================================================================
# 3. DEDUCTION CAPS (DEVELOPMENT_PLAN.md: topes de descuento 40% / 33.3%)
#    * 40% of the liquid salary for IESS + other obligations.
#    * 33.33% in general assets/credit cases (Decreto).
#    * Legally-priority deductions (pensiones alimenticias) exempt, paid first.
# ===========================================================================

def check_deduction_caps(
    liquid_salary,
    total_deductions,
    credit_deductions,
    cap_pct=40.0,
    decreto_pct=33.33,
    priority_deductions=0.0,
):
    """Validate the monthly deduction caps.

    ``liquid_salary``   salario líquido = gross − IESS personal − income tax
    ``total_deductions`` every employee-side deduction of the period
                        (IESS personal + income tax + préstamos + anticipos
                        + others), *including* the priority amounts.
    ``credit_deductions``loans/advances type deductions (assets & credit
                        cases governed by the Decreto 33.33% cap).
    ``priority_deductions`` pensiones alimenticias — legally priority,
                        deducted first and exempt from the caps.

    Returns a list of human-readable violations (empty list = compliant).
    """
    violations = []
    if liquid_salary <= MONEY_EPS:
        return violations

    countable = max(0.0, float(total_deductions) - float(priority_deductions))
    limit = float(liquid_salary) * float(cap_pct) / 100.0
    if countable > limit + MONEY_EPS:
        violations.append(
            "Descuentos obligatorios del periodo: $%.2f — exceden el tope "
            "del %.2f%% del salario líquido ($%.2f = $%.2f × %.2f%%).\n"
            "  Descuentos no prioritarios: $%.2f\n"
            "  Pensiones alimenticias (exentas, derecho preferente): $%.2f"
            % (
                countable,
                cap_pct,
                limit,
                liquid_salary,
                cap_pct,
                countable,
                priority_deductions,
            )
        )

    limit_decreto = float(liquid_salary) * float(decreto_pct) / 100.0
    if credit_deductions > limit_decreto + MONEY_EPS:
        violations.append(
            "Descuentos por bienes/créditos (préstamos y anticipos): $%.2f — "
            "exceden el tope del %.2f%% del salario líquido ($%.2f) aplicable "
            "en casos generales de bienes y créditos (Decreto)."
            % (credit_deductions, decreto_pct, limit_decreto)
        )
    return violations


# ===========================================================================
# 4. AUXILIO DE CESANTÍA / LIQUIDACIÓN POR SALIDA
#    Schedule given by the sprint requirement (NOT found in the knowledge
#    base docs — KB_LABOR_TERMINATION.md does not mention auxilio de
#    cesantía). Encoded here as data so it can be overridden per parameter.
#    Base: total décimo tercero earned during the service relationship.
# ===========================================================================

CESANTIA_SCHEDULE = (
    (1, 5, 25.0),    # 1-5 años  → 25% del décimo tercero total
    (6, 10, 50.0),   # 6-10 años → 50%
    (11, 15, 75.0),  # 11-15 años → 75%
    (16, 20, 100.0), # 16-20 años → 100%
    (21, 24, 110.0), # 21-24 años → 110%
    (25, None, 120.0),  # ≥25 años → 120%
)


def auxilio_cesantia_pct(years_of_service, schedule=None):
    """Percentage of the accrued décimo tercero paid as auxilio de cesantía.

    0% until the first completed year of service (art. 196+ CT per the
    requirement: services >1 year), then the schedule above on *completed*
    years of service.
    """
    schedule = CESANTIA_SCHEDULE if schedule is None else schedule
    completed = int(max(0.0, years_of_service))
    if completed < 1:
        return 0.0
    for low, high, pct in schedule:
        if completed >= low and (high is None or completed <= high):
            return float(pct)
    return 0.0


def auxilio_cesantia_amount(
    decimo_13_total, years_of_service, schedule=None
):
    """Auxilio de cesantía = % × total décimo tercero earned in service."""
    pct = auxilio_cesantia_pct(years_of_service, schedule)
    return _money(decimo_13_total * pct / 100.0)


# ===========================================================================
# 5. DÉCIMOS (KB_LABOR_SBU_DECIMOS.md)
# ===========================================================================

def decimo_tercero_proporcional(total_earnings, divisor=12.0):
    """Décimo 13 = (earnings of the period) ÷ 12 — KB §2.1."""
    if divisor <= 0:
        raise ValueError("Décimo 13 divisor must be positive")
    return _money(total_earnings / float(divisor))


def decimo_cuarto_proporcional(sbu, days_worked):
    """Décimo 14 = (SBU ÷ 360) × days worked — KB §3.4 ($482/360×150 = 200.83)."""
    if days_worked < 0:
        raise ValueError("Days cannot be negative")
    return _money(float(sbu) / 360.0 * float(days_worked))


def normalize_decimo_cuarto_region(value, default="sierra"):
    """Map a province/region label to the décimo cuarto payment region.

    * ``costa`` / ``insular`` (Costa & Galápagos) → ``costa`` (pago 15 marzo)
    * ``sierra`` / ``oriente`` (Sierra & Amazonía) → ``sierra`` (pago 15 agosto)

    Unknown/empty values fall back to ``default`` (Sierra/Amazonía).
    """
    if not value:
        return default
    raw = str(value).strip().lower()
    costa_aliases = {
        "costa", "costa/galapagos", "costa/galápagos", "galapagos",
        "galápagos", "guayas", "manabi", "manabí", "los rios", "los ríos",
        "el oro", "esmeraldas", "santo domingo", "santo domingo de los "
        "tsáchilas", "santo domingo de los tsachilas", "santa elena",
        "insular",
    }
    if raw in costa_aliases:
        return "costa"
    sierra_aliases = {"sierra", "oriente", "amazonia", "amazonía"}
    if raw in sierra_aliases:
        return "sierra"
    return default


def decimo_cuarto_deadline(payment_year, region="sierra"):
    """KB §3.1: Costa/Galápagos → 15 marzo; Sierra/Amazonía → 15 agosto."""
    if normalize_decimo_cuarto_region(region) == "costa":
        return date(int(payment_year), 3, 15)
    return date(int(payment_year), 8, 15)


def _is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def decimo_cuarto_period(payment_year, region="sierra"):
    """KB §3.2 calculation periods.

    * Costa & Galápagos: 1 mar (año anterior) → 28/29 feb (año de pago)
    * Sierra & Amazonía: 1 ago (año anterior) → 31 jul (año de pago)
    """
    payment_year = int(payment_year)
    if normalize_decimo_cuarto_region(region) == "costa":
        return date(payment_year - 1, 3, 1), date(
            payment_year, 2, 29 if _is_leap(payment_year) else 28
        )
    return date(payment_year - 1, 8, 1), date(payment_year, 7, 31)


def days_inclusive(start, end):
    """Inclusive day count (start and end counted)."""
    if end < start:
        return 0
    return (end - start).days + 1


# ===========================================================================
# 6. FONDOS DE RESERVA (KB_LABOR_FONDOS_RESERVA.md §2-3)
#    8.33% after 13 months of service, administered by IESS (paid through
#    the monthly IESS planilla — not as cash in the rol de pagos).
# ===========================================================================

def fondos_reserva_amount(
    gross_income,
    rate_pct,
    months_of_service,
    eligibility_months=13,
    ceiling=None,
):
    """8.33% of the IESS contribution base, only from month 13 onwards."""
    if months_of_service < eligibility_months:
        return 0.0
    base = float(gross_income)
    if ceiling is not None:
        base = min(base, float(ceiling))
    base = max(0.0, base)
    return _money(base * rate_pct / 100.0)


# ===========================================================================
# 7. VACACIONES (CT art. 69 / KB_LABOR_TERMINATION.md §3.3)
# ===========================================================================

# CT art. 69: base 15 days/year; +1 day per completed year after year 5,
# capped so the extra never exceeds 15 days (total max 30 days).
VACATION_BASE_DAYS = 15.0
VACATION_SENIORITY_AFTER_YEARS = 5
VACATION_MAX_EXTRA_DAYS = 15.0


def vacaciones_pay(monthly_wage, unused_days):
    """Vacation pay = (monthly wage ÷ 24) × unused days — KB §3.3."""
    if unused_days < 0:
        raise ValueError("Unused vacation days cannot be negative")
    return _money(float(monthly_wage) / 24.0 * float(unused_days))


def vacaciones_accrued_days(
    months_worked,
    completed_years,
    base_days=VACATION_BASE_DAYS,
    seniority_after_years=VACATION_SENIORITY_AFTER_YEARS,
    max_extra_days=VACATION_MAX_EXTRA_DAYS,
):
    """Accrued vacation days at termination.

    * base: ``15 × (months worked ÷ 12)`` (KB_LABOR_TERMINATION §3.3)
    * seniority: +1 day per completed year after year 5, capped at +15
      (total never exceeds 30 days, CT art. 69 / vacation ledger rules).
    """
    months = min(max(0.0, months_worked), 12.0)
    base = base_days * months / 12.0
    extra = 0.0
    if completed_years > seniority_after_years:
        extra = min(
            float(completed_years - seniority_after_years), max_extra_days
        )
    return min(base + extra, base_days + max_extra_days)


# ===========================================================================
# 8. SERVICE TIME
# ===========================================================================

def months_of_service(start_date, end_date):
    """Completed months between two dates (0 when end <= start)."""
    if not start_date or not end_date or end_date <= start_date:
        return 0
    months = (end_date.year - start_date.year) * 12 + (
        end_date.month - start_date.month
    )
    if end_date.day < start_date.day:
        months -= 1
    return max(0, months)


def years_of_service(start_date, end_date):
    """Completed years of service (= completed months // 12)."""
    return months_of_service(start_date, end_date) // 12


# ===========================================================================
# 9. ACCOUNT CODES (chart of accounts lookup)
#
#    The loaded NEC chart (l10n_ec_base/models/template_ec.py) uses 6-digit
#    codes; the dead CSV (data/account.account.template.csv) and
#    docs/CUMPLIMIENTO_REGULATORIO.md §2.2 use dotted variants. Candidates
#    are tried in order AND validated against the account name so a wrong
#    account with the same numeric code can never be picked.
#
#    NOTE for l10n_ec_withholding (30/70 IVA retention split): the 70%
#    destined to the IESS must be credited to the SAME account payroll uses
#    for the aporte personal — i.e. ``ACCOUNT_CODES["iess_aporte_personal"]``
#    = ``2010301`` (loaded chart) / ``2.01.04.01`` / ``2.01.06.01``.
# ===========================================================================

ACCOUNT_CODES = {
    # --- liabilities -----------------------------------------------------
    "iess_aporte_personal": ("2010301", "2.01.04.01", "2.01.06.01"),
    "iess_aporte_patronal": ("2010302", "2.01.04.02", "2.01.06.02"),
    "iess_fondos_reserva": ("2010306", "2.01.06.03", "2.01.04.04"),
    "iess_prestamos": ("2010303", "2.01.04.03"),
    "impuesto_renta": ("2010501", "2.01.03.04"),
    "sueldos_por_pagar": ("2010309", "2.01.05.01"),
    "decimo_13_por_pagar": ("2010304", "2.01.05.02"),
    "decimo_14_por_pagar": ("2010305", "2.01.05.03"),
    # --- assets (deductions of company loans/advances) --------------------
    "otras_cuentas_por_cobrar": ("1020103", "1.01.02.03"),
    # --- expenses ---------------------------------------------------------
    "gasto_sueldos": ("5020101", "5.02.01"),
    "gasto_aporte_patronal": ("5020104", "5.02.02"),
    "gasto_fondos_reserva": ("5020107", "5.02.06"),
    "gasto_decimo_13": ("5020105", "5.02.03"),
    "gasto_decimo_14": ("5020106", "5.02.04"),
}

ACCOUNT_NAME_PATTERNS = {
    "iess_aporte_personal": r"aporte\s+personal",
    "iess_aporte_patronal": r"aporte\s+patronal",
    "iess_fondos_reserva": r"fondos?\s+de\s+reserva",
    "iess_prestamos": r"(ie?ss\s+pr[eé]stamos|pr[eé]stamos?\s+iess)",
    "impuesto_renta": r"impuesto\s+a\s+la\s+renta",
    "sueldos_por_pagar": r"sueldos?\s+por\s+pagar",
    "decimo_13_por_pagar": r"d[eé]cimo\s+tercer\w*\s+.*por\s+pagar",
    "decimo_14_por_pagar": r"d[eé]cimo\s+cuarto\w*\s+.*por\s+pagar",
    "otras_cuentas_por_cobrar": r"otras\s+cuentas\s+por\s+cobrar",
    "gasto_sueldos": r"sueldos\s+y\s+salarios",
    "gasto_aporte_patronal": r"aporte\s+patronal",
    "gasto_fondos_reserva": r"fondos?\s+de\s+reserva",
    "gasto_decimo_13": r"d[eé]cimo\s+tercer",
    "gasto_decimo_14": r"d[eé]cimo\s+cuarto",
}

#: Canonical codes for the IESS "Aporte Personal por Pagar" account — the
#: account payroll posts to and the account the 70% IVA retention destined
#: to the IESS must use as well.
APORTE_PERSONAL_ACCOUNT_CODES = ACCOUNT_CODES["iess_aporte_personal"]
