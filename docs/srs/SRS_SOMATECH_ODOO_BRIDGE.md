# SRS — SOMATECH-ODOO-BRIDGE (integration layer) + Verticalization UI/UX layer

**Document ID:** SRS-BRIDGE-2026-001
**Version:** 1.0 · **Date:** 2026-10-16 · **Status:** Design approved (docs phase — **no code yet**)
**Normative:** ISO/IEC/IEEE 29148 · `docs/ISO/README.md` (`[VERIFY]`, DOC-05)
**Related:** ISO-EC-09 (architecture) · SRS-VERT-AGRO-2026-001 v1.1 (first consumer) · RES-VERT-2026-001 (D-06 pattern) · N-01 v1.1 (wizard) · MCP gateway (today's bridge)

---

## 1. Purpose and naming

**D-08 (operator, 2026-10-16):** the new integration layer of code shall be called
**`SOMATECH-ODOO-BRIDGE`**. It is the *only* thing between Odoo and everything else
(UI, agents, mobile, future services).

**D-09 (operator, same day):** the **whole UI/UX interface of the verticalization is a layer
on top of** `SOMATECH-ODOO-BRIDGE` — a thin client. It never talks to Odoo directly and Odoo's
own backend UI is *not* the verticalization interface.

* **In scope:** layer definition, contract (API surface), UI/UX layer spec, tenant/RBAC model,
  mapping of proven FAME/YACHAQ demo ideas, phased plan.
* **Out of scope:** code (per operator's no-code order), LLM provider selection (P3), and
  anything already specified in SRS-VERT-AGRO (models/FRs there remain authoritative).

## 2. What the FAME/YACHAQ demo proved (ideas extracted, 2026-10-16 read)

Source: `Documentos/Clientes/2026/FAME/FAMEAIERP` (ARCHITECTURE.md, YACHAQ_INTEGRATION_BRIEF.md,
YACHAQ_UI_BRAND_GUIDE.md, API.md, `yachaq-ui/backend/odoo_bridge`, `agent-zero-data/tools`).
A **dummy demo already connected to our same Odoo 18 + `l10n_ec*` modules** (same repo) — 4
services: PostgreSQL · Odoo 18 · Agent Zero (8 `fame_*` Python tools) · Django UI ("YACHAQ.AI").

| Proven pattern in the demo | Idea we adopt |
|---|---|
| Backend module literally named **`odoo_bridge`** (XML-RPC connector, session cache) | This is the seed of **SOMATECH-ODOO-BRIDGE** — generalized, renamed, productized |
| **Auth against Odoo** (XML-RPC `authenticate` → uid + groups) → RBAC inherited for free | Bridge authenticates *through* Odoo; never a second user store |
| **Drill-down dashboards**: L1 KPIs → L2 lists → L3 detail (`/api/<entity>/<id>/`) | The UI/UX layer's core navigation (§6) |
| **Role-pick login** + role-based sidebar nav (`NAV` map, 8 roles) | Vertical roles (§5.3) with same mechanism |
| **Chat panel on every screen** with **context injection** (role, current page) + tool attribution line | Agent experience on top of the bridge (MCP) |
| Tools as **triple**: `x.py` + `x.py.dox.md` + prompt | Our MCP tool docs convention (already true for 18 tools) |
| `_smart_fallback()` when the agent is down → direct queries still serve dashboards | **Degradation rule:** UI reads keep working if agent engine is down |
| 16 end-to-end scenarios as acceptance criteria | Same style for our vertical acceptance (§8) |
| Design system: `#FF4D00` brand, Geist/Inter/JetBrains Mono, dark mode, uppercase labels | **D-10:** reuse as the base design system (tokens in §6.4) |

**What we do differently (lessons, not copied):**
* Multi-tenant (1 DB = 1 tenant, ISO-09 TEN-01) — FAME was single-tenant, hardcoded role
  credentials in the connector → **credentials must be per-tenant secrets, never literals**.
* FAME mixed demo passwords in docs → **forbidden here** (SEC-01).
* FAME talked XML-RPC directly from every tool → **all access funnels through the bridge**
  (one contract, one audit point — AGT-02).
* Agent Zero as separate 2.5 GB engine → we already have the **MCP gateway** as agent front
  door; the bridge hosts/exposes it instead of adopting Agent Zero `[VERIFY: keep-vs-replace at P3]`.

## 3. Layered architecture (D-08 / D-09)

```
L3  UI/UX LAYER (thin client, crop-agnostic screens, brand system §6)
        │  HTTPS (JSON)
L2  ┌────▼─────────────────────────────────────────────────────┐
    │            S O M A T E C H - O D O O - B R I D G E        │
    │  auth/RBAC • read/write APIs • agent tools (MCP) •        │
    │  vertical domain services • cache • audit • needs_data    │
    └────┬───────────────────────┬─────────────────────────────┘
L1        │ Odoo XML-RPC/ORM     │ (future) standalone vertical services (D-06 gate)
    ┌─────▼──────────────────────────────────────────────────┐
L0  │  Odoo 18 + l10n_ec* (shared legal layer) + PostgreSQL  │  ← business core
    └────────────────────────────────────────────────────────┘
        ▲ SRI (l10n_ec_edi)    ▲ MCP clients (agents)
```

| Layer | Responsibility | Never does |
|---|---|---|
| **L0 Odoo** | Fiscal truth, money, stock, POS, HR; 1 DB = 1 tenant | UI for verticalization; crop logic |
| **L1 SOMATECH-ODOO-BRIDGE** | Single contract: sessions, typed read/write endpoints, MCP tool surface, vertical domain API (plots/cycles/lots/analysis/trace), rate limits, **bitácora**, cache, `needs_data` orchestration | Business rules that Odoo already owns (no second fiscal logic) |
| **L3 UI/UX** | Render, navigate, role-based, Spanish, offline-tolerant reads, chat | Direct Odoo calls; business validation (bridge/Odoo decide) |

## 4. Bridge requirements (FR-BR-NN → verification)

| ID | Requirement | Planned verification |
|---|---|---|
| FR-BR-01 | Authenticate via Odoo (`authenticate`); session/token mapped to Odoo uid + groups (no parallel user store) | auth unit test + role matrix |
| FR-BR-02 | RBAC: map Odoo groups → bridge roles → visible screens/actions (deny by default) | RBAC table test (incl. negative: operario can't invoice) |
| FR-BR-03 | Multi-tenant: every request scoped to tenant DB (`dbfilter`/`db` param); tenant B never reads tenant A | isolation test |
| FR-BR-04 | Read APIs follow drill-down: `kpis → list → detail` per entity (pattern from demo API.md) | contract tests |
| FR-BR-05 | Write APIs are dry-run + confirm (same W-class rule as MCP AGT-01); writes land in bitácora | tool tests |
| FR-BR-06 | Expose the 18 existing MCP tools + future trace tools unchanged (bridge *hosts* the MCP gateway contract) | MCP suite 54/54 → extended |
| FR-BR-07 | `needs_data` contract honored end-to-end: missing legal data → question, never failure (WIZ-02) | scenario test |
| FR-BR-08 | Degradation: agent/chat down ⇒ reads (`kpis/list/detail`) still serve (FAME `_smart_fallback` idea) | kill-switch drill |
| FR-BR-09 | Cache: read cache by tenant+role with TTL; SRI calls keep the SEC-06 anti-banneo limits | `--stats` evidence |
| FR-BR-10 | Secrets per tenant (`.p12`, passwords) from env/volumes only — never in repo/docs (SEC-01/02) | secret scan |
| FR-BR-11 | Audit: every mutation logs tool, args, user, before/after (AGT-02) | log inspection |
| FR-BR-12 | Spanish UI/agent output; USD formatting; EC legal phrasing | UI review |

## 5. UI/UX layer (the whole verticalization interface — D-09)

### 5.1 Screens (crop-agnostic)

| Group | Screens | Source idea |
|---|---|---|
| Entry | **Role-pick login** (auth via Odoo) + dark mode | FAME login mockup |
| Ops dashboards (per role) | KPI → list → detail drill-down for: Ventas/Facturación SRI, Compras, Bodega/Stock, Producción (MRP), Calidad, Financiero, RRHH | FAME `NAV` + 7 dashboards |
| **Vertical (agro) screens** | Predios · Ciclos · Lotes (split/aggregate) · Análisis de laboratorio (gate) · **Trazabilidad** (genealogía up/down, recall) · Eventos (append-only viewer) | SRS-VERT §5/§6 |
| Wizard | The 11-step setup wizard (N-01) with `needs_data` questions surfaced inline | N-01 |
| Agent | **Chat panel on every screen** (context: role + page + entity), tool attribution footer, quick actions per role | FAME chat flow |
| Admin | Tenant/seed/ingest (drag&drop step ⑧), compliance matrix view (ISO-06), bitácora | WIZ-03/AGT-02 |

### 5.2 Navigation contract (from demo `NAV`, generalized)

`vertical` + `role` → menu tree served **by the bridge** (single source; UI renders only).
Changing vertical/role changes screens with zero frontend deploy — this is what makes the
UI *verticalization-generic*.

### 5.3 Roles (baseline; per-tenant overridable)

`admin · gerente · ventas · compras · produccion/bodega · calidad · financiero · rrhh ·
agronomo (vertical) · auditor(ro)` — mapped to Odoo groups (FAME §6.1 mapping reused).

### 5.4 Design system (D-10 — reuse YACHAQ tokens)

Brand `#FF4D00` · ink `#050505` · Geist (hero, uppercase, tight tracking) · Inter (body/labels,
black uppercase micro-labels) · JetBrains Mono (data) · cards `rounded-2xl`, hover→brand invert ·
dark mode via `dark` class · brand scrollbar/selection. Crop screens use the *same* components —
crop-agnostic UI means **no crop-specific components**, only data.

### 5.5 Agent experience

Chat = MCP through the bridge: same 18+ tools, context injection (role/page/entity), answer
footers like `via trace_lot · bridge → Odoo`, and the platform's golden rule: **asks
(`needs_data`), never invents** (AGT-03).

## 6. Technology shape (decision input, final call at P1 gate)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Extend today's stdlib MCP gateway** (bridge = MCP + HTTP) | zero new deps, 54/54 suite, already front door | no web UI serving, stdlib limits | **P1 start** (bridge core = MCP contract) |
| **B. Own Python service (own container/venv)** like FAME's Django/ninja | full REST + sessions + templating; isolated from Odoo container (live-mounted, no rebuild) | first "new tech" instance → needs D-06 gate evidence at P2 exit | **P2 candidate** for UI hosting |
| **C. Odoo-native (website/JS)** | no extra service | drags vertical UI into L0; not crop-agnostic layering; D-09 violated | rejected |

Ground rules still hold: live-mounted volumes, no rebuilds, ≤8 GB cluster (ISO-EC-03) — any new
service gets a hard memory budget carved from the cap (P2 sizing task).

## 7. Mapping FAME module → bridge target

| FAME artifact | Our target |
|---|---|
| `backend/odoo_bridge/connector.py` (XML-RPC, session cache, multi-user auth) | bridge core connector (per-tenant credentials from env) |
| `dashboard` REST (kpis/lists/details per role) | bridge read API (FR-BR-04) |
| `agent_bridge` + chat endpoint | MCP hosting (FR-BR-06) + chat relay |
| 8 `fame_*` tools | our 18 MCP tools + planned `trace_lot/create_lot/record_lab_analysis/recall_report` (SRS-VERT §10) |
| seed script (15 products, 9 users, BOM) | `agro` template + wizard ingest (N-01 §⑧) |
| 16-scenario acceptance list | our §8 |

## 8. Acceptance scenarios (adapted, CANNACHAIN tenant)

1. Login as `gerente` → agro dashboard KPIs in <2 s.
2. Drill-down: KPI → lot list → lot detail with genealogy links.
3. Chat: "¿Cuánto lote de la cosecha X queda?" → tool → real stock (no invented data).
4. Create sale → SRI test invoice path unchanged (FR-AG-13).
5. Recall scenario: lot → affected invoices → credit note (FR-AG-06).
6. `operario` attempts invoice → denied (FR-BR-02).
7. Agent engine down → dashboards still read (FR-BR-08).
8. Tenant isolation check (FR-BR-03).

## 9. Plan (docs-first; code only on operator's go)

| Phase | Deliverable | Gate |
|---|---|---|
| **P0 (now)** | This SRS + registrations (ISO-09 N-07, ISO-README) | Docs merged |
| **P1** | Bridge core = MCP contract hardened as HTTP/JSON API (Option A): auth FR-BR-01/02/03, read `kpis/list/detail` for 3 entities | contract tests + suite green |
| **P2** | UI host decision (D-06 gate: A vs B) + seed role screens (login, 2 dashboards, chat panel) + sizing ≤ budget | scenario 1/2/7 |
| **P3** | Full screens (§5.1), vertical agro screens, wizard integration, agent context UX | scenarios 1–7 |
| **P4** | Trace tools MCP (SRS-VERT §10) + recall scenario + CELCER evidence | SRS-VERT P3/P4 unchanged |
| **P5** | Hardening: audit review, cache tuning, load test ≤8 GB | ISO-06/09 controls evidence |

## 10. Risks

| Risk | Mitigation |
|---|---|
| RAM cap breached by new service | Budget carved at P2; Option A needs no new service |
| Second business logic creeping into bridge | DES-06/FR-BR-04: bridge transports & shapes, never computes fiscal results |
| Demo's hardcoded-credential habit copied | FR-BR-10 + code review checklist |
| UI forks per crop | §5.4 rule: data-only differences; nav comes from bridge (§5.2) |

## 11. `[VERIFY]` index

1. Keep vs replace chat/agent engine at P3 (MCP-native vs external engine).
2. Django/ninja vs FastAPI vs HTMX for Option B (evidence at P2 gate).
3. Token/session lifetime policy for bridge sessions `[VERIFY: internal policy]`.

## 12. Revision history

| Ver. | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-10-16 | Platform | Initial: D-08 layer name, D-09 UI-on-top, D-10 design system; FAME demo analysis (§2/§7); FR-BR-01..12; layered architecture; P1–P5 plan. |
