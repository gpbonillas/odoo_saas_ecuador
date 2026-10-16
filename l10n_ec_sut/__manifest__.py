# -*- coding: utf-8 -*-
{
    "name": "Ecuador - SUT Reports (MDT)",
    "version": "18.0.1.0.0",
    "category": "Human Resources/Legal",
    "summary": "Generate TXT/XML for Ministry of Labor (Salarios en Línea)",
    "description": """
Ecuador SUT Reports
===================

Generates compliance files for the **Sistema Único de Trabajo (SUT)**:

1. **Décimo Tercero (13th) Report**: CSV/TXT extract with proportional
   value per payslip (earnings ÷ 12 — KB_LABOR_SBU_DECIMOS §2.1).
2. **Décimo Cuarto (14th) Report**: CSV/TXT extract with the legal
   payment region (Costa/Galápagos = 15 marzo; Sierra/Amazonía =
   15 agosto — KB_LABOR_SBU_DECIMOS §3.1) and the deadline date.
3. **Utilidades (art. 97-104)**: 15% of the fiscal-year net profit
   (auto-calculated from the posted P&L) split 10% proportional to
   days worked + 5% by cargas familiares. Filing deadline: April 15.

Scope note: this module produces *reporting extracts* only. The legal
math itself lives in ``l10n_ec_hr_payroll.models.l10n_ec_payroll_calc``
so it is shared with the payslip engine and unit-tested standalone.
It does **not** file to the MDT SUT web portal (no electronic
signature/transport here) — the generated file is uploaded manually.
    """,
    "author": "Somatech.dev",
    "depends": ["l10n_ec_hr_payroll"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/sut_report_wizard_view.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
