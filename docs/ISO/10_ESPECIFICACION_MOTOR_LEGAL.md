# ISO-EC-10 — Especificación del Motor de Reglas Legales (Requisitos de Software)

**Proyecto:** Odoo 18 Ecuador Localization · **Versión:** 1.1 · **Fecha emisión:** 2026-10-15 · **Última revisión:** 2026-10-16 (FR-LE-50 identidad EC)
**Responsable:** Gerencia Técnica / Equipo Fiscal-Contable · **Próxima revisión:** 2027-04-15
**Clasificación:** Uso interno
**Norma de referencia:** ISO/IEC/IEEE 29148:2018 (Ingeniería de requisitos — ciclos de vida de software)

---

## 1. Propósito y Alcance

Especifica el **motor de reglas legales ecuatorianas** implementado en módulo Python puro
(`mcp_server/rules.py`, sin dependencias de Odoo) y en las tablas de datos de los módulos
`l10n_ec_*`. Cada regla es **verificable, trazable a una fuente oficial y testeable de forma
aislada**. El motor alimenta el gateway **MCP** (18 herramientas) que es la puerta de entrada
de los agentes al ERP.

Principios rectores (derivados de la política de calidad ISO-EC-00):

* **R1 — Sin invención:** toda constante legal tiene resolución/acuerdo + fecha + URL oficial.
  Lo no confirmado se marca `NO_VERIFICADO` (nunca se inventa un número).
* **R2 — Puro y aislable:** `rules.py` no importa `odoo`; se prueba con `unittest` estándar.
* **R3 — Fuente única:** cada `ir.config_parameter` se define **una sola vez** (evita
  violación de la restricción única de `ir.config_parameter.key`).

## 2. Referencias Normativas (verificadas en auditoría legal 2026-10)

| ID | Norma | Materia | Vigencia 2026 |
|---|---|---|---|
| L-01 | Res. **NAC-DGERCGC26-00000009** (RO 233, 27-feb-2026) | Porcentajes retención **Impuesto a la Renta** (Tabla 19) | Vigente desde 01-mar-2026 |
| L-02 | Res. **NAC-DGERCGC20-00000061** (RO 473, 29-sep-2020) + reformas 21-00000037, 23-00000026 | Porcentajes retención **IVA** (casilleros 104) | Vigente (IVA **no** cambió mar-2026) |
| L-03 | Res. **NAC-DGERCGC25-00000017** (RO 92, 30-jul-2025) | Facturación electrónica: **transmisión mismo día**, anulación **día 7**, CF no anulable | Vigente desde 01-ene-2026 |
| L-04 | Acuerdo **MDT-2025-195** (RO Supl. 187) | **SBU 2026 = $482** | Vigente |
| L-05 | Tasas oficiales **IESS** (iess.gob.ec) | Aportes 9.45% personal / 11.15% patronal (+0.5 SECAP +0.5 IECE) | Vigente |
| L-06 | **Código del Trabajo** (RO Supl. 906, 20-dic-2016) | Décimos (art. 111/113), fondos reserva (art. 196), vacaciones, horas | Vigente |
| L-07 | **LRTI art. 50** + **Código Tributario art. 12** | Retención: entrega en 5 días hábiles (días hábiles) | Vigente |

## 3. Requisitos Funcionales del Motor (FR-LE-NN)

### 3.1 Retención de IVA — escala doble (FR-LE-10)

Los casilleros del Formulario 104 son **buckets de porcentaje**, no de materia
(Fuente: Guía SRI F.104 — *"721, 723: 10% y 20%; 725, 727, 729 y 731: 30%, 50%, 70% y 100%"*):

| Casillero | % | Aplicación (Res. L-02) |
|---|---|---|
| 721 | 10% | Bienes, agente→**contribuyente especial** (Art. 5.a) |
| 723 | 20% | Servicios/consultoría, agente→**contribuyente especial** (Art. 5.b) |
| 725 | 30% | Bienes (general) y **toda construcción** (Arts. 3.a / 5.c) |
| 727 | 50% | Casillero Res. 61 (casos específicos) |
| 729 | 70% | Servicios/consultoría y arrendamiento a obligados (Art. 3.b) |
| 731 | 100% | Honorarios personas naturales, arrendamiento a no obligados, liquidación de compra, importación de servicios, combustibles, y **exportadores habituales (Art. 11, siempre)** |

**Función:** `iva_retention_bucket(category, agent_especial, counterparty_especial,
counterparty_obligated, is_exportador)` → `{casillero, percentage, scale, reason}`.
Orden de selección: exportador (100%) > operaciones absolutas 100% > construcción (30%)
> especial→especial (10/20) > general (30/70).

**Cobertura verificada:** 17/17 casos de la tabla legal (ver ISO-EC-11).
**Dato clave auditado:** la retención de IVA se entrega **íntegramente al SRI**; **no existe
split IESS/SECE** del IVA (el campo `iess_share` se mantiene en `0.0` solo por compatibilidad).

### 3.2 Retención de Impuesto a la Renta (FR-LE-20)

`ir_retention_pct(base, category, override)` valida contra la Tabla 19 (L-01).
Defaults vigentes: honorarios `303 = 10%`; bienes muebles `312 = 2%`; mano de obra `307 = 3%`.
La tarifa **2.75% fue ELIMINADA** en 2026; `override` con valores fuera de la tabla se marca
`valid=False`. (Los porcentajes fueron corregidos en la auditoría: 304→10, 307→3, 308→10,
320→10, 340→3.)

### 3.3 Transmisión y anulación de comprobantes (FR-LE-30)

Res. L-03 (vigente 01-ene-2026):

* `transmission_deadline(issue_date, ...)` → **transmisión en el MISMO momento** de generación;
  la ventanilla legacy de 4 días hábiles quedó **derogada** (`TRANSMISSION_GRACE_DAYS_LEGACY=4`
  solo como referencia histórica).
* `annulment_ok(doc_type, issued_date, ...)` → anulación hasta **día 7** del mes siguiente
  (no día 10). **Facturas a consumidor final NO anulables.** NC/ND/retención requieren
  aceptación del receptor (5 días hábiles).
* `retention_deadline(invoice_date, ...)` → **5 días hábiles** para ENTREGAR el comprobante de
  retención al contraparte (L-07), excluyendo fines de semana y feriados (`ec_holidays`).

### 3.4 Parámetros económicos y de nómina (FR-LE-40)

Fuente única (`R3`): `l10n_ec_base/data/l10n_ec_sri_config.xml` (owner de los compartidos).

| Parámetro | Valor | Fuente |
|---|---|---|
| `l10n_ec.sbu` | 482.00 | L-04 |
| `l10n_ec.iess_aporte_personal` | 9.45 | L-05 |
| `l10n_ec.iess_aporte_patronal` | 11.15 | L-05 |
| `l10n_ec.iess_secap` / `iess_iece` | 0.5 / 0.5 | L-05 (total patronal 12.15%) |
| `l10n_ec.iess_ceiling_sbu_multiplicador` | 25 | **NO_VERIFICADO** (múltiplo 25×SBU; techo $12,050) |

`l10n_ec_hr_payroll` **depende de `l10n_ec_base`** (garantiza existencia de los parámetros
compartidos sin duplicar claves).

### 3.5 Validación de identidad EC — cédula y RUC (FR-LE-50)

Fuente de verdad: puerto fiel de `stdnum` (`ec.cedula`, `ec.ruc`) en `mcp_server/rules.py`;
reglas enseñadas por el operador (D-02/D-03, SRS-VERT-AGRO §7).

| ID | Requisito | Criterio / evidencia |
|---|---|---|
| FR-LE-50.1 | **Cédula**: 10 dígitos; provincia `01–24` (+`30`,`50`); 3er dígito `0–6`; módulo 10 (pesos 2,1) sobre los 10 dígitos = 0 | `rules.cedula_check_digit_ok` |
| FR-LE-50.2 | **RUC**: 13 dígitos con despacho por 3er dígito — `0–5` natural (valida como cédula + establecimiento ≠ `000`), `6` público (mod-11 primeros 9, pesos 3,2,7,6,5,4,3,2,1 con fallback natural), `9` jurídica (mod-11 primeros 10, pesos 4,3,2,7,6,5,4,3,2,1), `7/8` inválidos | `rules.ruc_check_digit_ok` |
| FR-LE-50.3 | **Equivalencia stdnum**: el puerto produce idéntico resultado a `stdnum` — verificación cruzada **20,195 casos → 0 diferencias** (contenedor, stdnum 1.19, 2026-10-16: IDs reales, mutaciones dígito a dígito, rejillas de provincia/3er dígito/establecimiento, 20,000 fuzz) | evidencia de corrida; test permanente `TestStdnumEquivalence` **pendiente** (hueco ISO-EC-11 §5) |
| FR-LE-50.4 | **RUC natural = cédula + `001`** (D-02, siempre); **comprar con cédula permitido, vender/emitir exige RUC ACTIVO** (D-03): `sri.status=INACTIVO` bloquea el wizard | guardrails N-01 §Guardrails |
| FR-LE-50.5 | Solo IDs de prueba del operador son válidos en tests/docs: `1713488185` (cédula) y `1793125212001` (RUC) — D-04; cualquier otro RUC es un bug | suite MCP 54/54 (IDs reales) |

## 4. Requisitos No Funcionales (NFR-NN)

| ID | Requisito | Criterio |
|---|---|---|
| NFR-01 | Aislamiento | `rules.py` sin importar `odoo`; testeable con stdlib |
| NFR-02 | Trazabilidad | Toda constante cita resolución + fecha (§2) |
| NFR-03 | Tolerancia a faltantes | Datos legales ausentes → el MCP **pregunta** (no falla) vía `build_question`/`missing_invoice_data` |
| NFR-04 | Determinismo | Mismas entradas → mismo casillero/monto (redondeo a 2 decimales) |
| NFR-05 | Fuente única | Sin duplicación de `ir.config_parameter` (restricción única) |

## 5. Trazabilidad Requisito → Implementación → Prueba

| Requisito | Implementación | Prueba |
|---|---|---|
| FR-LE-10 (IVA doble escala) | `rules.iva_retention_bucket`, `retention_codes_2026.xml` | `test_iva_bucket_dual_scale`, 17 casos standalone |
| FR-LE-20 (IR Tabla 19) | `rules.ir_retention_pct` | `test_ir_default_servicios`, `test_ir_override_*` |
| FR-LE-30 (transmisión/anulación) | `rules.transmission_deadline`, `annulment_ok`, `retention_deadline` | `test_sri_2026_rules.py` |
| FR-LE-40 (parámetros) | `l10n_ec_sri_config.xml`, `l10n_ec_payroll_data.xml` | `test_payroll_calc_standalone.py` |
| FR-LE-50 (identidad) | `rules.py`: `cedula_check_digit_ok`, `ruc_check_digit_ok` (puerto stdnum) | `test_server.py` `TestValidation` + equivalencia 20,195→0 |
| NFR-01..05 | diseño `rules.py` | `mcp_server/test_server.py` (54 tests) |

## 6. Índice de verificaciones pendientes (`NO_VERIFICADO`)

| Ítem | Nota |
|---|---|
| Techo IESS 25×SBU | No se localizó la norma que fije el múltiplo; verificar antes de auditoría externa |
| Casillero 727 (50%) | Existe en el F.104 oficial pero el gatillo exacto requiere el texto completo de Res. 61 |

> Los marcados `NO_VERIFICADO` se revisan en la próxima auditoría legal (KPI-16, ISO-EC-08).
