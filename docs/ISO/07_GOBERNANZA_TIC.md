# ISO-EC-07 — Gobernanza TIC

**Proyecto:** Odoo 18 Ecuador Localization · **Versión:** 1.0 · **Fecha emisión:** 2026-10-15
**Responsable:** Gerencia de TI / Junta Directiva · **Próxima revisión:** 2027-04-15
**Clasificación:** Uso interno

---

## 1. Propósito y Alcance

Define la **gobernanza de la tecnología** de la plataforma: principios (ISO/IEC 38500), derechos de
decisión, segregación de funciones, gestión de terceros (proveedores de software y servicios) y
**gobernanza de agentes de IA/MCP** que operan sobre Odoo. Es el documento rector; los controles
operativos viven en 01–05.

Alcance: plataforma Odoo 18 Ecuador, contenedores Docker/EC2, módulos `l10n_ec*`, integraciones
gubernamentales (SRI/IESS/SENAE/BCE) y el gateway MCP con sus 18 herramientas.

## 2. Referencias Normativas

| Referencia | Observación |
|---|---|
| ISO/IEC 38500:2024 (gestión de TI corporativa) | Seis principios (§3) |
| ISO/IEC 27001:2022 A.5.1–A.5.35 (controles organizacionales) | SoD, terceros |
| ISO/IEC 27017 / 27018 (seguridad y privacidad en la nube) | Proveedores cloud |
| ISO/IEC 42001 (gestión de IA) | Agentes IA/MCP |

## 3. Principios ISO/IEC 38500 y su aplicación

| Principio | Aplicación concreta en esta plataforma | Control |
|---|---|---|
| **Responsabilidad** | Dueños nombrados por control (00 §5); dueño de riesgo por riesgo (06b §4) | 00 §5, 06b |
| **Estrategia** | Alineación con `DEVELOPMENT_PLAN.md` y `docs/CUMPLIMIENTO_REGULATORIO.md` como fuente de roadmap | CHG-02 |
| **Adquisición** | Dependencias upstream (`github.com/odoo/odoo`, Debian, PostgreSQL) gestionadas por manifest y `requirements.txt` | SEG-20, CHG-08 |
| **Rendimiento** | KPIs y monitoreo (03, 08) | CAP-08, KPI-* |
| **Conformidad** | Matriz de cumplimiento (06) y auditoría (05) | CM-*, AUD-* |
| **Comportamiento humano** | Separación de duties, aprobación humana de agentes IA (§5) | SEG-12, GOV-09 |

## 4. Derechos de Decisión y Segregación de Funciones (SoD)

| Decisión | Quién decide | Quién ejecuta | Quién verifica | Artefacto |
|---|---|---|---|---|
| Publicar versión nueva del ERP | Gerencia TI | Dev (PR en `main`) | Revisor (peer) | PR de Git |
| Hotfix regulatorio SRI | Líder fiscal | Dev | QA fiscal | 04 §3.2, acta |
| Cambios de configuración (`config/*`, compose) | Gerencia TI | Infra (PR) | DevOps | Git |
| Alta/baja de usuarios y grupos Odoo | Administrador Odoo | Admin | Auditor (RO 395-2025) | 05 AUD-12 |
| Emisión/anulación de comprobantes | Área fiscal | Usuario fiscal | Admin | Odoo (AUD-04) |
| Ejecución de backup/restore | Infra | Infra | Calidad | 02 |
| Acceso root a la EC2 | Gerencia TI (con bitácora) | Infra | Seguridad | Bitácora |
| Uso de agentes IA sobre Odoo | Gerencia TI | Agente (limitado) | Humano aprobador | §5, §7 |

**Segregación mínima obligatoria**: quien administra la BD (superuser) no firma comprobantes; quien
desarrolla código no aprueba su propio PR; el Auditor de Transparencia tiene solo lectura
(`l10n_ec_base/security/l10n_ec_groups.xml`).

## 5. Gobierno de Agentes de IA / Gateway MCP

### 5.1 Clasificación de las herramientas del gateway Odoo

El catálogo expone **18 tools**; se listan las 14 visibles en el registro actual (las 4 restantes se
clasifican por defecto como *mutantes* hasta revisión del dueño del gateway — §5.2).

**De solo lectura (read-only)** — seguras para agentes sin aprobación humana:

| # | Tool | Nota |
|---|---|---|
| 1 | `detect_taxpayer` | Consulta SRI |
| 2 | `validate_ruc` | Validación RUC/cédula |
| 3 | `get_client_data` | Datos del cliente |
| 4 | `get_sales_summary` | Reporte |
| 5 | `get_ar_aging` | Reporte |
| 6 | `get_stock_level` | Reporte |
| 7 | `send_ride` | Envío de RIDE (lectura de comprobante) |
| 8 | `generate_ats` | Generación de reporte ATS |
| 9 | `generate_iess_planilla` | Generación de planilla IESS |
| 10 | `generate_payslips` | Nómina (lectura/cálculo, sin efecto fiscal inmediato) |

**Mutantes (con efecto fiscal/financiero)** — requieren **aprobación humana previa**:

| # | Tool | Efecto | Control |
|---|---|---|---|
| 11 | `create_partner` | Crea entidad con datos fiscales | GOV-09 |
| 12 | `post_invoice` | Publica y envía al SRI (firma electrónica) | GOV-09 (aprobación) |
| 13 | `record_payment` | Registra cobro/pago | GOV-09 (aprobación) |
| 14 | `create_credit_note` | Emite NC (anula efecto fiscal) | GOV-09 (aprobación) |

Resto del catálogo no listado (4 tools sin detalle en el registro): se clasifican por defecto como
**mutantes** hasta que el dueño del gateway revise y documente su efecto (§5.2).

### 5.2 Reglas operativas para agentes

| Regla | Descripción | Control |
|---|---|---|
| **Principio de mínimo privilegio** | Agente solo con permisos read-only por defecto | GOV-11 |
| **Aprobación humana** | Toda tool mutante (§5.1) requiere confirmación de usuario autorizado (fiscal) antes de ejecutarse | GOV-09 |
| **Rate limit** | Máximo N transacciones mutantes por hora/sesión por agente (definir N según volumen) | GOV-10 |
| **Trazabilidad** | Cada invocación de tool se registra (quién/qué/cuándo/resultado) — logs Odoo (`res.users.log`, `mail.tracking.value`) y logs del gateway | AUD-01, AUD-02, §7 |
| **No-escalada** | El agente no puede autogenerarse permisos ni ejecutar SQL arbitrario | SEG-12 |
| **Revisión de tools** | Catálogo de tools revisado trimestralmente (alta/baja de tools, cambios de permisos) | AUD-12, §7 |

### 5.3 Responsabilidades del uso de IA

| Rol | Responsabilidad |
|---|---|
| Dueño del gateway MCP | Publicar/mantener el código (`l10n_ec_base/mcp/`), clasificar tools, aplicar rate limit |
| Aprobador humano (fiscal) | Autoriza operaciones mutantes; responde por errores de negocio |
| Seguridad | Auditoría de logs, permisos y revisiones trimestrales |
| Auditor | Verifica segregación y trazabilidad |

## 6. Gestión de Terceros y Cadena de Suministro

| Tercero | Rol | Riesgo asociado | Control | Monitoreo |
|---|---|---|---|---|
| `github.com/odoo/odoo` | Base del ERP | Vulnerabilidades, cambios upstream | SEG-20, CHG-08 | Revisión de releases |
| Debian (base de imágenes) | SO de contenedores | CVEs | SEG-20 | Escaneo de imágenes |
| PostgreSQL | Motor de BD | Versiones, parches | CAP-04 | `SELECT version()` |
| AWS/EC2 (+ Docker Hub) | Infraestructura | Disponibilidad, seguridad | SEG-03 | Disponibilidad (KPI-01) |
| SRI / IESS / SENAE / BCE | Servicios gubernamentales | Indisponibilidad externa | BC-12, CM-* | Latencia SRI (KPI-09) |

## 7. Revisión y Reporte de Gobierno

| Actividad | Frecuencia | Responsable | Artefacto |
|---|---|---|---|
| Revisión del catálogo de tools MCP y permisos de agentes | Trimestral | Dueño del gateway + Seguridad | Acta (05 §8) |
| Revisión de riesgos (06b) y plan de tratamiento | Trimestral | Gerencia | 06b §6 |
| Revisión de cumplimiento (06) | Semestral | Cumplimiento | 06 §4 |
| Reporte a dirección (KPIs de 08) | Semestral | Gerencia TI | 08 §3 |

## 8. Seguimiento

| Métrica | Meta | Relación |
|---|---|---|
| Tools mutantes sin aprobación humana | 0 | GOV-09 |
| Invocaciones de tools registradas | 100% | GOV-10, AUD-01 |
| Revisiones de gobierno realizadas a tiempo | 100% | KPI-18 |
