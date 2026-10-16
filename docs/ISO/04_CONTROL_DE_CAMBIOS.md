# 04 — CONTROL DE CAMBIOS (ITIL 4 · ISO 9001 §8.5.6 · ISO/IEC 27001 A.8.9/A.8.32)

**Gestión de cambios de código, configuración y cambios regulatorios SRI**

| Campo | Valor |
|---|---|
| Código documento | ISO-EC-CHG-04 |
| Versión | 1.1 |
| Fecha de emisión | 2026-10-15 |
| Última actualización | 2026-10-16 (§5.4: registro CHG-2026-001..005) |
| Propietario | Comité Asesor de Cambios (CAB) |
| Aprobador | CIO |
| Próxima revisión | 2027-04-15 (anual) o tras 5 emergencias |
| Registro relacionado | `l10n_ec_sri/docs/00_project_management/CHANGE_CONTROL_PROCEDURE.md` (CCP-001) y `DOC_CONTROL_MATRIX.md` (DCM-001) |

---

## 1. Objeto y alcance (Purpose & Scope)

Asegurar que **todo cambio** (código, datos regulatorios, configuración de `docker-compose.yml`/`.env`/`config/*`, documentación) sea evaluado, aprobado, probado, desplegado y reversible, sin comprometer la validez fiscal de los comprobantes ya emitidos.

| En alcance | Fuera de alcance (otro control) |
|---|---|
| 20 módulos `l10n_ec*`, `tests/` | Cambios de infraestructura del proveedor cloud (R-017, `07` §5) |
| `docker-compose.yml`, `Dockerfile`, `.env`, `config/odoo.conf`, `config/postgresql.conf`, `config/entrypoint.sh` | Sistemas externos SRI/IESS (dependencia, no cambio nuestro) |
| Datos regulatorios (`*/data/*.xml`, `*.csv`), `__manifest__.py` | Incidencias operativas (→ `02`, `01` §6) |
| Documentación `docs/` e `docs/ISO/` | — |

## 2. Referencias normativas (Normative references)

| Ref. | Documento |
|---|---|
| [1] | ITIL 4 — Gestión de cambios de servicio (estándar/normal/emergente) |
| [2] | ISO 9001:2015 8.1 / 8.5.6 — Control de producción y cambios |
| [3] | ISO/IEC 27001:2022 A.8.9 (configuración), A.8.32 (desarrollo), A.8.31 (separación de entornos) |
| [4] | `CONTRIBUIR.md` — flujo de ramas/PR, formato de commit, revisión ≥1 |
| [5] | `DEVELOPMENT_PLAN.md` — reglas de terreno (pruebas obligatorias, sin nuevas deps pip/npm, ejecución en Docker) |
| [6] | `docs/ISO/06_MATRIZ_DE_CUMPLIMIENTO.md` (obligación → control) y `06b_MATRIZ_DE_RIESGOS.md` (R-001, R-007, R-012, R-019) |

## 3. Clasificación de cambios y aprobación — **CHG-01/CHG-02**

### 3.1 Categorías

| Categoría | Definición | Ejemplos reales | Aprobación | SLA | Registro |
|---|---|---|---|---|---|
| **Estándar** | Pre-aprobado, repetitivo, bajo riesgo, con checklist verificada | Bump de versión `18.0.1.0.0→18.0.1.0.1` con solo fixes y tests verdes; rotación de logs; actualización de documentación sin cambios de control | Checklist firmada por Líder Dev (sin CAB) | ≤5 días hábiles | Ticket + PR |
| **Normal** | Impacto en lógica fiscal, datos regulatorios, seguridad, esquema o configuración | Nueva tasa/retención; cambio en `postgresql.conf`; nuevos grupos en `security/`; refactor de `l10n_ec_edi/models/account_edi_format.py` | **CAB** semanal (§8) + ≥1 revisor en PR (`CONTRIBUIR.md`) | ≤10 días hábiles | Acta CAB + PR mergeado |
| **Emergente** | Incidente S1/S2 **o** Resolución SRI con vigencia inmediata (§3.2) | Res. SRI a mitad de año; caída de `cel.sri.gob.ec`; hotfix de rechazo masivo | CIO + Oficial Cumpl. (cuórum exprés, §8.2) | Despliegue ≤48 h; documentación ≤48 h posterior | Acta exprés + post-revisión |

**Determinación de categoría (CHG-01):** toda solicitud responde: ¿afecta cálculo fiscal/laboral, XML, secuencias SRI, evidencia o configuración? Si sí → Normal mínimo; si además hay vigencia legal inmediata o S1/S2 → Emergente; si solo documentación/cosmético → Estándar.

### 3.2 Cambio regulatorio SRI (ruta calificada) — control **CHG-09/CHG-10** ← riesgo **R-007**

*Las resoluciones del SRI llegan a mitad de año. Esta es la única ruta permitida para incorporarlas.*

| Paso | Acción | Artefacto real obligatorio | Salida |
|---|---|---|---|
| 1. **KB** | Registrar la norma en la base de conocimiento con fuente, fecha de vigencia y estado de verificación | `l10n_ec_sri/docs/11_regulatory_knowledge_base/KB_SRI_EINVOICING_2026.md` (Res. NAC-DGERCGC25-00000017) o KB específico (`KB_TAX_RATES_WITHHOLDINGS.md`, `KB_IESS_2026.md`, `KB_MINISTERIO_TRABAJO_2026.md`, `KB_SUPERCIAS_2026.md`, `KB_SENAE_2026.md`); actualizar `INDEX.md` (*Verification Status* + *Next Review*) | KB actualizado + fecha `Last Verified` |
| 2. **Data** | Expresar la regla como **dato**, nunca como número quemado en Python | Ejemplos verificados: `l10n_ec_income_tax/data/tax_table_2026_data.xml` (tabla 19/renta), `l10n_ec_withholding/data/retention_codes_2026.xml` (códigos 303/721/723/725/727…), `l10n_ec_base/data/l10n_ec_sri_config.xml` (`ir.config_parameter`: `l10n_ec.consumidor_final_limit`, `l10n_ec.annulment_day_limit`), `l10n_ec_hr_payroll/data/l10n_ec_payroll_data.xml` (`l10n_ec.sbu` = 482.00, 9.45/11.15/0.5/0.5/8.33), `l10n_ec_customs/data/l10n_ec_customs_data.xml` (FODINFA 0.005, IVA 0.15), `l10n_ec_ice/data/l10n_ec.ice.category.csv` | Archivo `data/*` modificado con `noupdate` correcto |
| 3. **Test** | Prueba que **falla antes** del cambio y pasa después | `tests/regulatory/test_sri_2026_rules.py` (reglas 2026), complementar con `tests/unit/` (`test_sri_validation.py`, `test_withholding.py`, `test_payroll.py`, `test_tax_calendar.py`, `test_consumidor_final.py`) y suites del módulo (`l10n_ec_sri/tests/`, `l10n_ec_base/tests/`, `l10n_ec_hr_payroll/tests/`, `l10n_ec_rimpe/tests/`, `l10n_ec_ice/tests/`) | Suite verde con `--test-enable` |
| 4. **Release** | Subir versión del `__manifest__.py` (§5), notas de release (§7), tag, despliegue | `main` + tag `release/YYYY-MM-DD` | Release con trazabilidad KB→data→test |

**Reglas de CHG-10 (checklist de cierre):** (a) la KB cita el número exacto de Resolución y su RO; (b) no hay números de tasa en `.py` (solo en `data/`); (c) la prueba referencia la KB; (d) se recalculó `06_MATRIZ_DE_CUMPLIMIENTO.md` (estado de la fila afectada); (e) si el cambio altera comprobantes en vuelo, existe plan de secuencias/re-emisión (`05` §4).
**Riesgo R-007** (P=4, I=5, P×I=20): *Resolución SRI a mitad de año no aplicada en plazo → rechazos masivos / multas.* Tratamiento: esta ruta con SLA emergente ≤48 h; control verificable: KPI-14 (tiempo norma→release).

## 4. Flujo de ramas y Pull Requests — **CHG-03/CHG-04**

Basado en `CONTRIBUIR.md` (verificado: rama `main` activa; `origin/master` histórica):

| Paso | Regla | Control |
|---|---|---|
| 1 | Rama: `git checkout -b feature/mi-mejora` desde `main` (prefijo `feature/`; emergentes: `hotfix/` con misma ruta) | CHG-03 |
| 2 | Estándares: PEP8/OCA, docstrings, `author/license` LGPL-3 en `__manifest__.py` | `CONTRIBUIR.md` |
| 3 | Commit: `[MODULO] Descripción corta (máx 72 caracteres)` + cuerpo + `Fixes #nnn` | CHG-03 |
| 4 | Pruebas: toda funcionalidad nueva tiene prueba en `tests/` o `tests/` del módulo; correr en Docker `docker compose exec odoo … --test-enable` | CHG-07 (`DEVELOPMENT_PLAN` ground rules) |
| 5 | PR: **≥1 revisión**, verificaciones CI en verde, sin conflictos, documentación actualizada si aplica | `CONTRIBUIR.md` §Proceso de Revisión |
| 6 | Aprobación adicional según categoría (§3.1); CAB para Normal/Emergente | CHG-02 |
| 7 | Merge a `main` **solo** desde PR (prohibido push directo) | CHG-04 |
| 8 | Despliegue: `docker compose build && docker compose up -d` en ventana (§6) | CHG-11 |

**Cambios de configuración (mismo flujo, ruta corta):** `.env`, `config/postgresql.conf`, `config/odoo.conf`, `docker-compose.yml` → rama `feature/config-*` → PR con sección **"Valores antes/después + recálculo de capacidad (`03` §3)"** → CAB. `config/entrypoint.sh` se trata como código (renderiza `odoo.conf`: `workers`, `dbfilter`, `logfile`).
**Prohibiciones (CHG-11):** editar `odoo.conf`/`postgresql.conf` directamente en un contenedor vivo (los montajes `:ro` y el render los sobrescriben); cambiar secretos por canales no-Git-CI; desactivar `synchronous_commit`/`fsync` (`config/postgresql.conf` líneas 21–23).

## 5. Política de migraciones y versionado — **CHG-05/CHG-06**

### 5.1 Reglas de datos (XML-ID y parámetros)

| Regla | Detalle | Sanción si se viola |
|---|---|---|
| **Nunca editar ni eliminar un XML-ID ya publicado** | IDs cargados en instalaciones existentes (`security/*.xml`, `data/*.xml`, `views/*`) solo se **añaden**; los cambios de valor usan `noupdate="1"` o nueva migración | Rompe `-u` en producción (incidente tipo DR-P5) |
| Renombrar `ir.config_parameter` exige migración | Ej.: `l10n_ec.sbu`, `l10n_ec.annulment_day_limit`, `l10n_ec.consumidor_final_limit` (`l10n_ec_base/data/l10n_ec_sri_config.xml`) | Parámetros huérfanos y reglas fiscales en silencio |
| Datos regulatorios con `noupdate` según intención | Tasas SRI/IESS/SBU: versionables (`noupdate="0"`) cuando la norma las actualiza; catálogos estables: `noupdate="1"` | Doble definición |
| Migraciones versionadas | Script `<modulo>/migrations/<versión>/pre-migrate.py` / `post-migrate.py` si cambia esquema | Pérdida de datos |
| Dump pre-upgrade obligatorio | `pg_dump -Fc` manual antes de cualquier `-u` en BD con datos (coherente con RPO 6 h, `02` §4) | Sin rollback seguro |

### 5.2 Reglas de versionado del `__manifest__.py` — **CHG-06**

```
versión = <serie Odoo>.<x>.<y>.<z>   →   18.0.1.0.0
         └ 18.0 (ODOO_REF=18.0, .env) ┘  └ mayor ┘└ menor ┘└ patch ┘
```

| Incremento | Cuándo | Ejemplo |
|---|---|---|
| `z` (patch) | Fix de bug sin cambio de esquema/contrato, con test | `18.0.1.0.0 → 18.0.1.0.1` |
| `y` (minor) | Nueva funcionalidad o nuevo dato regulatorio compatible | `18.0.1.0.1 → 18.0.1.1.0` |
| `x` (major) | Cambio de esquema/migración de datos o de contrato público (p. ej. MCP) | `18.0.1.1.0 → 18.0.2.0.0` |
| Serie `18.0` | Solo cuando `ODOO_REF` en `.env` cambia de serie (p. ej. `saas-18.4`) | Release mayor + campaña completa |

**No conformidad abierta (evidencia de auditoría interna):** `l10n_ec_ice/__manifest__.py` y `l10n_ec_rimpe/__manifest__.py` declaran `"version": "1.0"` — **no cumplen CHG-06**; deben normalizarse a `18.0.1.0.0`+ (CAPA `00` §10; riesgo R-012). El resto de los 20 módulos está en `18.0.1.0.0` (verificado con AST sobre cada manifest).

### 5.3 Catálogo de *breaking changes* Odoo 16/17 → 18 (hallados y corregidos en esta migración)

Durante la instalación de los 20 módulos sobre Odoo 18 (build from-source) se detectaron y
corrigieron estos puntos de ruptura. Sirven de checklist obligatorio (control **CHG-05**) para
cualquier módulo nuevo o migración de serie:

| # | Breaking change | Síntoma en instalación | Corrección | Archivos afectados |
|---|---|---|---|---|
| M-1 | `hr.employee.address_home_id` **eliminado** | `AttributeError: 'hr.employee' object has no attribute 'address_home_id'` | Usar campos planos `private_state_id`, `private_city`, `private_country_id` | `l10n_ec_hr_payroll/models/hr_employee_ec.py`, `l10n_ec_sut/wizard/sut_report_wizard.py` |
| M-2 | Vista `<tree>` **renombrada a `<list>`** | `Invalid view type: 'tree'` | `<tree…>`→`<list…>`, `</tree>`→`</list>` | `l10n_ec_loans`, `l10n_ec_reports`, `l10n_ec_vacation` (views) |
| M-3 | XML-ID de menú inexistente | `External ID not found: …menu_l10n_ec_hr_payroll_root` | Corregir a `menu_l10n_ec_payroll_root` (el real en hr_payroll) | `l10n_ec_loans`, `l10n_ec_vacation` |
| M-4 | Clave `ir.config_parameter` duplicada | `duplicate key value violates unique constraint "ir_config_parameter_key_uniq"` | Fuente única: `l10n_ec_base` dueño de `sbu`/`iess_aporte_*`; `l10n_ec_hr_payroll` depende de `l10n_ec_base` y no redefine | `l10n_ec_base/data`, `l10n_ec_hr_payroll/data` + manifest |

**Verificado como VIGENTE (no rompe) en Odoo 18:** `view_mode="tree,form"` en acciones (alias
aceptado; confirmado porque `l10n_ec_edi` instala con él) y `sum="…"` en columnas `<list>`
(`list_renderer.js` lee `attrs.sum`). **No requieren cambio.**

> Regla: ante un `ParseError`/`AttributeError`/`External ID not found` en la carga de un módulo,
> verificar primero este catálogo antes de proponer una solución nueva (evita regresiones y
> soluciones *ad-hoc*).

### 5.4 Registro de cambios — identidad EC (stdnum) y vertical AGRO (2026-10-16)

Primeros usos del flujo completo ISO-09 → ISO-04 → código (DOC-01). Secuencia de IDs
`CHG-2026-NNN` iniciada aquí.

| ID | Categoría (CHG-01) | Cambio | Estado | Evidencia / próxima acción |
|---|---|---|---|---|
| CHG-2026-001 | Normal | Validación de identidad EC alineada a **stdnum**: `cedula_check_digit_ok`/`ruc_check_digit_ok` con despacho por 3er dígito (0–5 natural = cédula+001, 6 público, 9 jurídica, 7/8 inválidos); IDs de prueba exclusivos `1713488185` / `1793125212001` (D-04) | **Implementado** (código en repo) | Suite `mcp_server/test_server.py` = **51/51 OK** (2026-10-16); equivalencia stdnum **20,195 casos → 0 diferencias** (contenedor, stdnum 1.19); ISO-EC-10 FR-LE-50 · ISO-EC-11 §3.1 |
| CHG-2026-002 | Estándar (solo documentación) | Conjunto documental **vertical agro multi-crop** (D-05): SRS-VERT-AGRO v1.1, RES-VERT-2026-001 (catálogo OpenTHC + Verdnt), registros ISO-09 N-06/DES-06, ISO-10 FR-LE-50, ISO-11 51/51, ISO-06 CM-40..42, N-01 v1.1 | **Implementado** (docs) | Esta entrada · índice `docs/ISO/README.md` (DOC-05) |
| CHG-2026-003 | Normal | Parser SRI catastro: leer nombres **reales** del JSON vivo (`estadoContribuyenteRuc`, `obligadoLlevarContabilidad`, fechas anidadas en `informacionFechasContribuyente`, `regimen`, `representantesLegales[]`, banderas rojas) + fix consumidor `contribuyente_especial` (`"NO"` truthy marcaba `special`) — `l10n_ec_sri_ruc_service.py` / `res_partner.py` | **Implementado** (2026-10-16) | `l10n_ec_base/tests/test_sri_ruc_parser.py` = **7/7 OK** con payload real (guard WIZ-07 ACTIVO verificado); suite Odoo `l10n_ec_base` 0 FAIL · ISO-EC-11 §3.2 |
| CHG-2026-004 | Normal | Alinear `res_partner._validate_ec_document` a las mismas reglas stdnum (provincias 30/50, 3er dígito 0–6, fallback natural del público, dispatch por largo 10/13) + `test_identity.py` reescrito con IDs exclusivos D-04 | **Implementado** (2026-10-16) | `TestStdnumEquivalenceResPartner` = 3/3 OK en contenedor: 360 mutaciones → 0 diffs vs stdnum · ISO-EC-11 §3.2 |
| CHG-2026-005 | Normal | Test permanente `TestStdnumEquivalence` en `mcp_server/test_server.py` (referenciado por cabecera de `rules.py`) | **Implementado** (2026-10-16) | Host `Ran 54 … OK (skipped=3)`; contenedor `Ran 54 … OK`; corpus **22,727 casos → 0 diferencias** (1,682 stdnum-válidos) · ISO-EC-11 §3.1 |
| CHG-2026-006 | **Alta** | Purga total de datos falsos ordenada por dirección ("REMOVE ALL FAKE DATA"): eliminar IDs/RUC/cédulas inventados de demo, plantillas de negocio, ejemplos de código, tests y documentación — sólo IDs aprobados D-04 (`1713488185`, `1713488185001`, `1793125212001`, `9999999999999`) y el representante legal real `1716341274` (payload CANNACHAIN) | **Implementado** (2026-10-16) | Inventario previo: **39 archivos / 169 líneas**; purge ejecutada en 48+ archivos (demo, wizard, plantillas, tests, docs, handoffs) · **scan final del repo = 0 IDs falsos** (sólo IDs aprobados + literales justificados no-identidad: sentinela autorización `9999999999`, placeholders de cuenta `0000000000`, bytes de memoria, EAN, teléfonos) · MCP 54/54 · standalone 174/174 · unidades vs baseline: `275/6/22` (baseline `275/8/24` → **0 nuevos, 4 corregidos**) · barrido 5 módulos Odoo **0 failed / 0 errors** (ver CHG-007) · ISO-EC-11 §4 A1c/A1d/A1e |
| CHG-2026-007 | Normal | Eliminar el ICP legado `l10n_ec.sri_environment` (`l10n_ec_base/data/l10n_ec_sri_config.xml`) y su fila huérfana en la BD: contradice el diseño por-empresa (campo `res.company.l10n_ec_sri_environment`, `default="test"` nativo), ningún código productivo lo lee (sólo el hook de migración legado y el test que exige "sin globales"); primera ejecución de `/l10n_ec` lo expuso | **Implementado** (2026-10-16) | Registro XML removido + fila ICP borrada de `odooec` · barrido `-u l10n_ec_base,l10n_ec,l10n_ec_sri,l10n_ec_reports,l10n_ec_bank_transfer --test-enable` → **0 failed / 0 errors** · ISO-EC-11 |
| — | Operativo | Reiniciar gateway MCP (PIDs viejos 54153/54232/54648 → luego 67337/67340/68628 con `rules.py` previo al fix 07:45): gateway con código actual + `docker compose restart odoo` (proceso vivo con parser/validador nuevos) | **Implementado** (2026-10-16) | PIDs viejos terminados; respawn vía toggle `mcp.odoo.enabled` en `~/.config/opencode/opencode.json` → `✓ odoo connected` (PIDs 82324/82327/82328); verificado E2E: `detect_taxpayer` + `get_client_data` (CANNACHAIN, rules jurídica) OK; Odoo `/web/health` 200 |

## 6. Rollback — **CHG-12**

| Escenario | Procedimiento | Objetivo |
|---|---|---|
| Código (release defectuoso) | 1) `git revert <merge>` + PR menor; 2) `docker compose build odoo`; 3) `docker compose up -d odoo`; 4) si hubo migración: restaurar dump pre-upgrade (§5.1) y reintentar tras fix | ≤30 min |
| Configuración (`.env`, `postgresql.conf`) | Revert del PR; `docker compose up -d db odoo` (Postgres requiere restart para `postgresql.conf`) | ≤30 min |
| Migración fallida | DR-P5 (`02` §6): restaurar dump + revert + prueba en `odooec_restore_test` antes de reintentar | ≤60 min |
| Dato regulatorio erróneo (tasa mal cargada) | Revert del archivo `data/*` + nueva versión + **revisar comprobantes emitidos en la ventana** (listado por fecha/hora) → notas de crédito si corresponde; CAPA | ≤24 h |
| Cambio de `docker-compose.yml` | Tag anterior de imagen (`odoo-ecuador:18.0` anterior) + compose anterior (git) | ≤15 min |

**Condiciones de rollback exitoso:** healthchecks OK (`/web/health`, `pg_isready`), TP-1…TP-7 de `03` §4 en meta, y **reconciliación fiscal** de los comprobantes emitidos durante la ventana (Oficial Cumplimiento).

## 7. Plantilla de notas de release — **CHG-12b**

```markdown
## Release <YYYY-MM-DD> — <tag>
**Versión módulos:** 18.0.x.y.z | **Odoo:** ODOO_REF=<ref> | **Aprobado por (CAB):** <acta>

### Cambios regulatorios (obligatorio citar norma)
- [KB:<ruta KB>] <Resolución/ Acuerdo, RO, vigencia> → data: `<archivo data/*>` → test: `<test>`

### Cambios
| ID | Tipo (estándar/normal/emergente) | Módulo/área | Descripción | PR | Test |
|---|---|---|---|---|---|

### Impacto fiscal (comprobantes en vuelo / secuencias / migraciones)
### Configuración (diff de .env/config/* con recálculo de `03` §3)
### Rollback (comando/tag exacto)
### Verificación posterior (quién, cuándo, resultado — KPI afectados)
### Estado de `06_MATRIZ_DE_CUMPLIMIENTO.md` (filas modificadas)
```

## 8. CAB (Change Advisory Board) — **CHG-02**

### 8.1 Composición y operación

| Campo | Definición |
|---|---|
| Miembros | CIO (chair), Arquitecto, Oficial de Cumplimiento, Líder de Desarrollo, DBA, QA, Ops |
| Cuórum | ≥3, **incluyendo obligatoriamente al Oficial de Cumplimiento** cuando el cambio toque §3.2, `data/*` regulatorio, `04` §5 o `01` §5 |
| Cadencia | Semanal (martes) + sesión exprés bajo demanda (§8.2) |
| Quórum de decisión | Mayoría simple; el Oficial de Cumplimiento puede **vetar** con causa regulatoria documentada |
| Registro | Acta: ID CHG-YYYY-NNN, categoría, riesgos (ref. `06b`), plan de rollback, fecha de verificación posterior |

### 8.2 Ruta exprés (emergencias)

1. Aprobación dual CIO + Oficial de Cumplimiento por escrito (hilo registrado).
2. PR con test y revisión ≥1 (inviolable: **la emergencia no salta pruebas ni revisión**).
3. Despliegue ≤48 h; acta exprés + notas de release ≤48 h posteriores.
4. Revisión post-implementación en la próxima reunión CAB (verificar si el cambio resolvió el disparador).

## 9. Controles, evidencias y cadencia

| ID | Control | Evidencia |
|---|---|---|
| CHG-01 | Categorización documentada de cada solicitud | Ticket/acta con categoría |
| CHG-02 | Aprobación CAB (o dual exprés) | Actas CAB |
| CHG-03 | Rama `feature/*` + commit `[MODULO] …` | Historial git |
| CHG-04 | Merge a `main` solo vía PR con ≥1 revisión | PRs |
| CHG-05 | Integridad de XML-ID publicados / migraciones versionadas | Código + salida de `-u` |
| CHG-06 | Versionado `18.0.x.y.z` en los 20 manifests | Auditoría trimestral de manifests |
| CHG-07 | Pruebas obligatorias (`--test-enable`) | Reportes de suite |
| CHG-08 | `pg_dump` previo a upgrades con datos | Artefacto de dump por release |
| CHG-09/CHG-10 | Ruta calificada KB→data→test→release (§3.2) | KB + data + test + release enlazados |
| CHG-11 | Ventana de mantenimiento y prohibiciones de config | Actas y PR de config |
| CHG-12 | Rollback definido y probado (§6 + T6 de `02` §7) | Registro del simulacro |

**Cadencia de revisión:** anual del documento; auditoría de CHG-06 cada trimestre; revisión post-emergencia inmediata.

---

*Riesgos controlados aquí: R-001 y R-007 (cambios normativos SRI), R-012 (versionado/configuración desviada), R-019 (migración corrupta). Matriz de cumplimiento afectada: `06_MATRIZ_DE_CUMPLIMIENTO.md`.*
