# ISO-EC-11 — Documentación de Pruebas de Software

**Proyecto:** Odoo 18 Ecuador Localization · **Versión:** 1.2 · **Fecha emisión:** 2026-10-15 · **Última revisión:** 2026-10-16 (54/54; cierre CHG-2026-003/004/005: parser SRI, validador stdnum y clase `TestStdnumEquivalence`)
**Responsable:** Gerencia Técnica / Equipo QA · **Próxima revisión:** 2027-04-15
**Clasificación:** Uso interno
**Norma de referencia:** ISO/IEC/IEEE 29119-1/2/3:2022 (Pruebas de software)

---

## 1. Propósito y Alcance

Define la **estrategia, suites y evidencias de prueba** del sistema. Las pruebas se agrupan en:
(a) **motor legal puro** (`mcp_server/`, stdlib, sin Odoo) y (b) **módulos Odoo** (`l10n_ec*`,
requieren ORM). La trazabilidad a requisitos está en ISO-EC-10 §5.

| Métrica | Valor |
|---|---|
| Pruebas definidas (total repo) | **440** (415 + 25: MCP +3 y `l10n_ec_base` +22 incorporado al inventario) |
| Suites de archivo | 29 (`test_*.py`) |
| Suite MCP (pura, sin Odoo) | **54 — estado: OK (100%)** (host: 51 + 3 skips sin stdnum; contenedor: 54/54, 2026-10-16) |
| Módulos `l10n_ec*` | 20 |

## 2. Estrategia de pruebas (ISO/IEC/IEEE 29119-2)

| Nivel | Qué cubre | Cómo se ejecuta | Estado |
|---|---|---|---|
| **Unitario puro** (`mcp_server/test_server.py`) | Reglas legales, validación RUC/cedula (stdnum), clave de acceso 49 d., split IR/IVA, buckets IVA, nómina, **equivalencia stdnum permanente** | `python3 mcp_server/test_server.py` | **54/54 OK** (host: 3 skips sin stdnum) |
| **Unitario Odoo** (`tests/unit/`, `l10n_ec*/tests/`) | Cálculo de nómina, reportes/ATS, retenciones, endpoints SRI, catálogos | `--test-enable` dentro del contenedor | Requiere BD |
| **Regulatorio** (`tests/regulatory/`) | Constantes legales 2026 vs. motor | `--test-enable` | Requiere BD |
| **Integración / E2E** | Emisión de factura → firma → SRI (celcer), libros, ATS | Flujo completo en contenedor | Pendiente (ver §5) |

## 3. Suites y cobertura (inventario verificado)

### 3.1 Motor legal puro — `mcp_server/test_server.py` (54 tests, OK)

| Bloque | Tema | Estado |
|---|---|---|
| TestWithholdingMath | IR defaults/overrides, **IVA full→SRI (sin split IESS)**, **buckets IVA dual-scale** | OK |
| TestPayrollMath | Impuesto progresivo, liquidación, décimos, IESS | OK |
| TestValidation | RUC/cédula dígito verificador (despacho stdnum), perfil contribuyente, **IDs reales exclusivos** (`1713488185`, `1793125212001`) | OK |
| TestAccessKey | Clave acceso 49 dígitos, validación, ambiente | OK |
| TestSRIRules | Transmisión mismo-día, anulación día-7, CF no anulable | OK |
| TestBusinessDays | Días hábiles, feriados Ecuador, plazo 5 días | OK |
| **TestStdnumEquivalence** (CHG-2026-005) | `rules.py` vs `stdnum.ec.ci`/`stdnum.ec.ruc`: IDs aprobados + mutaciones + barrido determinista provincias × 3er dígito × longitudes 10/13 | **OK — 22,727 casos → 0 diferencias** (contenedor; host: skip sin stdnum) |

> **Evidencia de equivalencia stdnum (2026-10-16):** el puerto `cedula_check_digit_ok` /
> `ruc_check_digit_ok` comparado contra `stdnum` 1.19 **dentro del contenedor Odoo**:
> primera verificación manual **20,195 casos → 0 diferencias**; desde CHG-2026-005 esto es una
> **prueba permanente** (`TestStdnumEquivalence`) que corre en cada suite del contenedor con
> corpus determinista: **22,727 casos → 0 diferencias (1,682 stdnum-válidos)**.

> Correcciones aplicadas en la auditoría 2026-10 (código correcto, test desactualizado → test corregido):
> `test_ir_default_servicios` (1.75→**10%**), `test_ir_override_valid` (2.75→**2.0**; 2.75 eliminado),
> `test_iva_split_30_70`→`test_iva_full_to_sri_no_iess_split` (**iess_share=0.0**),
> + `test_iva_bucket_dual_scale` (**17 casos** escala doble), + `test_ir_override_eliminated_rate`.

### 3.2 Módulos Odoo (tests/unit + l10n_ec*/tests)

| Archivo | Tests | Tema |
|---|---|---|
| `tests/unit/test_reports_ats.py` | 71 | Libros, formularios, ATS |
| `tests/unit/test_withholding.py` | 53 | Retenciones IR/IVA |
| `tests/unit/test_payroll_calc_standalone.py` | 39 | Cálculo de nómina |
| `tests/unit/test_bank_transfer.py` | 24 | Transferencias bancarias |
| `tests/unit/test_customs.py` | 16 | Aduana/SENAE |
| `tests/unit/test_nec_chart_static.py` | 16 | Plan de cuentas NEC |
| `tests/unit/test_payroll.py` | 16 | Payslips |
| `tests/unit/test_liquidacion_compra.py` | 10 | Liquidación de compra |
| `tests/unit/test_manifest_data.py` | 10 | Datos de manifiesto |
| `tests/unit/test_tax_calendar.py` | 10 | Calendario tributario |
| `tests/unit/test_sri_tax_codes.py` | 13 | Códigos tributarios SRI |
| `l10n_ec_sri/tests/*` (3 archivos) | 13 | Servicio, firma, XML |
| `l10n_ec/tests/test_company_setup.py` | 7 | Config. empresa |
| `l10n_ec_base/tests/test_identity.py` | 9 | IDs aprobados (D-04) + **equivalencia stdnum de `res.partner`** (CHG-2026-004) |
| `l10n_ec_base/tests/test_sri_ruc_parser.py` | 7 | **Payload real SRI**: llaves nuevas, fechas anidadas, guard ACTIVO (CHG-2026-003) |
| `l10n_ec_base/tests/test_chart_template.py` | 6 | Plan de cuentas EC |
| Otros unitarios (access_key, cf, invoice, pos, endpoints, validation) | 48 | Varios |
| **Total módulos Odoo** | **~386** (364 + 22 de `l10n_ec_base`, recuento 2026-10-16) | — |

## 4. Criterios de aceptación y evidencia

* **A1 — Motor legal:** 100% de las pruebas puras en verde antes de cualquier cambio
  (evidencia host: `python3 mcp_server/test_server.py` → `Ran 54 … OK (skipped=3)`;
  evidencia contenedor —con stdnum—: `Ran 54 … OK` sin skips).
* **A1b — Módulos Odoo:** `l10n_ec_base` verde en BD `odooec`
  (evidencia 2026-10-16: `odoo.tests.stats: l10n_ec_base: 30 tests` ×2 corridas, **0 FAIL**;
  22 tests post-install: identity 9 + parser SRI 7 + chart 6).
* **A2 — Constantes legales:** cada constante con resolución+fecha+URL (ISO-EC-10 §2);
  lo no confirmado se marca `NO_VERIFICADO` (nunca se inventa).
* **A3 — Instalación:** los 20 módulos `l10n_ec*` pasan a `installed` sin `CRITICAL`/`ERROR`
  en el log (`ir_module_module.state`).
* **A4 — Regresión:** tras cada cambio regulatorio se re-ejecuta la suite afectada (ver ISO-EC-04).

## 5. Huecos de prueba conocidos (deuda documentada)

| Hueco | Impacto | Plan |
|---|---|---|
| ~~**`TestStdnumEquivalence` inexistente**~~ | — | **CERRADO 2026-10-16 (CHG-2026-005):** clase creada en `test_server.py`, corpus 22,727 → 0 en contenedor; ver §3.1 |
| Pruebas E2E de firma→SRI (celcer) | Alto (producción) | Instalar módulos y correr flujo completo en contenedor |
| Pruebas de módulos Odoo en BD limpia | Medio (bajó de Alto: `l10n_ec_base` ya corre en BD real) | `--test-enable` sobre las 20 suites (depende de instalación completa) |
| Fuzzing de firma XAdES / claves | Medio | l10n_ec_security (planificado) |
| Cobertura de techo IESS 25×SBU | Bajo | Resolución pendiente (NO_VERIFICADO, ISO-EC-10 §6) |

## 6. Cómo ejecutar (evidencia reproducible)

```bash
# (a) Motor legal puro — sin Odoo (host: 51 + 3 skips sin stdnum)
python3 mcp_server/test_server.py          # espera: Ran 54 … OK (skipped=3)

# (a') Con stdnum (equivalencia completa, dentro del contenedor)
docker compose cp mcp_server odoo:/tmp/mcp_server_ec
docker compose exec -T odoo sh -c "cd /tmp && python3 mcp_server_ec/test_server.py"
                                             # espera: Ran 54 … OK (sin skips)

# (b) Módulos Odoo — dentro del contenedor (requiere BD instalada)
docker compose run --rm odoo -d odooec -u l10n_ec_base \
  --test-enable --test-tags /l10n_ec_base \
  --stop-after-init    # evidencia: odoo.tests.stats ... l10n_ec_base … 0 FAIL
```
