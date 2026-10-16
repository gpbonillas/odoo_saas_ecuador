# -*- coding: utf-8 -*-
{
    "name": "Ecuador - Bank Cash Management (Transferencias)",
    "version": "18.0.2.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Batch payment files (TXT) for Ecuadorian banks: payroll, "
    "supplier payments and salary advances",
    "description": """
Ecuador Bank Transfer - Cash Management
=======================================

Generates the `.txt` batch files used by Ecuadorian banks for:

* **Nómina** — bulk payroll payments (from payslips)
* **Adelantos de sueldo** — salary advances
* **Pago a Proveedores** — supplier payments (from vendor bills)

Supported bank layouts (one generator class per bank, each documented
and marked `TODO: validate against bank spec` — none are bank-certified
yet):

1.  Banco Pichincha (Cash Management)
2.  Banco Guayaquil (Multicash)
3.  produbanco (Multiacceso)
4.  Banco Pacífico
5.  Banco del Austro
6.  Banco Bolivariano
7.  Banco del Loja
8.  Banco Internacional
9.  IB / CENPE (transferencia interbancaria BCE)
10. Genérico (fallback)

Also provides a per-bank-account type (ahorro/corriente) and reusable
Libro de Bancos data helpers (the report itself lives in
`l10n_ec_reports`).
    """,
    "author": "Somatech.dev",
    "depends": ["l10n_ec_hr_payroll", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_ec_bank_transfer_data.xml",
        "views/bank_transfer_view.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
