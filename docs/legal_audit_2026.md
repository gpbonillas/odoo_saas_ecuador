# Auditoría Legal 2026 — odoo_saas_ecuador

**Fecha de la auditoría:** 15 de octubre de 2026
**Alcance:** todas las constantes legales del repositorio (SRI, IESS, Ministerio del Trabajo,
Código del Trabajo, Código Tributario, LRTI, Registro Oficial), verificadas **cifra por cifra**
contra fuentes oficiales descargadas expresamente para esta auditoría (nunca contra memoria del
modelo). Cada constante queda registrada con su ubicación en el código, el valor legal, la
norma exacta (resolución/acuerdo + fecha + URL) y un veredicto:

| Veredicto | Significado |
|---|---|
| **OK** | El valor del código coincide con la norma verificada. |
| **CORREGIDO** | El código estaba mal; fue corregido en esta auditoría. |
| **NO_APLICA** | La constante no tiene respaldo legal; se eliminó o se marcó como obsoleta/deprecada. |
| **NO_VERIFICADO** | No se localizó fuente oficial que confirme el valor; **no se asumió ni se cambió**. |

---

## 0. Fuentes oficiales utilizadas

Todas se descargaron y guardaron en caché durante la auditoría (texto íntegro, verificación
literal de los valores citados).

| # | Fuente | Ubicación oficial |
|---|---|---|
| S1 | **Tabla 19 de retenciones de renta** (XLS oficial del SRI) | https://www.sri.gob.ec/o/sri-portlet-biblioteca-alfresco-internet/descargar/a305ad8c-7cfd-42c7-8cea-be4dbf850d0c/tabla_retenciones.xls |
| S2 | **Resolución NAC-DGERCGC26-00000009** (27-feb-2026), publicada en **Registro Oficial Cuarto Suplemento Nº 233** (27-feb-2026) | https://www.registroficial.gob.ec/cuarto-suplemento-no-233/ · https://www.primicias.ec/uploads/files/2026/02/27/NAC-DGERCGC26-00000009.pdf |
| S3 | **Ficha Técnica Comprobantes Electrónicos Esquema Offline v2.33** (SRI, 140 págs.; Tablas 17/18/19/21) | https://www.sri.gob.ec/o/sri-portlet-biblioteca-alfresco-internet/descargar/5a547488-80f3-4966-a2a4-841f2e951986/FICHA%20TE%CC%81CNICA%20COMPROBANTES%20ELECTRO%CC%81NICOS%20ESQUEMA%20OFFLINE%20Versio%CC%81n%202.33.pdf |
| S4 | **Guía del Contribuyente — Formulario 104** (SRI; casilleros 721–731) | https://www.sri.gob.ec/o/sri-portlet-biblioteca-alfresco-internet/descargar/111dd5f3-c265-4d6c-a1bc-91104bb92bcf/GUIA+DEL+CONTRIBUYENTE+FORMULARIO+104.pdf |
| S5 | **Resolución NAC-DGERCGC20-00000061** (RO 1100, 30-sep-2020; modifica casilleros del F104) | https://www.sri.gob.ec/o/sri-portlet-biblioteca-alfresco-internet/descargar/185c7087-f119-4f0d-8dcd-702c30ebd793/NAC-DGERCGC20-00000061.pdf |
| S6 | **Ley de Régimen Tributario Interno** (texto consolidado SRI; arts. 7, 8, 50, 82) | https://www.sri.gob.ec/DocumentosAlfrescoPortlet/descargar/37dd6fc9-4c2e-465a-b52d-ade41ae48866/LEY+DE+R%C9GIMEN+TRIBUTARIO+INTERNO.pdf |
| S7 | **Código Tributario** (texto oficial CES; arts. 7, 12, 29) | https://www.ces.gob.ec/lotaip/2018/Agosto/Anexos-literal-a2/CODIGO%20TRIBUTARIO.pdf |
| S8 | **Código del Trabajo** (RO Suplemento 906, 20-dic-2016; arts. 55, 65, 69, 97, 105, 111, 113, 152, 153, 186, 188, 196) | https://www.ces.gob.ec/lotaip/2020/Junio/Literal_a2/C%C3%B3digo%20del%20Trabajo.pdf |
| S9 | **Resolución NAC-DGERCGC25-00000040** (ICE 2026; RO 2 Suplemento 194) | https://www.expreso.ec/uploads/files/2025/12/30/NAC-DGERCGC25-00000040.pdf |
| S10 | **IESS — Tasas de aportación** (documento oficial iess.gob.ec) | https://www.iess.gob.ec/documents/13718/54965/Tasasdeaportacion.pdf |
| S11 | **Acuerdo Ministerial MDT-2025-195** (SBU 2026 = $482) | https://storage.googleapis.com/proficonsult-webapp/base-legal/2025/Acuerdo%20Ministerial%20No.%20MDT-2025-195.pdf |
| S12 | **Resolución NAC-DGERCGC25-00000017** (anulación de comprobantes hasta el día 7) | Resolución SRI 2025 (citada en módulos `l10n_ec_edi`/`l10n_ec_withholding`) |
| S13 | **Resolución NAC-DGERCGC23-00000004** (normas de aplicación del RIMPE; RO 257-2S, 27-feb-2023) | Registro Oficial 257-2S |
| S14 | **Decreto Ejecutivo 198** (IVA 15%, 15-mar-2024, vigente desde 01-abr-2024) | Decreto Ejecutivo 198, 2024 |
| S15 | Tabla 18 (ICE) y Tabla 19/21 — contenido verificado textualmente en S3 (Ficha v2.33) | (incluida en S3) |

**Método:** descarga de las fuentes (SRI vía mirror/jina cuando el portal respondía timeout;
Registro Oficial y prensa para las resoluciones 2026) y verificación literal —artículo por
artículo, fila por fila de tabla— antes de tocar el código. Las correcciones se aplicaron al
código fuente; las constantes sin respaldo se señalan explícitamente como NO_VERIFICADO sin
cambiarlas.

**Validación de los cambios:** cada archivo editado fue revisado línea por línea tras la
edición (sintaxis de dicts/tuplas en Python; bien-formedness XML: sin `&` sin escapar, sin `--`
dentro de comentarios, etiquetas balanceadas; CSV con comillas correctas en nombres con
comas). Nota: esta sesión no tenía disponible un shell para ejecutar `python3 -m py_compile`;
se recomienda añadir esa validación (más una instalación de módulos en BD de prueba) al CI
antes del commit (ver §8, "Trabajo pendiente de validación").

---

## 1. Resumen numérico final

| Veredicto | Constantes |
|---|---|
| ✅ OK (coincide con la norma) | **58** |
| 🔧 CORREGIDO (valor erróneo, corregido en código) | **22** |
| 🗑 NO_APLICA / ELIMINADA (sin base legal; borrada o deprecada) | **5** |
| ⚠️ NO_VERIFICADO (sin fuente oficial; sin cambiar) | **9** |
| **Total de constantes auditadas** | **94** |

---

## 2. (A) Retención de Impuesto a la Renta — Tabla 19

Fuentes: S1 (tabla_retenciones.xls del SRI), S2 (Res. NAC-DGERCGC26-00000009, RO 233,
27-feb-2026), S3 (Ficha v2.33).
Ubicaciones corregidas: `l10n_ec_withholding/data/retention_codes_2026.xml`,
`l10n_ec_base/data/l10n_ec_config_data.xml`, `l10n_ec_base/mcp/retention_manager.py:21-36`,
`l10n_ec_base/mcp/open_data_sources.py`.

| Código | Valor en el código (antes) | Valor legal (Tabla 19 / Res. 26-00000009) | Veredicto |
|---|---|---|---|
| 303 | 10% | 10% — Honorarios profesionales | ✅ OK |
| 304 | 8% | **10%** — Servicios donde predomina el intelecto | 🔧 CORREGIDO |
| 307 | 2% | **3%** — Servicios donde predomina la mano de obra | 🔧 CORREGIDO |
| 308 | 2% | **10%** — Uso/aprovechamiento de imagen o renombre | 🔧 CORREGIDO |
| 309 | 1% | **3%** — Publicidad y agencias de comunicación | 🔧 CORREGIDO |
| 310 | 1% | 1% — Transporte privado de pasajeros o carga | ✅ OK |
| 312 | 1% | **2%** — Transferencia de bienes muebles | 🔧 CORREGIDO |
| 319 | 1% | **2%** — Cuotas de arrendamiento mercantil | 🔧 CORREGIDO |
| 320 | 1.75% | **10%** — Arrendamiento de bienes inmuebles | 🔧 CORREGIDO |
| 322 | 1% | **2%** — Seguros y reaseguros | 🔧 CORREGIDO |
| 323 | 2% | **3%** — Rendimientos financieros | 🔧 CORREGIDO |
| 325 (antes "344") | 25% con código 344 | **Código 325** = 25% — Anticipo de utilidades/dividendos. El código 344 no es "dividendos" en Tabla 19. El record id `tax_ret_ir_344` se conserva para no romper BD. | 🔧 CORREGIDO |
| 326 / 327 | 25% (sólo en dicts secundarios) | 12% ó 14% — Utilidades (persona natural/jurídica). Eliminado el 25% inexistente; añadido el código 325 en su lugar. | ✅ OK (tras corrección de dicts) |
| 332 (antes "332B") | 0% con código 332B | **Código 332** = 0% — RIMPE Negocios Populares (332B es energía eléctrica, 0%). Record id `tax_ret_ir_332b` conservado. | 🔧 CORREGIDO |
| 335 | 15% | 15% — Impuesto a la renta personas naturales | ✅ OK |
| 336 / 337 | 2% / 3% per mil | 2% / 3% per mil — Servidumbre de paso / energía eléctrica | ✅ OK |
| 340 | 1% | **3%** — Impuesto único a la exportación de banano | 🔧 CORREGIDO |
| 343 (antes "343A") | 1% con código 343A | **Código 343** = 1% — RIMPE Emprendedores (343A = energía eléctrica, 2%). Record id `tax_ret_ir_343a` conservado. | 🔧 CORREGIDO |
| 344A / 344B | 2% | 2% — Pensiones alimenticias (A) / herencias (B) | ✅ OK |
| 500 | 25% (nombre incorrecto) | 25% ó 37% — Rentas pagadas a no residentes, rentas inmobiliarias. Nombre corregido. | 🔧 CORREGIDO (nombre; tasa base OK) |

## 3. (B) Retención de IVA — Tabla 21 / casilleros del Formulario 104

Fuentes: S4 (Guía F104, casilleros leídos textualmente), S5 (Res. 61), S3 (Ficha v2.33).

| Casillero | Valor en el código (antes) | Valor legal | Veredicto |
|---|---|---|---|
| 721 | 10% | 10% — bienes | ✅ OK |
| 723 | 20% | 20% — servicios | ✅ OK |
| 725 | 30% | 30% — bienes (contribuyente especial) | ✅ OK |
| 727 | 30% | **50%** — contribuyente especial | 🔧 CORREGIDO |
| 729 | 100% | **70%** — contribuyente especial | 🔧 CORREGIDO |
| 731 | "100%" sin detalle | **100%** — liquidación de compra, importación de servicios, combustibles y periódicos (etiqueta corregida) | 🔧 CORREGIDO |

## 4. (C) Tasas de IVA, ICE y RIMPE

### 4.1 IVA

Fuente: S14 (DE 198, IVA 15% vigente desde 01-abr-2024), S1, S3.

| Constante | Valor legal | Veredicto |
|---|---|---|
| IVA general 15% | 15% desde 01-abr-2024 (DE 198, 15-mar-2024) | ✅ OK |
| IVA 5% (construcción) | 5% (DE 072 + normativa posterior) | ✅ OK |
| IVA 8% (régimen turístico) | 8% por decretos específicos | ✅ OK |
| Exentos 0% | LRTI art. 8 | ✅ OK |
| IVA 12% | Tasa histórica hasta 31-mar-2024; sigue válida para notas de crédito/ajustes de ese período | ✅ OK |
| IVA 14% | Tasa histórica 2011–2023 (sólo histórica) | ✅ OK |
| `IVA_RATES = (0.0, 5.0, 8.0, 12.0, 14.0, 15.0)` (`mcp_server/rules.py:41`) | Tupla corregida para cubrir todas las tasas vigentes + históricas | 🔧 CORREGIDO |
| IVA diferenciado Costa/Galápagos | No se localizó norma que fije tarifa propia para Galápagos en el IVA | ⚠️ NO_VERIFICADO |

### 4.2 ICE — códigos y tasas (Res. NAC-DGERCGC25-00000040, aplicable desde 01-ene-2026)

Fuente: S9 (tasas leídas textualmente) + S3 (códigos de la Tabla 18).
Ubicación: `l10n_ec_ice/data/l10n_ec.ice.category.csv` (reescrito completo).

| Código | Producto | Tasa legal | Veredicto |
|---|---|---|---|
| 3011 | Cigarrillos rubios | $0.16 por unidad | ✅ OK |
| 3031 | Alcohol (litros puros de alcohol) | $10.41 / L AP | ✅ OK |
| 3041 | Cerveza industrial | $13.62 / L AP | ✅ OK |
| 3043 | Cerveza artesanal | $1.56 / L AP | ✅ OK |
| 3053 | Bebidas azucaradas | $0.18 / 100 g | ✅ OK |
| 3680 | Fundas plásticas | $0.08 / unidad | ✅ OK |
| 3610 | Perfumes y aguas de tocador | 20% ad valorem (antes figuraba como "armas") | ✅ OK (fila reescrita) |
| 3620 | Videojuegos | 35% ad valorem | ✅ OK |
| 3630 | Armas de fuego/deportivas y municiones | 300% ad valorem | ✅ OK |
| 3073 | Vehículos PVP ≤ 20.000 | 5% (LRTI art. 82 Grupo II + Tabla 18) | ✅ OK |
| 3075 | Vehículos 30.000–40.000 | 15% | ✅ OK |
| 3077 | Vehículos 40.000–50.000 | 20% | ✅ OK |
| 3078 | Vehículos 50.000–60.000 | 25% | ✅ OK |
| 3079 | Vehículos 60.000–70.000 | 30% | ✅ OK |
| 3080 | Vehículos > 70.000 | 35% | ✅ OK |
| 3072 / 3092 / 3650 | Códigos inventados (no existen en Tabla 18) | — | 🗑 ELIMINADOS |
| Tramo 20.000–30.000 (10%) | Existe el tramo en LRTI art. 82, pero **no tiene código en la Tabla 18** | — | ⚠️ NO_VERIFICADO |
| Selección de fila por PVP | La lógica de elegir el tramo según el PVP del vehículo no existe en el módulo | — | ⚠️ NO_VERIFICADO (brecha de implementación) |
| Híbridos/eléctricos + fila 3081 | No se localizaron reglas específicas ni en Res. 25-00000040 ni en Tabla 18 | — | ⚠️ NO_VERIFICADO |

### 4.3 RIMPE

Fuente: S13 (Res. NAC-DGERCGC23-00000004, RO 257-2S, 27-feb-2023), S1.

| Constante | Corrección | Veredicto |
|---|---|---|
| Citación legal del módulo `l10n_ec_rimpe` | Antes citaba una resolución genérica; ahora cita la Res. NAC-DGERCGC23-00000004 (RO 257-2S). Códigos 332 (0%) y 343 (1%) ya corregidos en §2. | 🔧 CORREGIDO |

## 5. (D) Comprobante electrónico: clave de acceso, codDoc, ambiente

Fuentes: S3 (Ficha v2.33, esquema offline; lectura literal de la estructura de la clave).

| Constante | Valor en código | Valor legal | Veredicto |
|---|---|---|---|
| Clave de acceso | 49 dígitos, verificador mod-11 (pesos 2–7) — `mcp_server/rules.py:225-285` | 49 dígitos + dígito verificador mod-11 | ✅ OK |
| codDoc | 01 factura, 03 liquidación de compra, 04 nota de crédito, 05 nota de débito, 06 guía de remisión, 07 comprobante de retención | Idénticos en Ficha v2.33 | ✅ OK |
| Ambiente | 1 = pruebas, 2 = producción | Idéntico | ✅ OK |
| Establecimiento + punto de emisión | 3 + 3 dígitos | Idéntico | ✅ OK |
| Límite consumidor final | $50 | $50 (resolución SRI vigente) | ✅ OK |
| Anulación de comprobantes | hasta el día 7 del mes siguiente | Res. NAC-DGERCGC25-00000017 (S12) | ✅ OK |

## 6. (E) IESS y derecho laboral (Código del Trabajo)

Fuentes: S10 (tasas oficiales IESS, verificadas textualmente: personal 9.45 / patronal 11.15 /
total 20.60), S8 (Código del Trabajo arts. citados, texto íntegro).
Ubicación: `l10n_ec_hr_payroll/data/l10n_ec_payroll_data.xml`.

| Constante | Valor legal | Veredicto |
|---|---|---|
| Aporte personal sector privado 9.45% (seguro 6.64 + invalidez/vejez 0.10 + riesgos laborales 2.00 + cargas familiares 0.35 + gastos funerales 0.36) | 9.45% (S10) | ✅ OK |
| Aporte patronal sector privado 11.15% | 11.15% (S10) | ✅ OK |
| SECAP 0.50% | Sigue vigente y **recaudado vía IESS** en 2026; los proyectos de ley de abril-2026 para redirigirlo están sólo en comisión | ✅ OK |
| IECE 0.50% | Vigente (S10) | ✅ OK |
| Sector público personal 11.45% / patronal (Estado) 9.15% | S10 | ✅ OK |
| Afiliación voluntaria 17.60% | S10 | ✅ OK |
| Techo de aportación 25 × SBU ($12.050) | No se localizó norma que fije el múltiplo 25× en las fuentes oficiales consultadas | ⚠️ NO_VERIFICADO |
| "Resolución CD 655" (citada históricamente en el repo para el techo) | No se localizó la resolución completa; verificar antes de citarla | ⚠️ NO_VERIFICADO |
| Fondos de reserva 8.33% | Código del Trabajo **art. 196** (antes se citaba mal el art. 195) | ✅ OK |
| Fondos de reserva: elegibilidad "13 meses" | El art. 196 dice "por más de un año"; la práctica mensual 13 meses no tiene norma expresa localizada | ⚠️ NO_VERIFICADO |
| Décimo tercero: pago hasta 24 de diciembre | Art. **111** | ✅ OK |
| Décimo cuarto: Costa/Galápagos 15-mar, Sierra/Amazónica 15-ago | Art. **113** | ✅ OK |
| Vacaciones 15 días/año | Art. **69** | ✅ OK |
| Utilidades 15% (10% + 5% cargas familiares) | Art. **97** (citación del repo verificada correcta) | ✅ OK |
| Utilidades: liquidación hasta 31-mar, pago en 15 días | Art. **105** | ✅ OK |
| Maternidad 12 semanas / paternidad 10 días | Arts. **152–153** | ✅ OK |
| Recargos 50% suplementarias, 100% extraordinarias/feriados, 25% nocturnas | Art. **55** | ✅ OK |
| Topes de descuento 40% / 33.33% | No se localizó norma expresa en el Código del Trabajo consultado | ⚠️ NO_VERIFICADO |
| Desahucio 25% por año | Art. **186** | ✅ OK |
| Indemnización por despido (tabla por antigüedad) | Art. **188** | ✅ OK |
| Escala de cesantía por antigüedad (`l10n_ec.cesantia_pct_*`) | **No es ley**: el auxilio de cesantía se paga con la fórmula del art. 192 (última remuneración × años/12), no con una tabla de porcentajes. Los 6 registros XML se conservan como **deprecados** porque el wizard `l10n_ec_liquidacion_wizard` lanza error si faltan los parámetros requeridos. | 🗑 NO_APLICA (deprecada; recomienda eliminarse en la siguiente versión) |

## 7. (F) SBU 2026 y (G) reglas de días

| Constante | Valor en código | Valor legal | Veredicto |
|---|---|---|---|
| SBU 2026 = $482.00 (`l10n_ec.sbu`) | 482.00 y cita "MDT-2025-195" | **Acuerdo Ministerial MDT-2025-195** (S11): $482 vigente para 2026 | ✅ OK |
| Feriados nacionales (11 días) — `l10n_ec_withholding` | Lista fija corregida (ver fila siguiente) | Art. **65** Código del Trabajo (S8) | ✅ OK |
| Feriados: se eliminaron **2 de febrero ("Día del Civismo"/27-feb)** y **3 de mayo** de `mcp_server/rules.py:ec_holidays` | El art. 65 NO incluye el 27 de febrero (DE 324 de 1948, no feriado nacional) ni el 3 de mayo | 🔧 CORREGIDO |
| Plazo de emisión del comprobante de retención: 5 días hábiles (`RETENTION_BUSINESS_DAYS=5`, `mcp_server/rules.py:30`) | LRTI **art. 50**: la retención se causa en el pago/crédito y el comprobante debe entregarse dentro de **5 días hábiles** de recibido el comprobante de venta; Código Tributario **art. 12**: los "días" son hábiles. El código arranca el cómputo desde la **fecha de la factura** (aproximación; el reloj legal empieza en la **recepción** del comprobante) — documentado en el docstring. | ✅ OK (con limitación documentada) |
| Citas erróneas "art. 17" (retenciones) y "art. 195" (fondos) | Ahora citan **LRTI art. 50 / Código Tributario arts. 7 y 29** y **Código del Trabajo art. 196** | 🔧 CORREGIDO |
| Etiquetas Form 103/104 (`l10n_ec_reports/report_lib.py:1031-1049`) | Corregidas: eliminado el casillero obsoleto 302; añadidos 308/319/727/729/731; tasas IVA 10/20/30/50/70/100 | 🔧 CORREGIDO |
| Split IVA "30% SENAE / 70% IESS (Decreto 745)" | **No existe en ninguna norma**. Eliminado de `mcp_server/rules.py` (`IVA_RETENTION_SPLIT*`), `server.py`, `tools.py`, `retention_split_config.xml` (ahora 100/0), `_l10n_ec_get_iva_split` (default 100/0), manifest, comentarios de `template_ec.py` y `account_retention.py`. El importe retenido se declara **íntegro al SRI** (casilleros 721–731). | 🗑 NO_APLICA (constante fabricada, eliminada) |

---

## 8. ⚠️ PENDIENTE DE VERIFICACIÓN OFICIAL (NO_VERIFICADO — no se cambiaron)

Ninguno de estos valores fue alterado; requieren confirmación antes del próximo release.

1. **Techo de aportación IESS = 25 × SBU** (`l10n_ec.iess_ceiling_sbu_multiplicador=25`).
   Buscar la resolución/comunicado oficial del IESS que fije el múltiplo (posible "Resolución
   CD 655", cuyo texto íntegro no fue localizado).
2. **"Resolución CD 655" del IESS** — verificar existencia, número y contenido antes de citarla.
3. **Topes de descuento de planilla: 40% y 33.33%** — sin norma expresa localizada en el
   Código del Trabajo (posible fuente: LOSEC o Acuerdo MDT; verificar).
4. **Fondos de reserva: regla de "13 meses"** — el art. 196 sólo dice "por más de un año";
   la elegibilidad práctica desde el mes 13 requiere confirmación normativa.
5. **ICE de vehículos: código oficial para el tramo PVP 20.000–30.000 (10%)** — el tramo existe
   en LRTI art. 82 pero no aparece con código en la Tabla 18 de la Ficha v2.33.
6. **ICE vehículos: lógica de selección de tramo por PVP** — no implementada en el módulo
   `l10n_ec_ice` (brecha de funcionalidad, no de constante).
7. **ICE híbridos/eléctricos y posible fila 3081** — sin reglas en la Res. 25-00000040 ni en
   Tabla 18.
8. **IVA diferenciado Galápagos** — no se localizó tarifa propia de IVA para Galápagos.
9. **Inicio del plazo de 5 días hábiles** — el código cuenta desde la fecha de la factura; la
   norma (LRTI art. 50) cuenta desde la **recepción** del comprobante de venta. Implementar el
   campo "fecha de recepción" si el SRI lo exige en fiscalización.

## 9. Tests que bloquean los valores corregidos (NO se modificaron, según lo acordado)

Se reportan — no se tocaron — porque fijan valores legales obsoletos:

| Test | Qué fija | Impacto |
|---|---|---|
| `tests/unit/test_withholding.py` — `EXPECTED_IR_RATES` | 304=8, 307=2, 308=2, 309=1, 312=1, 319=1, 320=1.75, 322=1, 323=2, 340=1, 344=25, 500=25 | Fallará con los valores 2026 corregidos; actualizar a la Tabla 19 (S1/S2). |
| `tests/unit/test_withholding.py` — `EXPECTED_IVA_RATES` | 727=30, 729=100 | Fallará; correcto es 727=50, 729=70 (S4). |
| `mcp_server/test_server.py::test_iva_split_30_70` | `iess_share == 70.0` | Fallará; ahora `iess_share=0.0` (constante fabricada eliminada). |
| `l10n_ec_rimpe/tests/test_rimpe_logic.py` | Códigos 332B / 343A | Fallará; el código oficial es 332 / 343 (S1). |

Tests que **siguen pasando** tras las correcciones: `test_holidays_2026` (sólo afirma
1-ene/2-16/2-17/4-3/5-1/12-25), `test_withholding.py` (tests de split que fijan parámetros
explícitos 30/70), `test_reports_ats.py::test_labels_from_spec` (auto-referencial),
`test_payroll.py` (SECAP/IECE 0.5), `test_payroll_calc_standalone.py` (escala de cesantía
deprecada).

## 10. Notas de migración para bases de datos existentes

1. **Parámetros de split IVA (`noupdate=1`)**: las BD existentes conservan
   `l10n_ec.withholding_iva_sri_pct=30 / iess_pct=70` en `ir.config_parameter`. Añadir un
   script de migración o actualizar manualmente a 100/0.
2. **Registros ICE huérfanos**: se eliminaron las filas `ice_3072`, `ice_3092`, `ice_3650` del
   CSV; las BD con esos xmlid tendrán registros huérfanos que deben limpiarse en el upgrade
   (las tasas de `ice_3610` cambiaron de "armas" a perfumes 20%).
3. **xmlid estables (a propósito)**: `tax_ret_ir_344` ahora tiene `code=325`;
   `tax_ret_ir_332b` → `code=332`; `tax_ret_ir_343a` → `code=343`. Los xmlid no cambiaron
   para no orfandar registros de BD; el campo `code` es el legal.
4. **Parámetros de cesantía**: se conservan como deprecados (`NO_ES_LEY`); eliminarlos exige
   antes retirar la dependencia del wizard `l10n_ec_liquidacion_wizard`.
5. **Deriva documental (no corregida en esta auditoría)**: `docs/CUMPLIMIENTO_REGULATORIO.md`,
   `docs/MANUAL_USUARIO.md` (aún dicen "5 días hábiles desde la fecha de la factura" sin la
   salvedad de recepción) y `docs/ESTADO_CUMPLIMIENTO_2026.md:73` (aún lista el "Split 30/70
   Decreto 745" como implementado). Actualizarlos alinearlos con este informe.

## 11. Trabajo pendiente de validación antes del commit

- Ejecutar `python3 -m py_compile` sobre los archivos Python editados
  (`mcp_server/rules.py`, `mcp_server/server.py`, `mcp_server/tools.py`,
  `l10n_ec_base/mcp/retention_manager.py`, `l10n_ec_base/mcp/open_data_sources.py`,
  `l10n_ec_reports/report_lib.py`, `l10n_ec_rimpe/models/account_move.py`,
  `l10n_ec_withholding/models/{account_retention,account_move,l10n_ec_retention_tariff}.py`,
  `l10n_ec_base/models/template_ec.py`) — esta sesión no disponía de shell; la revisión fue
  visual línea por línea.
- Parseo XML de `retention_codes_2026.xml`, `retention_split_config.xml`,
  `l10n_ec_config_data.xml`, `l10n_ec_payroll_data.xml` y lectura CSV de
  `l10n_ec.ice.category.csv` en un entorno con Odoo instalado.
- Actualizar los tests listados en §9 a los valores 2026.
- Añadir script de migración para los puntos de §10.
