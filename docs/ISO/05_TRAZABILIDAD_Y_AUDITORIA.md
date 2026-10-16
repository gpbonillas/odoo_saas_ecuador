# ISO-EC-05 — Trazabilidad y Auditoría

**Proyecto:** Odoo 18 Ecuador Localization · **Versión:** 1.0 · **Fecha emisión:** 2026-10-15
**Responsable:** Equipo de Desarrollo / Auditores Internos · **Próxima revisión:** 2027-04-15
**Clasificación:** Uso interno

---

## 1. Propósito y Alcance

Documento que define cómo se **registra, conserva, protege y audita** la información del sistema
Odoo 18 Ecuador: qué eventos quedan registrados, con qué grado de inmutabilidad, cuánto tiempo se
conservan las evidencias (contables, tributarias y de seguridad) y qué rutinas de auditoría se
ejecutan. Es la base del principio de **trazabilidad** (ISO/IEC 27001 A.8.15, A.8.16; A.5.33
protección de registros).

Alcance: registros de Odoo (`account.move`, `res.users.log`, `mail.message`,
`mail.tracking.value`, `ir.logging`), XMLs firmados y claves de acceso del SRI, logs de contenedor,
historial de configuración, y mecanismos de bloqueo contable (`fiscalyear_lock_date`,
`quarterly_lock_date`).

Fuera de alcance: auditoría financiera externa (estados financieros) y nómina IESS.

## 2. Referencias Normativas

| Referencia | Observación |
|---|---|
| ISO/IEC 27001:2022 A.8.15 (logging), A.8.16 (monitorización), A.5.33 (protección de registros) | — |
| ISO/IEC 27037 (identificación, colección y preservación de evidencia digital) | — |
| Código Tributario, Art. 43 [VERIFY: obligación de conservar libros/registros contables por 7 años — verificar número de artículo y redacción vigente en sri.gob.ec] | Respaldo de la retención ≥ 7 años |
| Resolución SRI (adopción de facturación electrónica) — texto completo [VERIFY: número de resolución] | Inmutabilidad del comprobante autorizado |
| RO 395-2025 (control de seguridad de credenciales) | Auditoría de accesos |
| Odoo 18: `addons/base/models/res_users.py:304` (`res.users.log`), `addons/mail/models/mail_tracking_value.py` | Verificado en imagen `odoo:18.0` |

## 3. Controles

| ID | Control | Implementación verificada | Evidencia | Frecuencia |
|---|---|---|---|---|
| AUD-01 | **Autenticación auditada**: cada login (y logout) crea registro `res.users.log` (immutable: borrado lógico por `ir.model.data`) | `res_users.py:304` en `odoo:18.0` | Tablas `res_users_log`, consulta SQL | Continua |
| AUD-02 | **Historial de cambios en campos críticos** con `tracking=True` → `mail.tracking.value` conserva valor anterior/nuevo con usuario y fecha | Modelos l10n_ec_edi/payroll (buscar `tracking=True`) | `mail_tracking_value` | Continua |
| AUD-03 | **Traza de mensajes/acciones** en `mail.message` por documento fiscal | `mail_message` | Semanal | Continua |
| AUD-04 | **Inmutabilidad del asiento contable**: sin `move_id.button_cancel` ni borrado físico desde UI; anulación contable solo por NC (`04_CONTROL_DE_CAMBIOS.md` CHG-11) | `l10n_ec_edi/models/account_move.py` | Auditoría de `account_move.state='cancel'` sin NC asociada (debe ser 0) | Mensual |
| AUD-05 | **Bloqueo de períodos contables** (`fiscalyear_lock_date` / `quarterly_lock_date`) tras cierre: Configuración → Contabilidad → Bloquear/Enviar contabilidad | Campo `fiscalyear_lock_date` verificado en Odoo 18 (menú de Ajustes) | Captura de settings + fecha del lock en tabla | Trimestral |
| AUD-06 | **XML firmado inmutable**: el comprobante XML autorizado por el SRI se conserva con clave de acceso y URL de autorización; la NC referencia el documento origen | `l10n_ec_edi/models/` (`sri_signer.py`, `sri_service.py`, `access_key.py`) | Archivos XML en filestore + tabla de claves de acceso | Continua |
| AUD-07 | **RIDE y XML firmado disponibles para entrega/re-auditoría** (herramientas `send_ride`, evidencia de clave de acceso) | `l10n_ec_edi` + MCP `send_ride` | Clave de acceso consultable contra SRI | Bajo demanda |
| AUD-08 | **Logs SQL de lentitud** activos (`log_min_duration_statement=250ms`) | `config/postgresql.conf:19` | Log Postgres | Continua |
| AUD-09 | **Logs Odoo** en `ir.logging` (modo `logging_collector=on`) | `config/odoo.conf:2` | Tabla `ir_logging` | Continua |
| AUD-10 | **Logs de contenedor** con rotación (docker `json-file`, 50m, 10 archivos → ~500 MB por servicio) | `docker-compose.yml` secciones `logging` de `odoo-odoo` y `postgres` | `docker inspect` | Trimestral |
| AUD-11 | **Registro de cambios de configuración**: todo cambio en `config/*` y `docker-compose.yml` vía PR con revisor y diff visible | Historial Git | `git log` | Continua |
| AUD-12 | **Revisión trimestral de accesos** (grupos Odoo y SSH) | `l10n_ec_base/security/`, `l10n_ec/security/l10n_ec_security.xml`, clave `authorized_keys` de la EC2 | Acta de revisión | Trimestral |
| AUD-13 | **Retención de evidencias contables/tributarias ≥ 7 años** [VERIFY: Art. 43 Código Tributario — confirmar en sri.gob.ec] | Política de retención (§6) | Inventario de retención | Anual |
| AUD-14 | **Bitácora de auditoría del sistema** (actas de control de cambios, incidentes, CAPA) conservada ≥ 3 años | `docs/ISO/04_CONTROL_DE_CAMBIOS.md` §6; carpeta `docs/` | Bitácora | Continua |

### 3.1 Modelo de amenazas a la trazabilidad (qué se mitiga)

| Amenaza | Control asociado | Nota |
|---|---|---|
| Alteración de XML autorizado post-firma | AUD-06, CHG-11 | Firma RSA sobre XML; clave de acceso independiente en BD |
| Borrado de asientos para ocultar transacciones | AUD-04, AUD-05 | Lock date + revisión mensual |
| Borrado de logs | AUD-09, AUD-10, AUSE-02 | Logs en BD (ir_logging) + Docker, separados del proceso Odoo |
| Uso indebido de superusuario | SEG-12, AUD-12, GOV-05 | SoD entre Admin (operativo) y Auditor (solo lectura) |
| Cambios ocultos de configuración | AUD-11, CHG-04 | `:ro` + render por entrypoint (R-020, pendiente de cerrar) |

## 4. Responsables

| Rol | Responsabilidad | Artefacto |
|---|---|---|
| Administrador Odoo | Ejecuta bloqueos de período, conserva logs, aplica AUD-08..10 | Config capturada |
| Auditor de Transparencia (grupo RO 395-2025) | Revisión independiente de accesos y transacciones (AUD-12) | Acta trimestral |
| Responsable de Calidad | Verifica AUD-13/14 y mantiene el inventario de retención | Inventario |
| Desarrollador | No altera registros fiscalmente relevantes; cambios solo por PR | Git |

## 5. Evidencias y Artefactos

| Artefacto | Ubicación | Retención |
|---|---|---|
| `res.users.log` (logins) | BD Odoo | ≥ 7 años [VERIFY] |
| `mail.tracking.value` (cambios de campos) | BD Odoo | ≥ 7 años [VERIFY] |
| XML firmados + claves de acceso | Filestore + BD | Permanente (documentos tributarios) [VERIFY] |
| Logs SQL/Postgres | Volúmenes Docker | Rotación ~500 MB/servicio |
| `ir_logging` | BD Odoo | Podar > 1 año |
| Bitácora de auditoría (actas, CAPA) | `docs/` en Git | ≥ 3 años |

## 6. Retención

| Categoría | Retención mínima | Fundamento |
|---|---|---|
| Comprobantes electrónicos y registros contables | 7 años (política del proyecto) | [VERIFY: Código Tributario, Art. 43 — verificar en sri.gob.ec] |
| Logs de autenticación y seguridad | 7 años (alineado con lo anterior) | Política interna |
| Logs de aplicación/infraestructura | 1 año (rotación) | AUD-10 |
| Bitácora de auditoría del SGSI | 3 años | AUD-14 |
| Backups (cuando exista filestore) | 90 días | BC-03/BC-04 |

> **Nota de honestidad:** la retención ≥ 7 años solo es operable hoy para datos en BD (los XML
> viven en el filestore, sin respaldo automático, BC-03). Mientras BC-03/BC-04 estén
> *pendientes*, la evidencia tributaria no tiene copia sobreviviente ante pérdida del host.

## 7. Procedimientos de Auditoría (rutinas)

| # | Rutina SQL/consulta | Objetivo | Frecuencia |
|---|---|---|---|
| A-1 | `SELECT * FROM res_users_log ORDER BY id DESC LIMIT 200` | Últimos accesos; detectar accesos fuera de horario | Semanal |
| A-2 | `account_move` con `state='cancel'` sin NC referenciada | Violación de AUD-04 (debe ser 0) | Mensual |
| A-3 | Claves de acceso en BD vs XML en filestore (muestra de 50) | Consistencia AUD-06 | Trimestral |
| A-4 | `mail_tracking_value` sobre campos `amount_total`, `l10n_ec_sri_*` | Cambios materiales tras emisión | Trimestral |
| A-5 | Membresía de grupos Odoo vs matriz `SECURITY_ROLE_MATRIX.md` | Drift de permisos | Trimestral |
| A-6 | Archivos en filestore sin referencia en BD (huerfanos) | Higiene/espacio | Semestral |

Cada rutina deja acta con: fecha, ejecutor, muestra, hallazgos y CAPA asociado (04 §6).

## 8. Calendario de Auditoría

| Mes | Actividad | Control |
|---|---|---|
| Ene | Auditoría anual de accesos (A-5) + inventario de retención | AUD-12/13 |
| Abr, Jul, Oct | Revisión trimestral de accesos (A-5) y bloqueos de período (AUD-05) | AUD-05/12 |
| Mensual | A-1, A-2 | AUD-01/04 |
| Bajo demanda | Auditoría SRI/evidencias (A-3, A-4, A-6, `send_ride`) | AUD-06/07 |

## 9. Seguimiento

| Métrica | Meta | Relación |
|---|---|---|
| Logins sin registro en `res_users_log` | 0 | KPI-17 |
| Asientos cancelados sin NC | 0 | KPI-17 |
| Evidencias de rutinas con acta completa | 100% | KPI-18 |
