# SRS — Wizard Dinámico de Configuración: CATÁLOGO COMPLETO DE PARÁMETROS

**Versión**: 1.1 · **Fecha**: 2026-10-16 · **Estado**: Diseño aprobado (brainstorm)
**Arquitectura**: `INDUSTRIA × TAMAÑO × CAPACIDADES` + capa legal EC fija.
**Regla de oro**: el wizard NUNCA pregunta lo que el SRI ya sabe (evitar pregunta si `source=SRI` ya resolvió).
**v1.1 (2026-10-16)**: alta del vertical **agro** (multi-crop, SRS-VERT-AGRO-2026-001 v1.1) — 9 parámetros `v.*` nuevos, 2 guardrails, 3 `ingest.kind`; 96+43 = 139 parámetros.

---

## 0. Convención de cada parámetro

| Campo | Valores |
|---|---|
| **ID** | identificador estable (se persiste en `SetupSession`) |
| **Tipo** | text, int, money, bool, select, multi, file, cascader, computed |
| **Fuente** | `SRI` = auto desde consulta · `USER` = el usuario lo da · `TEMPLATE` = del vertical · `SIZE` = del tamaño · `DERIVED` = calculado · `DEFAULT` = constante legal |
| **Visible cuando** | `always` · `size≥medium` · `vertical=hotel` · `capability=inv.stock` … |
| **Validación** | regla que puede bloquear o pedir dato (`needs_data`) |
| **Obligatorio** | S = no puede faltar · N = opcional |

**Pasos**: ① Empresa · ② SRI (auto, solo lectura) · ③ Negocio · ④ Tamaño · ⑤ Capacidades · ⑥ Legal/Fiscal · ⑦ Contabilidad · ⑧ Ingesta · ⑨ Usuarios · ⑩ Firma · ⑪ Revisión.

---

## ① EMPRESA — identidad

| ID | Tipo | Fuente | Req | Validación / notas |
|---|---|---|---|---|
| `company.legal_name` | text | SRI | S | razón social exacta del SRI (no editable si difiere → mostrar aviso) |
| `company.vat` | text(13) | USER | S | mod-11 + `detect_taxpayer`; si persona natural: cédula 10 díg. (mod-10) |
| `company.trade_name` | text | SRI→USER | S | nombre comercial; SRI lo devuelve vacío → se pregunta |
| `company.email` | text | USER | S | formato RFC; obligatorio (SRI lo exige en facturación en línea) |
| `company.phone` | text | USER | N | |
| `company.address.provincia` | cascader | SRI→USER | S | `l10n_ec.province` (24) |
| `company.address.canton` | cascader | USER | S | `l10n_ec.canton`, filtrado por provincia |
| `company.address.parroquia` | cascader | USER | N | |
| `company.address.calle` | text | USER | S | |
| `company.address.numero` | text | USER | S | `"s/n"` permitido |
| `company.currency` | select | DEFAULT | S | **USD fijo** (dolarización) |
| `company.country` | select | DEFAULT | S | Ecuador |
| `company.logo` | file | USER | N | PNG/JPG ≤ 2MB → cabecera RIDE |
| `company.phone_or_web` | text | USER | N | |
| `company.fiscalyear_start` | select month | USER | S | inicio ejercicio (enero por defecto) |

## ② SRI — auto-detección (solo lectura, 1 llamada cacheada)

| ID | Tipo | Fuente | Uso |
|---|---|---|---|
| `sri.id_type` | select | SRI | RUC vs Cédula |
| `sri.person_type` | select | SRI | `persona_natural` / `persona_juridica` (3er dígito) |
| `sri.status` | select | SRI | ACTIVO/INACTIVO — **INACTIVO bloquea wizard** |
| `sri.regime` | select | SRI | GENERAL/RIMPE/etc → sugiere régimen |
| `sri.accounting_obliged` | bool | SRI | → sugiere tamaño |
| `sri.withholding_agent` | bool | SRI | → habilita paso retenciones |
| `sri.special_taxpayer` | bool | SRI | → exige `sri.special_resolution` |
| `sri.main_activity` | text | SRI | + `sri.ciiu` → sugiere VERTICAL |
| `sri.start_date` | date | SRI | primera declaración |
| `sri.phantom` / `sri.fake_trans` | bool | SRI | **alerta roja** si NO |
| `sri.legal_representatives` | list | SRI | pre-llena usuarios |

## ③ NEGOCIO — vertical (kanban)

| ID | Tipo | Fuente | Req | Notas |
|---|---|---|---|---|
| `vertical.id` | select(kanban) | USER | S | código: `retail`, `restaurant`, `bakery`, `pharmacy`, `hotel`, `cafe`, `fastfood`, `workshop`, `clinic`, `services`, `transport`, `construction`, `import`, `school`, `ngo`, `agro`… |
| `vertical.suggested` | computed | DERIVED | N | a partir de `sri.ciiu` (lista de apertura) |
| `vertical.search` | text | USER | N | "farmacia", "hotel"… |

## ④ TAMAÑO — complejidad

| ID | Tipo | Fuente | Req | Valores |
|---|---|---|---|---|
| `size.id` | radio | USER | S | `simple` / `medium` / `enterprise` |
| `size.suggested` | computed | DERIVED | N | reglas: natural+sin obligado→simple; obligado→medium; >50K$ o 4+ locales→enterprise |
| `size.reason` | text | DERIVED | N | **muestra por qué** sugiere ese tamaño |
| `size.employees` | int | USER | S | 1-3 / 4-15 / 16+ |
| `size.revenue_year` | money | USER | N | <50K / 50-500K / >500K |
| `size.locations` | int | USER | S | # locales físicos |
| `size.users` | int | USER | S | # usuarios Odoo |
| `size.multi_ruc` | bool | USER | S | ¿varios RUC? → **decide topología tenant** |

## ⑤ CAPACIDADES — toggles con dependencias

| ID | Requiere | simple | medium | enterprise | Efecto |
|---|---|---|---|---|---|
| `cap.ec_invoicing` | — | ✅ | ✅ | ✅ | **BLOQUEADO ON** (legal) |
| `cap.pos.basic` | — | ✅ | ✅ | ✅ | módulo `point_of_sale`, 1 caja |
| `cap.pos.tables` | pos.basic | ⬜ | ✅ | ✅ | `pos_restaurant`, mesas/zonas |
| `cap.pos.delivery` | pos.basic | ⬜ | ⬜ | ✅ | delivery, comandas |
| `cap.products.simple` | — | ✅ | ✅ | ✅ | registro simple (sin costeo) |
| `cap.inv.stock` | — | ⬜ | ✅ | ✅ | `stock`, almacén |
| `cap.inv.recipes` | inv.stock | ⬜ | ✅ | ✅ | BOM/recetas |
| `cap.inv.merma` | inv.recipes | ⬜ | ⬜ | ✅ | mermas % |
| `cap.inv.multi_warehouse` | inv.stock | ❌ | ⬜ | ✅ | N almacenes |
| `cap.cost.cogs` | inv.stock | **OFF** | ✅ | ✅ | costo de ventas real; OFF ⇒ compras a gasto |
| `cap.stock.alerts` | inv.stock | ❌ | ✅ | ✅ | mínimo/reorden |
| `cap.purchase` | inv.stock | ⬜ | ✅ | ✅ | órdenes de compra |
| `cap.mrp` | inv.recipes | ❌ | ⬜ | ✅ | producción/OP |
| `cap.accounting.full` | — | ⬜ | ✅ | ✅ | libros, conciliación, cierre |
| `cap.accounting.analytic` | accounting.full | ❌ | ❌ | ✅ | centros de costo |
| `cap.budget` | accounting.full | ❌ | ❌ | ✅ | presupuestos |
| `cap.hr` | — | ⬜ | ✅ | ✅ | empleados/contratos |
| `cap.payroll` | hr | ❌ | ✅ | ✅ | nómina/IESS |
| `cap.payroll.advanced` | payroll | ❌ | ❌ | ✅ | horas extra, utilidades, liquidaciones |
| `cap.loans_iess` | payroll | ❌ | ✅ | ✅ | préstamos IESS |
| `cap.bank_transfer` | payroll | ⬜ | ✅ | ✅ | archivos bancarios |
| `cap.multi_company` | size=enterprise | ❌ | ❌ | ✅ | N empresas/RUC |
| `cap.consolidation` | multi_company | ❌ | ❌ | ✅ | estados consolidados |
| `cap.crm` | — | ❌ | ⬜ | ✅ | pipeline |
| `cap.project` | — | ❌ | ⬜ | ✅ | tareas/obra |
| `cap.quality` | mrp | ❌ | ❌ | ✅ | control calidad |
| `cap.portal` | — | ❌ | ✅ | ✅ | portal cliente |
| `cap.ecuapass` | — | ❌ | ❌ | ✅ (importador) | SENAE |
| `cap.import_fx` | — | ❌ | ❌ | ✅ (importador) | multi-divisa |

**Efecto de cada toggle**: `MODULES` (instalar) + `MENUS` (mostrar/ocultar) + `SETTINGS` (parámetros).

## ⑥ LEGAL / FISCAL EC (capa fija + condicionales)

| ID | Tipo | Fuente | Req | Validación |
|---|---|---|---|---|
| `ec.ambiente` | radio | USER | S | `pruebas` (default) / `produccion`; producción **exige** `.p12` |
| `ec.obliged_accounting` | bool | SRI | S | editable sólo si mismatch con SRI |
| `ec.special_taxpayer` | bool | SRI | S | si ON → `ec.special_resolution` + `ec.special_date` obligatorios |
| `ec.withholding_agent` | bool | SRI | S | si ON → paso retenciones activo |
| `ec.regime` | select | SRI→USER | S | general / rimpe_empresario / rimpe_negocio_popular / especial / zede |
| `ec.establecimientos` | list | USER | S | c/u: `codigo(3)`, dirección, teléfono → define claves |
| `ec.puntos_emision` | list(cascada) | USER | S | por establecimiento: `punto(3)`, secuencia inicial `001` |
| `ec.default_doc` | select | DEFAULT | S | tipo identificación cliente default (RUC/CI/CE/Pasaporte/CF) |
| `ec.cf_limit` | money | DEFAULT | S | **50.00** (constante, sólo lectura) |
| `ec.ret_ir_enabled` | bool | DERIVED | S | por actividad CIIU → `ec.ret_ir_codes` (tabla) |
| `ec.ret_iva_enabled` | bool | DERIVED | S | default 30%/70% (SRI/IESS) → `ec.ret_iva_split` |
| `ec.ret_deadline_days` | int | DEFAULT | S | **5** hábiles (constante) |
| `ec.annul_days` | int | DEFAULT | S | **7** días (constante) |
| `ec.tax_support` | multi | USER | N | soporte tributario (exportaciones, ICE) |
| `ec.export_iva` | bool | DERIVED | N | si CIIU exporta → tarifa 0% |
| `ec.accounting_criteria` | radio | USER | S | `devengado` (default) / `caja` — **caja sólo persona natural** |
| `ec.bookkeeping_start` | date | USER | S | fecha inicio operaciones |
| `ec.contribuyente_resol` | text | USER | cond | obligatorio si especial |
| `ec.agent_ret_resol` | text | USER | cond | obligatorio si agente |

## ⑦ CONTABILIDAD

| ID | Tipo | Fuente | Req | Notas |
|---|---|---|---|---|
| `acc.chart_variant` | select | SIZE→USER | S | `nec_full` (enterprise/medium) / `nec_simple` (simple) |
| `acc.journals.ventas` | bool | TEMPLATE | S | con secuencia + diario |
| `acc.journals.compras` | bool | TEMPLATE | S | |
| `acc.journals.bancos` | list | USER | S | N cuentas bancarias (nombre, banco, tipo ahorro/corriente, no.) |
| `acc.journals.caja` | bool | TEMPLATE | S | efectivo |
| `acc.inventory_method` | select | DERIVED | S | `costo_ventas` (default) / `permanente` — sólo si `cap.inv.stock` |
| `acc.chart_accounts_extra` | list | TEMPLATE | N | cuentas rubro (hotel: ingresos habitación…) |
| `acc.fiscal_year` | select | USER | S | inicio ejercicio |

## ⑧ INGESTA — drag & drop (usa `base_import`)

| ID | Tipo | Fuente | Req | Notas |
|---|---|---|---|---|
| `ingest.file` | file | USER | N | CSV / XLSX / XML / RIDE-PDF / JSON |
| `ingest.kind` | select | USER | S | `customers` `products` `suppliers` `prices` `recipes` `employees` `tables` `rooms` `purchase_xml` `plots` `lots` `analyses` |
| `ingest.mapping` | map | USER | S | columna→campo (auto por cabecera) |
| `ingest.on_error` | select | USER | S | `report` (default) / `skip` / `abort` |
| `ingest.dup_policy` | select | USER | S | `update` / `skip` / `ask` (clave: vat / barcode) |
| `ingest.result` | computed | DERIVED | — | `n_total, n_ok, n_errors[{row,col,msg}]` |
| `ingest.requires` | computed | DERIVED | — | **`needs_data`** con las filas inválidas para re-soltar |

Campos por `kind`:
- **customers**: name, vat, email, phone, address, pricelist, category, credit_limit
- **products**: name, code, barcode, category, uom, cost, price, tax_group, `sri_ice_code`, image
- **recipes** (vertical): product, component, qty, waste_%
- **employees**: name, cédula, cargo, contrato, salario, fecha_ingreso, banco, cuenta, jornada → alimenta nómina
- **tables/mesas**: zona, mesa, sillas → POS
- **rooms/habitaciones**: número, tipo, tarifa_base → hotel
- **purchase_xml**: XML/RIDE de proveedor → compra + retención automática
- **plots** (agro): name, hectares, ubicación, responsable → `l10n_ec.agro.plot`
- **lots** (agro): name, producto, crop_type, variedad, fecha_cosecha, qty → `stock.lot`
- **analyses** (agro): lot, analito, valor, unidad, límite, lab, fecha, certificado → `l10n_ec.agro.analysis`

## ⑨ USUARIOS Y ROLES

| ID | Tipo | Fuente | Req | Notas |
|---|---|---|---|---|
| `users.admin` | obj | USER | S | nombre, email, password/invitación |
| `users.list` | list | USER | N | c/u: name, email, **role** |
| `users.role` | select | TEMPLATE | S | `admin` `accountant` `salesman` `cashier` `warehouse` `manager` `auditor(ro)` |
| `users.role_caps` | computed | DERIVED | — | rol → grupos Odoo (no improvisar) |
| `users.pos_operators` | int | SIZE | N | operadores caja |

## ⑩ FIRMA DIGITAL (obligatoria para producción)

| ID | Tipo | Fuente | Req | Validación |
|---|---|---|---|---|
| `cert.file` | file `.p12` | USER | cond | **exigido si `ec.ambiente=produccion`** |
| `cert.password` | password | USER | cond | prueba de carga (no se persiste en claro) |
| `cert.validity` | date | DERIVED | — | expiración (aviso si <30 días) |

## ⑪ REVISIÓN Y APLICACIÓN

| ID | Tipo | Notas |
|---|---|---|
| `review.summary` | computed | resumen por capa (empresa/vertical/size/capacidades) |
| `review.diff` | computed | creará/actualizará/saltará: N empresas, M productos, K usuarios, J menús |
| `review.dry_run` | bool | **default ON**; OFF + confirmación = aplicar |
| `review.snapshot` | bool | snapshot previo (BD) para rollback |
| `review.confirm` | button | gate humano |
| `review.result` | computed | ids creados + `setup_id` (retomable por MCP) |

---

## Matrices por INDUSTRIA (parámetros extra del vertical)

| Vertical | Parámetros específicos | Por defecto del template |
|---|---|---|
| 🍔 **fastfood / 🍽️ restaurant** | `v.zones` (salón/terraza/patio), `v.tables_count`, `v.menu_file`, `v.tip_pct` (propina voluntaria) [VERIFY], `v.delivery`, `v.pico_horas` | 12 mesas, 1 zona, delivery OFF |
| ☕ **cafe** | `v.menu_file`, `v.tables_count`, `v.to_go` | 6 mesas |
| 🍞 **bakery** | `v.recipes_on`, `v.waste_pct`, `v.lineas_produccion` | recetas ON, 5% |
| 🏪 **retail/bazaar** | `v.pos_lines`, `v.barcode_scan`, `v.min_stock` | 1 caja, scan ON |
| 🏥 **pharmacy** | `v.lotes_fechas`, `v.receta_medica`, `v.meds_control` , `v.ice_codes` [VERIFY tasas] | lotes ON, receta ON |
| 🏨 **hotel** | `v.rooms`, `v.room_types`, `v.tarifas`, `v.temporadas`, `v.checkin`, `v.checkout`, `v.ocup_target` | 10 hab, checkin 14:00 / out 12:00 |
| 💇 **services / clinic / workshop** | `v.appointments` (Odoo `appointment`), `v.hours_billing`, `v.garantia_dias` | citas ON |
| 🚗 **transport** | `v.guia_remision_auto`, `v.flota`, `v.rutas` | guía ON |
| 🏗️ **construction** | `v.projects`, `v.presupuesto`, `v.ret_socios` | proyectos ON |
| 🚚 **import** | `v.ecuapass`, `v.fx_currency`, `v.ad_valorem_tbl`, `v.isd` | ECUAPASS OFF (cap.) |
| 🏫 **school / ngo** | `v.regimen_especial`, `v.form101f` [VERIFY] | — |
| 🌱 **agro** (multi-crop, SRS-VERT-AGRO v1.1) | `v.lotes`, `v.predios`, `v.cultivos` (any crop: café, cacao, plátano, cáñamo…), `v.variedades`, `v.analisis_lab`, `v.analisis_limites` (analito=límite, p. ej. THC [VERIFY]), `v.genealogia` (`lote_simple`/`seed_to_sale`), `v.recall`, `v.registro_sanitario` (cond.) | lotes ON, genealogia=seed_to_sale, recall ON, analisis_lab ON |

## Guardrails (el agente avisa, no rompe)

| Condición | Acción |
|---|---|
| `sri.status=INACTIVO` | ⛔ bloquea — "el RUC está inactivo, no puede facturar" |
| `size=simple` pero `size.locations>1` | sugiere `medium`/`enterprise` |
| `cap.cost.cogs` ON sin `cap.inv.stock` | auto-enciende `inv.stock` y explica |
| `cap.multi_company` con `size≠enterprise` | bloquea + pide subir tamaño |
| `ec.special_taxpayer` con `size=simple` | avisa: exige libros/retenciones → sugiere medium |
| `vertical=hotel` con `size=simple` | avisa que necesita almacén/servicios |
| `ec.ambiente=produccion` sin `.p12` | bloquea paso ⑪ |
| `company.vat` checksum inválido | bloquea paso ① |
| `vertical=agro` sin `cap.inv.stock` | auto-enciende `inv.stock` + explica (la trazabilidad exige inventario) |
| `vertical=agro` con `size=simple` | avisa: necesita inventario/producción → sugiere `medium` |
| `vertical=agro` con `v.cultivos` vacío | `needs_data`: pide al menos un cultivo (D-05, any crop) |

## Correspondencia Wizard ↔ Tool MCP (misma capa de servicio)

| Paso | Tool MCP | Idempotente |
|---|---|---|
| ① | `create_company` | ✅ por `vat` |
| ② | `detect_taxpayer` | ✅ cache 24h |
| ③ | `list_templates` / `suggest_template` | ✅ |
| ④ | `suggest_size` | ✅ |
| ⑤ | `get_capabilities` / `set_capability` | ✅ |
| ⑥ | `set_company_config` | ✅ |
| ⑦ | `set_accounting_config` | ✅ |
| ⑧ | `ingest_data` | ✅ por clave dup |
| ⑨ | `create_user(role)` | ✅ por email |
| ⑩ | `upload_certificate` | ✅ |
| ⑪ | `apply_setup(dry_run)` / `resume_setup` | ✅ |

**Total de parámetros: 96 core + 43 por industria = 139.** (v1.1: +9 del vertical `agro`.)

## Historial

| Ver. | Fecha | Cambio |
|---|---|---|
| 1.0 | 2026-10-15 | Catálogo inicial (96 + 34 = 130). |
| 1.1 | 2026-10-16 | Vertical **agro** multi-crop: 9 params `v.*`, 3 guardrails, `ingest.kind` +`plots`/`lots`/`analyses` (SRS-VERT-AGRO v1.1 + RES-VERT-2026-001). |
