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

> **Nota CHG-2026-006:** los tests de `l10n_ec_sri/tests/*` heredan `unittest.TestCase`
> (no los recoge el cargador de Odoo — se ejecutan directos, §6 e):
> `test_xml_generator` 4 OK · `test_sri_service` OK (transporte mockeado) ·
> `test_sri_signer` requiere fixture ausente (§5). `l10n_ec_reports/tests/__init__.py`
> no importa nada a propósito: su suite es la standalone `tests/unit/test_reports_ats.py`.

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
* **A1c — Pureza de datos (CHG-2026-006):** scan repo-wide de IDs fiscales = **0 falsos**
  (sólo IDs aprobados D-04 + literales justificados no-identidad: sentinela de
  autorización `9999999999`, placeholders de cuenta `0000000000`, bytes de memoria,
  EAN-13, teléfonos); comando en §6 (c).
* **A1d — Regresión de unidades (`tests/unit` vs baseline congelado):** tras la purge
  (2026-10-16) → `run=275 fail=6 err=22 skip=15` (baseline 8/24) — **0 fallos nuevos,
  4 preexistentes corregidos** (`test_sri_validation.test_01/test_04`,
  `test_tax_calendar.test_extract_9th_digit_*`).
* **A1e — Barrido completo (CHG-2026-007):** `-u l10n_ec_base,l10n_ec,l10n_ec_sri,
  l10n_ec_reports,l10n_ec_bank_transfer --test-enable --test-tags …` →
  **`odoo.tests.result: 0 failed, 0 error(s)`** (§6 d).
* **A2 — Constantes legales:** cada constante con resolución+fecha+URL (ISO-EC-10 §2);
  lo no confirmado se marca `NO_VERIFICADO` (nunca se inventa).
* **A3 — Instalación:** **20 de 21** módulos `l10n_ec*` en `installed`
  (falta `l10n_ec_website_sale`) sin `CRITICAL`/`ERROR` en el log
  (`ir_module_module.state`, verificado 2026-10-16).
* **A4 — Regresión:** tras cada cambio regulatorio se re-ejecuta la suite afectada (ver ISO-EC-04).

## 5. Huecos de prueba conocidos (deuda documentada)

| Hueco | Impacto | Plan |
|---|---|---|
| ~~**`TestStdnumEquivalence` inexistente**~~ | — | **CERRADO 2026-10-16 (CHG-2026-005):** clase creada en `test_server.py`, corpus 22,727 → 0 en contenedor; ver §3.1 |
| Fixture `l10n_ec_sri/tests/certificates/test_certificate.p12` ausente del repo (nunca trackeado) | Medio (`TestXAdESSigner` no ejecuta — preexistente, no regression de CHG-006) | Fixture auto-firmado de desarrollo trackeable ó migrar el test a `odoo.tests.common` con cert generado en `setUpClass` |
| Pruebas E2E de firma→SRI (celcer) | Alto (producción) | Instalar módulos y correr flujo completo en contenedor |
| Pruebas de módulos Odoo en BD limpia | **Bajo** (2026-10-16: barrido de 5 módulos en `odooec` = **0 failed / 0 errors**; sólo falta BD recién creada de cero) | `-i` en BD nueva con `--test-enable` |
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

# (b') Barrido de 5 módulos (CHG-2026-006/007). OJO: --test-enable fuerza el spawn
#      del daemon HTTP (server.py start()), así que --no-http no basta: mover el puerto.
docker compose exec -T odoo /opt/odoo/odoo-bin -d odooec --db_host=db --db_port=5432 \
  --db_user=odoo --db_password="$POSTGRES_PASSWORD" \
  --addons-path=/mnt/extra-addons,/opt/odoo/addons,/opt/odoo/odoo/addons \
  -u l10n_ec_base,l10n_ec,l10n_ec_sri,l10n_ec_reports,l10n_ec_bank_transfer \
  --test-enable --test-tags /l10n_ec_base,/l10n_ec,/l10n_ec_sri,/l10n_ec_reports,/l10n_ec_bank_transfer \
  --stop-after-init --no-http --http-port=8199 --max-cron-threads=0
  # evidencia: odoo.tests.result: 0 failed, 0 error(s)

# (c) Pureza de IDs fiscales (CHG-2026-006) — espera: RESIDUAL = 0
python3 - <<'PY'
import re, pathlib
A = {"1713488185","1713488185001","1793125212001","9999999999999","1716341274"}
L = {"0123456789","1234567890","123456789","9876543210","0000000000000","1234567890123","1111111111111"}
J = {"0000000000","9999999999","4294967296","3221225472","7890123456789","0991234567","0987654321"}
pat = re.compile(r"(?<!\d)(\d{13}|\d{10})(?!\d)"); n = 0
for f in pathlib.Path(".").rglob("*"):
    if f.suffix not in {".xml",".py",".csv",".md"} or not f.is_file() or "__pycache__" in str(f): continue
    for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for m in pat.finditer(l):
            if m.group(1) not in A | L | J:
                n += 1; print(f"{f}:{i}: {m.group(1)}")
print("RESIDUAL =", n)
PY

# (d) Unidades Odoo (tests/unit) — runner en shell (TransactionCase necesita registro)
#     baseline congelado: run=275 fail=8 err=24 skip=15
#     2026-10-16 post-purge: run=275 fail=6 err=22 skip=15 (0 nuevos, 4 corregidos)

# (e) Suites de l10n_ec_sri (unittest.TestCase puro, fuera del cargador de Odoo)
python3 l10n_ec_sri/tests/test_xml_generator.py   # Ran 4 … OK
python3 l10n_ec_sri/tests/test_sri_service.py     # OK (transporte mockeado)
```
