# RAPID DEVELOPMENT PLAN — odoo_saas_ecuador

**Target:** real 100% Ecuadorian compliance (SRI, IESS, Ministerio de Trabajo, SENAE, Superintendencia, Banco Central) + full MCP exposure so an AI agent can operate the whole Odoo ("hazme una factura para este cliente").
**Baseline audit:** 20 modules / 393 files. Verified against code, not docs.
**Cluster:** Docker Compose (Postgres 16 + Odoo 18 + workers + MCP gateway).

---

## 0. Compliance baseline (what 100% means)

| Regulator | Obligation |
|---|---|
| **SRI** | Facturación electrónica (codDoc 01/03/04/05/06/07), 49-digit clave + mod11, XAdES-BES, celcer/cel, retenciones IR+IVA, IVA 0/4/5/6/7, ATS, Formularios 101/102/103/104/107/108, RIMPE, ICE, ISD/Renta |
| **IESS** | 9.45% personal, 11.15% patronal, 0.5% SECAP, 0.5% IECE, techo 25×SBU, planillas, préstamos, fondos de reserva 8.33% |
| **Min. Trabajo** | SBU 2026 $482, décimo tercero/cuarto, utilidades 15%, vacaciones 15 d, horas +50/+100/+25 con topes, auxilio de cesantía, topes de descuento 40%/33.3% |
| **Superintendencia (NEC/NIIF)** | Plan de cuentas NEC 6 grupos, libros (Diario, Mayor, **Bancos**, Compras, Ventas, Retenciones, Caja, Inventarios y Balances), estados financieros + notas |
| **SENAE** | AD VALOREM, FODINFA 0.5%, ISD 5%, IVA importación, ECUAPASS |
| **BCE / Bancos** | Formatos Pichincha PAC/IBS, Guayaquil, produbanco, pacífico, IB/CENPE; Libro de Bancos; pago a proveedores |
| **MCP** | Todo el Odoo expuesto al agente (invoice, partner, withholding, payroll, stock, reports) |

---

## 1. Sprints

### Sprint 0 — Cluster (day 0)
- [x] Docker 29.7.2 / Compose v5.5.1 available
- `docker-compose.yml`: `db` (postgres:16-alpine), `odoo` (odoo:18, workers, `/mnt/extra-addons` = repo modules), `mcp` (pure-Python stdlib MCP gateway, zero pip deps)
- Odoo boots clean, modules install in dependency order, base DB seeded

### Sprint 1 — P0 SRI blockers (invoice would be rejected today)
| ID | Task | Module |
|---|---|---|
| S1.1 | Fix `codigo_porcentaje` mapping → 5% / exento / no-objeto emit wrong code (currently all fall to `0`) | `l10n_ec_edi/models/account_edi_format.py:56-65` |
| S1.2 | Add `edi_templates.xml` (+ all needed data) to `__manifest__.py` | `l10n_ec_edi` |
| S1.3 | Implement codDoc 03 `liquidacionCompra` v1.1.0 | `l10n_ec_edi` |
| S1.4 | Load dead CoA/tax CSVs **or** migrate dotted NEC codes into `template_ec.py` | `l10n_ec_base` |
| S1.5 | Fix bank wizard `slip.number` AttributeError + validation of accounts | `l10n_ec_bank_transfer` |

### Sprint 2 — Accounting setup per taxpayer (persona natural vs jurídica)
- Per-company settings (not global `ir.config_parameter`): ambiente, contribuyente especial, agente retención, obligado contabilidad, régimen
- Persona natural: electivo caja vs devengado; contribuyente especial: libros electrónicos + notación en factura
- RIMPE / régimen especial / nonprofit as valid selections
- Wire `chart_template` selection (currently dead field) and install NEC 6-group CoA with required codes (1.01.01.01 Caja … 4.01.04 Exportaciones)

### Sprint 3 — Books, estados financieros, formularios
- Libros: Diario, Mayor, **Bancos (BCE)**, Compras, Ventas, Retenciones, Caja, Inventarios y Balances, Socios, Actas
- Estados: Balance, Resultados, Flujo, Cambios en Patrimonio, Notas (SUPERCIAS)
- Formularios reales (no drafts): 101, 102, 103, **104 con datos**, 107, 108; **ATS wizard** (docs claim files that don't exist)

### Sprint 4 — Payroll / MinTrabajo / IESS
- Full IESS rates + techo in payslip; topes de descuento; auxilio de cesantía; topes de horas extras; `l10n_ec_sut` defined
- 30% SRI / 70% IESS split of IVA retention posted correctly

### Sprint 5 — Bancos + SENAE + periphery
- Real bank layouts (Pichincha PAC, Guayaquil, produbanco, pacífico, IB/CENPE), pago a proveedores, Libro de Bancos
- ECUAPASS linkage; POS SRI transmission; RIMPE/ICE/income-tax real logic

### Sprint 6 — MCP gateway (agent operates Odoo)
- Pure-Python MCP stdio server (no pip/npm — registries blocked) → Odoo JSON-RPC
- Tools: `detect_taxpayer`, `get_client_data`, `create_invoice` (asks for missing legal data), `post_invoice`, `send_ride`, `create_withholding`, `calculate_withholding`, `create_credit_note`, `generate_payslips`, `generate_iess_planilla`, `generate_ats`, `get_sales_summary`, `validate_ruc`, `record_payment`
- Rule engine enforced server-side: CF $50, 5-day retención, 7-day anulación, taxpayer-type detection on every invoice

---

## 2. Specialist agents (parallel)

| Agent | Track | Modules |
|---|---|---|
| A | SRI e-invoicing P0 fixes | `l10n_ec_edi`, `l10n_ec_sri` |
| B | Retenciones IR/IVA + 30/70 | `l10n_ec_withholding` |
| C | Plan de cuentas + setup persona natural/empresa | `l10n_ec_base`, `l10n_ec` |
| D | Libros + estados + formularios + ATS | `l10n_ec_reports`, `l10n_ec_asset`, `l10n_ec_income_tax` |
| E | Nómina / MinTrabajo / IESS | `l10n_ec_hr_payroll`, `l10n_ec_loans`, `l10n_ec_vacation`, `l10n_ec_sut` |
| F | Bancos + POS + stock + customs | `l10n_ec_bank_transfer`, `l10n_ec_pos`, `l10n_ec_stock`, `l10n_ec_customs` |
| G | MCP gateway + agent rules | `l10n_ec_base/mcp`, new `mcp_server/` |

**Ground rules for every agent:** run inside Docker (`docker compose exec odoo ...`), `--test-enable` on install, no docs-only changes, no new pip/npm deps, every fix must have a test in `tests/`.

## 3. Definition of done
1. `docker compose up` → all 20 modules install with 0 errors
2. `pytest`/Odoo test suite green (`tests/unit` + `tests/regulatory`)
3. A real invoice posts, signs, and returns a 49-digit clave (mock SRI)
4. MCP tool `create_invoice` succeeds from a client prompt end-to-end
5. Books + Form 104 + ATS produce real numbers
