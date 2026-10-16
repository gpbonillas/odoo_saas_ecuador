# 02 — CONTINUIDAD DE NEGOCIO Y RECUPERACIÓN ANTE DESASTRES (ISO 22301)

**BCP/DR — Clúster Docker `odoo-ec` (Postgres 16 + Odoo 18 + MCP + backup)**

| Campo | Valor |
|---|---|
| Código documento | ISO-EC-BCP-02 |
| Versión | 1.0 |
| Fecha de emisión | 2026-10-15 |
| Propietario | Responsable de Operaciones (Ops) / DBA |
| Aprobador | CIO |
| Próxima revisión | 2027-04-15 (anual) y tras **cualquier** restauración real o incidente ≥S2 |
| Estado | Aprobado con brechas declaradas (§5.2, BC-03/BC-04) |

---

## 1. Objeto y alcance (Purpose & Scope)

Definir los objetivos de recuperación y los procedimientos para restaurar la plataforma tras la pérdida de datos o de infraestructura, considerando que la plataforma emite **comprobantes electrónicos con validez legal** (SRI) y procesa planillas (IESS): la pérdida de datos no es solo indisponibilidad, es **pérdida de evidencia fiscal**.

**Alcance:** servicios `db`, `odoo`, `mcp`, `backup`; volúmenes `dbdata`, `dblogs`, `dbbackups`, `odoo-filestore`, `odoo-sessions`, `odoo-logs`; configuración `docker-compose.yml`, `config/*`, `.env`; código del repositorio.

## 2. Referencias normativas (Normative references)

| Ref. | Documento |
|---|---|
| [1] | ISO 22301:2019 — Continuidad de negocio; ISO 22316 — Principios y conceptos |
| [2] | ISO/IEC 27031 — Preparación para la continuidad de TI |
| [3] | `docs/ISO/01_POLITICA_DE_SEGURIDAD.md` (SEG-14 respaldos, clasificación de incidentes §6) |
| [4] | `docs/ISO/03_GESTION_DE_CAPACIDAD.md` (escalado, caídas por recursos) |
| [5] | `docs/ISO/04_CONTROL_DE_CAMBIOS.md` §6 (rollback de cambios/migraciones) |
| [6] | `docs/ISO/05_TRAZABILIDAD_Y_AUDITORIA.md` §8 (retención legal de evidencia ≥7 años) |

## 3. Actividad crítica y dependencias

| ID | Proceso de negocio crítico | Servicio TI | Dependencia externa | Pérdida máxima tolerable (MTDL) |
|---|---|---|---|---|
| BP-1 | Emisión y autorización de facturas/NC/retenciones (SRI) | `odoo` + `db` + certificado `.p12` | `cel.sri.gob.ec` / `celcer.sri.gob.ec` | 4 horas (sanciones y ruptura de cadena de valor) |
| BP-2 | Cálculo y pago de nómina y planillas IESS | `odoo` + `db` | Portal IESS | 24 horas (plazos legales) |
| BP-3 | Cierre contable y formularios (ATS, 104, 101…) | `odoo` + `db` | Portal SRI | Según calendario tributario (`l10n_ec_base/models/tax_calendar.py`) |
| BP-4 | Consulta/operación por agente IA | `mcp` → `odoo` | — | 24 horas (degradación aceptable) |

## 4. Objetivos de recuperación (RPO/RTO) — control **BC-06**

| Servicio / activo | RPO (pérdida máxima de datos) | RTO (tiempo de restitución) | Base del cálculo | Estado |
|---|---|---|---|---|
| **`db` — base transaccional (`dbdata`)** | **≤ 6 horas** | ≤ 60 min | `pg_dump -Fc` automático cada **21600 s = 6 h** (servicio `backup`, `sleep 21600` en `docker-compose.yml`), retención `KEEP_DAYS=14` | **Implementado** |
| **`odoo-filestore`** (XML firmados, RIDE, `.p12`, adjuntos) | **Sin respaldo automatizado → RPO indefinido** (objetivo: ≤6 h) | ≤ 120 min | El servicio `backup` **solo ejecuta `pg_dump`**; no hay copia del filestore | **Pendiente — BC-03 (R-002)** |
| Servicio `odoo` (aplicación) | 0 (código en git, montajes directos de `./l10n_ec*`) | ≤ 30 min | `docker compose up -d odoo` + healthcheck (`start_period 240s`) | Implementado |
| Servicio `mcp` (agente IA) | 0 (código en git) | ≤ 15 min | `docker compose up -d mcp` | Implementado |
| Configuración (`config/*`, `.env`) | 0 (versionado en git; `odoo.conf` se re-renderiza en arranque con `config/entrypoint.sh`) | ≤ 15 min | `git pull` + `docker compose up -d` | Implementado |
| Volúmen `dbbackups` (los propios respaldos) | Retención 14 días / 56 dumps | ≤ 30 min | `find /backups -name '*.dump' -mtime +14 -delete` | Implementado |
| **Copia fuera del host (off-host)** | No existe | — | Respaldos viven en el mismo host que la BD | **Pendiente — BC-04 (R-018)** |
| **Clúster completo** | ≤ 6 h (BD) + filestore indefinido | ≤ 4 h (objetivo) | Restauración desde `git` + `dbbackups` (§6) | **Parcial** |

**Aceptación del RPO de BD ≤6 h:** aprobada por CIO el 2026-10-15; implica que en el peor caso se pierden hasta 6 horas de comprobantes **no** transmitidos — si se transmitieron al SRI, la evidencia existe en el SRI, pero la secuencia interna puede tener huecos → ver control de secuencias en `05` §4.

## 5. Continuidad: preparación — controles BC-*

| ID | Control | Descripción | Estado |
|---|---|---|---|
| BC-01 | Respaldo automático de BD cada 6 h | Servicio `backup`: `pg_dump -Fc -d $ODOO_DB -f /backups/$ODOO_DB-$TS.dump` con `PGHOST=db` | Implementado |
| BC-02 | Verificación semanal de integridad de dumps | `pg_restore --list` sobre el dump más reciente + prueba de restauración en BD temporal `odooec_restore_test` | **Pd** (ver §7 T2, debe rutinarse) |
| BC-03 | Respaldo del filestore (`odoo-filestore`) | Requerido: volcado periódico del volumen (ej. `tar`/`rsync` a `dbbackups` o bucket) con misma ventana de 6 h | **Pendiente (R-002)** |
| BC-04 | Copia off-host de `dbbackups` | Réplica cifrada a segunda zona/almacenamiento; sine qua non para ransomware (§6 DR-P4) | **Pendiente (R-018)** |
| BC-05 | Procedimientos de recuperación probados | §6 de este documento | Implementado (documentado), ensayo pendiente |
| BC-07 | Simulacro anual de DR completo | §7 | Programado |
| BC-08 | Restauración parcial trimestral | §7 T1/T2 | Programado |
| BC-09 | Inventario de dependencias | §3 | Implementado |
| BC-10 | Interruptor de emisión (kill switch) | Congelar emisión SRI ante incidente sin cortar contabilidad: sacar secuencias a emisión, suspender cron de envío, mantener Odoo en solo-lectura de cierre | **Pd** — sin procedimiento automatizado |
| BC-11 | Comunicación de continuidad | Plantilla de aviso a inquilinos (qué, cuándo, impacto fiscal, plazos) | **Pd** |
| BC-12 | Lecciones aprendidas | Toda restauración real → registro en `06b` + CAPA (`00` §10) en ≤10 días | Implementado (proceso) |

### 5.1 Condiciones previas (antes de un incidente)

1. `dbbackups` con ≥7 dumps diarios disponibles (`ls /backups`); alerta si falta alguno.
2. `.env` y `config/*` respaldados en git (privado) — con acceso de emergencia documentado (§8).
3. Lista de secuencias SRI por emisor (establecimiento-punto-emisión) exportada mensualmente desde `l10n_ec_sri/data/ir_sequence_data.xml` + BD → evita reutilización de claves tras restauración antigua (`05` §4).
4. Runbook de contactos (§8) actualizado `[VERIFY: nombres y teléfonos — no incluidos por ser información personal no verificable]`.

### 5.2 Brechas conocidas (honestidad de estado)

| Brecha | Efecto | Mitigación temporal | Plan |
|---|---|---|---|
| Filestore sin respaldo (BC-03) | Pérdida de XML firmados/RIDE en desastre → imposibilidad de demostrar comprobantes ante SRI/auditor | Filestore = volumen Docker con retención del proveedor; RIDE reemitible desde SRI si la factura está autorizada | Implementar BC-03 antes de 2026-11-30 (R-002) |
| Sin copia off-host (BC-04) | Un ransomware que cifre el host deja BD+respaldos inútiles | Réplica manual semanal a segundo host como medida transitoria | Automatizar antes de 2026-12-15 (R-018) |
| Respaldo solo de `ODOO_DB` | Otros inquilinos (multi-tenant) no respaldados | Limitar inquilinos o parametrizar el `pg_dump` por BD | Ampliar el servicio `backup` a todas las BD `odooec*` |
| `odoo.log` sin rotación propia | Pérdida de evidencia operativa por crecimiento | Retención limitada por volumen `odoo-logs` | Ver `05` §5 |

## 6. Procedimientos de recuperación (procedures) — paso a paso

*Precondición general de todos los procedimientos: identificar ventana, detener emisión (BC-10), registrar inicio en el registro de incidentes (`01` §6), y ejecutar con dos personas (Ops + DBA). Comandos ejecutables desde la raíz del repositorio.*

### DR-P1 — Pérdida/corrupción del volumen `dbdata` (Postgres)

| Paso | Acción | Comando / artefacto | Responsable |
|---|---|---|---|
| 1 | Detener escrituras | `docker compose stop odoo mcp` | Ops |
| 2 | Verificar servicio DB y volúmen | `docker compose ps db`; `docker volume inspect odoo-ec_dbdata` | DBA |
| 3 | Identificar el dump válido más reciente (≤6 h) | `docker compose run --rm --entrypoint sh backup -c 'ls -la /backups'` | DBA |
| 4 | Verificar integridad del dump | `pg_restore --list /backups/<archivo>.dump \| head` | DBA |
| 5 | Crear BD de validación y restaurar | `docker compose run --rm backup sh -c 'createdb odooec_restore_test && pg_restore -d odooec_restore_test /backups/<archivo>.dump'` | DBA |
| 6 | Validar conteo crítico | SQL: `account_move` (estado `posted`), `account_retention`, secuencias SRI vs valores esperados | Oficial Cumpl. |
| 7 | Restaurar en producción (ventana) | `docker compose run --rm backup sh -c 'dropdb odooec && createdb odooec && pg_restore -d odooec /backups/<archivo>.dump'` | DBA |
| 8 | Reiniciar y verificar health | `docker compose up -d odoo mcp` → esperar `/web/health` OK | Ops |
| 9 | Reconciliar secuencias y claves de acceso emitidas tras el punto de corte | Exportar comprobantes emitidos por SRI del período y comparar (`l10n_ec_edi/models/access_key.py`) | Oficial Cumpl. |
| 10 | Cerrar: registro, CAPA, actualizar `06b` si corresponde | `00` §10 | Oficial Cumpl. |

**Riesgo residual:** pérdida de hasta 6 h de comprobantes no transmitidos (RPO). **Tiempo objetivo:** ≤60 min RTO.

### DR-P2 — Pérdida del volumen `odoo-filestore`

| Paso | Acción | Nota |
|---|---|---|
| 1 | Detener `odoo` | `docker compose stop odoo` |
| 2 | Evaluar daño: ¿el volumen existe pero está corrupto, o fue eliminado? | `docker volume inspect odoo-ec_odoo-filestore` |
| 3a | **Corrupción parcial:** restaurar desde copia de filestore (BC-03) | `[VERIFY: BC-03 aún no implementado — hasta entonces, restaurar filestore desde snapshot del volumen del proveedor]` |
| 3b | **Sin ninguna copia:** reconstruir lo recuperable | Los XML autorizados se re-descargan del SRI por clave de acceso; los RIDE se regeneran desde Odoo si la factura sigue `posted`; los `.p12` se re-suben por los clientes (`l10n_ec.certificate`) |
| 4 | Verificar adjuntos críticos | Muestra: 20 facturas `posted` con XML + RIDE disponibles; certificados `.p12` en estado `active` |
| 5 | Registrar pérdida de evidencia como no conformidad | CAPA + riesgo R-002 residual |

**Impacto fiscal:** sin XML firmado local, la evidencia ante SRI depende de la re-descarga del servicio de autorización (`check_authorization` en `l10n_ec_edi/models/sri_service.py`) — verificar antes de declarar pérdida total.

### DR-P3 — Pérdida total del clúster (host inutilizable)

| Paso | Acción | Artefacto/fuente | Objetivo |
|---|---|---|---|
| 1 | Provisionar host nuevo con Docker + Compose | Lista de requisitos `[VERIFY: versión mínima de Docker/Compose aceptada]` | ≤30 min |
| 2 | Clonar repositorio en `main` y restaurar `.env`/`config/*` desde git | `git clone … && git checkout <tag-release>` | ≤15 min |
| 3 | Copiar `dbbackups` desde la copia off-host (BC-04) o desde el medio remanente | transferencia cifrada | ≤30 min |
| 4 | Levantar solo `db` y restaurar BD (pasos 5–7 de DR-P1) | `docker compose up -d db` → `pg_restore` | ≤60 min |
| 5 | Restaurar filestore (BC-03) o ejecutar DR-P2 3b | — | ≤120 min |
| 6 | Levantar `odoo` + `mcp`; verificar health y módulos | `docker compose up -d` → `/web/health`; login y emisión de prueba en ambiente de pruebas SRI | ≤30 min |
| 7 | Validar secuencias SRI e imprimir comprobante de prueba antes de reanudar | Checklist DR-P1 paso 9 | Reanudar emisión solo tras validación |
| 8 | Notificar a inquilinos (BC-11) y abrir CAPA | Plantilla de comunicación | ≤2 h del cierre |

### DR-P4 — Ransomware / cifrado malicioso

| Paso | Acción | Razón |
|---|---|---|
| 1 | **Aislar, no apagar:** desconectar el host de la red (cortar `backend` y puertos 8069/8072) | Preservar evidencia forense de `odoo-logs`, `dblogs`, `json-file` |
| 2 | Escalar S1 (01 §6): CIO + Oficial Cumpl. + aviso a clientes afectados ≤2 h | Evidencia fiscal comprometida |
| 3 | No intentar descifrar ni pagar; declarar compromiso de `.p12` si el host estaba comprometido | Rotar/revoke certificados (`action_check_expiry`/emisor) — R-004 |
| 4 | Reconstruir en host **limpio** nuevo (nunca reusar el host comprometido) vía DR-P3 | Elimina persistencia |
| 5 | Restaurar BD **solo** desde copia off-host verificable (BC-04) | Los respaldos locales pueden estar cifrados/destruidos |
| 6 | Verificar integridad: firmas de los XML del filestore (hash XAdES), checksums de `dbbackups` | `sha256` registrado en el manifiesto de respaldo |
| 7 | Auditoría forense + notificación según obligaciones `[VERIFY: obligaciones de notificación de la Ley 0/14 y del regulador sectorial]` | — |

### DR-P5 — Migración de módulo corrupta (upgrade fallido)

| Paso | Acción | Relación con `04_CONTROL_DE_CAMBIOS.md` |
|---|---|---|
| 1 | Detener actividad y no forzar reintentos | — |
| 2 | Determinar alcance: ¿solo metadata XML-ID o datos? (`-u <modulo>` abortado) | CHG-05 (nunca editar XML-ID ya publicado) |
| 3 | Restaurar dump pre-upgrade (obligatorio: **todo upgrade se precede de `pg_dump` manual** — control CHG-08) | `04` §5 |
| 4 | `git revert <commit>` del cambio problemático y reconstruir imagen | `04` §6 |
| 5 | Reintentar upgrade en BD de prueba primero (`odooec_restore_test`) con `--test-enable` | CHG-07 |
| 6 | Restaurar producción y aplicar fix con nueva versión `18.0.x.y.z` | CHG-06 |
| 7 | CAPA: ¿faltó prueba de migración? → actualizar `tests/` | `00` §10 |

## 7. Plan de pruebas de recuperación (annual test plan) — **BC-07/BC-08**

| ID | Prueba | Alcance | Frecuencia | Responsable | Criterio de éxito | Registro |
|---|---|---|---|---|---|---|
| T1 | Restauración de BD desde el dump más reciente en BD temporal | DR-P1 pasos 3–6 | **Trimestral** (ene/abr/jul/oct) | DBA | Restaura sin error; conteos `account_move posted` coherentes | Acta T1 + log `pg_restore` |
| T2 | Verificación de integridad de dumps (`pg_restore --list`) + antigüedad máxima | Muestreo 7 dumps | **Mensual** | DBA | 100% legibles; antigüedad ≤6 h en el más reciente | Checklist T2 |
| T3 | Restauración de filestore desde copia | DR-P2 | Trimestral (desde BC-03) | Ops | Muestra de 20 XML/RIDE recuperables | Acta T3 |
| T4 | Reconstrucción completa de clúster en host aislado | DR-P3 completo | **Anual** (próximo: 2027-03-15, con ensayo previo 2026-12-15) | Ops + DBA | RTO ≤4 h demostrado; emisión de prueba SRI (ambiente pruebas `celcer`) OK | Informe DR con métricas |
| T5 | Simulacro de ransomware (aislamiento + reconstrucción en sandbox) | DR-P4 pasos 1–6 | Anual | CIO + Ops | Evidencia forense preservada; RTO ≤4 h; firmas XML verificadas | Informe + CAPA |
| T6 | Rollback de migración | DR-P5 completo con drop de un módulo `l10n_ec_*` en BD de prueba | Anual (previo a cada release mayor) | Líder Dev | BD restaurada; upgrade exitoso tras fix | Reporte de prueba |

**Post-ensayo:** desviaciones → CAPA (`00` §10) y actualización de este documento en ≤30 días. **Ninguna prueba se declara exitosa sin evidencia registrada** (control Q-03).

## 8. Escalación (escalation)

| Nivel | Rol | Disparador | Tiempo de contacto | Acciones |
|---|---|---|---|---|
| L1 | Ops (guardia) | Healthcheck `odoo`/`db` falla 3 ciclos; dump diario ausente | Inmediato | Reinicio acotado (≤2 intentos), clasificar S3, abrir ticket |
| L2 | DBA + Líder Dev | Falla de restauración; corrupción; RDOW/degradación sostenida | ≤30 min | Activar DR-P1/P5; decidir ventana |
| L3 | CIO + Arquitecto | RTO >2 h; caída de clúster; pérdida de filestore | ≤1 h | Activar DR-P2/P3; declarar S1/S2 |
| L4 | CIO + Oficial de Cumplimiento + Gerencia | Ransomware; fuga; impacto a clientes con obligaciones fiscales en curso | ≤2 h | DR-P4, comunicación BC-11, notificaciones `[VERIFY: canales y obligaciones legales]` |
| L5 | Externo | SRI/IESS inaccesible; emisor de certificados comprometido | Según caso | Avisar a proveedor; suspender emisión (BC-10) |

**Contactos:** ver runbook de guardias `[VERIFY: nombres, teléfonos y correos de guardia — datos personales no incluidos en este documento]`.

## 9. Evidencias, responsabilidades y cadencia

| Evidencia / artefacto | Ubicación | Conservación |
|---|---|---|
| Dumps de BD (`odooec-YYYYmmdd-HHMMSS.dump`) | volumen `odoo-ec_dbbackups` | 14 días (local) + off-host (BC-04) |
| Manifiesto de respaldo con checksums | `dbbackups/manifiesto.sha256` `[VERIFY: implementación]` | ≥7 años si contiene evidencia fiscal |
| Actas T1–T6 | `docs/ISO/registros/BCP/` `[VERIFY: creación del directorio de registros]` | ≥7 años (05 §8) |
| Registro de incidentes y post-mortems | `docs/ISO/registros/INC/` | ≥7 años |
| Actas de revisión de este documento | carpeta de actas | Vigencia del ciclo |

**Responsables:** RACI en `00` §5.2 — ejecución: Ops/DBA (R); aprobación de RPO/RTO: CIO (A); verificación de evidencia fiscal: Oficial Cumplimiento (C).

**Cadencia de revisión:** anual (2027-04-15); tras toda restauración real; ante cambio de arquitectura, nuevo servicio en `docker-compose.yml`, o variación del RPO real (detección de dump faltante).

---

*Riesgos asociados: R-002 (filestore sin respaldo), R-005 (ransomware), R-018 (sin copia off-host), R-019 (pérdida de `dbdata`) en `06b_MATRIZ_DE_RIESGOS.md`. Indicadores: KPI-08…KPI-12 en `08_INDICADORES_Y_METAS.md`.*
