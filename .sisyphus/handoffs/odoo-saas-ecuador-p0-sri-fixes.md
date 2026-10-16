# Handoff: P0 SRI Electronic-Invoicing Fixes (odoo_saas_ecuador)

Session date: 2026-10-15. Status: **implementation complete, all local
verification green; Odoo-runtime tests written but NOT executed** (Docker
compose is down; do not wait for it).

## Mission
Fix 4 P0 SRI blockers in `l10n_ec_edi/` + `l10n_ec_sri/` (codigoPorcentaje
mapping, missing manifest data entries, missing codDoc 03 liquidacionCompra),
verify/fix access key, endpoints, XAdES, CF rules, codDoc 04/05/06/07
templates. Report table + REMAINING BLOCKERS at the end.

## What was done (all verified locally)

### l10n_ec_edi
- `models/account_edi_format.py` (rewritten around 4 new helpers):
  - `_get_sri_tax_codes(tax)` -> (codigo, codigoPorcentaje): catalog-driven
    (`l10n_ec.tax.code` by `tax_id` link, then type+rate search with 0%
    disambiguation "0"/"6"/"7" by name), ICE keeps ("3","3023"), rate
    fallback map {0:"0",5:"5",12:"2",14:"3",15:"4"} + warning/fallback "0".
  - `_get_l10n_ec_line_taxes(invoice)`: per-line impuesto entries; untaxed
    lines get one IVA 0% entry (LC XSD requires >=1 <impuesto> per detalle).
  - `_compute_tax_aggregates` now groups the per-line entries (adds "tarifa"
    key; totals stay consistent with detalles).
  - `_get_l10n_ec_modified_doc(invoice)`: NC/ND modified-doc values from
    reversed_entry_id/debit_origin_id (fallbacks cod "01",
    num "001-001-000000000", motivo=narration or "Documento afectado").
  - `_get_l10n_ec_edi_values`: populates `tax_map` (was always {}), adds
    `line_taxes`, zero-rated totals fallback, `vals['modificado']`.
  - `_get_l10n_ec_edi_template` + `_export_l10n_ec_edi`: template by latam
    doc code 01/03/04/05 (fallback by move_type for refunds).
  - `_get_l10n_ec_identifier_code`: vat-length fallback when
    l10n_ec_identifier_type unset (13->04, 10->05).
- `models/res_partner.py` (new): `_l10n_ec_is_forced_to_keep_accounting()`
  (special->True; 10-digit->False; 13-digit->3rd digit in 6789; else
  company_type).
- `models/account_move.py`:
  - `_generate_access_key` hardened: ruc/estab/pto digit-sanitized, seq
    digits-only last-9 zfill, doc-type fallback 04/01, UserError(ValidationError)
    on bad company RUC or non-49-digit key.
  - `_compute_l10n_latam_document_type` override: draft in_invoice (no
    debit_origin_id) with ec_dt_03 available -> codDoc 03 iff vendor not
    obligated; restores ec_dt_01 when obligated.
- `models/sri_endpoints.py` (new, pure python): sri_environment_key /
  sri_config_key / sri_fallback_url.
- `models/sri_service.py`: `_get_service_url(service, environment)` =
  ir.config_parameter (l10n_ec.sri_{reception,authorization}_url_{test,prod})
  -> official celcer/cel fallback. `send_document` passes its environment
  arg; `check_authorization(access_key, environment=None)` defaults to the
  company environment. Company URL fields no longer used for routing.
- `data/edi_templates.xml`: factura detalle impuestos now use precomputed
  line_taxes (codigo from SRI code, tarifa present); NEW templates
  `l10n_ec_edi_liquidacion_compra` (1.1.0, PROVEEDOR fields),
  `l10n_ec_edi_nota_credito` (1.1.0, incl. REQUIRED totalConImpuestos),
  `l10n_ec_edi_nota_debito` (1.0.0, impuestos inside infoNotaDebito +
  required motivos, NO detalles). agenteRetencion truncated to [:8]
  (SRI maxLength).
- `__manifest__.py`: added `data/edi_templates.xml`.
- `models/__init__.py`: added res_partner import.

### l10n_ec_sri
- `models/l10n_ec_sri_xml.py`: env mapped "1"/"2" (was raw "test"/"production"
  -> key length != 49); journal serie fallback 001001 (was AttributeError on
  nonexistent journal fields); seq digits-only; doc-type fallback;
  `render_xml` delegates to `account.edi.format._export_l10n_ec_edi`
  (old target template id `l10n_ec_sri.xml_invoice` never existed).
  `_get_modulo_11` kept (tests use it).
- `models/account_move.py`: `action_check_sri` reads `response["xml"]`
  (was "authorized_xml") and handles str/bytes before b64encode.
- `__manifest__.py`: added `views/account_move_xml_template.xml` +
  `data/account.tax.group.csv`.

### Tests (repo-root tests/unit/, registered in __init__.py)
- Pure python (run standalone, ALL PASSING now):
  `python3 tests/unit/test_access_key.py` (7 tests),
  `test_sri_endpoints.py` (10), `test_manifest_data.py` (10: manifest
  coverage both modules, XML well-formedness, template root/version/codDoc,
  no hardcoded percentage codes, LC PROVEEDOR fields, ND motivos).
- Odoo runtime (TransactionCase, NOT executed — Docker down):
  `test_sri_tax_codes.py` (mapping incl. 15->"4", 5->"5", 0->"0",
  no-objeto->"6", exento->"7", ICE, fallbacks, aggregates, tax_map),
  `test_liquidacion_compra.py` (detection, bill doc type 03/01, LC/factura/NC
  XML structure). Valid partner vats (sólo IDs aprobados D-04, CHG-2026-006):
  cedula "1713488185", natural RUC "1713488185001", company RUC "1793125212001".

## Verification evidence (all run this session)
- `python3 -m py_compile` on every touched/new .py: OK.
- `xml.dom.minidom.parse` on edi_templates.xml: OK.
- XSD validation (one-off script
  /private/var/folders/2g/.../T/opencode/render_check.py; patched official
  SRI XSDs + W3C xmldsig schema in .../T/opencode/sri_xsd_local/): all 4
  templates render XSD-VALID vs factura_V1.1.0 / LiquidacionCompra_V1.1.0 /
  NotaCredito_V1.1.0 / NotaDebito_V1.0.0. The renderer is a QWeb-subset
  emulator (t-out/t-if/t-foreach, transparent <t>) — not proof of QWeb
  runtime behavior, but strong schema evidence.
- The 3 standalone test suites: OK (27 tests total).

## Remaining blockers (report section, not fixed here)
1. Dead data files in l10n_ec_sri (unloadable in Odoo 18, excluded in
   test_manifest_data.EXCLUDED_UNLOADABLE): data/l10n_ec_chart_data.xml
   (account.chart.template is AbstractModel in 18; property_* fields gone),
   data/account.account.template.csv, data/account.tax.template.csv
   (models removed in Odoo 18). Delete or migrate (S1.4/agent C).
2. codDoc 07: l10n_ec_sri/views/l10n_ec_retention_xml_template.xml emits
   comprobanteRetencion version="1.0.0" while current SRI schema is
   V2.0.0 (l10n_ec_withholding/data/retention_template.xml already uses
   2.0.0). Duplicated/shadowed implementation — coordinate with agent B.
3. l10n_ec_edi + l10n_ec_sri both define account.move.action_send_sri;
   l10n_ec_sri (loaded later, no super()) shadows l10n_ec_edi's version.
   Both paths now work (render_xml delegates), but consolidation needed.
4. Existing shared tests used invalid vats (RUCs falsos, purgados en
   CHG-2026-006) that fail l10n_ec_base's _check_l10n_ec_vat —
   pre-existing, l10n_ec_base/agent C scope.
5. Certificate content bytes/b64 question: l10n_ec_certificate.action_validate
   b64decodes content but sri_signer.sign_xml only b64decodes str (Binary
   field reads back as bytes) — potential double-encoding bug, unverified
   without a runtime.
6. Nota de Débito official schema is V1.0.0 (repo docs claiming 1.1.0 are
   wrong). Template follows the real schema.
7. LiquidacionCompra detalle impuesto `codigo` pattern is [2] (IVA only) in
   the SRI XSD; an ICE line in a liquidacion de compra would fail SRI XSD
   validation (documented limitation, no runtime guard).
8. Odoo-runtime tests (test_sri_tax_codes.py, test_liquidacion_compra.py)
   must be run once Docker is up:
   `docker compose run --rm odoo odoo -d test --test-tags /l10n_ec_edi --stop-after-init`

## Git state
My changes are confined to l10n_ec_edi/, l10n_ec_sri/, tests/unit/. The
working tree also contains pre-existing uncommitted changes in other modules
(l10n_ec_bank_transfer, l10n_ec_customs, l10n_ec_hr_payroll, l10n_ec_reports,
l10n_ec_stock, l10n_ec_withholding, ...) — NOT mine, do not touch/revert.
