# SRS — Vertical AGRO: Sistema de Trazabilidad Agroalimentaria Multi-Cultivo

**Document ID:** SRS-VERT-AGRO-2026-001
**Version:** 1.1 · **Date:** 2026-10-16 · **Status:** Design approved (docs phase — no code yet)
**Normative reference:** ISO/IEC/IEEE 29148:2018 (requirements engineering); collection rules `docs/ISO/README.md` (`[VERIFY]` policy, DOC-05 registration)
**Related:** ISO-EC-09 (vertical/wizard architecture) · **SRS-BRIDGE-2026-001** `SRS_SOMATECH_ODOO_BRIDGE.md` (D-08/D-09: capa de integración + UI/UX encima) · N-01 `SRS_WIZARD_PARAMETERS.md` v1.1 · **RES-VERT-2026-001** `RESEARCH_TRACEABILITY_FEATURE_CATALOG.md` (OpenTHC 29 módulos + Verdnt/FSMA-204 feature catalog → D-06/D-07) · `SRS_BUSINESS_TEMPLATES.md` · `SRS_PARTNER_TYPES.md` · ISO-EC-04 §5.4 · ISO-EC-06 §3.8 · ISO-EC-10 FR-LE-50 · ISO-EC-11 §3.1

---

## 1. Purpose and Scope

Defines the first **industry vertical** implemented under the `INDUSTRIA × TAMAÑO × CAPACIDADES`
architecture (ISO-EC-09 §3): a **full, end-to-end traceable agri-food system for ANY type of
crop** (coffee, cacao, banana, lino, hemp, fruit, vegetables, spices, livestock-derived goods…),
and the **own Odoo module layer** (`l10n_ec_agro`) we must build on top of the shared `l10n_ec*`
legal layer.

**Scope rule (operator, D-05):** the vertical is **crop-agnostic**. Crop type is *data*
(catalog value on cycle/lot + analysis analytes), never schema. Hemp/CBD is simply the
reference tenant's product line — an *instance* exercising the generic model, and the
hemp-specific regulatory overlay (§11) applies **only** to tenants that grow that crop.

* **In scope:** vertical definition (generic multi-crop), reference tenant (CANNACHAIN S.A.S.),
  seed-to-sale traceability model, own-module specification, wizard/parameter integration,
  MCP tooling plan, SRI test-environment emission path, compliance rows (with `[VERIFY]`,
  split generic vs crop-specific overlay).
* **Out of scope:** writing code (P1+ phases, §12), crop-specific legal advice (all specifics
  `[VERIFY]`), production emission (requires tenant `.p12`, §10 FR-AG-13).

**Ground rules inherited** (`DEVELOPMENT_PLAN.md`): no new pip/npm deps; all code live-mounted
via Docker volumes; Odoo built from source; 8 GB RAM cluster cap (ISO-EC-03).

## 2. Definitions and Acronyms

| Term | Definition |
|---|---|
| Seed-to-sale | Full chain: inputs purchase → cultivation → harvest → processing → storage → sale, each stage lot-stamped. |
| Crop (cultivo/especie) | Any cultivated species. Stored as **catalog data** on cycle/lot (`v.cultivos`), never as schema or module variant. |
| Analyte | Measured substance per lab analysis (humidity, THC, CBD, pesticide residue, mycotoxins…). Arbitrary rows in `l10n_ec.agro.analysis` — this is how crop-specific limits (e.g. THC ceiling) are modeled generically. |
| Lote (lot) | Atomic traceability unit (`stock.lot` + agro attributes, §6). |
| Genealogy | Upstream (components/BOM) and downstream (moves/invoices/clients) query for one lot. |
| Recall | Given lot/date, list every electronic invoice + partner affected; enable credit note. |
| CF | Consumidor Final RUC `9999999999999` (see `mcp_server/rules.py` `CF_RUC_DEFAULT`). |
| RIDE / Clave de acceso | SRI-printable receipt / 49-digit access key (TEN-03, ISO-EC-09). |
| CELCER | SRI test environment (`celcer.sri.gob.ec`), ambiente `1=PRUEBAS`. |
| ARCSA / AGROCALIDAD | Ecuadorian sanitary / agro-food regulators (rows CM-40..42, `[VERIFY]`). |
| ICE | Impuesto a los Consumos Especiales (applicability to CBD products `[VERIFY]`). |

## 3. Reference Tenant (live-verified, SRI 2026-10-16)

Endpoint: `GET https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc?ruc=…` (schema per `SRS_WIZARD_COMPANY_EC.md` §4.1, corrected this date).

| Field | Value | Source |
|---|---|---|
| RUC | `1793125212001` | SRI live (operator-given test ID, exclusive) |
| Razón social | `CANNACHAIN S.A.S.` (trailing space in API payload — trim on ingest) | SRI live |
| Tipo contribuyente | `SOCIEDAD` (3rd digit 9 → persona jurídica, FR-LE-50) | SRI live |
| Estado | **`ACTIVO`** (`estadoContribuyenteRuc`) — wizard gate; INACTIVO blocks | SRI live |
| Régimen | `GENERAL` | SRI live |
| Obligado contabilidad | **`SI`** (`obligadoLlevarContabilidad`) → size ≥ medium (N-01 §④) | SRI live |
| Contribuyente especial / agente retención | `NO` / `NO` | SRI live |
| Actividad económica | `CULTIVO DE LINO Y CÁÑAMO.` (text only — **endpoint returns no CIIU code**, §9) | SRI live |
| Fecha inicio actividades | 2021-02-26 (actualización 2025-01-15) | SRI live (`informacionFechasContribuyente`, nested) |
| Representante legal | `ENCALADA EGUEZ VICTOR AUGUSTO`, cédula `1716341274` | SRI live (`representantesLegales`, nested list → pre-fills §9 users) |
| `contribuyenteFantasma` / `transaccionesInexistente` / `motivoCancelacionSuspension` | `NO` / `NO` / `null` (red-flag fields if ever ≠ NO/NO/empty) | SRI live |
| Nombre comercial / dirección / teléfono / correo | **Not returned by endpoint** → wizard step ① asks (`USER`) | SRI live |
| Secondary test ID (persona natural) | cédula `1713488185` → RUC `1713488185001` (cédula + `001`, §7) | SRI live |

**Decisions (operator, 2026-10-16):**
*D-01* Tenant = CANNACHAIN S.A.S. (agricultural company — grows hemp among crops; CBD is
**one product line**, not the vertical's scope). *D-02* Natural-person RUC = cédula + `001`
(system standard). *D-03* Cédula may **buy**; **selling/emitting requires an activated RUC**
(§7). *D-04* Only the two operator-given IDs above are valid test identities; any other RUC
in tests/docs is a bug (both older invented IDs confirmed non-existent: SRI returns
empty/non-JSON body). *D-05* The `agro` vertical must support **any type of crop**;
hemp/CBD specifics are a tenant-level overlay (§11), never hardwired into the model.

## 4. Overall Description

### 4.1 Actors

| Actor | Role |
|---|---|
| Producer (CANNACHAIN) | Buys inputs, cultivates **any crop** (hemp among them), processes, stores, sells crop products (incl. CBD line), emits electronic invoices. |
| Operator/manager | Runs wizard, sets lots/params, users (from legal representative). |
| AI agent (MCP) | Reads stock/lots/invoices, creates partners/invoices, plans future trace tools (§10). |
| Laboratory | Issues analysis per lot (manual upload; no external API integration in P1). |
| Final customer | Buys with cédula (purchaser) or RUC; ≤ $50 → Consumidor Final flow. |
| SRI (CELCER) | Receives/authorizes comprobantes in test ambiente. |
| Regulators | SRI; ARCSA/AGROCALIDAD for sanitary/phyto rules `[VERIFY]` (ISO-EC-06 §3.8). |

### 42. System context (external interfaces)

```
                    ┌──────────────────────────────┐
   wizard (UI) ────►│ Odoo 18 + l10n_ec* (shared)  │◄──── MCP gateway (18 tools, stdio)
   operator         │  stock / mrp / account / POS │      agent: read ⇄ write(dry-run)
                    │  + l10n_ec_agro (OWN layer)  │
                    └──────────────┬───────────────┘
              SRI catastro (GET)   │   SRI CELCER (recepción/autorización, .p12 XML sign)
              srienlinea (§3)      ▼   celcer.sri.gob.ec (ambiente 1 = PRUEBAS)
```

Constraints: USD-only (dolarization), 8 GB RAM cap, no new dependencies, live-mounted modules
(no rebuild), secrets (`.p12`) never in git — `secrets/` mode 600.

## 5. Traceability System Design (seed-to-sale)

| Stage | Trigger | Lot stamping | Compliant artifact |
|---|---|---|---|
| A. Inputs purchase | PO receipt | Incoming lot (semillas, fertilizantes) | Supplier invoice XML + retentions |
| B. Cultivation | Cycle start/end | Cycle ↔ plot ↔ incoming lots | — (own models, §6) |
| C. Harvest | Cycle close | New raw lot (kg, date) | — |
| D. Processing | MRP BOM (any crop: e.g. flores → aceite, café cereza → tostado, cacao → nibs) | Consumed lots → produced lot (genealogy) | Production order |
| E. Lab analysis | Sample per lot | Analysis record attached; **pass-gate before stock leaves** (configurable) | Certificate file |
| F. Storage | Internal moves | Lot moves, FEFO | Stock valuation |
| G. Sale | POS / invoice | Invoice line ↔ lot (internal code = lot) | Factura electrónica (clave 49 d.) + RIDE |
| H. Delivery | Transport | Lot + partner + route | Guía de remisión (`l10n_ec_stock`) |
| I. Recall | Incident | Lot → downstream query | Affected invoices list → NC (`create_credit_note`) |

## 6. Own Module Layer — `l10n_ec_agro` (our layer into Odoo)

Layering rule (**DES-06**, ISO-EC-09): vertical modules **depend on** the shared legal layer and
never fork it; shared constants stay in `l10n_ec_base` (single owner of `ir.config_parameter`).

**D-06 (operator, 2026-10-16, evidencia RES-VERT §7):** Odoo = **business core** (facturación SRI,
inventario, POS, compra, nómina); la **verticalización completa vive en nuestra propia capa** —
`l10n_ec_agro` es la fase 1 de esa capa. Si una capacidad resulta demasiado difícil dentro de
Odoo (captura offline en campo, sensores, portal público…), se implementa en la capa propia con
**tecnología nueva** habilitada, hablando con Odoo por API; el gate de decisión es la salida de
P2 (§12). Referencia de diseño: patrón OpenTHC (CRE + plug-ins vía API), RES-VERT §2/§7.

```
l10n_ec_base / l10n_ec_edi / l10n_ec_sri / l10n_ec_withholding   (SHARED legal — never duplicated)
        ▲
l10n_ec_stock / l10n_ec_quality / l10n_ec_pos                    (shared capabilities)
        ▲
l10n_ec_agro            ← NEW OWN MODULE (vertical layer, crop-agnostic)
l10n_ec/data/templates/agro.xml   ← template data (loader: l10n_ec.business.template)
```

**Draft manifest:** `l10n_ec_agro` v `18.0.1.0.0` (CHG-06), depends:
`['l10n_ec_base', 'l10n_ec_stock', 'l10n_ec_quality', 'stock', 'mrp']`.
Live-mounted like the other 20 modules (`docker-compose.yml` bind → `/mnt/extra-addons`).

### 6.1 Models (SRS-level; fields follow repo naming `l10n_ec_*`)

| Model | Purpose | Key fields |
|---|---|---|
| `stock.lot` (**extended**) | Lot gains generic agro attributes — **crop-agnostic** (D-05) | `l10n_ec_crop_type` (catalog: café, cacao, plátano, cáñamo…), `l10n_ec_variety`, `l10n_ec_cycle_id`, `l10n_ec_harvest_date`, `l10n_ec_lab_state` (`none/passed/failed`), `l10n_ec_sanitary_reg` |
| `l10n_ec.agro.plot` | Predio/cultivo | name, hectares, location, responsible |
| `l10n_ec.agro.cycle` | Cultivation cycle | plot, crop_type, variety, sow date, expected/actual harvest, state |
| `l10n_ec.agro.analysis` | Lab result per lot — **any analyte** (humidity, THC, CBD, residues…) | lot, analyte, value, unit, **limit**, pass/fail, lab name, certificate file, date |
| `l10n_ec.agro.trace_event` | Immutable audit event | lot, stage, qty, partner, comprobante ref, timestamp |

> **No crop-specific columns anywhere** (D-05): crop type = catalog data on cycle/lot;
> crop-specific substance limits (e.g. legal THC ceiling for hemp) = `limit` on analysis
> rows, fed by `v.analisis_limites` (§8). Adding a new crop = catalog entry, zero schema change.

### 6.2 Functional requirements (FR-AG-NN) → implementation → verification

| ID | Requirement | Implementation (planned) | Verification |
|---|---|---|---|
| FR-AG-01 | Every product lot carries crop type/variety/harvest/lab state — **any crop**; substance values (THC/CBD/humidity…) live only as analysis rows | `stock.lot` extension + `l10n_ec.agro.analysis` | `l10n_ec_agro/tests/test_lot_fields.py` |
| FR-AG-02 | Cycles per plot with dates + state | `l10n_ec.agro.cycle` | `tests/test_cycle.py` |
| FR-AG-03 | Analysis per lot; **generic gate**: lot cannot move out while a required analyte exceeds its `limit` (analyte list = `v.analisis_limites`) | `l10n_ec.agro.analysis` + stock constraint | `tests/test_lab_gate.py` |
| FR-AG-04 | Genealogy: lot → consumed lots (BOM) and → moves/invoices/customers | MRP moves + trace service | `tests/test_genealogy.py` |
| FR-AG-05 | Append-only trace events (AUD-style immutability) | `l10n_ec.agro.trace_event` (no unlink) | `tests/test_events_immutable.py` |
| FR-AG-06 | Recall report: lot/date → affected invoices/partners → NC | lot on `account.move.line` via stock | `tests/test_recall.py` + MCP manual run |
| FR-AG-07 | Invoice line traces to lot (product internal code = lot) | `l10n_ec_edi` payload passthrough | SRI test invoice (§10 FR-AG-13) |
| FR-AG-08 | Guía de remisión carries lots | `l10n_ec_stock` (exists) | existing transport tests + walk-through |
| FR-AG-09 | POS sells by lot | Odoo 18 POS lot/serial (standard) + `l10n_ec_pos` | POS manual scenario |
| FR-AG-10 | Idempotent template load (create/update/skip, dry-run) | DES-03/DES-04 loader + `agro.xml` | re-run twice → no duplicates |
| FR-AG-11 | MCP can read stock and (future) trace lots | today: `get_stock_level`; future tools §10 | MCP suite (54/54, ISO-EC-11) |
| FR-AG-12 | Wizard `vertical=agro` activates params/caps + guardrails | N-01 §③/§5 rows (updated v1.1) | wizard walk-through step ③ |
| FR-AG-13 | Test-environment emission with `.p12`; **certificate must belong to the tenant RUC** `[VERIFY: cert↔RUC binding]` | `l10n_ec_edi` + `ec.ambiente=pruebas` | transmit 1 factura in CELCER, archive XML/RIDE |
| FR-AG-14 | Sanitary registry required before **regulated** product sales (instance: CBD line) | `v.registro_sanitario` param → warning guardrail | guardrail unit test |

Every FR traces: `requirement → control (ISO-EC-09/04) → module/file → test` (DOC-04). Gaps are
honest: all `l10n_ec_agro` tests are **planned** until P1 (§12).

## 7. Identity Rules Applied in this Vertical (ground truth: stdnum port)

Implemented in `mcp_server/rules.py`; suite **54/54 OK (2026-10-16)**. **stdnum equivalence
cross-check** (inside Odoo container, `stdnum` 1.19): **20,195 cases → 0 diffs** (real IDs,
single-digit mutations of both test IDs, province/third-digit/establishment edge grids,
20,000 random fuzz); live SRI confirms both IDs `ACTIVO`. Since CHG-2026-005 the check is a
**permanent test class** (`TestStdnumEquivalence`, deterministic corpus **22,727 → 0 diffs**)
and `res.partner._validate_ec_document` has the same port proven vs stdnum
(`TestStdnumEquivalenceResPartner`, CHG-2026-004). Full requirement: FR-LE-50, ISO-EC-10 §3.5.

| Rule | Value |
|---|---|
| Cédula | 10 digits; province `01–24` (+`30`,`50`); 3rd digit `0–6`; mod-10 (2,1) over all 10 digits = 0 |
| RUC | 13 digits; 3rd digit dispatch: `0–5` natural (validates as cédula + establishment ≠ `000`), `6` público (mod-11 first 9, weights 3,2,7,6,5,4,3,2,1, natural fallback), `9` jurídica (mod-11 first 10, weights 4,3,2,7,6,5,4,3,2,1), `7/8` invalid |
| Natural RUC | = cédula + `001` (operator D-02; system standard) |
| Buy vs sell | **Buy with cédula OK** (purchaser ID); **sell requires activated RUC** (operator D-03) — `sri.status=INACTIVO` blocks wizard (N-01 guardrail) |
| Consumidor Final | `9999999999999`, limit $50.00, non-annullable (already implemented, ISO-EC-10 §3.3) |

## 8. Wizard Integration (parameter updates → N-01 v1.1)

| Param | Type | Source | Req | Notes |
|---|---|---|---|---|
| `vertical.id` | select | USER | S | value `agro` (kanban row already in catalog) |
| `v.lotes` | bool | TEMPLATE | S | lot traceability ON (required by vertical) |
| `v.predios` | int | USER | S | number of plots/cultivos |
| `v.cultivos` | multi | USER | S | crop types grown — **any crop** (café, cacao, plátano, lino, cáñamo…) (D-05) |
| `v.variedades` | multi | USER | N | varieties within the chosen crops |
| `v.analisis_lab` | bool | TEMPLATE | S | lab analysis per lot (default ON) |
| `v.analisis_limites` | multi (analyte=limit) | USER | cond | required analyte limits per crop (e.g. cáñamo → THC `[VERIFY: límite legal]`); drives FR-AG-03 gate |
| `v.genealogia` | select | TEMPLATE | S | `lote_simple` / `seed_to_sale` (default seed_to_sale) |
| `v.recall` | bool | TEMPLATE | S | recall report enabled |
| `v.registro_sanitario` | text | USER | cond | sanitary registry no. when products are regulated `[VERIFY]` → FR-AG-14 |

Capabilities used (no new caps): `cap.ec_invoicing` (locked ON), `cap.inv.stock`,
`cap.inv.recipes`, `cap.purchase`, `cap.mrp`, `cap.quality` (enterprise), `cap.stock.alerts`.
Suggested size for tenant: **medium** (obligado contabilidad = SI → N-01 §④ rule).
Guardrails added: `vertical=agro` without `cap.inv.stock` ⇒ auto-enable + explain; `agro` + `size=simple` ⇒ warn (needs inventory/production).

Template defaults (`agro`): `enable_inventory=True`, `enable_mrp=True`, `enable_pos=True`;
generic categories: Insumos & Fertilizantes · Semillas & Plantines · Cultivos Frescos ·
Cultivos Procesados · Envasados & Alimentarios · Cosméticos & Sanitarios. Tenant-specific
products (e.g. CANNACHAIN's CBD line) are ingested at wizard time (`USER`/import), never
invented here.

## 9. Data / Ingest Notes

* `ingest.kind` additions catalog-wide: `plots`, `lots`, `analyses` (N-01 §⑧).
* `vertical.suggested`: **cannot** derive from `sri.ciiu` — the consolidated endpoint returns no
  CIIU code (verified 2026-10-16, §3). Requirement: local mapping table `activité-text →
  vertical` (own data, maintained by us; SRI text only). N-01 row updated accordingly.
* Ingest duplicate keys: vat (partners), barcode (products), lot name (lots).

## 10. MCP Tooling

Current gateway: **18 tools** (verified `mcp_server/tools.py`), covering §6 partial (stock read,
invoice/partner/payment/withholding/payroll/ATS/RIDE). Planned vertical additions (gap, not yet
implemented):

| Planned tool | Purpose | Class (ISO-EC-09 §7) |
|---|---|---|
| `trace_lot` | lot genealogy up/down | R (read) |
| `create_lot` | register harvest/processing lot | W (dry-run + confirm) |
| `record_lab_analysis` | attach lab result to lot | W |
| `recall_report` | lot/date → affected invoices | R |

Adding tools = MCP contract change → **major** per CHG-06 → registered before implementation.

## 11. Regulatory Compliance (ISO-EC-06 rows CM-40..42)

Split per D-05: the vertical's **generic** obligations apply to every agro tenant; the
**crop-specific overlay** below applies only to tenants growing that crop (reference tenant: hemp).

**Generic (all agro tenants):**

| Topic | Status | Action |
|---|---|---|
| SRI electronic invoicing, retentions, ATS, CF $50 | Implemented (shared layer) | Re-verify via CELCER emission (FR-AG-13) |
| Lab-analysis gate + recall capability for any crop | Designed (§5/§6) | FR-AG-03/06 tests |
| CIIU of tenant activity (endpoint returns text only) | Not exposed by endpoint | Local mapping `activité-text → vertical` (§9); request code from SRI portal `[VERIFY]` |

**Crop-specific overlay (instance: hemp/CBD for CANNACHAIN — `[VERIFY]`, tenant-level only):**

| Topic | Status | Action |
|---|---|---|
| Cannabis/hemp cultivation permits (health legislation reform) | `[VERIFY: exact law + RO]` | ISO-06 CM-41, operator to supply citation |
| Sanitary registry of CBD food/cosmetic products (ARCSA) | `[VERIFY: norm]` | ISO-06 CM-40; FR-AG-14 guardrail |
| ICE applicability to cannabinoid products | `[VERIFY]` | ISO-06 CM-42; check `l10n_ec_ice` catalog |
| CIIU code for "cultivo de lino y cáñamo" | Not exposed by endpoint | Local mapping (§9) `[VERIFY]` |

Nothing above is asserted without a source — collection `[VERIFY]` policy (README).

## 12. Implementation Phases (docs-first; code starts only on approval)

| Phase | Deliverable | Gate |
|---|---|---|
| P0 (this doc) | SRS + registrations: ISO-09 N-06/DES-06, ISO-04 §5.4, ISO-06 §3.8, N-01 v1.1, ISO-10 FR-LE-50, ISO-11 54/54 | Docs merged (standard CHG) |
| P1 | `l10n_ec_agro` skeleton: 4 models + tests §6.2 | `--test-enable` green in container |
| P2 | `agro` template + wizard params wiring + guardrails | FR-AG-10/12 walk-through |
| P3 | MCP tools (§10) | MCP suite extended; major version bump |
| P4 | CELCER emission: test factura signed with tenant `.p12` → XML/RIDE archived | FR-AG-13 evidence |
| P5 | Close `[VERIFY]` items (§11) with operator's official sources | ISO-06 rows updated |

## 13. Open Items (`[VERIFY]` index)

**Tenant/crop overlay (hemp — only needed for CANNACHAIN-class tenants):**
1. Cannabis/hemp cultivation law citation (RO number + date).
2. ARCSA sanitary registry norm for CBD products; 3. ICE applicability; 4. Legal THC ceiling;
7. AGROCALIDAD organic/phyto certification, if pursued.

**Vertical-generic:**
5. CIIU code of tenant activity; 6. SRI certificate↔RUC binding rule in test ambiente.

## 14. Revision History

| Ver. | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-10-16 | Platform | Initial: CANNACHAIN tenant (live-verified), seed-to-sale design, `l10n_ec_agro` spec (FR-AG-01..14), wizard params v1.1, MCP plan, compliance rows, phases. |
| 1.1 | 2026-10-16 | Platform | **Crop-agnostic vertical (D-05):** any crop supported — crop type/variety as catalog data, THC/CBD removed from schema (now `limit` on analysis rows), params `v.cultivos`/`v.variedades`/`v.analisis_limites` replace `v.thc_top_pct`, template `agro_cbd.xml` → `agro.xml` with generic categories, compliance split generic vs hemp overlay. |
