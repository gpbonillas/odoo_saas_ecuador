# 03 — GESTIÓN DE CAPACIDAD Y RENDIMIENTO (ISO/IEC 20000-1 · ISO/IEC 25010)

**Dimensionamiento del clúster `odoo-ec` para volúmenes de millones de transacciones**

| Campo | Valor |
|---|---|
| Código documento | ISO-EC-CAP-03 |
| Versión | 1.0 |
| Fecha de emisión | 2026-10-15 |
| Propietario | DBA (ejecución) / Arquitecto (decisiones) |
| Aprobador | CIO |
| Próxima revisión | 2027-01-15 (trimestral) o bajo detonante (§6) |
| Subsistema de calidad (25010) | Rendimiento-eficiencia (uso de recursos bajo condiciones de uso) |

---

## 1. Objeto y alcance (Purpose & Scope)

Definir la fórmula de dimensionamiento, los límites de conexiones, las metas de rendimiento, las métricas a recolectar, los disparadores de revisión y el runbook de escalado de la plataforma, de modo que soporte **millones de transacciones/año** sin degradación ni agotamiento de recursos.

**Alcance:** servicio `odoo` (workers/cron), servicio `db` (`config/postgresql.conf`), servicio `backup`, servicio `mcp`, volúmenes, red `backend`. Fuera de alcance: cliente SRI/IESS (rendimiento externo, tratado como dependencia R-006).

## 2. Referencias normativas (Normative references)

| Ref. | Documento |
|---|---|
| [1] | ISO/IEC 20000-1:2018 cl. 8 — Capacidades y capacidad |
| [2] | ISO/IEC 25010:2011 — Subsistema Rendimiento-Eficiencia |
| [3] | PostgreSQL 16 — PostgreSQL: High Availability, Replication & Clustering (tuning) |
| [4] | Odoo 18 — Deployment/Performance docs (fórmula de workers, pool de conexiones) |
| [5] | Valores verificados: `docker-compose.yml`, `.env`, `config/postgresql.conf`, `config/odoo.conf`, `config/entrypoint.sh` |
| [6] | `docs/ISO/02_CONTINUIDAD_Y_RECUPERACION.md` (RPO/RTO), `06b_MATRIZ_DE_RIESGOS.md` (R-003, R-010, R-011, R-016, R-020) |

## 3. Dimensionamiento (Sizing) — control **CAP-01** (fórmula de workers) y **CAP-02** (conexiones)

### 3.1 Fórmula de workers de Odoo

```
workers ≈ (núcleos de CPU × 2) + 1
```

| Parámetro | Valor verificado | Fuente |
|---|---|---|
| Núcleos del host | 16 | `sysctl -n hw.ncpu` (host del clúster) |
| RAM del host | 64 GiB | `sysctl -n hw.memsize` = 68719476736 |
| Workers según fórmula (host) | (16 × 2) + 1 = **33** | cálculo |
| **Workers configurados** | **8** | `.env` `ODOO_WORKERS=8`; default en `docker-compose.yml` (`ODOO_WORKERS:-8`, línea 79) y en `config/entrypoint.sh` (línea 10) |
| Límite de memoria del contenedor `odoo` | 10 GB | `docker-compose.yml` `deploy.resources.limits.memory: 10G` (línea ~125) |
| `limit_memory_hard` por worker | 4 GiB (4294967296) | `.env` / `entrypoint.sh` |
| `limit_memory_soft` por worker | 3 GiB (3221225472) | `.env` / `entrypoint.sh` |

**Por qué 8 y no 33 (decisión documentada):** 33 workers × `limit_memory_hard` 4 GiB = 132 GiB teóricos ≫ 10 GB de contenedor ⇒ OOM-kill por Docker (OOM antes de que Odoo aplique sus propios límites). Con workers=8 el presupuesto por proceso es `10 GB / 8 ≈ 1.25 GB` (incluyendo proceso principal), consistente con `limit_memory_soft` efectivo de ≤1 GB/worker.
**Regla de gobierno (CAP-01):** `workers ≤ (memoria_contenedor × 0.75) / memoria_por_worker_objetivo` y `workers ≤ (núcleos × 2) + 1`. Si se sube el límite del contenedor, recalcular y actualizar `.env` vía CHG (`04`).

**Advertencia de configuración dual [VERIFY]:** `config/odoo.conf` (línea 11) declara `workers = 4`, pero `config/entrypoint.sh` **re-renderiza** `/etc/odoo/odoo.conf` en cada arranque desde `.env` (`workers = ${ODOO_WORKERS}` = 8), y `docker-compose.yml` monta `./config/odoo.conf` en modo `:ro` sobre la misma ruta — el render fallaría con *Read-only file system* (probado en este entorno) o el archivo estático quedaría obsoleto. **Verificar en arranque real cuál valor aplica:** `docker compose exec odoo grep '^workers' /etc/odoo/odoo.conf`. Mientras se verifica, el valor operativo de referencia es **8** (`.env`). → R-020.

### 3.2 Conexiones a PostgreSQL — el clásico atasco `workers × dbconnections < max_connections`

**Valores exactos de este despliegue:**

| Parámetro | Valor | Fuente |
|---|---|---|
| `max_connections` (PostgreSQL) | **200** | `config/postgresql.conf` línea 5 (`max_connections = 200`); también `.env` `PG_MAX_CONNECTIONS=200` |
| `superuser_reserved_connections` | 3 | `config/postgresql.conf` línea 6 ⇒ **197 conexiones usables** |
| `workers` (Odoo) | 8 | `.env` `ODOO_WORKERS=8` |
| `max_cron_threads` | 2 | `.env` / `entrypoint.sh` ⇒ 2 procesos `WorkerCron` (verificado en Odoo: `server.py` `worker_spawn(WorkerCron)` por cada `max_cron_threads`) |
| Proceso principal Odoo | 1 | prefork (`main` no atiende HTTP pero mantiene pool) |
| **Procesos Odoo con pool propio** | **1 + 8 + 2 = 11** | cálculo |
| `db_maxconn` (pool por proceso, por defecto) | **64** | Odoo 18 `tools/config.py`: `--db_maxconn … my_default=64`; **no está definido** en `config/odoo.conf` ni en `entrypoint.sh` ⇒ aplica 64 |

**Matemática exacta:**

```
Peor caso teórico = procesos × db_maxconn = 11 × 64 = 704 conexiones
704 ≫ max_connections (200)  ⇒  FATAL: sorry, too many clients already
                             o PoolError "The Connection Pool Is Full" (sql_db.ConnectionPool)
```

**Condición obligatoria (CAP-02):**

```
(workers + max_cron_threads + 1) × db_maxconn + margen ≤ max_connections − superuser_reserved
```

Con los valores actuales:

```
11 × db_maxconn + 2 (backup psql + admin) ≤ 197
db_maxconn ≤ (197 − 2) / 11 = 17.7  ⇒  db_maxconn = 16
Verificación: 11 × 16 = 176; 176 + 2 = 178 ≤ 197 ✓ (holgura 19)
Regla clásica simplificada: workers × dbconnections = 8 × 16 = 128 < 200 ✓
```

**Acción pendiente:** declarar `db_maxconn = 16` (o `db_maxconn_gevent` si se usa modo evented) en `config/entrypoint.sh`/`odoo.conf` vía CHG. **Hasta entonces el valor por defecto 64 deja una ventana de agotamiento de conexiones** → riesgo **R-003** (P=3, I=4, P×I=12).

**Notas multi-tenant:** cada proceso comparte un único pool para todas las BD que toca; el límite global por proceso no crece con el número de inquilinos, pero sí el uso concurrente agregado. Con N inquilinos activos simultáneos el consumo real por proceso sube hacia `db_maxconn` ⇒ recalcular con `N` pico. Réplicas de lectura: si se habilita `db_replica_host`, el pool de solo-lectura es **adicional** (`sql_db._Pool_readonly`) ⇒ dividir `db_maxconn` a la mitad (8) o duplicar `max_connections`.

### 3.3 Memoria de la base (`config/postgresql.conf`)

| Parámetro | Valor | Regla / riesgo |
|---|---|---|
| `shared_buffers` | 4 GB (≈25% de la RAM de la capa de datos, límite contenedor 12 GB) | Al subir RAM del contenedor: ≤25% |
| `effective_cache_size` | 12 GB | Igual al límite de contenedor (asume todo el SO en caché) |
| `work_mem` | 64 MB | Peor caso: 64 MB × 178 sesiones ≈ 11 GB teóricos — **solo si todas hacen sort/hash simultáneo**; vigilar con `log_temp_files=0` |
| `maintenance_work_mem` | 1 GB | Favorece autovacuum/índices |
| `synchronous_commit` / `fsync` / `full_page_writes` | `on` (líneas 21–23: *"NEVER off: SRI/e-invoice auditability"*) | **Prohibido desactivar** — comprometería la no repudio/auditoría (`05` §3) |

## 4. Metas de rendimiento y capacidad (throughput targets) — **CAP-03**

*Metas (objetivos de servicio), no mediciones históricas. Medición: §5; KPI: `08` KPI-03…KPI-07.*

| ID | Métrica de servicio | Meta | Condiciones |
|---|---|---|---|
| TP-1 | Emisión completa (guardar + firmar XAdES + recibir en SRI) — p95 local | ≤ 3 s (excluye red SRI) | 8 workers, `db_maxconn=16` |
| TP-2 | Latencia de autorización SRI (recepción + autorización externa) — p95 | ≤ 5 s | Dependencia externa R-006 |
| TP-3 | Throughput sostenido de comprobantes firmados | ≥ 2 facturas/s (≈ 60.000/h) | Ocupación de 8 workers a ~1.5 s/factura de CPU interna |
| TP-4 | Pico soportado (cierre mensual, planillas, ATS) | ≥ 5 min sostenido al 100% de workers sin error 503 | Cola en `bus`/reintentos |
| TP-5 | Volumen de diseño | ≥ 2.000.000 de `account_move` `posted` por año por instancia (≈ 167.000/mes) | Crecimiento monitoreado (§5 M-4) |
| TP-6 | Consultas lentas (≥250 ms) | ≤ 20/hora en régimen; 0 sostenidas >5 s | `log_min_duration_statement = 250ms` |
| TP-7 | Disponibilidad de la aplicación (healthcheck `/web/health`) | ≥ 99.5% mensual | Fuera de mantenimiento planificado |
| TP-8 | Generación de planilla IESS/ATS de un período | ≤ 10 min para 1.000 empleados / 50.000 líneas | Ventana nocturna |

## 5. Monitoreo: métricas exactas a recolectar — **CAP-04** (A.8.6/A.8.16)

| # | Métrica | Fuente exacta (configuración real) | Fórmula/consulta | Umbral de alerta | Frec. | Responsable |
|---|---|---|---|---|---|---|
| M-1 | **Lag de trabajos en cola / cron** | Odoo **no tiene `queue_job` instalado** (0 coincidencias en el repo; módulo OCA) ni `ir.cron` declarados aún ⇒ métrica habilitable: `SELECT count(*), max(now() - nextcall) FROM ir_cron WHERE active;` | `edad_máxima(nextcall)` | > 15 min | 5 min | Ops |
| M-2 | **Consultas lentas** | `config/postgresql.conf` línea 47: `log_min_duration_statement = 250ms` → logs en `log_directory=/var/log/postgresql` (volumen `dblogs`), `postgresql-YYYY-MM-DD.log` | conteo/día + top 10 por duración | > 20/hora | 1 h | DBA |
| M-3 | **Actividad de autovacuum** | `log_autovacuum_min_duration = 0` (línea 53: se loguea **toda** ejecución); ajustes `autovacuum_max_workers=6`, `scale_factor=0.01` (tablas) / `0.005` (analyze) | `pg_stat_user_tables`: `n_dead_tup`, `last_autovacuum`, ratio `n_dead_tup / (n_live_tup+1)` | `n_dead_tup > 20%` de `n_live_tup` por >30 min; worker count saturado (6) | 15 min | DBA |
| M-4 | **Crecimiento del filestore** | volumen `odoo-filestore` (`du -sb /var/lib/odoo/filestore` dentro de `odoo`) | GB/mes, MB por comprobante = filestore/`account_move posted` | > 1.5× crecimiento lineal proyectado; disco contenedor >75% | Diaria | Ops |
| M-5 | **Latencia de autorización SRI** | `l10n_ec_edi/models/sri_service.py`: `send_document()` (recepción) y `check_authorization()` (autorización) — marcar `t0/t1` | p50/p95 de `t1−t0` por ambiente (`celcer`/`cel`) | p95 > 5 s o tasa de intentos fallidos > 5% | 1 h | Ops + Oficial Cumpl. |
| M-6 | **Uso de conexiones vs 200** | `pg_stat_activity` | `count(*) / 200` | ≥ 70% (140) ⇒ investigar; ≥ 85% ⇒ escalar `db_maxconn`/`max_connections` | 5 min | DBA |
| M-7 | **Pool de Odoo y respawns de workers** | logs `odoo-logs/odoo.log`: mensajes de pool lleno, `Worker` respawns por `limit_memory_*`, `limit_time_*` | respawns/hora | > 2/hora | 1 h | Ops |
| M-8 | **Wait events / bloqueos** | `log_lock_waits=on` (línea 51); `pg_stat_activity.wait_event` | tiempo en `Lock`/`IO` | Lock esperado > 5 s | 5 min | DBA |
| M-9 | **Hit ratio de caché y checkpoints** | `log_checkpoints=on` (línea 48); `pg_stat_database` | `blks_hit/(blks_hit+blks_read)` | < 95% | 1 h | DBA |
| M-10 | **Disco y WAL** | `max_wal_size=4GB`, `min_wal_size=1GB`; `df` de `dbdata`, `dbbackups`, `odoo-filestore`, `odoo-logs` | % de uso | > 75% | 1 h | Ops |
| M-11 | **Recursos de contenedores** | `docker stats` vs límites (db 12 G, odoo 10 G) | % RAM/CPU | > 80% sostenido 15 min | 5 min | Ops |
| M-12 | **Tamaño de logs** | Docker `json-file` `max-size 50m, max-file 10` ⇒ máx. 500 MB/servicio; `odoo.log` sin rotación propia | MB/día | `odoo.log` > 1 GB ⇒ rotar (`05` §5) | Diaria | Ops |
| M-13 | **Crecimiento de BD** | `pg_database_size` | GB/mes; líneas por `account_move` | Proyección > 80% del disco a 90 días | Semanal | DBA |

**Instrumentación mínima exigida (CAP-05):** consulta.sql de M-3/M-6/M-8/M-9 en el runbook del DBA + revisión manual de `dblogs` diaria mientras no exista colector de métricas `[VERIFY: herramienta de observabilidad aprobada — sin agente en el repo]`.

## 6. Disparadores de revisión de capacidad (review triggers) — **CAP-06**

| # | Disparador | Acción | Máx. en |
|---|---|---|---|
| TR-1 | Uso de conexiones ≥70% (M-6) durante 3 días | Revisar `db_maxconn` y `max_connections`; considerar PgBouncer | 5 días hábiles |
| TR-2 | `limit_memory_soft` de workers alcanzado o respawns >2/h (M-7) | Recalcular fórmula §3.1 (workers vs RAM) | 48 h |
| TR-3 | p95 autorización SRI > 5 s por 24 h (M-5) | Distinguir causa local vs externa (R-006); escalar a proveedor | 24 h |
| TR-4 | Consultas lentas > 20/h sostenidas (M-2) | Tuning de índices/estadísticas (`default_statistics_target=500` ya activo) | 5 días hábiles |
| TR-5 | Autovacuum atrasado (M-3) | Ajustar `autovacuum_*` o limitar escrituras | 48 h |
| TR-6 | Proyección de disco > 80% a 90 días (M-13) | Verticalizar o archivar (política `05` §8) | 10 días hábiles |
| TR-7 | Nuevos inquilinos SaaS que dupliquen `account_move` activos/mes | Recalcular §3 con N pico | Antes de alta |
| TR-8 | Cambio de `docker-compose.yml` (RAM/CPU/workers) | Recalcular §3.1–3.3 y actualizar este doc (CHG) | Con el cambio |
| TR-9 | TP-1…TP-8 fuera de meta 2 ciclos consecutivos | CAPA (`00` §10) + plan de escalado | Con el KPI |

## 7. Runbook de escalado (scaling) — **CAP-07/08/09**

*Orden obligatorio: **vertical → réplica de lectura → sharding multi-tenant**. Cada paso es un CHG normal (`04` §3.1) con plan de rollback (`04` §6).*

### 7.1 Paso 1 — Escalado vertical (CAP-07) — primero siempre

| Sub-sistema | Ajuste | Recálculo obligatorio |
|---|---|---|
| Odoo | Subir `deploy.resources.limits.memory` (10→14 GB) y CPU; recién entonces subir `ODOO_WORKERS` hacia `(núcleos×2)+1` | `workers ≤ (RAM×0.75)/1.25 GB`; `db_maxconn = (197−2)/(workers+2+1)` |
| Postgres | Subir contenedor 12→16 GB; `shared_buffers = 25% RAM` (4→5 GB); `effective_cache_size = RAM disponible` | `work_mem` solo si M-11 < 60% |
| Conexiones | Subir `max_connections` 200→300 **solo** después de fijar `db_maxconn` | Revalidar fórmula §3.2 |
| Contenedores | Subir límites en `docker-compose.yml` (CHG) | Actualizar §3 y `.env` |

Pasos: 1) backup pre-cambio (dump manual) 2) editar `.env`/`docker-compose.yml` en rama `feature/*` 3) PR + CAB 4) `docker compose up -d` en ventana 5) validar TP-1…TP-7 6) rollback = revertir `.env` y `up -d`.

### 7.2 Paso 2 — Réplica de lectura (CAP-08)

1. Provisionar `postgres-readonly` (streaming) — `wal_level = logical` ya habilitado (línea 16) es compatible con replicación.
2. Configurar en Odoo `db_replica_host`/`db_replica_port` **si aplica al flujo** `[VERIFY: comportamiento de réplicas de solo lectura en Odoo 18 Community — confirmar soporte de db_replica en esta build]`.
3. Repartir conexiones: dividir `db_maxconn` (pool `_Pool` + `_Pool_readonly`).
4. Aplicar a: consultas de informes/ATS (`l10n_ec_reports`), portal (`l10n_ec_portal`), consultas MCP de lectura (§7.4).
5. **Prohibido** enrutar escrituras fiscales (post/firma) a la réplica.
6. Criterio de éxito: M-6 < 50% en primario con mismas cargas; lag de réplica < 5 s.

### 7.3 Paso 3 — Sharding multi-tenant por base de datos (CAP-09)

El diseño ya es **una BD por inquilino** (`ODOO_LIST_DB=true`, `ODOO_DBFILTER=odooec.*`, comentario *"Multi-tenant (SaaS): one database per tenant"*). Escalar:

1. Agrupar inquilinos por nodo: nodo A `dbfilter=tenant_a.*`, nodo B `tenant_b.*` (re-render por `.env`/entorno por nodo).
2. Balanceo por host/URL (?db= o subdominio) en el proxy inverso (`proxy_mode=true` ya está activo en `.env` — requiere proxy real delante, **verificar** [VERIFY]).
3. Un `max_connections` **por nodo**, no global: la fórmula §3.2 se aplica por nodo con su `N` de inquilinos activos.
4. Respaldos: parametrizar el `pg_dump` del servicio `backup` por lista de BD del nodo (hoy solo duma `$ODOO_DB` — brecha documentada en `02` §5.2).
5. Criterio: ningún nodo supera TR-1/TR-2 tras 7 días; alta de inquilino ≤ 1 h.
6. Siguiente frontera si el sharding por BD no basta: partición/tablas por rango de fechas en `account_move` (archivado anual, control AUD-09 `05`).

### 7.4 Nota sobre el servicio `mcp`

`mcp` (`python:3.12-slim`, sin recursos definidos) no consume memoria comparable; su riesgo de capacidad es **el patrón de consulta** (búsquedas amplias vía MCP): aplicar `limit` a listados (ya presente en `get_stock_level {limit}`) y rate-limit (`07` §6) → **CAP-10**.

## 8. Responsabilidades, evidencias y revisión

| Rol | Responsabilidad |
|---|---|
| DBA | Métricas M-2/M-3/M-6/M-8/M-9/M-13, tuning `postgresql.conf`, ejecuta escalado vertical |
| Ops | M-4/M-5/M-7/M-10/M-11/M-12, alertas, healthchecks |
| Arquitecto | Aprueba paso de escalado (réplica/sharding), recalcula fórmulas |
| CIO | Aprueba consumo de infraestructura (capex/opex) |
| Oficial Cumplimiento | Valida que el escalado no rompa controles fiscales (secuencias, evidencia) |

**Evidencias:** informe mensual de capacidad (§5 con M-1…M-13), actas de revisión TR-*, registro de cambios CHG de capacidad, salida de validación de TP-1…TP-8 tras cada cambio.

**Cadencia de revisión:** métricas mensuales (informe de capacidad); revisión completa de capacidad **trimestral** (próxima 2027-01-15); recalculo de fórmulas ante TR-7/TR-8.

---

*Riesgos: R-003 (agotamiento de conexiones), R-006 (SRI lento/caído), R-010 (bloat/autovacuum), R-011 (OOM de workers), R-016 (host único sin HA), R-020 (divergencia workers 4 vs 8) — ver `06b_MATRIZ_DE_RIESGOS.md`. KPI: `08_INDICADORES_Y_METAS.md` KPI-03…KPI-07.*
