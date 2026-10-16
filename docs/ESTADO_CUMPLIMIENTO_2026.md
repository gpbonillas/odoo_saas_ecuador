# Estado de Cumplimiento — Ecuador 2026
> Documento vivo · Generado 15-oct-2026 · Refrescar tras cada sprint y tras la auditoría legal
> **Meta: 100% de cumplimiento legal ecuatoriano (SRI, IESS, Min. Trabajo, Superintendencia/BCE, SENAE)**

---

## 0. RESUMEN EJECUTIVO

| Dimensión | Estado | Nota |
|---|---|---|
| Clúster Docker (prod local, tope 8G) | 🟢 Operativo | db+odoo healthy, backups ON, MCP vía proceso local |
| Instalación de 20 módulos | 🟡 En curso | ~1 de 20 instalado; sigue corriendo sin demo |
| Facturación electrónica SRI | 🟡 Base sólida, sin runtime | Plantillas XSD-válidas; falta prueba end-to-end |
| Retenciones IR/IVA + split 30/70 | 🟡 Código completo, sin runtime | 43 tests escritos |
| Planilla/nómina IESS | 🟡 Código completo, sin runtime | 39 tests standalone OK; cesantía sin fuente |
| Libros/ATS/formularios | 🟡 Payloads OK, render pendiente | Agent D espera e2e |
| **Auditoría legal vs ley oct-2026** | 🔵 En curso | Agente corriendo; refinará esta matriz |
| Verificación end-to-end en Odoo | 🔴 Bloqueada | por el install |

**Veredicto honesto:** el *esqueleto* de cumplimiento está construido y es técnicamente sólido (plantillas XSD válidas contra esquemas oficiales SRI, tablas de retención, motor de cálculo de nómina aislado). Lo que **falta para el 100%** es (1) ejecutar y pasar los tests en Odoo real, (2) cerrar la auditoría legal con fuentes oficiales, (3) los módulos aún pendientes (NEC, libro de bancos, ECUAPASS real, Ley 0/14). Nada está "inventado", pero nada está aún **probado en runtime**.

---

## 1. INFRAESTRUCTURA (clúster local de producción)

| Componente | Límite | Estado | Pendiente |
|---|---|---|---|
| Postgres 16 (`db`) | 3 GB | 🟢 healthy | shared_buffers 1G, max_conn 60, WAL durable, audit log |
| Odoo 18 desde fuente (`odoo`) | 4 GB | 🟢 healthy (HTTP 200) | 4 workers, proxy mode, dbfilter tenant |
| Backup (`backup`) | 128 MB | 🟢 | pg_dump 6h, retención 14d |
| MCP gateway | — | 🟢 proceso local (OpenCode) | ~~servicio Docker~~ eliminado (bucle stdio) |

**Completado:** Dockerfile from-source, volúmenes live, healthchecks, log-rotation, fix `zope.interface`/`pkg_resources`, fix `odoo.conf` `:ro`, limpieza de huérfanos.

**Pendiente infra:**
- [ ] Confirmar install termina y los 20 módulos en estado `installed`
- [ ] Backup restore probado (hoy solo dump; falta test de restauración)
- [ ] TLS/reverse-proxy (hoy HTTP plano en 8069) — requerido para SRI producción
- [ ] Multi-tenant real (1 DB por jurídico) — hoy 1 DB `odooec`

---

## 2. CUMPLIMIENTO SRI (Facturación Electrónica)

| Documento | codDoc | Versión | Estado | Pendiente para 100% |
|---|---|---|---|---|
| Factura | 01 | 1.1.0 | 🟢 XSD-válido | Prueba end-to-end con firma real |
| Liquidación de Compra | 03 | 1.1.0 | 🟢 XSD-válido | Guard: línea ICE inválida en LC (SRI restringe a IVA) |
| Nota de Crédito | 04 | 1.1.0 | 🟢 XSD-válido | Prueba end-to-end |
| Nota de Débito | 05 | 1.0.0 | 🟢 XSD-válido | Prueba end-to-end (único esquema oficial es 1.0.0) |
| Guía de Remisión | 06 | — | 🟡 Parcial | Validación completa + transporte |
| Comprobante de Retención | 07 | 2.0.0 | 🟡 Parcial | **Duplicado** con `l10n_ec_sri` (v1.0.0 obsoleto) |
| Clave de acceso 49 díg. | — | — | 🟢 | End-to-end |
| Firma XAdES + recepción/autorización | — | — | 🟡 | Duda bytes/b64 en certificado (punto 5 Agent A) |
| Endpoints por ambiente | test/prod | — | 🟢 Celcer correcto | — |

**Bloqueos SRI (Agent A):**
1. 3 data files muertos en `l10n_ec_sri` (chart/tax CSV) — borrar/migrar
2. codDoc 07 duplicado (v1.0.0 en `l10n_ec_sri` vs v2.0.0 en `l10n_ec_withholding`) — consolidar
3. `action_send_sri` definido en 2 módulos sin `super()` — consolidar
4. Vats inválidos en tests compartidos (RUCs inventados — regla D-04: sólo `1713488185`/`1793125212001`) — cruzar con Agent C
5. Posible doble-codificación b64 del certificado — verificar en runtime
6. Línea ICE en liquidación de compra pasaría inválida al SRI — añadir guard

---

## 3. CUMPLIMIENTO SRI (Retenciones e Impuestos)

| Ítem | Tabla/Código | Estado | Pendiente |
|---|---|---|---|
| Retención IR (Tabla 19) | 303…500 | 🟢 Reescrita + test-lock | ✅ **Confirmado vs ley oct-2026** (Res. NAC-DGERCGC26-00000009; ver ISO-EC-10 FR-LE-20) |
| Retención IVA (Tabla 21) | 721–731 | 🟢 Escala doble implementada | ✅ **Confirmado vs Res. NAC-DGERCGC20-00000061** (ISO-EC-10 FR-LE-10; `iva_retention_bucket`) |
| Split 30% SRI / 70% IESS (Decreto 745) | — | 🔴 Sin respaldo en IVA | Auditoría 2026: la retención de IVA va **100% al SRI**; no existe split IESS/SECE del IVA. Verificar alcance de Decreto 745 (si aplica a otra retención) |
| Transmisión mismo día (Res. 25-00000017) | — | 🟢 Implementado | `transmission_deadline`/`annulment_ok` (ISO-EC-10 FR-LE-30) |
| Regla 5 días (entrega retención) | — | 🟢 Resuelta | **5 días hábiles desde RECEICIÓN** del comprobante (LRTI art. 50); verificado |
| Detección auto por 4to díg. RUC | — | 🟢 Modelo nuevo | — |
| ICE / RIMPE / régimen | — | 🟡 | Versionado anomalía (`1.0` vs `18.0.1.0.0`) |
| IVA 12/14/15% + Costa/Galápagos | — | 🟡 | Confirmar tasas vigentes |
| Clasificación actividad 4to díg. | — | 🟢 | — |

**Bloqueo crítico (Agent B):** `l10n_ec_base/models/template_ec.py` (Agent C) tiene **tasas IR equivocadas** — 312→1.75 (debe 1.0), 320→2.75 (debe 1.75), **344→1 (debe 25)**, y faltan 309/319/322/323/340/500. Los `account.tax` generados contradicen las tablas ya corregidas. **Debe corregirse antes de cualquier prueba.**

---

## 4. CUMPLIMIENTO IESS / NÓMINA

| Ítem | Valor legal | Estado | Pendiente |
|---|---|---|---|
| SBU 2026 | $482 (Acuerdo MDT-2025-195) | 🟡 | **Verificar** (fuentes internas discrepaban 195 vs 227) |
| Aporte personal | 9.45% | 🟢 | Verificar vigencia |
| Aporte patronal + SECAP + IECE | 11.15% + 0.5% + 0.5% | 🟢 | Verificar |
| Techo contribución | 25×SBU ($12,050) | 🟢 | Verificar |
| Horas extra recargos | +50/+100/+25%, topes 4h/día 12h/sem | 🟢 | Validación dura implementada |
| Tope deducciones | 40% / 33.33% | 🟢 | — |
| Fondos reserva | 8.33% desde mes 13 | 🟢 | — |
| Décimo 13 / 14 | 24-dic / Costa 15-mar Sierra 15-ago | 🟢 | Región computada |
| Vacaciones | 15 días/año | 🟢 | — |
| Utilidades | 15% (10% días + 5% días×cargas) | 🟡 | Verificar reparto |
| **Auxilio cesantía** | tramos 25→120% | 🔴 **SIN FUENTE** | Schedule no está en KB ni CT — validar contra art. 196+ antes de go-live |
| Planilla IESS | — | 🟡 | Modelo `l10n_ec.iess.planilla` pendiente (Agent E follow-up) |
| Asiento contable nómina | — | 🟡 | Resolución de cuentas por código/nombre — confirmar en CoA real |

**Bloqueo nómina:** la tabla de cesantía vino del brief, **no de ley verificable**. Marcada como `NO_VERIFICADO`; debe confirmarse con el Código del Trabajo art. 196+ o resolución MDT.

---

## 5. LIBROS, FORMULARIOS Y ANEXOS

| Ítem | Estado | Pendiente |
|---|---|---|
| Libro de ventas | 🟡 | e2e render |
| Libro de compras | 🟡 | e2e render |
| Libro de retenciones | 🟡 | e2e render |
| Formulario 101 (Renta) | 🟡 | e2e |
| Formulario 104 (IVA) | 🟡 | e2e |
| ATS (Anexo Transaccional) | 🟡 payloads OK | e2e + validar contra XSD SRI |
| Estados financieros | 🟡 | Agent D |
| Liquidación de compra (reporte) | 🟡 | — |

*Agent D validó estáticamente: 95 refs XML resuelven, menús/ACL correctos, payloads ATS completos. Falta render e2e en puerto 8169.*

---

## 6. PENDIENTES SIN CÓDIGO (brechas para el 100%)

Estos **no tienen implementación** según la matriz de riesgos y son necesarios para el 100% de cumplimiento:

| # | Área | Ítem | Esfuerzo | Prioridad |
|---|---|---|---|---|
| 1 | Superintendencia | **NEC** — Norma de Estándares Contables / estados financieros | Alto | Alta |
| 2 | BCE | **Libro de bancos** + validación | Medio | Alta |
| 3 | BCE | Umbrales antilavado / reportes | Medio | Media |
| 4 | SENAE | **ECUAPASS real** (hoy stub) + guía remisión completa | Alto | Media |
| 5 | Ley 0 | Compras sector público | Medio | Media |
| 6 | Ley 14 | Microempresa / RIMPE simplificado | Bajo | Media |
| 7 | Datos | Ley Orgánica Protección de Datos | Medio | Media |
| 8 | SRI | **Liquidación de compra electrónica** real al SRI | Medio | Alta |
| 9 | MDT | **SUT** — filing electrónico (hoy solo CSV) | Alto | Baja |

---

## 7. BLOCKERS CRÍTICOS (orden de resolución)

1. 🔴 **`template_ec.py` tasas IR incorrectas** (Agent C) — desbloquea pruebas de impuestos
2. 🔴 **Install debe terminar** — todo lo demás (tests runtime) está detrás
3. 🔴 **Auditoría legal** (agente corriendo) — refresca toda la sección 2-4 con fuentes
4. 🟡 **Consolidar codDoc 07 + `action_send_sri`** (A vs B)
5. 🟡 **Auxilio cesantía sin fuente** (Agent E)
6. 🟡 **Modelo duplicado retención** `l10n_ec.retention` (l10n_ec_sri) vs `account.retention` (withholding)
7. 🟡 **Vats inválidos en tests** compartidos
8. 🟡 **RIDE report** + **planilla modelo** + **establishment fields** (follow-ups Agent G)

---

## 8. PLAN PARA EL 100%

**Fase A — Desbloquear runtime (inmediato)**
1. Terminar install de 20 módulos; corregir errores que salgan
2. Corregir `template_ec.py` tasas IR
3. Ejecutar suites: `--test-tags /l10n_ec_edi,/l10n_ec_withholding,/l10n_ec_hr_payroll,...`
4. Consolidar codDoc 07 y `action_send_sri`

**Fase B — Verificación legal (en curso)**
5. Agente legal refresca constantes vs fuentes oficiales oct-2026
6. Aplicar correcciones + eliminar leyes no aplicables
7. Resolver cesantía y SBU con fuente oficial

**Fase C — Cierre funcional**
8. End-to-end real: factura firmada → autorizada SRI (ambiente test Celcer)
9. RIDE, planilla IESS, establishment/emission-point fields
10. Libros + 101/104 + ATS render + validación XSD

**Fase D — Brechas restantes**
11. NEC, libro de bancos, ECUAPASS, Ley 0/14, datos personales

---

*Esta matriz se refresca con la auditoría legal (agente en curso). Ver `docs/legal_audit_2026.md` cuando esté disponible.*
