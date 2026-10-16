# RESEARCH — Traceability Feature Catalog (OpenTHC + industry platforms)

**Document ID:** RES-VERT-2026-001
**Version:** 1.0 · **Date:** 2026-10-16 · **Status:** Research digest → feeds SRS-VERT-AGRO-2026-001 (v1.1)
**Normative:** `[VERIFY]` policy `docs/ISO/README.md` (DOC-05) · DOC-01 (this is pre-design research, ISO-09 follows)
**Sources (all fetched live 2026-10-16):**
`openthc.com` (home, `/app`, `/pos`, `/lab`, `/reg`, `/api`) · `github.com/openthc` (29 public repos, MIT/GPL mix) · `api.openthc.org` (common data model + OpenAPI) · Verdnt blog *"Best Food Traceability Software…"* (2026-09-13, updated 2026-09-23).

---

## 1. Purpose

1. Extract the **complete feature set** of OpenTHC (open-source cannabis track-and-trace) and of
   the food-traceability market (Verdnt/FSMA-204) for our `agro` vertical.
2. Every feature must be **crop-generic** (operator D-05): cannabis is *one crop instance*, never
   a code branch.
3. Decide **what lives in Odoo** vs **our own verticalization layer** (operator D-06, §7).

## 2. OpenTHC architecture digest (why it matters to us)

OpenTHC is not a monolith: a **CRE (Compliance Reporting Engine)** is the single data-store/core,
and *everything else plugs into it through a documented API* + thin **middleware** for
per-agency/per-tenant rules (source: `/reg`, `/api`). That is precisely the pattern operator D-06
chose for us: **business core + pluggable vertical layer**. Their common data model is published
as JSON Schema (`github.com/openthc/api`: Company, Contact, License, Lot, Product, Variety,
Lab Sample, Lab Result, B2B Sale, B2C Sale + base catalogs incl. *Lab Metric Type*).

> **D-07 (proposal):** adopt the OpenTHC common model as the **reference schema** for our own
> layer's `Lot / Variety / LabSample / LabResult / License` entities (crop-agnostic already by
> design), translated to Odoo naming (`stock.lot`, `l10n_ec.agro.*`). `[VERIFY: exact schema
> versions]` before implementation.

## 3. OpenTHC module inventory → generic feature map

29 repos (GitHub `openthc`, fetched 2026-10-16). Functional groups:

| Group | Repos (module) | Function | Crop-generic? |
|---|---|---|---|
| **Core** | `cre` | Compliance Reporting Engine — primary data store + API hub | ✅ by design |
| | `common` | shared PHP library | ✅ |
| | `sso` | auth (OAuth2) | ✅ |
| | `docker` | deployment images | ✅ |
| **Seed-to-sale app** | `app` | main web app: **Grow → Process → Package → Sell → Analyze** | ✅ (cannabis fields = data) |
| | `app-android` / `app-ios` / `app-electron` | mobile/desktop clients, barcode scanners | ✅ |
| | `rpi` | environmental monitoring/sensors (Raspberry Pi) | ✅ (any crop) |
| | `box` | automated growing enclosure | ⚙ hardware, out of scope |
| **Data model / interop** | `api` | common data model + OpenAPI spec (Lot, Variety, Lab…) | ✅ |
| | `bong` | Basic Object Normalization Gateway (traceability objects) | ✅ |
| | `pipe` | wrapper over compliance reporting engines | ✅ |
| | `cre-adapter` | adapters: **BioTrackTHC, LeafData, METRC, WCIA, CCRS** | 🇺🇸 US states; pattern reusable → SRI adapter analog |
| | `p2p` | peer-to-peer mesh data exchange between tenants | ✅ |
| **Catalogs** | `vdb` | Variety/Strain database | ✅ (variety = any crop) |
| | `dir` | Company/Contact/**License** directory | ✅ |
| | `wcia-analytes` | standardized **analyte** names/IDs (lab metrics) | ✅ — validates our `agro.analysis.analyte` design |
| **Lab / QA** | `lab` | lightweight **LIMS**: create sample → lab updates result → search/publish COA; OAuth2 API; link-sharing; regulatory import | ✅ |
| **Retail** | `pos` | POS/checkout: **ID scanning (age gate), sales limits, discounts, holds, loyalty, online ordering, product intake w/ lab results carried over, P2P supplier receipt** | ✅ (age gate = cannabis overlay) |
| **Reporting / open data** | `data`, `meta` | analytics portals (Metabase) | ✅ |
| | `pub` | public data sharing portal | ✅ |
| | `log` | logging server/display | ✅ |
| | `chat` | internal chat (Mattermost) | ❌ not a product feature |
| **Government** | `ccrs`, `license-applicant-portal` | state tracking (WSLCB), license applications | 🇺🇸 regulator-side; Ecuador analog = SRI/Senasa |
| **Infra** | `cloudprnt-server` | label/receipt printing (Star CloudPRNT) | ✅ |

### 3.1 Feature catalog harvested from OpenTHC (all of them)

**A. Crop & field (grow):** seeds/clones/plants tracking · grow management cycles ·
environmental monitoring (sensors via `rpi`: temp/humidity/EC/light) · variety/strain registry
(`vdb`) · planting/harvest events · **every item is crop-agnostic** (cannabis vocabulary lives in
base-data catalogs, not schema).

**B. Lot & inventory:** lot identity from harvest → cure → processing → packaging · packaging &
labeling · harvested plant material · cured/processed material · transfers (B2B) · aggregation
logic (upstream/downstream) · intake workflow with lab results attached.

**C. Lab/QA:** lab sample create (grower) → lab update → downstream search · COA publishing ·
standardized analytes/metrics (`wcia-analytes`) · QA pass/fail gates · shareable sample links ·
regulatory-system sample import · OAuth2 API for labs/integrators.

**D. Sales & retail:** wholesale transfers · POS checkout · **ID scanning** · **configurable
sales limits** · discounts (multi-type) · cart holds · loyalty program (email/phone/card) ·
online ordering + in-store pickup · self-checkout (roadmap) · product intake from any compliant
supplier · receipt printing.

**E. Compliance & government:** license & application management · track-and-trace (prevent
diversion) · operational reporting · tax assessment · middleware-driven agency rules · adapters
to government engines (Metrc/BioTrack/LeafData/WCIA/CCRS pattern).

**F. Interop & identity:** common data model w/ JSON Schema (Company, Contact, License, Lot,
Product, Variety, Lab Sample, Lab Result, B2B Sale, B2C Sale) · normalized gateway (`bong`) ·
P2P tenant-to-tenant exchange · directory services · SSO/OAuth2 · middleware extension points.

**G. Devices & ops:** web app on any OS · Android/iOS apps with Socket Mobile scanners ·
printers/scanners/sensors · cloud printing · minimal-network/no-open-port operation · logging ·
analytics (Metabase) · public sharing portal.

## 4. Food-traceability market catalog (Verdnt blog, FSMA-204 lens)

The 10 compared platforms (Verdnt, TraceGains, ReposiTrak, Trustwell FoodLogiQ, SafetyChain,
Farmforce, Cropin/RootTrace, SourceTrace, KoltiTrace, Dimitra) converge on this **generic** set:

| Domain | Features (all crops) |
|---|---|
| First-mile | grower onboarding/identity · field identifiers/GIS maps · harvest records at source · offline mobile capture · barcode/QR/GS1 labels · authenticated (tamper-evident) scans |
| Lot logic | lot creation at source · **split lots** · **aggregation** · lot continuity across the chain · transformation/BOM genealogy |
| Regulatory events | **CTE** (Critical Tracking Events: harvest, cooling, initial packing, receiving, transformation, shipping) · **KDE** (Key Data Elements) · traceability lot code linkage · traceability plan document · **auditable record of changes** |
| Response | recall investigation views · affected-lot identification · **24-hour retrieval** window · FDA sortable-record export |
| Partner network | trading-partner data exchange · supplier compliance · certifications/specs · corrective actions |
| Enterprise | ERP/quality/procurement integration · role-based access · audit trails · ESG/VSME sustainability reporting |
| Consumer | provenance/labeling · scan-to-verify |
| Verdict | **blockchain optional** — value comes from consistent IDs, clean lot data, event capture, audit trails, fast retrieval (explicit in the article FAQ) |

> FSMA-204 is a **US** rule; Ecuador analog rows are SRI e-invoicing + AGROCALIDAD/ARCSA
> `[VERIFY]`. The *structure* (CTE/KDE/lot code/24-h retrieval) is what we adopt generically.

## 5. Feature → our vertical (mapping table)

Legend: **Odoo-core** = standard capability used as-is · **Own-layer** = `l10n_ec_agro` / future
vertical service · **Overlay** = crop-specific (cannabis) config or rule · **Later** = post-P5.

| # | Feature (source) | Where it lives | Crop-genericity |
|---|---|---|---|
| 1 | Field/plot registry + GIS (Verdnt, Dimitra) | Own-layer (`l10n_ec.agro.plot`, + coords later) | ✅ |
| 2 | Crop cycles seed→harvest (OpenTHC app) | Own-layer (`l10n_ec.agro.cycle`) | ✅ |
| 3 | Variety/strain catalog (OpenTHC `vdb`) | Own-layer data (`v.cultivos`/`v.variedades`) | ✅ |
| 4 | Environmental monitoring (OpenTHC `rpi`) | Later — sensor ingestion service | ✅ |
| 5 | Lot identity + split/aggregate (all) | Odoo `stock.lot` + Own-layer trace_event | ✅ |
| 6 | Genealogy/transformation BOM (Verdnt, SafetyChain) | Odoo `mrp` + Own-layer | ✅ |
| 7 | Lab sample→result→COA (OpenTHC `lab`) | Own-layer (`l10n_ec.agro.analysis`) | ✅ |
| 8 | Analyte standard catalogs (OpenTHC `wcia-analytes`) | Own-layer base data (`v.analisis_limites`) | ✅ |
| 9 | QA pass-gate before shipping (SafetyChain/OpenTHC) | Own-layer (FR-AG-03) | ✅ |
| 10 | Trace events append-only + audit trail (FSMA) | Own-layer (`trace_event`, AUD-*) | ✅ |
| 11 | Recall: lot→invoices→NC (Trustwell) | Odoo `account` + Own-layer + MCP `recall_report` | ✅ |
| 12 | CTE/KDE-style event capture + 24-h retrieval | Own-layer reports (structure only, no FDA) | ✅ |
| 13 | Guía de remisión / transport | Odoo `l10n_ec_stock` (exists) | ✅ |
| 14 | POS retail: limits, discounts, loyalty, holds (OpenTHC `pos`) | Odoo `point_of_sale` + `l10n_ec_pos` | ✅ |
| 15 | ID scan / age verification (OpenTHC `pos`) | Overlay (age gate = regulated-crop rule) | Overlay |
| 16 | ID scanning for *purchaser* identity | Odoo POS (reuse for cédula capture, D-03) | ✅ |
| 17 | Wholesale/B2B transfers (OpenTHC) | Odoo `sale`/`purchase` + `l10n_ec_stock` | ✅ |
| 18 | Supplier intake w/ lab results carried (OpenTHC `pos`/P2P) | Own-layer intake (later: P2P-style exchange) | ✅ |
| 19 | Licenses & directory (OpenTHC `dir`, `license-app…`) | Own-layer (license model per partner) | ✅ (EC license types = data `[VERIFY]`) |
| 20 | Compliance report to regulator (CRE/pipe pattern) | Later — adapter over our layer (SRI already covered by `l10n_ec_edi`) | ✅ |
| 21 | Analytics portal (OpenTHC `data`/`meta`) | Odoo reporting + Later Metabase-style portal | ✅ |
| 22 | Public scan/provenance portal (Verdnt, `pub`) | Later (new tech, §7-B) | ✅ |
| 23 | Offline field capture mobile (Verdnt, Farmforce) | **Later — likely outside Odoo** (§7-B) | ✅ |
| 24 | Common JSON data model/API (OpenTHC `api`) | Our MCP tools already mirror this; adopt schema (D-07) | ✅ |
| 25 | SSO/OAuth2 (OpenTHC `sso`) | Odoo auth + Later portal SSO | ✅ |
| 26 | Environmental/label printing (OpenTHC `cloudprnt`) | Odoo reports/labels; hardware Later | ✅ |
| 27 | Sanitary registry / ARCSA / THC ceiling / cultivation permits | **Overlay** (tenant/crop config, `[VERIFY]` rows CM-40..42) | Overlay |
| 28 | State interop (Metrc/BioTrack adapters) | Not applicable (Ecuador = SRI, already native) | — |

## 6. Genericity rules (operator D-05) — how modules "exist once"

1. **Crop type = data**, never a module, model variant, or code branch (`v.cultivos` catalog).
2. **Substances = analysis rows** (analyte/value/unit/limit), never columns (THC is just one
   analyte of many).
3. **Regulated-crop rules = overlays** (params + guardrails + compliance rows), loaded only when
   the tenant's crop requires them.
4. **Base-data catalogs** (analytes, product types, license types) mirror OpenTHC's `./etc` YAML
   pattern → versioned data, not code.

## 7. Architecture decision input (operator D-06)

> **D-06:** Use **Odoo capabilities for business** (accounting, SRI e-invoicing, inventory, POS,
> purchase, MRP, HR/payroll) and **design our own layer for the whole verticalization**. If
> building a capability inside Odoo proves too hard, implement it in the own layer with new
> technology (allowed) — Odoo stays the business core.

| Part | Choice | Rationale |
|---|---|---|
| Business (fiscal, money, stock moves, POS, payroll) | **Odoo** (`l10n_ec*` shared layer) | Already built, SRI-tested, 54/54 MCP suite |
| Verticalization (plots, cycles, lots, events, lab, licenses, traceability reports) | **Own layer** — starts as `l10n_ec_agro` module (P1–P2), can graduate to a standalone vertical service talking to Odoo via API | Matches OpenTHC CRE+plug-ins pattern; keeps Odoo core untouched (DES-06) |
| Candidates to go standalone ("new tech") if Odoo is a poor fit | offline mobile field capture, sensor ingestion, public provenance portal, heavy interop hub | these are weak points of a server ERP; decide at **P2 evaluation gate** with evidence |
| Interop contract | MCP tool surface + OpenTHC-style JSON model (D-07) | one contract for UI, agents, and any future service |

**Decision gate (P2 exit):** for each own-layer feature, verdict *Odoo-module-fit* vs
*standalone-service* based on: form/mobile UX, offline needs, latency, and update cadence.
Never fork the shared legal layer (DES-06); never duplicate Odoo business data (single source:
Odoo DB; the layer reads/writes through its API).

## 8. Out of scope / not adopted

* OpenTHC **regulator-side** components (US state systems) — Ecuador regulator = SRI (already
  native via `l10n_ec_edi`).
* **Blockchain** — explicitly unnecessary for core value (Verdnt FAQ); revisit only for
  multi-party provenance demand.
* OpenTHC `chat`, `wiki`, `box` (internal tooling/hardware).

## 9. `[VERIFY]` index

1. OpenTHC exact schema versions of `api` JSON models `[VERIFY]` (repo fetched, tags not read).
2. Ecuador first-mile regulatory analogs of CTE/KDE (AGROCALIDAD/Senasa) `[VERIFY: fuente]`.
3. FSMA-204-style 24-h retrieval obligation existence in Ecuador `[VERIFY]` (not asserted).
4. License types for agro/cannabis in Ecuador `[VERIFY: orgánica]`.

## 10. Revision history

| Ver. | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-10-16 | Platform | Initial: OpenTHC 29-repo inventory + feature catalog, Verdnt/FSMA-204 catalog, mapping table (28 rows), D-06 architecture analysis, D-07 proposal. |
