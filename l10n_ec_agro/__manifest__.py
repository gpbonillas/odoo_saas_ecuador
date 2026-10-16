# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Trazabilidad Agroalimentaria (Vertical)",
    "version": "18.0.1.1.0",
    "category": "Manufacturing/Vertical",
    "summary": "Trazabilidad seed-to-sale multi-cultivo (crop-agnóstico, D-05)",
    "description": """
Módulo vertical AGRO — capa propia (SRS-VERT, fase P1)
======================================================

Capa vertical OWN (D-06/D-08) sobre la capa legal compartida l10n_ec*.
Diseño: docs/srs/SRS_VERTICAL_AGRO_TRACEABILITY.md (§6).

* Catálogo de cultivos (`l10n_ec.agro.crop`): nuevo cultivo = entrada de
  catálogo, **cero cambio de esquema** (D-05 — nunca columnas por cultivo).
* Predios (`l10n_ec.agro.plot`) y ciclos de cultivo (`l10n_ec.agro.cycle`).
* Lotes (`stock.lot`) con atributos agro genéricos: cultivo, variedad,
  ciclo, fecha de cosecha, estado de laboratorio y registro sanitario.
* Análisis de laboratorio por lote (`l10n_ec.agro.analysis`): analito
  genérico (humedad, THC, CBD, residuos…) con límite y pass/fail.
* **Gate de laboratorio** (FR-AG-03): un lote con análisis reprobado no
  puede salir del stock interno.
* Eventos de trazabilidad append-only (`l10n_ec.agro.trace_event`, FR-AG-05):
  sin `write`/`unlink` — inmutabilidad estilo AUD.
* **P2**: plantilla vertical `templates/agro_medium.json` (categorías
  genéricas + params base, cargadas por el loader `l10n_ec_vertical`,
  FR-AG-10) y **guardrail FR-AG-14**: producto `l10n_ec_regulated` no se
  vende sin el parámetro `v.registro_sanitario`.
    """,
    "author": "Somatech.dev",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        "l10n_ec_base", "l10n_ec_stock", "l10n_ec_quality",
        "l10n_ec_vertical", "stock", "mrp", "sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_ec_agro_views.xml",
    ],
    "installable": True,
    "application": False,
}
