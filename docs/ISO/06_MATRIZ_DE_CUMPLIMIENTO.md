# ISO-EC-06 — Matriz de Cumplimiento Regulatorio

**Proyecto:** Odoo 18 Ecuador Localization · **Versión:** 1.1 · **Fecha emisión:** 2026-10-15 · **Última revisión:** 2026-10-16 (§3.8 CM-40..42, vertical AGRO)
**Responsable:** Gerencia de Cumplimiento / Equipo Fiscal-Contable · **Próxima revisión:** 2027-04-15
**Clasificación:** Uso interno

---

## 1. Propósito y Alcance

Inventario **honesto** de obligaciones regulatorias aplicables a la plataforma (SRI, IESS,
Ministerio del Trabajo, Superintendencia, BCE, SENAE, protección de datos) con el estado real de
implementación en el repositorio. **Esta matriz no es un 100%**: el 100% de las filas marcadas
*Pendiente*/*Parcial* son deuda documentada que debe priorizarse en plan de trabajo (§4).

Criterios de estado:

| Estado | Definición |
|---|---|
| **Implementado** | Código/funcionalidad existe, es verificable en el repo y cubre la obligación completa |
| **Parcial** | Existe código parcial, plantilla, catálogo o URL de referencia, pero con lagunas conocidas (ver "Brecha") |
| **Pendiente** | No se encontró implementación en el repo |

## 2. Referencias Normativas

| Referencia | Observación |
|---|---|
| Resoluciones SRI de facturación electrónica [VERIFY: números de resolución vigentes] | Comprobantes electrónicos |
| Código Tributario — obligación de retener [VERIFY: artículos aplicables] | Retenciones IR/IVA |
| Reglamento para la Aplicación de la Ley de Régimen Tributario Interno [VERIFY] | ATS, formularios, ICE, RIMPE |
| Convenio de Colaboración SRI–IESS [VERIFY: convenio vigente] | Split 30%/70% de retenciones |
| Ley Orgánica de Seguridad Social (LOESS), reglamentos de aportes [VERIFY] | IESS |
| Acuerdos MDT sobre SBU y actualizaciones salariales [VERIFY: acuerdo MDT-2025-195 vs MDT-2025-227 — discrepancia entre fuentes internas] | SBU |
| Código del Trabajo (décimos, fondos de reserva, vacaciones, utilidades, horas extra) [VERIFY] | Laboral |
| Normativa Superintendencia de Compañías (NEC) [VERIFY] | Estados financieros/libros |
| Normativa BCE sobre libro de bancos y reporte de transacciones [VERIFY: valores de umbral] | BCE/prevención lavado |
| Convenio Ecuador–OMPI/EUIPO [VERIFY] | Marcas |
| Ley Orgánica de Protección de Datos Personales (Ley 0/14) y su reglamento [VERIFY: número del decreto reglamentario] | Datos personales |

## 3. Matriz

### 3.1 SRI — Facturación electrónica

| ID | Obligación | Implementación actual (ruta real) | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-01 | Comprobantes electrónicos firmados (clave de acceso 49 dígitos, XAdES) | `l10n_ec_edi/models/sri_signer.py`, `l10n_ec_edi/models/access_key.py`, `l10n_ec_edi/models/sri_service.py` | CHG-11, SEG-05 | **Parcial** | Endurecer pruebas de firma/fuzzing (l10n_ec_security), revisar `edi_templates.xml` no listado en manifest |
| CM-02 | Factura (codDoc 01) y Nota de Crédito (codDoc 04) | `l10n_ec_edi/models/account_move.py`, wizard NC | CHG-11 | **Parcial** | Completar validación de esquema XML por tipo |
| CM-03 | Liquidación de Compra (codDoc 03) | — | CHG-11 | **Pendiente** | Sprint 12 de `DEVELOPMENT_PLAN.md` |
| CM-04 | Nota de Venta (02), Nota de Débito (05), Retención (06), Guía de Remisión (07) | — | CHG-11 | **Pendiente** | Priorizar 05/06 por uso frecuente |
| CM-05 | Autorización SRI + reintento ante indisponibilidad | Parcial (cliente HTTP) | BC-12 | **Parcial** | Cola de reintentos con backoff y monitoreo (R-006) |

### 3.2 SRI — Retenciones

| ID | Obligación | Implementación actual | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-06 | Retención IR en la fuente (rentas 15/17/27, etc.) | Parcial: catálogos y cálculo básico en `l10n_ec_edi`/`l10n_ec_withholding` | CHG-11 | **Parcial** | Validar mapeo por tipo de renta vs RUC del proveedor |
| CM-07 | Split 30% SRI / 70% IESS en retención IVA | Solo códigos de impuesto definidos; **sin lógica de división de pago** | CHG-11 | **Pendiente** | Implementar liquidación y pago separados (Convenio SRI–IESS [VERIFY]) |
| CM-08 | Regla de retención "5 días hábiles" (aplicar retención cuando el proveedor también retiene) | Marcada **ELIMINADA en 2026** en el código fuente, pero `CUMPLIMIENTO_REGULATORIO.md` la reporta vigente | CHG-11 | **Parcial** | [VERIFY: vigencia de la regla en el SRI — conciliar código vs documentación] |
| CM-09 | Comprobante de retención electrónico (codDoc 06) | No implementado | CHG-11 | **Pendiente** | Sprint posterior |

### 3.3 SRI — Declaraciones y libros

| ID | Obligación | Implementación actual | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-10 | ATS (Anexo Transaccional Simplificado) | `generate_ats` (MCP) + `l10n_ec_edi` | CHG-11 | **Parcial** | Validar esquema anual y prorrateo de montos |
| CM-11 | Formulario 101 (impuesto a la renta) | — | CHG-11 | **Pendiente** | Sprint de formularios |
| CM-12 | Formulario 102 (IVA) | — | CHG-11 | **Pendiente** | Sprint de formularios |
| CM-13 | Formulario 103 (retenciones en la fuente) | — | CHG-11 | **Pendiente** | Sprint de formularios |
| CM-14 | Formulario 104 (IVA) | Parcial: asientos e impuestos modelados | CHG-11 | **Parcial** | Completar exportación/pago |
| CM-15 | Formulario 107 (IESS - aportes) | Plantilla en `l10n_ec_payroll_data.xml` (parcial) | CHG-11 | **Parcial** | Completar generación automática |
| CM-16 | Formulario 108 (retenciones IESS) | — | CHG-11 | **Pendiente** | Sprint de formularios |
| CM-17 | Libros electrónicos (ventas/compras) vía SRI | Parcial: reportes estándar Odoo; sin flujo de remisión de libros | BC-12 | **Pendiente** | Evaluar portal SRI de libros |
| CM-18 | ICE (impuesto a los consumos especiales) | `l10n_ec_ice` existe, pero `"version": "1.0"` (anomalía de versionado, R-012) | CHG-06 | **Parcial** | Corregir versionado + completar cálculo |
| CM-19 | RIMPE (régimen simplificado/monotributo, obligaciones especiales) | `l10n_ec_rimpe` existe, misma anomalía `version: 1.0` | CHG-06 | **Parcial** | Corregir versionado + validar régimen |

### 3.4 IESS

| ID | Obligación | Implementación actual | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-20 | Aportes personal (9.45%) y patronal (11.15%) | Parcial: cálculo en `l10n_ec_payroll` | CHG-11 | **Parcial** | Validar tasas vigentes [VERIFY] y topes |
| CM-21 | Techo de aportes (25 × SBU) | No encontrado en código | CHG-11 | **Pendiente** | Implementar tope en cálculo de aportes |
| CM-22 | Planillas IESS (generación y pago) | Solo URL de referencia en `gov_services_registry` | CHG-11 | **Pendiente** | Definir alcance (manual vs automatizado) |
| CM-23 | Caso especial: 40% de aportes sobre remuneración de horas extra | No encontrado en código | CHG-11 | **Pendiente** | Implementar en motor de nómina |

### 3.5 Ministerio del Trabajo

| ID | Obligación | Implementación actual | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-24 | SBU y su actualización anual | Parcial: parámetro en `l10n_ec_payroll_data.xml` (referencia a acuerdo MDT [VERIFY: número]) | CHG-11 | **Parcial** | Proceso anual de actualización (R-007) |
| CM-25 | Décimo tercero (agüinaldo) y décimo cuarto (vacaciones) | Parcial: cálculo en `l10n_ec_payroll` | CHG-11 | **Parcial** | Validar fechas de pago y proporcionalidad |
| CM-26 | Fondos de reserva (8.33%) | Parcial: cálculo en `l10n_ec_payroll` | CHG-11 | **Parcial** | Validar régimen de transición |
| CM-27 | Utilidades (15% sobre utilidades netas) | — | CHG-11 | **Pendiente** | Sprint posterior (fuera de alcance MVP) |
| CM-28 | Vacaciones (15 días + incremento) | Parcial: saldo y pago en nómina | CHG-11 | **Parcial** | Validar incremento legal acumulado |
| CM-29 | Horas extra (150%/200%) y recargo nocturno | Parcial: reglas en `l10n_ec_payroll` | CHG-11 | **Parcial** | Verificar topes de horas extra |
| CM-30 | Auxilio de cesantía | — | CHG-11 | **Pendiente** | Implementar cálculo y provisiones |

### 3.6 Superintendencia, BCE y otros

| ID | Obligación | Implementación actual | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-31 | NEC (Norma Ecuatoriana de Contabilidad) — plan de cuentas y estados financieros | — | CHG-11 | **Pendiente** | Evaluar plantillas EC de Odoo vs NEC |
| CM-32 | Libros contables y estados financieros para Superintendencia | Parcial: reportes estándar; sin libros formales | BC-12 | **Pendiente** | Definir alcance |
| CM-33 | Libro de bancos (BCE) | — | CHG-11 | **Pendiente** | Integración con extractos bancarios |
| CM-34 | SENAE / ECUAPASS (comercio exterior) | Solo URL de referencia en `gov_services_registry` | CHG-11 | **Pendiente** | Fuera de alcance MVP; definir alcance futuro |
| CM-35 | Reporte de transacciones en efectivo / prevención de lavado de activos (BCE) | — | CHG-11 | **Pendiente** | Requiere definir umbrales y reportes [VERIFY] |

### 3.7 Protección de datos y gobierno de agentes IA

| ID | Obligación | Implementación actual | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-36 | Ley 0/14 — tratamiento de datos personales (consentimiento, minimización, derechos ARCO) | — | SEG-19 | **Pendiente** | Inventario de datos, política de retención, mecanismo de ejercicio de derechos |
| CM-37 | Reglamento de la Ley 0/14 [VERIFY: decreto] | — | SEG-19 | **Pendiente** | Alineado con CM-36 |
| CM-38 | Gobierno de agentes MCP/IA (uso de tools, aprobación humana) | Parcial: `l10n_ec_base/mcp/`, managers por módulo; `mcp_server/` **ausente del repo** aunque `docker-compose.yml` lo monta (R-014) | GOV-09, GOV-10 | **Parcial** | Publicar `mcp_server/` o ajustar compose; aplicar clasificación read-only vs mutating (07 §5) |
| CM-39 | Control de credenciales y permisos (RO 395-2025) | Implementado: `l10n_ec_base/security/l10n_ec_groups.xml`, `l10n_ec/security/l10n_ec_security.xml` (Auditor de Transparencia solo lectura) | SEG-12, AUD-12 | **Implementado** | Auditoría trimestral (AUD-12) |

### 3.8 Agrícola / agroalimentario (vertical AGRO multi-crop — N-06)

Filas del overlay de cultivo: aplican **solo** a tenants del vertical `agro`; las genéricas del
vertical (SRI + trazabilidad) ya están cubiertas en §3.1–3.3. Referencia: `SRS-VERT-AGRO-2026-001` §11.

| ID | Obligación | Implementación actual | Control | Estado | Brecha / próxima acción |
|---|---|---|---|---|---|
| CM-40 | Registro sanitario de productos agroalimentarios procesados (ARCSA) — instancia del overlay: línea CBD del tenant CANNACHAIN [VERIFY: norma aplicable] | — (parámetro diseñado: `v.registro_sanitario` + guardrail, N-01 v1.1) | FR-AG-14 | **Pendiente** | Operator aporta la norma/certificado; guardrail a implementar en P2 |
| CM-41 | Permisos/certificación de cultivo de especies reguladas (AGROCALIDAD/MSP) — instancia: cáñamo/CBD [VERIFY: ley + RO + vigencia] | — | CHG-09/CHG-10 | **Pendiente** | Sin cita oficial no se afirma nada; ruta regulatoria al recibirla |
| CM-42 | ICE — Impuesto a los Consumos Especiales aplicable a productos del vertical (catálogo de categorías) [VERIFY: disparadores por producto] | Parcial: catálogo `l10n_ec_ice/data/l10n_ec.ice.category.csv` | CHG-09/CHG-10 | **Parcial** | Definir qué productos del vertical disparan ICE (tenant-overlay) |

## 4. Resumen y Plan de Trabajo

| Estado | Cantidad |
|---|---|
| Implementado | 1 |
| Parcial | 18 |
| Pendiente | 23 |
| **Total** | **42** |

**Secuencia sugerida** (alineada con `DEVELOPMENT_PLAN.md`):
1. Sprint 12: Liquidación de compra (CM-03), completar 104/107 (CM-14/15), split 30/70 (CM-07).
2. Formularios 101/102/103/108 (CM-11..13, CM-16).
3. Libros y BCE (CM-17, CM-32, CM-33).
4. Ministerio del Trabajo restante (CM-27, CM-30) y techo IESS (CM-21).
5. Ley 0/14 (CM-36/37) y gobierno MCP (CM-38) con soporte de 07.

## 5. Seguimiento

| Métrica | Meta | Relación |
|---|---|---|
| Filas *Pendiente* convertidas a *Parcial/Implementado* por trimestre | ≥ 3 | KPI-16 |
| Filas *Parcial* cerradas a *Implementado* por semestre | ≥ 4 | KPI-16 |
| Discrepancias código vs documentación regulatoria detectadas y conciliadas | 100% conciliadas en 30 días | CHG-11 |
