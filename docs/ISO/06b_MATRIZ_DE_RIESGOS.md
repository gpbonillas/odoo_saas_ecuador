# ISO-EC-06b — Matriz de Riesgos

**Proyecto:** Odoo 18 Ecuador Localization · **Versión:** 1.0 · **Fecha emisión:** 2026-10-15
**Responsable:** Gerencia de Riesgos / Equipo de Seguridad · **Próxima revisión:** 2027-04-15
**Clasificación:** Uso interno

---

## 1. Propósito y Alcance

Registro de riesgos (amenazas, vulnerabilidades, impacto, controles asociados y tratamiento) para
la plataforma Odoo 18 Ecuador. Cada riesgo se vincula a un control en otro documento de esta serie
por ID (`SEG-*`, `BC-*`, `DR-P*`, `CAP-*`, `CHG-*`, `AUD-*`, `GOV-*`, `KPI-*`).

**Escala de severidad** (Impacto × Probabilidad, 1–5): 1–6 Bajo · 8–12 Medio · 15–20 Alto · 25 Crítico.

## 2. Referencias Normativas

| Referencia | Observación |
|---|---|
| ISO/IEC 27001:2022 A.5.8 (inventario de información), A.5.7 (threat intelligence), A.8.x (controles operativos) | Marco de gestión de riesgos |
| ISO 31000:2018 | Metodología de valoración |

## 3. Metodología de valoración

| Paso | Descripción | Fuente |
|---|---|---|
| 1 | Identificar activos (BD, filestore, `.p12`, config, código) | 01 §4 |
| 2 | Identificar amenazas y vulnerabilidades | Este documento |
| 3 | Calcular Severidad = Impacto × Probabilidad (1–5 cada uno) | §4 |
| 4 | Asignar control existente o registrar brecha | Cruzado con 00–05, 07 |
| 5 | Definir tratamiento (mitigar/evitar/transferir/aceptar) y owner | §4, §6 |
| 6 | Revisar trimestralmente en comité de riesgos | §6 |

**Apetito de riesgo**: la plataforma tolera riesgos de severidad ≤ 12 con plan activo; los de
severidad ≥ 15 requieren tratamiento prioritario y reporte a dirección; los críticos (25) bloquean
despliegues hasta mitigación.

## 4. Matriz de Riesgos

| ID | Riesgo | Amenaza / Vulnerabilidad | Sev. | Impacto | Control | Tratamiento | Owner | Detección | Métrica |
|---|---|---|---|---|---|---|---|---|---|
| R-001 | Cambio regulatorio SRI a mitad de año (resolución nueva, cambio de esquema XML) | Actualización legal fuera de ciclo | 20 (Alto) | Multas/incumplimiento fiscal | CHG §3.2, CM-01, CM-05 | Mitigar: monitoreo de resoluciones SRI, proceso de hotfix | Fiscal | Monitoreo SRI | Tiempo de respuesta a resolución |
| R-002 | **Pérdida del filestore** (documentos XML firmados, RIDE, adjuntos) sin respaldo | `filestore_odoo-ec` no tiene backup automatizado (solo `pg_dump`) | 25 (Crítico) | Pérdida de evidencia tributaria; imposibilidad de reenviar comprobantes | BC-03 (Pendiente) | Mitigar: agregar backup de filestore (objetivo 2026-Q4) | Infra | Fallo de volumen | Existencia de backup de filestore |
| R-003 | Agotamiento de conexiones Postgres | `db_maxconn=64` por defecto × 11 procesos Odoo = 704 > `max_connections=200` | 25 (Crítico) | Caída total del servicio bajo carga | CAP-03 (recomendación `db_maxconn=16`) | Mitigar: aplicar en `postgresql.conf` y/o `odoo.conf` | Infra | `pg_stat_activity` | KPI-08 (<80%) |
| R-004 | Compromiso del certificado digital `.p12` (firma fraudulenta de comprobantes) | Clave exportable en filestore/compartida | 20 (Alto) | Facturación fraudulenta a nombre de la compañía | SEG-05, SEG-13, AUD-12 | Mitigar: custodia del `.p12`, rotación, revocación ante incidente | Fiscal/Seg | Auditoría de accesos | Accesos al archivo `.p12` |
| R-005 | Ataque de ransomware sobre el host | Exposición de puertos Odoo/Postgres (falta de whitelist de seguridad) | 20 (Alto) | Pérdida de datos y disponibilidad | SEG-03, BC-06 (aislamiento), BC-08 (copia inmutable) | Mitigar: copia inmutable + hardening de red | Infra | Escaneo/anomalías | Copias inmutables presentes |
| R-006 | Indisponibilidad del SRI para autorización de comprobantes | Dependencia del servicio externo | 15 (Alto) | Retraso de emisión y cobros | BC-12 (cola de reintentos), KPI-09 | Mitigar: reintento con backoff y monitoreo | Fiscal/Dev | Latencia SRI | KPI-09, KPI-10 |
| R-007 | Cambio regulatorio sin proceso de hotfix (regla 5 días, nuevas resoluciones) | Ausencia de proceso formal de cambios | 15 (Alto) | Incumplimiento | CHG-01..12 | Mitigar: proceso de cambios (04 §3.2) | Dev | Auditoría de cambios | Cambios sin PR = 0 |
| R-008 | Uso indebido de agentes MCP/IA (tools mutating sin aprobación humana) | Exposición de `create_invoice`, `post_invoice`, `record_payment` a agentes | 20 (Alto) | Transacciones no autorizadas, fraude | GOV-09, GOV-10 (07 §5) | Mitigar: aprobación humana previa, permisos read-only por defecto | Seg | Logs de invocación | Tools mutantes aprobadas 100% |
| R-009 | Credenciales por defecto en `.env`/compose | `ADMIN_PASS`, `POSTGRES_PASSWORD`, `DB_PASSWORD` con valores por defecto en el repo | 20 (Alto) | Acceso no autorizado | SEG-06, SEG-14 | Mitigar: rotar credenciales, secretos externos | Infra | Escaneo de repo | Credenciales default = 0 |
| R-010 | Sobreutilización de CPU por workers mal dimensionados | Fórmula `(cores×2)+1` mal aplicada | 12 (Medio) | Latencia, timeouts | CAP-02, CAP-10 | Mitigar: HPA + revisión trimestral | Infra | Uso de CPU | KPI-01 |
| R-011 | Degradación por vacíums/estadísticas obsoletas | `autovacuum` sin tuning | 8 (Medio) | Lentitud de consultas | CAP-07, AUD-08 | Mitigar: monitoreo y ajustes de parámetros | DBA | `pg_stat` | KPI-06, KPI-07 |
| R-012 | Deriva de versionado de módulos (`l10n_ec_ice`, `l10n_ec_rimpe` en `1.0` vs `18.0.1.0.0`) | Falta de convención/validación de manifest | 8 (Medio) | Errores en instalación/upgrade | CHG-06 | Mitigar: normalizar y validar en CI | Dev | CI | Anomalías = 0 |
| R-013 | Datos sensibles sin cifrado en reposo | Postgres/filestore sin cifrado de volumen | 15 (Alto) | Fuga de datos personales/financieros | SEG-15 (Pendiente) | Mitigar: cifrado de volumen (requisito para SaaS) | Infra | Revisión de config | Cifrado activo |
| R-014 | Compose monta `./mcp_server` que no existe en el repo | Directorio ausente; volumen huérfano | 8 (Medio) | Fallo en despliegue, superficie de ataque | GOV-09 | Mitigar: publicar código o ajustar compose | Dev | Fallo de despliegue | Directorio presente |
| R-015 | Incumplimiento de Ley 0/14 (datos personales) | Sin inventario ni política de datos | 15 (Alto) | Sanciones, pérdida de confianza | SEG-19, CM-36/37 | Mitigar: inventario y política de datos personales | Legal | Auditoría | Inventario completo |
| R-016 | Falta de alta disponibilidad (HA) | Despliegue single-host, sin réplicas | 15 (Alto) | Tiempo de inactividad prolongado | CAP-05, BC-05 | Mitigar: réplicas de lectura y DRP (objetivo 2027) | Infra | Disponibilidad | KPI-01 |
| R-017 | Falta de plan de continuidad documentado y probado | Ausencia de DRP formal | 12 (Medio) | Recuperación desordenada ante incidente | BC-01, DR-P1..P5 | Mitigar: documentar y probar DRP | Infra | Revisión documental | Pruebas DRP realizadas |
| R-018 | Sin copia de seguridad fuera del host (single point of failure) | Backups en el mismo host/EC2 | 20 (Alto) | Pérdida total ante robo/fallo del host | BC-04 (Pendiente) | Mitigar: copia a S3 u objeto remoto | Infra | Fallo del host | Copia off-host presente |
| R-019 | Migración corrupta de BD (p. ej., entre versiones Odoo) | Migraciones manuales sin validación | 12 (Medio) | Inconsistencia contable | CHG-07, BC-09 (rollback) | Mitigar: validar antes de migrar | Dev | Validación post-migración | Migraciones validadas 100% |
| R-020 | Divergencia de configuración (workers=4 en `odoo.conf` vs `workers=8` en `entrypoint.sh`/`.env`) | Montaje `:ro` impide editar `odoo.conf` en runtime | 12 (Medio) | Config inesperada, comportamiento distinto por entorno | CHG-04, AUD-11 | Mitigar: fuente única de verdad (entrypoint) y reconciliar valores | Infra | Auditoría de config | Divergencias = 0 |

## 5. Heatmap resumido

| Severidad | Riesgos |
|---|---|
| Crítico (25) | R-002, R-003 |
| Alto (15–20) | R-001, R-004, R-005, R-006, R-007, R-008, R-009, R-013, R-015, R-016, R-018 |
| Medio (8–12) | R-010, R-011, R-012, R-014, R-017, R-019, R-020 |
| Bajo (1–6) | — |

## 6. Plan trimestral (acciones inmediatas)

| Trimestre | Riesgo | Acción | Control |
|---|---|---|---|
| 2026-Q4 | R-002 | Implementar backup de filestore (objetivo RPO ≤ 6 h) | BC-03 |
| 2026-Q4 | R-003 | Aplicar `db_maxconn=16` (o equivalente) y validar con carga | CAP-03 |
| 2026-Q4 | R-020 | Reconciliar workers y cerrar divergencia de configuración | CHG-04 |
| 2026-Q4 | R-012 | Corregir versionado de `l10n_ec_ice` y `l10n_ec_rimpe` | CHG-06 |
| 2027-Q1 | R-018 | Copia off-host (S3) con retención 90 días | BC-04 |
| 2027-Q1 | R-013 | Cifrado en reposo (requisito SaaS) | SEG-15 |
| 2027-Q1 | R-008 | Aprobación humana en tools mutating MCP + rate limit | GOV-09/10 |
| 2027-Q2 | R-016 | Réplicas de lectura y pruebas de failover | CAP-05, BC-05 |

## 7. Fichas de riesgos críticos

### R-002 — Pérdida del filestore

| Campo | Valor |
|---|---|
| Descripción | El volumen `filestore_odoo-ec` (XMLs firmados, RIDE, adjuntos) no tiene backup automatizado; solo se respalda la BD vía `pg_dump` (`docker-compose.yml`, servicio `backup`, `sleep 21600`) |
| Escenario | Fallo del disco/instancia EC2, borrado accidental, ransomware |
| Consecuencia | Incumplimiento de retención de evidencia tributaria ≥ 7 años (05 §6); imposibilidad de regenerar comprobantes |
| Control objetivo | BC-03: backup del filestore con la misma cadencia (6 h) y retención (14 días) que `pg_dump` |
| Acción inmediata | Script de `tar`/`rsync` del filestore al volumen de backups + plan de copia off-host (BC-04) |
| Métrica de cierre | KPI-12 (backups OK) extendido a filestore |

### R-003 — Agotamiento de conexiones Postgres

| Campo | Valor |
|---|---|
| Descripción | Odoo crea 11 procesos (1 main + 8 workers + 2 cron); con `db_maxconn=64` (default) exigirían 704 conexiones contra `max_connections=200` → errores de conexión bajo carga |
| Escenario | Pico de usuarios o jobs simultáneos |
| Consecuencia | Caída total del servicio ("too many connections") |
| Control objetivo | CAP-03: `db_maxconn=16` → 11×16 = 176 + margen ≤ 197 (reservando `superuser_reserved_connections`) |
| Acción inmediata | Aplicar `db_maxconn=16` y validar con prueba de carga (03 §5) |
| Métrica de cierre | KPI-08 < 80% de uso sostenido |

## 8. Registro de transferencia / aceptación

| Riesgo | Decisión | Justificación | Revisión |
|---|---|---|---|
| R-006 (SRI externo) | Transferir parcialmente | Dependencia de servicio gubernamental fuera de control; se mitiga con cola de reintentos | Trimestral |
| R-001 (cambios regulatorios) | Aceptar con mitigación parcial | Imposible eliminar; se absorbe vía proceso de hotfix (04 §3.2) | Trimestral |

## 9. Seguimiento

| Métrica | Meta | Relación |
|---|---|---|
| Riesgos críticos con plan de tratamiento activo | 100% | KPI-14 |
| Riesgos con dueño asignado | 100% | KPI-14 |
| Riesgos con severidad residual aceptable (cerrados o mitigados) | ≥ 2 por trimestre | KPI-15 |
