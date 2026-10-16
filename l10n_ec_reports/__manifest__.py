# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Reports (Libros, Formularios SRI, ATS, Estados Financieros)",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations/Reporting",
    "summary": "Statutory books, SRI forms with real calculations, ATS XML "
               "and SUPERCIAS financial statements",
    "description": """
Ecuador Tax & Statutory Reports Module
======================================

SRI / NEC / SUPERCIAS reporting for Ecuador:

* Statutory books (Libros)
  - Ventas, Compras, Retenciones, Bancos (BCE), Caja, Diario, Mayor,
    Inventarios y Balances (PDF + XLSX + CSV)
  - Libro de Socios and Libro de Actas (mercantile registers)
* SRI forms with REAL calculations (all math in ``report_lib``, unit tested)
  - Form 101 / 102 (Impuesto a la Renta)
  - Form 103 (Retenciones en la fuente)
  - Form 104 (IVA + ICE) - casilleros 411/412/415/421/422/480/520/601/699
  - Form 107 (Renta personas naturales, tabla progresiva 2026)
  - Form 108 (Notas de credito emitidas)
  - Gastos Personales (topes configurables por categoria, SBU)
* ATS (Anexo Transaccional Simplificado)
  - compras (+air, retenciones IVA, pagoExterior, formasDePago), ventas,
    ventasEstablecimiento, anulados, exportaciones, retenciones
  - REQ-ATS-001 validation before generation
* Estados financieros SUPERCIAS / NIIF
  - Situacion Financiera, Resultados, Flujos de Efectivo,
    Cambios en el Patrimonio, Notas (estructura NIC 1)

**Filing Deadlines**: ATS / 103 / 104 monthly, by RUC 9th digit;
Form 101 / 102 annual (SUPERCIAS statements by April 30).

**Regulatory Compliance**: SRI 2026, Res. NAC-DGERCGC25-00000043,
SUPERCIAS SCVS-INC-DNCDN-2019-0010
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        "l10n_ec_base",
        "l10n_ec_edi",
        "l10n_ec_withholding",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ats_template.xml",
        "report/form_templates.xml",
        "report/libro_templates.xml",
        "report/estados_financieros_templates.xml",
        "report/reports.xml",
        "wizard/l10n_ec_ats_wizard_views.xml",
        "wizard/libro_wizard_views.xml",
        "wizard/form_wizard_views.xml",
        "wizard/estado_financiero_wizard_views.xml",
        "views/l10n_ec_registers_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
