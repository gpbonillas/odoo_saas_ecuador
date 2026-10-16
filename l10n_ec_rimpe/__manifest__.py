# -*- coding: utf-8 -*-
{
    "name": "Ecuador - RIMPE Regime",
    "version": "1.0",
    "category": "Accounting/Localizations",
    "summary": "Manage RIMPE (Emprendedores & Negocios Populares)",
    "description": """
        Implements the RIMPE regime (Régimen Simplificado para Emprendedores
        y Negocios Populares), previsto en la LRTI; normas de aplicación:
        Resolución SRI NAC-DGERCGC23-00000004 (RO 257-2S, 27-feb-2023).
        Supports:
        - Partner Classification (Popular vs Entrepreneur)
        - Document Type 02 (Notas de Venta) logic
        - Retention codes per SRI Tabla 19 (332=0% Negocios Populares,
          343=1% Emprendedores; Res. NAC-DGERCGC26-00000009)
        - Retention Restrictions (0% for Popular)
    """,
    "author": "Somatech Ecuador",
    "depends": ["account", "l10n_ec_base", "l10n_ec_withholding"],
    "data": [
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
