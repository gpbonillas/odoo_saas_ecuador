# -*- coding: utf-8 -*-
"""
Unit Tests: Ecuador payroll pure calculation library
====================================================

PURE PYTHON (stdlib `unittest` only) — no Odoo runtime required, because
``l10n_ec_hr_payroll/models/l10n_ec_payroll_calc.py`` is deliberately
importable standalone.

Run directly:
    python3 tests/unit/test_payroll_calc_standalone.py
or via pytest from the repo root:
    python3 -m pytest tests/unit/test_payroll_calc_standalone.py

Covers every legal schedule encoded in the calc library:
* IESS contributions (9.45% / 11.15% + 0.5% SECAP + 0.5% IECE) + 25xSBU ceiling
* Overtime hour rate and recargos (50/100/25) + art. 55 caps (4h/day, 12h/week)
* Deduction caps (40% general / 33.33% credit, pensiones alimenticias exempt)
* Auxilio de cesantía schedule (sprint requirement, NOT in the KB docs)
* Décimo 13 / 14 formulas, regional period + deadline (KB §2-4)
* Fondos de reserva 8.33% gated at 13 months
* Vacation pay / accrued days (art. 69, cap 30 days)
* Account code maps for journal-entry posting
"""
import os
import sys
import unittest
from datetime import date

# Make the pure calc library importable without Odoo.
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_CALC_DIR = os.path.join(_REPO_ROOT, "l10n_ec_hr_payroll", "models")
if _CALC_DIR not in sys.path:
    sys.path.insert(0, _CALC_DIR)

import l10n_ec_payroll_calc as calc  # noqa: E402

SBU_2026 = 482.0


class TestIESS(unittest.TestCase):
    """IESS rates + 25xSBU ceiling (KB_IESS_2026 §1-2)."""

    def test_ceiling_25x_sbu(self):
        self.assertEqual(calc.iess_ceiling(SBU_2026), 12050.0)

    def test_ceiling_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            calc.iess_ceiling(0)
        with self.assertRaises(ValueError):
            calc.iess_ceiling(SBU_2026, multiplier=0)

    def test_contributions_below_ceiling(self):
        res = calc.iess_contributions(
            gross_income=1000.0,
            ceiling=calc.iess_ceiling(SBU_2026),
            personal_pct=9.45,
            patronal_pct=11.15,
            secap_pct=0.5,
            iece_pct=0.5,
        )
        self.assertEqual(res["base"], 1000.0)
        self.assertEqual(res["personal"], 94.50)
        self.assertEqual(res["patronal"], 111.50)
        self.assertEqual(res["secap"], 5.00)
        self.assertEqual(res["iece"], 5.00)
        # employer total = 11.15 + 0.5 + 0.5 = 12.15%
        self.assertEqual(res["employer_total"], 121.50)
        self.assertEqual(res["total_to_iess"], 216.00)

    def test_contributions_capped_at_ceiling(self):
        res = calc.iess_contributions(
            gross_income=20000.0,  # way above 12,050
            ceiling=calc.iess_ceiling(SBU_2026),
            personal_pct=9.45,
            patronal_pct=11.15,
            secap_pct=0.5,
            iece_pct=0.5,
        )
        self.assertEqual(res["base"], 12050.0)
        self.assertEqual(res["personal"], 1138.73)  # 12050 × 9.45%
        self.assertEqual(res["employer_total"], 1464.08)  # 12050 × 12.15%

    def test_contributions_rejects_bad_ceiling(self):
        with self.assertRaises(ValueError):
            calc.iess_contributions(1000.0, 0, 9.45, 11.15)


class TestOvertime(unittest.TestCase):
    """Hour rate = wage/240; recargos 50/100/25 (KB_MINISTERIO_TRABAJO §6)."""

    def test_hour_rate(self):
        self.assertAlmostEqual(calc.hour_rate(482.0), 2.0083, places=4)
        self.assertAlmostEqual(calc.hour_rate(1000.0), 1000.0 / 240.0)

    def test_overtime_amount_recargos(self):
        # 2h suplementaria (+50%) on SBU: 2 × 2.0083 × 1.5 = 6.025 → 6.03
        self.assertEqual(calc.overtime_amount(2.0, 482.0, 50), 6.03)
        # 2h extraordinaria (+100%)
        self.assertEqual(calc.overtime_amount(2.0, 482.0, 100), 8.03)
        # 2h nocturna (+25%)
        self.assertEqual(calc.overtime_amount(2.0, 482.0, 25), 5.02)

    def test_negative_hours_rejected(self):
        with self.assertRaises(ValueError):
            calc.overtime_amount(-1.0, 482.0, 50)

    def test_daily_cap(self):
        self.assertIsNone(calc.check_daily_overtime(4.0))
        msg = calc.check_daily_overtime(5.0)
        self.assertIn("art. 55", msg)

    def test_weekly_cap(self):
        self.assertIsNone(calc.check_weekly_overtime(12.0))
        msg = calc.check_weekly_overtime(13.0)
        self.assertIn("12 horas", msg)

    def test_period_caps_prorated(self):
        # 30 days, 60 hours → 2h/day avg, 14h/week equiv → weekly violation
        msg = calc.check_overtime_caps(60.0, 30)
        self.assertIsNotNone(msg)
        self.assertIn("Promedio semanal", msg)
        # compliant case: 40h over 30 days = 1.33h/day, 9.33h/week
        self.assertIsNone(calc.check_overtime_caps(40.0, 30))
        # zero/negative hours → no violation
        self.assertIsNone(calc.check_overtime_caps(0.0, 30))


class TestDeductionCaps(unittest.TestCase):
    """40% / 33.33% of the liquid salary (DEVELOPMENT_PLAN Min. Trabajo)."""

    def test_within_caps(self):
        self.assertEqual(
            calc.check_deduction_caps(
                liquid_salary=1000.0,
                total_deductions=400.0,
                credit_deductions=333.30,  # exactly at the 33.33% cap
            ),
            [],
        )

    def test_over_40_percent(self):
        violations = calc.check_deduction_caps(
            liquid_salary=1000.0,
            total_deductions=450.0,
            credit_deductions=0.0,
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("40.00%", violations[0])

    def test_over_3333_credit(self):
        violations = calc.check_deduction_caps(
            liquid_salary=1000.0,
            total_deductions=400.0,
            credit_deductions=400.0,
        )
        self.assertEqual(len(violations), 1)
        self.assertIn("33.33%", violations[0])

    def test_pension_exempt_from_cap(self):
        # 500 total deductions but 200 is pension alimenticia → countable 300
        self.assertEqual(
            calc.check_deduction_caps(
                liquid_salary=1000.0,
                total_deductions=500.0,
                credit_deductions=0.0,
                priority_deductions=200.0,
            ),
            [],
        )

    def test_both_caps_violated(self):
        violations = calc.check_deduction_caps(
            liquid_salary=1000.0,
            total_deductions=500.0,
            credit_deductions=500.0,
        )
        self.assertEqual(len(violations), 2)

    def test_zero_liquid_salary_no_violation(self):
        self.assertEqual(
            calc.check_deduction_caps(0.0, 100.0, 100.0), []
        )


class TestAuxilioCesantia(unittest.TestCase):
    """Sprint schedule — NOT in the KB docs (reported separately)."""

    def test_zero_before_one_year(self):
        self.assertEqual(calc.auxilio_cesantia_pct(0), 0.0)
        self.assertEqual(calc.auxilio_cesantia_pct(0.99), 0.0)

    def test_schedule_boundaries(self):
        self.assertEqual(calc.auxilio_cesantia_pct(1), 25.0)
        self.assertEqual(calc.auxilio_cesantia_pct(5), 25.0)
        self.assertEqual(calc.auxilio_cesantia_pct(6), 50.0)
        self.assertEqual(calc.auxilio_cesantia_pct(10), 50.0)
        self.assertEqual(calc.auxilio_cesantia_pct(11), 75.0)
        self.assertEqual(calc.auxilio_cesantia_pct(15), 75.0)
        self.assertEqual(calc.auxilio_cesantia_pct(16), 100.0)
        self.assertEqual(calc.auxilio_cesantia_pct(20), 100.0)
        self.assertEqual(calc.auxilio_cesantia_pct(21), 110.0)
        self.assertEqual(calc.auxilio_cesantia_pct(24), 110.0)
        self.assertEqual(calc.auxilio_cesantia_pct(25), 120.0)
        self.assertEqual(calc.auxilio_cesantia_pct(40), 120.0)

    def test_amount(self):
        # 10 years of service, décimo 13 total = $1,000 → 50%
        self.assertEqual(calc.auxilio_cesantia_amount(1000.0, 10), 500.0)


class TestDecimos(unittest.TestCase):
    """KB_LABOR_SBU_DECIMOS §2-4."""

    def test_decimo_13(self):
        self.assertEqual(calc.decimo_tercero_proporcional(1000.0), 83.33)
        with self.assertRaises(ValueError):
            calc.decimo_tercero_proporcional(1000.0, divisor=0)

    def test_decimo_14_kb_example(self):
        # KB §3.4: $482/360 × 150 días = $200.83
        self.assertEqual(calc.decimo_cuarto_proporcional(SBU_2026, 150), 200.83)

    def test_decimo_14_full_year(self):
        # Full year (360 days divisor): one SBU
        self.assertEqual(calc.decimo_cuarto_proporcional(SBU_2026, 360), 482.00)

    def test_region_normalization(self):
        self.assertEqual(calc.normalize_decimo_cuarto_region("Guayas"), "costa")
        self.assertEqual(calc.normalize_decimo_cuarto_region("Manabí"), "costa")
        self.assertEqual(
            calc.normalize_decimo_cuarto_region("Galápagos"), "costa"
        )
        self.assertEqual(calc.normalize_decimo_cuarto_region("Pichincha"), "sierra")
        self.assertEqual(calc.normalize_decimo_cuarto_region("Loja"), "sierra")
        self.assertEqual(calc.normalize_decimo_cuarto_region("Zona 5"), "sierra")
        self.assertEqual(calc.normalize_decimo_cuarto_region(""), "sierra")
        self.assertEqual(calc.normalize_decimo_cuarto_region(None), "sierra")

    def test_deadlines_kb_31(self):
        # Costa/Galápagos → 15 marzo; Sierra/Amazonía → 15 agosto.
        # (The old SUT wizard comment said "Sept 15" — wrong.)
        self.assertEqual(
            calc.decimo_cuarto_deadline(2026, "costa"), date(2026, 3, 15)
        )
        self.assertEqual(
            calc.decimo_cuarto_deadline(2026, "sierra"), date(2026, 8, 15)
        )

    def test_periods_kb_32(self):
        start, end = calc.decimo_cuarto_period(2026, "costa")
        self.assertEqual((start, end), (date(2025, 3, 1), date(2026, 2, 28)))
        start, end = calc.decimo_cuarto_period(2028, "costa")  # leap year
        self.assertEqual((start, end), (date(2027, 3, 1), date(2028, 2, 29)))
        start, end = calc.decimo_cuarto_period(2026, "sierra")
        self.assertEqual((start, end), (date(2025, 8, 1), date(2026, 7, 31)))

    def test_days_inclusive(self):
        self.assertEqual(calc.days_inclusive(date(2026, 1, 1), date(2026, 1, 1)), 1)
        self.assertEqual(calc.days_inclusive(date(2026, 1, 1), date(2026, 1, 31)), 31)
        self.assertEqual(calc.days_inclusive(date(2026, 2, 1), date(2026, 1, 1)), 0)


class TestFondosReserva(unittest.TestCase):
    """8.33% after 13 months, via IESS planilla (KB_FONDOS_RESERVA §2-3)."""

    def test_not_eligible_before_13_months(self):
        self.assertEqual(
            calc.fondos_reserva_amount(1000.0, 8.33, months_of_service=12), 0.0
        )

    def test_eligible_from_13_months(self):
        self.assertEqual(
            calc.fondos_reserva_amount(1000.0, 8.33, months_of_service=13), 83.30
        )

    def test_ceiling_applied(self):
        # 20,000 gross, ceiling 12,050 → 8.33% of 12,050 = 1003.77
        self.assertEqual(
            calc.fondos_reserva_amount(
                20000.0, 8.33, months_of_service=24,
                ceiling=calc.iess_ceiling(SBU_2026),
            ),
            1003.77,
        )


class TestVacaciones(unittest.TestCase):
    """CT art. 69: 15 days base, +1/year after year 5, cap 30."""

    def test_pay_formula(self):
        # KB §3.3: (wage / 24) × unused days
        self.assertEqual(calc.vacaciones_pay(480.0, 10), 200.00)

    def test_pay_rejects_negative(self):
        with self.assertRaises(ValueError):
            calc.vacaciones_pay(480.0, -1)

    def test_accrued_days_base(self):
        # 12 months, <5 years → 15 days
        self.assertEqual(calc.vacaciones_accrued_days(12, 3), 15.0)
        # 6 months → 7.5 days
        self.assertEqual(calc.vacaciones_accrued_days(6, 0), 7.5)

    def test_accrued_days_seniority_cap(self):
        # 10 years → +5 days (capped at +15)
        self.assertEqual(calc.vacaciones_accrued_days(12, 10), 20.0)
        # 30 years → +15 (cap) → total 30
        self.assertEqual(calc.vacaciones_accrued_days(12, 30), 30.0)
        # 60 years → still capped at 30
        self.assertEqual(calc.vacaciones_accrued_days(12, 60), 30.0)

    def test_service_time(self):
        self.assertEqual(
            calc.months_of_service(date(2024, 1, 15), date(2026, 1, 14)), 23
        )
        self.assertEqual(
            calc.months_of_service(date(2024, 1, 15), date(2026, 1, 15)), 24
        )
        self.assertEqual(
            calc.years_of_service(date(2020, 1, 1), date(2026, 6, 1)), 6
        )
        self.assertEqual(calc.months_of_service(None, date(2026, 1, 1)), 0)


class TestAccountMaps(unittest.TestCase):
    """Account code candidates used by the payslip journal posting."""

    def test_aporte_personal_codes(self):
        self.assertEqual(
            calc.APORTE_PERSONAL_ACCOUNT_CODES,
            calc.ACCOUNT_CODES["iess_aporte_personal"],
        )
        self.assertIn("2010301", calc.APORTE_PERSONAL_ACCOUNT_CODES)

    def test_every_key_has_name_pattern(self):
        for key in calc.ACCOUNT_CODES:
            self.assertIn(key, calc.ACCOUNT_NAME_PATTERNS, key)

    def test_loaded_chart_codes_present(self):
        # 6-digit codes from l10n_ec_base/models/template_ec.py
        for key, expected in (
            ("iess_aporte_personal", "2010301"),
            ("iess_aporte_patronal", "2010302"),
            ("iess_fondos_reserva", "2010306"),
            ("gasto_sueldos", "5020101"),
        ):
            self.assertEqual(calc.ACCOUNT_CODES[key][0], expected, key)


class TestCitation(unittest.TestCase):
    """The SBU resolution must be cited consistently repo-wide (MDT-2025-195)."""

    def test_payroll_data_cites_mdt_2025_195(self):
        data_file = os.path.join(
            _REPO_ROOT,
            "l10n_ec_hr_payroll",
            "data",
            "l10n_ec_payroll_data.xml",
        )
        with open(data_file, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn(
            "MDT-2025-195",
            content,
            "SBU param must cite MDT-2025-195 (repo-wide consensus)",
        )
        self.assertNotIn(
            "MDT-2025-227",
            content,
            "Stale MDT-2025-227 citation must be gone",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
