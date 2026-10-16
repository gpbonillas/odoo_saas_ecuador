# 01 — POLÍTICA DE SEGURIDAD DE LA INFORMACIÓN (ISO/IEC 27001:2022)

**ISMS — Plataforma SaaS Odoo 18 Ecuador (clúster `odoo-ec`)**

| Campo | Valor |
|---|---|
| Código documento | ISO-EC-ISMS-01 |
| Versión | 1.0 |
| Fecha de emisión | 2026-10-15 |
| Propietario | Responsable de Seguridad de la Información (RSI) |
| Aprobador | CIO |
| Próxima revisión | 2027-04-15 (anual) / inmediata ante incidente S1–S2 |
| Clasificación | Uso interno — ISO-EC-CL/2 |

---

## 1. Objeto y alcance del ISMS (Purpose & Scope)

Proteger la confidencialidad, integridad y disponibilidad de la información de la plataforma que procesa transacciones fiscales, laborales y contables ecuatorianas a escala empresarial.

**Alcance (ISMS scope statement):**

| Capa | Elementos incluidos (verificados en `docker-compose.yml`) |
|---|---|
| Datos | Servicio `db` (`postgres:16-alpine`), volumen `dbdata` (datos transaccionales), `dblogs` (bitácora Postgres), `dbbackups` (dumps `pg_dump -Fc`) |
| Aplicación | Servicio `odoo` (imagen `odoo-ecuador:18.0` construida desde `github.com/odoo/odoo` vía `Dockerfile`), volumen `odoo-filestore` (adjuntos: **XML firmados, RIDE, claves de acceso**), `odoo-sessions`, `odoo-logs` |
| Agente IA | Servicio `mcp` (`python:3.12-slim`, `MCP_TRANSPORT=stdio`) — ver §5 y `07_GOBERNANZA_TIC.md` §6 |
| Respaldo | Servicio `backup` (`postgres:16-alpine`, `pg_dump -Fc` cada 21600 s = 6 h, retención `KEEP_DAYS=14`) |
| Configuración | `config/odoo.conf` (montado `:ro`), `config/postgresql.conf` (montado `:ro`), `config/entrypoint.sh` (renderiza `odoo.conf` en arranque), `.env` (secretos) |
| Red | Red `backend` (bridge, `internal: false`); puertos 8069/8072 publicados |
| Código | 20 módulos `l10n_ec*`, `tests/`, `l10n_ec_base/mcp/` |

**Fuera de alcance (gestionado como riesgo de tercero):** infraestructura física del proveedor cloud, SRI/IESS (sistemas externos), emisor de certificados, proveedor de correo para RIDE.

## 2. Referencias normativas (Normative references)

| Ref. | Documento |
|---|---|
| [1] | ISO/IEC 27001:2022 cláusulas 4–10 y Annex A (93 controles, 4 temas) |
| [2] | ISO/IEC 27002:2022 — guía de controles |
| [3] | Ficha Técnica SRI v2.32 y Res. NAC-DGERCGC25-00000017 (requisitos de firma y no repudio) |
| [4] | Ley Orgánica de Protección de Datos Personales (Ley 0/14) + reglamento `[VERIFY: número exacto del decreto reglamentario — verificar en Registro Oficial / Portal de Trámites]` |
| [5] | Resolución 395-2025 (RO) — Auditor de Transparencia, referenciada en `l10n_ec/security/l10n_ec_security.xml` `[VERIFY: texto íntegro de la RO]` |
| [6] | `docs/ISO/02_CONTINUIDAD_Y_RECUPERACION.md`, `04_CONTROL_DE_CAMBIOS.md`, `05_TRAZABILIDAD_Y_AUDITORIA.md`, `06b_MATRIZ_DE_RIESGOS.md`, `07_GOBERNANZA_TIC.md` |

## 3. Gestión de activos (Inventory of assets) — control **SEG-01** (Annex A.5.9)

### 3.1 Servicios y volúmenes

| Activo ID | Activo | Tipo | Valor/CIA | Propietario | Ubicación verificada | Retención/respaldo |
|---|---|---|---|---|---|---|
| AS-01 | Servicio `db` | Contenedor | C/I/A — núcleo | DBA | `docker-compose.yml` (líneas 38–66), límite 12 G | `pg_dump` cada 6 h → `dbbackups` |
| AS-02 | Volumen `dbdata` | Datos | C/I/A | DBA | `volumes.dbdata` | Respaldado vía AS-06 (SQL) |
| AS-03 | Servicio `odoo` | Aplicación | C/I/A | Arquitecto | `docker-compose.yml` (69–125), límite 10 G | Código en git; filestore **sin respaldo automatizado** (→ R-002) |
| AS-04 | Volumen `odoo-filestore` | Datos | **A/I — XML firmados, RIDE** | Oficial Cumpl. | mount `odoo-filestore:/var/lib/odoo/filestore` | **Pendiente** (ver `02` §5.2, BC-03) |
| AS-05 | Servicio `mcp` + `l10n_ec_base/mcp/` | Agente IA | C/I/A | Líder Dev | `docker-compose.yml` (127–142) | Código en git |
| AS-06 | Servicio `backup` + volumen `dbbackups` | Respaldos | A | DBA | `docker-compose.yml` (144–172) | 14 días, máx. 56 dumps |
| AS-07 | Certificados `.p12` de clientes | Credencial | **C/A — no repudio** | Custodio .p12 | Modelo `l10n_ec.certificate` (`l10n_ec_edi/models/l10n_ec_certificate.py`) con `attachment=True` | En filestore (AS-04) |
| AS-08 | `.env` (contraseñas PG/Odoo), `config/*` | Configuración | C/I | DBA | raíz del repo | Cambios vía CHG (`04`) |
| AS-09 | Bitácoras `dblogs`, `odoo-logs`, `json-file` | Evidencia | I/A | Ops | volúmenes `dblogs`/`odoo-logs`; logging `50m × 10` | Ver `05` §5 |
| AS-10 | Repositorio git `github.com/somatechlat/odoo_saas_ecuador` | Código | C/I/A | Líder Dev | `git remote -v` | Historial inmutable en `main` |

### 3.2 Clasificación de la información

| Nivel | Ejemplos | Controles mínimos |
|---|---|---|
| L3 Crítico | `.p12` + contraseñas, `admin_passwd`, contraseñas PG | Acceso solo grupo `base.group_system`; nunca en git; rotación (`SEG-05`) |
| L2 Restringido | XML firmados, RIDE, claves de acceso 49 díg., nómina, datos personales | Solo roles autorizados (`SEG-03`); respaldo; retención ≥7 años (`05` §8) |
| L1 Interno | Códigos fuente, KPI, documentación ISO | Control de versiones, revisión por pares |
| L0 Público | README, manuales de usuario | Publicación vía CHG-09 |

## 4. Evaluación de riesgos de seguridad (Risk assessment) — **SEG-02**

### 4.1 Matriz de valoración (probabilidad × impacto)

| Prob. | Definición | | Impacto | Definición (C/I/A) |
|---|---|---|---|---|
| 5 | Casi segura (>80%) | | 5 | Crítico — parálisis fiscal/laboral, sanciones SRI/IESS |
| 4 | Probable (50–80%) | | 4 | Mayor — pérdida de datos con recuperación >24 h |
| 3 | Posible (20–50%) | | 3 | Moderado — degradación >4 h o evidencia dañada |
| 2 | Poco probable (5–20%) | | 2 | Menor — incidente aislado, sin impacto regulatorio |
| 1 | Rara (<5%) | | 1 | Inapreciable |

**Umbral de tratamiento:** P×I ≥ 12 → tratamiento obligatorio con plan y fecha; 6–11 → tratamiento o aceptación documentada; ≤5 → aceptación con monitoreo.

### 4.2 Riesgos de seguridad registrados (extracto — registro completo en `06b_MATRIZ_DE_RIESGOS.md`)

| Riesgo | Desc. | P | I | P×I | Tratamiento | Control (este doc u otro) |
|---|---|---|---|---|---|---|
| R-001 | Resolución SRI a mitad de año no aplicada → comprobantes rechazados | 4 | 5 | **20** | Mitigar | CHG-09/CHG-10 (`04` §3.2) → `l10n_ec_edi/` |
| R-002 | Pérdida de `odoo-filestore` (XML firmado/RIDE) sin respaldo | 3 | 5 | **15** | Mitigar | BC-03 (`02` §5.2) |
| R-004 | Compromiso/uso indebido de certificado `.p12` | 3 | 5 | **15** | Mitigar | SEG-04, SEG-05 (§5.3) |
| R-008 | Agente MCP muta sin aprobación humana | 3 | 5 | **15** | Mitigar | GOV-07…GOV-09 (`07` §6) |
| R-009 | Credenciales por defecto en `.env` (`change-me-*`) en producción | 4 | 4 | **16** | Mitigar | SEG-06 (§5.1) |
| R-012 | Exceso de privilegios / sin revisión trimestral de accesos | 3 | 4 | **12** | Mitigar | SEG-07 (§5.1), AUD-10 (`05`) |
| R-015 | Fuga de datos personales (Ley 0/14) | 3 | 4 | **12** | Mitigar | SEG-16 (§5.5), GOV-10 (`07`) |
| R-017 | Compromiso de suministro: `github.com/odoo/odoo`, Debian, Postgres | 3 | 4 | **12** | Mitigar | SEG-11 (§5.6) |

## 5. Selección de controles Annex A (Statement of Applicability)

*Seleccionados y justificados los aplicables; controles no aplicables se documentan con justificación en el registro SOA. Estado: **I**mplementado / **P**arcial / **Pd**endiente.*

### 5.1 Controles organizativos y de acceso

| Control | ID | Annex A | Implementación real en este despliegue | Estado |
|---|---|---|---|---|
| Política de seguridad y usos aceptables | SEG-01/SEG-17 | A.5.1, A.5.10 | Este documento + `07_GOBERNANZA_TIC.md` | I |
| Inventario de activos | SEG-01 | A.5.9 | §3 de este documento | I |
| Control de acceso / identidades | SEG-03 | A.5.15, A.5.16, A.5.18 | Grupos: `l10n_ec_base/security/l10n_ec_groups.xml` (Invoice Clerk, Accountant, AP/AR Clerk, Payroll, HR Manager); `l10n_ec/security/l10n_ec_security.xml` (Accountant, Manager, **Auditor de Transparencia RO 395-2025 solo-lectura**); matrix `l10n_ec_sri/docs/09_security_matrix/SECURITY_ROLE_MATRIX.md` | **P** (faltan `ir.rule` multiempresa por módulo — verificar `l10n_ec/security/` vs 20 módulos) |
| Información de autenticación (secretos) | SEG-06 | A.5.17 | `.env` con `POSTGRES_PASSWORD`, `ODOO_ADMIN_PASSWD` (defaults `change-me-*` **prohibidos en producción**); `config/odoo.conf` con `chmod 640` (`entrypoint.sh` línea 53) | **P** — ver R-009 |
| Revisión de accesos | SEG-07 | A.5.18 | Revisión trimestral obligatoria (`05` §7) | **Pd** (sin registro aún) |
| Separación de entornos | SEG-08 | A.5.15 | Ambientes SRI pruebas (`celcer`) vs producción (`cel`) en `l10n_ec_edi/models/sri_service.py` | I |
| Políticas de desarrollo seguro | SEG-09 | A.5.37, A.8.26 | `CONTRIBUIR.md` (revisión ≥1 PR), pruebas obligatorias (`DEVELOPMENT_PLAN.md` ground rules), `tests/` | **P** |

### 5.2 Criptografía y no repudio — control **SEG-10** (Annex A.8.24)

| Requisito | Implementación verificada | Estado |
|---|---|---|
| Firma electrónica avanzada de comprobantes | Firma **XAdES-BES (SHA-256)** en `l10n_ec_edi/models/sri_signer.py` → `sign_xml(xml_content_bytes, p12_binary, p12_password)`, `_build_signed_info`, `_build_qualifying_properties` | I |
| Custodia del certificado `.p12` | `l10n_ec.certificate` (`l10n_ec_edi/models/l10n_ec_certificate.py`): `content` (Binary, `attachment=True`), `password` con `groups="base.group_system"`, validación `action_validate()` y `action_check_expiry()` | I |
| Cifrado en tránsito | Endpoints SRI vía HTTPS (`celcer.sri.gob.ec`, `cel.sri.gob.ec`) consumidos con `zeep`/`requests` (`l10n_ec_edi/models/sri_service.py`) | I |
| Cifrado en reposo (filestore, `dbdata`) | **No implementado a nivel de aplicación** — depende del cifrado del volumen del proveedor cloud | **Pd** — R-013, `[VERIFY: cifrado de volúmenes del proveedor]` |
| Control de integridad post-firma | XML firmado + clave de acceso 49 dígitos (módulo 11) en `l10n_ec_edi/models/access_key.py`; cualquier alteración invalida el hash | I |

### 5.3 Seguridad operativa y de red

| Control | ID | Annex A | Implementación real | Estado |
|---|---|---|---|---|
| Registro (logging) | SEG-11 | A.8.15 | `config/postgresql.conf`: `logging_collector=on`, `log_connections/disconnections/lock_waits=on`, `log_min_duration_statement=250ms` → volumen `dblogs`; Odoo `logfile=/var/log/odoo/odoo.log` (render, `entrypoint.sh` línea 47) → `odoo-logs`; Docker `json-file` `max-size 50m, max-file 10` | **P** — `odoo.log` sin rotación propia (ver `05` §5) |
| Monitoreo | SEG-12 | A.8.16 | Healthchecks `pg_isready` y `/web/health` en `docker-compose.yml`; métricas de `03` §5 | **P** |
| Gestión de capacidad | SEG-13 | A.8.6 | `03_GESTION_DE_CAPACIDAD.md` | I |
| Copias de seguridad | SEG-14 | A.8.13 | Servicio `backup`: `pg_dump -Fc` cada 6 h, retención 14 d | **P** — solo BD principal (`ODOO_DB`), sin filestore (`02` §5.2) |
| Respuesta a incidentes | SEG-15 | A.5.24, A.5.26 | Clasificación §6 + procedimiento `02` §6 | **P** |
| Control de cambios en configuración | SEG-18 | A.8.9, A.8.32 | `04_CONTROL_DE_CAMBIOS.md` (CHG) — montajes `:ro`, render por `entrypoint.sh` desde `.env` | I |
| Protección contra malware / parches | SEG-19 | A.8.2, A.8.7 | Builds desde `debian:bookworm-slim` + `ODOO_REF` fijo en `.env` | **Pd** — sin proceso documentado de CVE scan → R-017 |
| Instalación en producción | SEG-20 | A.8.19 | Solo vía `docker compose build` + PR a `main` (CHG-04) | I |

### 5.4 Suministro (supplier) — control **SEG-11b** (Annex A.5.19, A.5.22, A.5.23)

| Proveedor | Activo/adquisición | Riesgo | Control |
|---|---|---|---|
| Odoo S.A. | Código fuente `https://github.com/odoo/odoo` @ `ODOO_REF=18.0` (`Dockerfile` líneas 8–22) | Cambio/breaking upstream | Fijar ref en `.env`; reglas de upgrade en `04` §5 |
| Proyecto Debian | `debian:bookworm-slim`, paquetes apt | CVE de sistema | Actualizaciones en ventana CHG-11 `[VERIFY: frecuencia de rebuild de imagen]` |
| PostgreSQL | `postgres:16-alpine`, `config/postgresql.conf` | CVE / malconfiguración | Parámetros con `synchronous_commit=on`, `fsync=on` (`postgresql.conf` líneas 21–23) |
| Emisor de certificados | Security Data, ANF AC Ecuador, BCE (`docs/INSTALACION.md`) | Vigencia/revocación | `action_check_expiry()` + alarma 30 días (KPI-16) |
| Proveedor cloud (host) | Volúmenes y red | Indisponibilidad/fuga | RPO/RTO `02` §4; `[VERIFY: SLA y cifrado del proveedor]` |

### 5.5 Privacidad (Ley 0/14) — control **SEG-16** (Annex A.5.34)

Datos personales procesados: socios/RUC/cédula, nómina (`hr.employee`, `hr.payslip`), asistencia, portal (`l10n_ec_portal/controllers/portal.py`). Controles: minimización por grupo de seguridad (§5.1), retención documentada (`05` §8), registro de accesos. **Estado: Pd** — no existe registro de actividades de tratamiento ni base legal por tratamiento `[VERIFY: exigencias del reglamento de la Ley 0/14]`.

## 6. Clasificación y gestión de incidentes — **SEG-15** (§6)

| Severidad | Definición (ejemplos reales) | Notificación | Contención | Plazo resolución objetivo |
|---|---|---|---|---|
| **S1 Crítico** | Pérdida de `dbdata`; ransomware; fuga de `.p12` o de XML firmados de clientes; rechazo masivo SRI por cambio no aplicado | CIO + Oficial Cumpl. + affected clients ≤2 h | Detener emisión; aislar red `backend`; activar `02` §5 | ≤4 h (MTTR, KPI-09) |
| **S2 Alto** | `odoo-filestore` dañado/pérdida parcial; certificado `.p12` vencido/comprometido; post/annul no autorizado por agente MCP | CIO + Oficial Cumpl. ≤4 h | Rollback (`04` §6); congelar agente MCP | ≤8 h |
| **S3 Medio** | Caída del servicio `odoo`/`db` (healthcheck fail); agotamiento de conexiones PG (R-003); lentitud SRI sostenida | Ops ≤8 h | Restart/escalamiento vertical (`03` §7) | ≤24 h |
| **S4 Bajo** | Log crecido sin rotación; configuración desviada detectada en auditoría | Ticket estándar | Corregir vía CHG | ≤5 días hábiles |

**Registro obligatorio de todo incidente ≥S3:** causa, línea de tiempo, evidencias (`05` §2), acciones, CAPA (`00` §10). Lección aprendida → actualizar `06b` en ≤10 días.

## 7. Métricas de seguridad (medición del Annex A)

| ID | Métrica | Meta | Frecuencia | Responsable |
|---|---|---|---|---|
| SEC-M1 | Incidentes S1/S2 por trimestre | 0 | Trimestral | RSI |
| SEC-M2 | MTTR de incidentes S1/S2 | ≤4 h | Por evento | Ops |
| SEC-M3 | Usuarios con privilegio `base.group_system` revisados | 100% revisados/trimestre | Trimestral | DBA + Oficial Cumpl. |
| SEC-M4 | Certificados `.p12` vigentes (sin vencer en ≤30 días) | 100% | Mensual | Custodio .p12 |
| SEC-M5 | Cambios de config sin ticket CHG | 0 | Mensual | RSI |
| SEC-M6 | Cobertura de respaldo BD (ventana ≤6 h) | ≥99% ejecuciones | Diaria | DBA |

## 8. Responsabilidades, evidencias y revisión

| Rol | Responsabilidad (RACI ampliado en `00` §5.2) |
|---|---|
| CIO | Aprueba la política; escala S1; aprueba excepciones |
| Responsable de Seguridad (RSI) | Mantiene SOA, evaluación de riesgos, clasifica incidentes |
| DBA | Ejecuta respaldos/restauraciones, revisa accesos de BD, aplica `postgresql.conf` |
| Ops | Monitoreo, rotación de logs, primer filtro de incidentes |
| Custodio `.p12` | Custodia, rotación, revocación de certificados |
| Oficial de Cumplimiento | Traduce obligación regulatoria → control (matriz `06`); valida evidencias |
| Auditor de Transparencia (RO 395-2025) | Solo lectura sobre logs y transmisiones SRI (`l10n_ec/security/l10n_ec_security.xml`) |

**Evidencias/artefactos:** §3 inventario; SOA (§5); registro de riesgos `06b`; registro de incidentes; actas de revisión; logs en `dblogs`/`odoo-logs`/`json-file`; actas de revisión de accesos (`05` §7).

**Cadencia de revisión:** anual (2027-04-15); revisión de accesos trimestral; evaluación de riesgos trimestral o bajo detonante (nueva Res. SRI, incidente ≥S2, cambio de arquitectura, nuevo módulo `l10n_ec_*`).

---

*Relacionado: `06b_MATRIZ_DE_RIESGOS.md` (R-001…R-020) · `02_CONTINUIDAD_Y_RECUPERACION.md` (BC-*) · `05_TRAZABILIDAD_Y_AUDITORIA.md` (AUD-*) · `07_GOBERNANZA_TIC.md` (GOV-*, agente MCP).*
