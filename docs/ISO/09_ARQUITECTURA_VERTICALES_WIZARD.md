# 09 — ARQUITECTURA VERTICAL, WIZARD DINÁMICO Y GOBERNANZA DE DATOS

**Código**: ISO-EC-09 · **Versión**: 1.1 · **Fecha**: 2026-10-16
**Clasificación**: Documento de control — Arquitectura y configuración
**Propietario**: Arquitecto de plataforma · **Aprobador**: Gerencia TIC
**Próxima revisión**: 2027-01-15 (o ante cambio de regulación SRI/IESS)
**Relacionados**: ISO-EC-04 (Control de Cambios) · ISO-EC-06 (Matriz de Cumplimiento) · ISO-EC-07 (Gobernanza TIC/IA) · ISO-EC-03 (Capacidad)

---

## 1. Propósito y alcance

Define los **parámetros de configuración del wizard dinámico**, el modelo de
**plantillas verticales enriquecidas**, la **estructura de tenant (multi-empresa)** y las
**acciones del agente IA** sobre Odoo, de modo que la configuración de un cliente nuevo sea
reproducible, auditable y conforme a la normativa ecuatoriana.

Alcance: plataforma Odoo 18 (fuente `odoo/odoo`) + localización `l10n_ec*` + gateway MCP
`mcp_server/`, desplegados en el clúster Docker (`docker-compose.yml`).

**Fuera de alcance**: certificación de formatos bancarios (ver ISO-EC-06 fila BAN-*),
integración ECUAPASS real (stub documentado).

## 2. Referencias normativas

| Ref | Documento |
|---|---|
| N-01 | `docs/srs/SRS_WIZARD_PARAMETERS.md` (catálogo maestro: 96 parámetros core + 43 por industria = 139, desde v1.1) |
| N-02 | `docs/srs/SRS_BUSINESS_TEMPLATES.md` (sistema de plantillas, 2 dimensiones) |
| N-03 | `docs/srs/SRS_ERP_REGULATION_MATRIX.md` (matriz regulatoria) |
| N-04 | `DEVELOPMENT_PLAN.md` (sprints y agentes) |
| N-05 | Código del Trabajo, Ley de RIMPE, Código Tributario, Resolución NAC-DGERCGC (SRI) — ver ISO-EC-06 |
| N-06 | `docs/srs/SRS_VERTICAL_AGRO_TRACEABILITY.md` (vertical **agro** multi-crop, v1.1) · `docs/srs/RESEARCH_TRACEABILITY_FEATURE_CATALOG.md` (RES-VERT-2026-001: catálogo OpenTHC + trazabilidad agroalimentaria) |
| N-07 | `docs/srs/SRS_SOMATECH_ODOO_BRIDGE.md` (capa **SOMATECH-ODOO-BRIDGE** D-08 + UI/UX de verticalización encima D-09/D-10; patrón validado en demo FAME/YACHAQ) |

---

## 3. Modelo de configuración (3 dimensiones + capa legal)

```
INDUSTRIA × TAMAÑO × CAPACIDADES  +  CAPA LEGAL EC (fija, no editable)
        │
        ├─ MODULES   → módulos Odoo instalados
        ├─ FEATURES  → capacidades/UI visible
        └─ SETTINGS  → parámetros de comportamiento
```

| Control ID | Control | Evidencia |
|---|---|---|
| DES-01 | La **capa legal EC es compartida**: ninguna plantilla copia constantes legales (SBU, topes, límites $50, 5 días, 7 días, 30/70). Cambio único ⇒ heredado por todos los verticales. | `l10n_ec_base/data/*` · prueba de herencia |
| DES-02 | Las plantillas se declaran como **datos versionados** (YAML/CSV en git), nunca como código condicional. | ruta `templates/<vertical>/<size>.*` |
| DES-03 | Cada plantilla publica declara **`version` + `checksum` + `changelog`**; el loader es **idempotente** por XML-ID (re-cargar = actualizar, jamás duplicar). | `l10n_ec_vertical` · test de re-ejecución |
| DES-04 | Toda aplicación de plantilla exige **dry-run previo** con diff (creará/actualizará/saltará). | `preview_template()` · log |
| DES-05 | Ocultar capacidades **no desinstala datos**: desactivar `cost.cogs` sólo oculta/marca comportamiento; no borra registros. | prueba de toggle ON→OFF→ON |
| DES-06 | Los módulos de vertical **dependen** de la capa legal/compartida y **nunca la bifurcan**; las constantes compartidas viven en `l10n_ec_base`. Además, todo módulo de vertical es **agnóstico de cultivo** (tipo de cultivo = dato, sustancias = filas de análisis, reglas de cultivo regulado = overlays de parámetros — D-05/N-06). | grafo de dependencias `__manifest__.py` · test de campo genérico |

## 4. Capacidades y módulos (control de activación)

| Control ID | Control | Evidencia |
|---|---|---|
| CAP-01 | Toda capacidad (`cap.*`) declara **dependencias explícitas**; activar una activa sus dependencias automáticamente. | tabla de capacidades N-01 §5 |
| CAP-02 | `cap.ec_invoicing` está **bloqueado ON** (obligación SRI): no puede desactivarse. | validación wizard + tool `set_capability` |
| CAP-03 | El wizard **muestra el menú resultante** antes de aplicar (lo que verá el usuario = lo que se activa). | paso ⑤/⑪ |
| CAP-04 | Cambiar de tamaño (`simple→medium→enterprise`) es **aditivo**: nunca re-crea ni degrada datos existentes. | `apply_setup` idempotente |
| CAP-05 | Parámetros legales bloqueados (constante + `source=DEFAULT` + `readonly`): CF 50.00, 5 días hábiles, 7 días anulación, split 30/70 IVA. | `mcp_server/rules.py` tests 54/54 |

## 5. Modelo de tenant (SaaS multi-empresa)

| Control ID | Control | Evidencia |
|---|---|---|
| TEN-01 | **Tenant = 1 base de datos** = 1 grupo jurídico. Aislamiento por `dbfilter` (`ODOO_DBFILTER`). | `config/entrypoint.sh` |
| TEN-02 | **`res.company` = 1 RUC**. Varias sociedades con RUC propio ⇒ varias empresas hijas **dentro** del tenant, con padre jerárquico. | estructura Odoo |
| TEN-03 | **Establecimiento (3) + punto de emisión (3)** = unidad de firma; toda clave de acceso 49 dígitos traza a `empresa+establecimiento+punto`. | `l10n_ec_edi` clave |
| TEN-04 | Decisión de topología **siempre explícita**: *"¿Cuántos RUC firman facturas?"* → 1 RUC = establecimientos; N RUC = empresas múltiples. Nunca se infiere en silencio. | paso ④ `size.multi_ruc` |
| TEN-05 | Libros, ATS, planillas IESS y Libro de Bancos se generan **por `res.company` (= RUC)**; el consolidado es una vista de grupo. | `l10n_ec_reports` |
| TEN-06 | Credenciales y `.p12` son **por tenant/empresa**: jamás compartidos entre tenants. | §8 |

## 6. Wizard dinámico — parámetros y trazabilidad

| Control ID | Control | Evidencia |
|---|---|---|
| WIZ-01 | El wizard **nunca pregunta lo que el SRI sabe** (razón social, estado, régimen, obligación contable, agente retención, actividad, fechas). Fuente `SRI` ⇒ campo oculto/solo-lectura. | N-01 convención de fuentes |
| WIZ-02 | Todo campo **obligatorio faltante** se entrega como `needs_data` + `question` (contrato único UI↔MCP). | `mcp_server/tools.py` `create_invoice` |
| WIZ-03 | **Drag & drop** (`base_import`) con resultado por fila (`n_ok`, `n_errors[row,col,msg]`), política de errores y de duplicados explícitas por corrida. | paso ⑧ |
| WIZ-04 | **Dry-run obligatorio** antes de aplicar; aplicación con confirmación humana y snapshot previo (rollback). | paso ⑪ |
| WIZ-05 | Sesión **reanudable** (`setup_session`): lo iniciado en UI lo continúa el agente y viceversa, misma capa de servicio. | `apply_setup`/`resume_setup` |
| WIZ-06 | Los 11 pasos del wizard tienen **equivalente 1:1 en tool MCP** (tabla N-01 §"Correspondencia"). | `tools/list` (18 tools) |
| WIZ-07 | Validaciones bloqueantes: RUC mod-11, RUC/cédula inactivo ⛔, `.p12` exigido en producción, `size=simple` con `locations>1` ⇒ sugerencia de cambio de tamaño. | guardrails N-01 |
| WIZ-08 | Las 96+43 constantes del wizard viven en **un único catálogo versionado** (N-01); el código no puede definir parámetros fuera de él. | revisión de código |

## 7. Acciones del agente IA sobre Odoo

| Control ID | Control | Evidencia |
|---|---|---|
| AGT-01 | Acciones clasificadas **R (lectura, automática)**, **W (escritura, dry-run+confirm)**, **⚠ (aprobación humana explícita)** — 14 acciones ⚠. | N-01 §"acciones" + ISO-EC-07 |
| AGT-02 | Toda mutación queda en **bitácora**: tool, args, usuario, resultado, antes/después. | log Odoo + log MCP (stderr) |
| AGT-03 | El agente **no inventa datos legales**: si falta ⇒ `needs_data`; si duda ⇒ pregunta; nunca completa un RUC, dirección o tarifa por su cuenta. | `rules.py` |
| AGT-04 | Consultas al SRI sujetas al **control de tasa** (2 s, 5/min, caché 24 h, kill-switch) — ver SEC-06. | `mcp_server/sri_client.py` |
| AGT-05 | Los umbrales de negocio del agente (topes, feriados, tablas) se leen de `ec://rules`/`ec://holidays`, no de literales en el prompt. | recursos MCP |

## 8. Datos, secretos y auditoría (vínculo con ISO-EC-01/05)

| Control ID | Control |
|---|---|
| SEC-01 | Secretos (contraseñas DB/maestra, `.p12`) sólo en `.env` fuera de git + volúmenes; **nunca** en plantillas ni logs. |
| SEC-02 | Contraseñas de certificado **no se persisten en claro**; sólo se prueban al cargar. |
| SEC-03 | El gateway MCP **no escribe en stdout** salvo protocolo (logs a stderr) — separación de canales. |
| SEC-04 | Datos de prueba/ingesta de clientes: tratamiento conforme a la **Ley Orgánica de Protección de Datos Personales** (ver ISO-EC-06 fila DP-*). |
| SEC-05 | Retención de evidencia de configuración: XML firmados, claves, RIDE ≥ plazo legal (ver ISO-EC-05). |
| SEC-06 | **Anti-banneo SRI**: intervalo ≥ 2 s, ≤ 5 llamadas/min, backoff ante 429, caché 24 h, `SRI_DISABLED=1` como corte total. Contador de llamadas evidenciable (`--stats`). |

## 9. Ciclo de vida del documento (gestión documental continua)

| Control ID | Regla |
|---|---|
| DOC-01 | **Todo cambio de diseño pasa primero por aquí** (ISO-EC-09), luego por ISO-EC-04 (Cambio), luego por código. Nada de "decisión en el chat y se olvida". |
| DOC-02 | Cada decisión de brainstorming se convierte en: (a) fila de control con ID, (b) fila en ISO-EC-06 si toca cumplimiento, (c) test si es verificable. |
| DOC-03 | Cadencia: revisión trimestral + **revisión inmediata ante**: resolución SRI/MDT/IESS nueva, alta de vertical, alta de tool MCP, cambio de tenant/topología. |
| DOC-04 | Trazabilidad inversa obligatoria: `parámetro → control (este doc) → módulo/archivo → test`. Una cadena rota = no conformidad. |
| DOC-05 | El índice y el control de revisiones viven en `docs/ISO/README.md`; ningún documento se añade sin registrarse ahí. |
| DOC-06 | Versión semántica: `1.x` cambios editoriales · `2.x` cambios de arquitectura · `3.x` cambios por normativa nueva. |

## 10. Indicadores (vínculo ISO-EC-08)

| Indicador | Meta | Fuente |
|---|---|---|
| Tiempo wizard: RUC → empresa operativa | ≤ 5 min (simple) | `setup_session` timestamps |
| Parámetros que el usuario debe teclear (vs auto-SRI) | ≤ 12 en simple | log del wizard |
| Corrección de ingesta en 1ª pasada | ≥ 98% filas válidas | `ingest.result` |
| Plantillas con checksum validado en CI | 100% | test de plantillas |
| Mutaciones del agente con bitácora completa | 100% | log MCP |
| Llamadas SRI cacheadas | ≥ 90% | `--stats` |

## 11. Historial de revisiones

| Ver. | Fecha | Autor | Cambio |
|---|---|---|---|
| 1.0 | 2026-10-15 | Plataforma | Versión inicial: verticales, capacidades, tenant, wizard (96+34 parámetros), reglas del agente, ciclo de vida documental. |
| 1.1 | 2026-10-16 | Plataforma | Alta vertical **agro** multi-crop: ref. N-06, control **DES-06** (dependencia de capa compartida + agnosticismo de cultivo, D-05), catálogo N-01 96+43=139, evidencia CAP-05 51/51. |
