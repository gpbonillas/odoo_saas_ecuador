# ISO-EC-08 — Indicadores y Metas

**Proyecto:** Odoo 18 Ecuador Localization · **Versión:** 1.0 · **Fecha emisión:** 2026-10-15
**Responsable:** Gerencia TI / Calidad · **Próxima revisión:** 2027-04-15
**Clasificación:** Uso interno

---

## 1. Propósito y Alcance

Define los indicadores clave de desempeño (KPIs) del sistema: fórmula, meta, frecuencia de medición,
responsable y fuente de datos. Todos los KPIs son medibles con datos disponibles en la plataforma
(BD Odoo, logs, monitoreo, matriz de cumplimiento 06). Cada KPI se asocia al control que lo sostiene
(KPI-* ↔ control de otro documento).

**Criterio de medición**: toda métrica tiene fuente identificable y responsable asignado. Los KPIs se
reportan en el comité trimestral y se consolidan semestralmente para dirección (07 §7).

## 2. Referencias Normativas

| Referencia | Observación |
|---|---|
| ISO/IEC 27001:2022 A.9 (accesos), A.8 (operaciones), A.5.36 (cumplimiento) | Métricas de control |
| ISO/IEC 27004 / ISO 22301 (medición de seguridad y continuidad) | Metodología de KPI |

## 3. Tabla de KPIs

| ID | Indicador | Fórmula / método | Meta | Frecuencia | Responsable | Fuente / evidencia | Control |
|---|---|---|---|---|---|---|---|
| KPI-01 | Disponibilidad del servicio | Tiempo activo / Tiempo total × 100 | ≥ 99.5% | Mensual | Infra | Monitoreo host / logs | CAP-05 |
| KPI-02 | RPO (pérdida de datos aceptada en desastre) | Horas desde último backup válido | ≤ 6 h | Mensual | Infra | `pg_dump` cada 6h (`docker-compose.yml`, `sleep 21600`) | BC-01 |
| KPI-03 | RTO (tiempo de recuperación) | Tiempo hasta restauración funcional | ≤ 4 h (objetivo; probar) | Por prueba | Infra | Prueba de restore (02 §5) | BC-09 |
| KPI-04 | MTTR (tiempo medio de reparación de incidentes) | Σ Tiempos de resolución / Nº incidentes | ≤ 4 h | Mensual | Soporte | Bitácora de incidentes | BC-10 |
| KPI-05 | Cobertura de pruebas automatizadas | Tests que pasan / Tests totales | ≥ 80% | Por release | Dev | Suite de tests del repo (15 `test_*.py`) | Q-11 |
| KPI-06 | Efectividad del autovacuum | Tablas con `n_dead_tup` estable tras VACUUM / total monitoreadas | ≥ 95% | Semanal | DBA | `pg_stat_user_tables` | CAP-07 |
| KPI-07 | Consultas lentas | Nº consultas con duración > 250 ms (`log_min_duration_statement`) | Reducir 10% trimestral | Mensual | DBA | Log Postgres | AUD-08 |
| KPI-08 | Conexiones DB dentro de límite | Conexiones usadas / `max_connections` × 100 | < 80% | Mensual | DBA | `pg_stat_activity` | CAP-03 |
| KPI-09 | Latencia de autorización SRI | Tiempo medio de respuesta del SRI (por comprobante) | ≤ 5 s (p95) | Mensual | Fiscal/Dev | Logs del cliente SRI (`l10n_ec_edi`) | BC-12 |
| KPI-10 | Tasa de autorización SRI al primer intento | Comprobantes autorizados / Comprobantes enviados × 100 | ≥ 99% | Mensual | Fiscal | BD Odoo (estado de comprobantes) | BC-12 |
| KPI-11 | Retenciones emitidas a tiempo | Retenciones emitidas ≤ 5 días hábiles / Total × 100 [VERIFY: plazo vigente] | 100% | Mensual | Fiscal | BD Odoo | CHG-11, CM-06 |
| KPI-12 | Backups exitosos | Backups OK / Backups programados × 100 | 100% | Mensual | Infra | `pg_dump` + log | BC-02 |
| KPI-13 | Restores probados con éxito | Restores OK / Restores intentados × 100 | 100% (al menos 1/año) | Anual | Infra | Prueba de restore | BC-09 |
| KPI-14 | Riesgos con dueño y plan de tratamiento | Riesgos tratados / Total de riesgos × 100 | 100% | Trimestral | Gerencia | 06b §4 | 06b |
| KPI-15 | Riesgos cerrados o mitigados | Nº riesgos que redujeron severidad residual | ≥ 2/trimestre | Trimestral | Gerencia | 06b §6 | 06b |
| KPI-16 | Avance de matriz de cumplimiento | Filas que pasan de Pendiente/Parcial a Implementado | ≥ 3/trimestre | Trimestral | Cumplimiento | 06 §3–4 | CM-* |
| KPI-17 | Incidentes de trazabilidad | Asientos cancelados sin NC + accesos no registrados | 0 | Mensual | Auditor | 05 §7 (rutinas A-1, A-2) | AUD-04 |
| KPI-18 | Auditorías/revisiones completadas a tiempo | Revisiones realizadas / Revisiones programadas × 100 | 100% | Trimestral | Calidad | Bitácora | AUD-12/14 |

## 4. Especificación de medición (fuentes y consultas)

| KPI | Fuente de datos | Método de obtención |
|---|---|---|
| KPI-01 | Monitoreo del host / logs Docker | Diferencia entre timestamps de arranque y caída del servicio `odoo-odoo` |
| KPI-02 | `pg_dump` en `odoo-ec_dbbackups` (`docker-compose.yml`, `sleep 21600`) | Hora actual − hora del dump más reciente válido |
| KPI-03 | Bitácora de pruebas de restore (02 §5) | Cronómetro desde inicio del procedimiento hasta functional check |
| KPI-04 | Bitácora de incidentes | Σ (fin − inicio) / nº de incidentes |
| KPI-05 | Suite de pruebas del repo (15 archivos `test_*.py`) | Tests que pasan / tests totales en CI |
| KPI-06 | `pg_stat_user_tables` | Comparación de `n_dead_tup` antes/después del ciclo de autovacuum |
| KPI-07 | Log Postgres (`log_min_duration_statement=250ms`, `config/postgresql.conf:19`) | Conteo de líneas que superan el umbral |
| KPI-08 | `pg_stat_activity` | `COUNT(*)` de conexiones vs `max_connections` (200) |
| KPI-09 | Logs del cliente SRI (`l10n_ec_edi/models/sri_service.py`) | p95 del tiempo de respuesta por comprobante |
| KPI-10 | BD Odoo (estado de comprobantes autorizados vs rechazados) | Autorizados al primer envío / Total enviados |
| KPI-11 | BD Odoo (fecha de emisión de retención vs fecha de la operación) | Retenciones dentro del plazo / Total [VERIFY: plazo vigente] |
| KPI-12 | Volúmen de backups + log | Backups OK / Backups programados |
| KPI-13 | Prueba de restore anual (02 §5) | Restores OK / Restores intentados |
| KPI-14 | 06b §4 (matriz de riesgos) | Riesgos con dueño y plan / Total |
| KPI-15 | 06b §6 (plan trimestral) | Riesgos que redujeron severidad residual |
| KPI-16 | 06 §3–4 (matriz de cumplimiento) | Filas que avanzaron de estado |
| KPI-17 | 05 §7 (rutinas A-1 y A-2) | Conteo de anomalías (debe ser 0) |
| KPI-18 | Bitácora de auditoría | Revisiones realizadas / programadas |

## 5. Ejemplos de cálculo

| KPI | Ejemplo | Resultado |
|---|---|---|
| KPI-08 | 150 conexiones activas de 200 | 75% → **cumple** (< 80%) |
| KPI-10 | 1.000 comprobantes enviados, 985 autorizados al primer intento | 98.5% → **no cumple** (< 99%) |
| KPI-02 | Último `pg_dump` hace 5 h | 5 h → **cumple** (≤ 6 h) |
| KPI-05 | 80 de 100 tests pasan | 80% → **cumple** (≥ 80%) |
| KPI-07 | 40 consultas > 250 ms este mes vs 45 el anterior | −11% → **cumple** (mejora ≥ 10%) |

## 6. Tablero y Escalamiento

| Nivel | Umbral de alerta | Acción | Responsable |
|---|---|---|---|
| Verde | Dentro de meta | Registro en acta | Dueño del KPI |
| Ámbar | Meta − 10% (relativo) o valor absoluto crítico | Plan de acción correctiva (CAPA) con fecha | Dueño del KPI + Calidad |
| Rojo | KPI-08 > 90% · KPI-12 < 100% · KPI-02 > 6 h · KPI-01 < 95% | Incidente formal + escalamiento a Gerencia TI (BC-10) | Gerencia TI |

**Tablero**: hoja de cálculo/acta del comité con los 18 KPIs, tendencia de 3 meses y estado
semáforo. Se actualiza al cierre de cada mes (§7) y se presenta en el comité trimestral.

## 7. Medición y Reporte

| Elemento | Definición |
|---|---|
| **Unidad** | % o conteo, según tabla |
| **Ventana de medición** | Mes calendario (o trimestre/año para los indicadores así definidos) |
| **Umbral de alerta** | Meta − 10% (o valor absoluto crítico: KPI-08 > 90%, KPI-12 < 100%) |
| **Canal de reporte** | Comité trimestral + reporte semestral a dirección |
| **Registro** | Acta del comité con valor, tendencia y acción correctiva si hay desviación |

## 8. Metas por Período

| Período | Metas prioritarias |
|---|---|
| 2026-Q4 | KPI-02 (RPO ≤ 6h) y KPI-12 (100%) estables; KPI-08 < 80% tras aplicar `db_maxconn` |
| 2027-Q1 | KPI-03 (RTO ≤ 4h) probado; KPI-01 ≥ 99.5%; KPI-13 (restore probado) |
| 2027-Q2 | KPI-05 ≥ 80%; KPI-16 ≥ 9 filas avanzadas en total; KPI-10 ≥ 99% |

## 9. Seguimiento

| Acción | Responsable | Frecuencia |
|---|---|---|
| Actualizar tablero de KPIs | Infra/Calidad | Mensual |
| Revisar desviaciones y abrir CAPA | Calidad | Trimestral |
| Revisar y ajustar metas | Gerencia TI | Semestral |
