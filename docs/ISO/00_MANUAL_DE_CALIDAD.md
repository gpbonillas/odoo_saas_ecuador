# 00 — MANUAL DE CALIDAD (ISO 9001:2015)

**Sistema de Gestión de Calidad — Plataforma SaaS Odoo 18 Ecuador**

| Campo | Valor |
|---|---|
| Código documento | ISO-EC-QM-00 |
| Versión | 1.0 |
| Fecha de emisión | 2026-10-15 |
| Propietario | Oficial de Cumplimiento (Compliance Officer) |
| Aprobador | Gerencia General / CIO |
| Próxima revisión | 2027-04-15 (semestral) |
| Estado | Aprobado |
| Registros asociados | `docs/ISO/08_INDICADORES_Y_METAS.md`, `docs/ISO/06b_MATRIZ_DE_RIESGOS.md` |

---

## 1. Objeto (Purpose)

Establecer el Sistema de Gestión de Calidad (SGC) de la plataforma de localización ecuatoriana para Odoo 18 (`odoo_saas_ecuador`), diseñada para operar **millones de transacciones a nivel empresarial**, con cumplimiento verificable frente a SRI, IESS, Ministerio de Trabajo, Superintendencia de Compañías, SENAE y Banco Central del Ecuador.

Este manual es el **documento raíz** de la jerarquía documental de `docs/ISO/` (ver §12 y `README.md`).

## 2. Alcance (Scope)

| Dimensión | Incluido | Excluido |
|---|---|---|
| Código | 20 módulos `l10n_ec*` + `tests/` del repositorio | Núcleo Odoo upstream (`github.com/odoo/odoo` @ `ODOO_REF=18.0`, ver `Dockerfile`) |
| Infraestructura | Clúster Docker Compose `odoo-ec`: servicios `db`, `odoo`, `mcp`, `backup` (`docker-compose.yml`) | Red WAN, proveedor de conectividad, SaaS de terceros |
| Datos | Volúmenes `dbdata`, `odoo-filestore`, `dbbackups`, `odoo-logs`, `dblogs`, `odoo-sessions` | Datos de clientes alojados fuera del clúster |
| Procesos | Desarrollo, pruebas, despliegue, operación, soporte, cumplimiento regulatorio | Fabricación de hardware; emisión de certificados digitales (proveedor externo) |
| Multi-tenant | Bases por inquilino (`ODOO_DBFILTER=odooec.*`, `ODOO_LIST_DB=true`) | — |

**Justificación de exclusión:** los elementos excluidos se gestionan como riesgos de terceros en `docs/ISO/01_POLITICA_DE_SEGURIDAD.md` §6 y `docs/ISO/07_GOBERNANZA_TIC.md` §5.

## 3. Referencias normativas (Normative references)

| Ref. | Documento | Uso en este SGC |
|---|---|---|
| [1] | ISO 9001:2015 — Sistemas de gestión de la calidad | Estructura de este manual (cláusulas 4–10) |
| [2] | ISO 31000:2018 — Gestión de riesgos | `docs/ISO/06b_MATRIZ_DE_RIESGOS.md` |
| [3] | ISO/IEC 27001:2022 + Annex A | `docs/ISO/01_POLITICA_DE_SEGURIDAD.md` |
| [4] | ISO 22301 — Continuidad de negocio | `docs/ISO/02_CONTINUIDAD_Y_RECUPERACION.md` |
| [5] | ISO/IEC 20000-1 e ISO/IEC 25010 | `docs/ISO/03_GESTION_DE_CAPACIDAD.md` |
| [6] | ISO/IEC 38500 — Gobernanza TIC | `docs/ISO/07_GOBERNANZA_TIC.md` |
| [7] | ITIL 4 — Gestión de cambios | `docs/ISO/04_CONTROL_DE_CAMBIOS.md` |
| [8] | Ficha Técnica Comprobantes Electrónicos SRI v2.32; Res. NAC-DGERCGC25-00000017 | Obligaciones en `docs/ISO/06_MATRIZ_DE_CUMPLIMIENTO.md` |
| [9] | `docs/CUMPLIMIENTO_REGULATORIO.md` y `l10n_ec_sri/docs/11_regulatory_knowledge_base/` | Base de conocimiento regulatorio |
| [10] | `CONTRIBUIR.md` | Flujo de ramas y revisión de código |

## 4. Contexto de la organización (Context of the organization)

### 4.1 Partes interesadas y requisitos

| Parte interesada | Requisito regulatorio/contractual | Control que lo respalda |
|---|---|---|
| SRI | Facturación electrónica, retenciones, ATS, formularios | CM-01…CM-14 (`06`) |
| IESS | Aportes 9.45%/11.15%, planillas, fondos de reserva | CM-15…CM-17 (`06`) |
| Ministerio de Trabajo | SBU, décimos, vacaciones, horas extras | CM-18…CM-25 (`06`) |
| Superintendencia de Compañías | Plan de cuentas NEC, estados financieros, libros | CM-26…CM-28 (`06`) |
| SENAE / BCE | Aranceles, libro de bancos, reportes | CM-29…CM-31 (`06`) |
| Autoridad de protección de datos | Ley Orgánica de Protección de Datos Personales (Ley 0/14) | CM-32 (`06`), GOV-10 (`07`) |
| Clientes SaaS | Disponibilidad, RPO/RTO, trazabilidad | BC-01…BC-12 (`02`), KPI-08…KPI-11 (`08`) |

### 4.2 Enfoque por procesos

Los procesos del SGC se describen en §8. Los riesgos asociados están registrados en `06b_MATRIZ_DE_RIESGOS.md` (R-001…R-020); los objetivos medibles en `08_INDICADORES_Y_METAS.md` (KPI-01…KPI-18).

## 5. Liderazgo (Leadership)

### 5.1 Política de calidad

> La plataforma se entrega y opera con **cumplimiento regulatorio ecuatoriano verificable**, evidencia auditable, cambios controlados y mejora continua medida por indicadores. Ninguna afirmación de cumplimiento se publica sin evidencia en código, pruebas o registros.

### 5.2 Responsabilidad y autoridad — RACI

R = Responsable · A = Aprueba · C = Consultado · I = Informado

| Actividad | GG/CIO | Oficial Cumplim. | Arquitecto | DBA | Líder Dev | QA | Operaciones | Custodio .p12 | CAB | Auditor |
|---|---|---|---|---|---|---|---|---|---|---|
| Aprobar este manual y su revisión | **A** | R | C | C | C | C | C | I | C | I |
| Política de seguridad (01) | A | R | C | C | I | I | C | C | I | I |
| Plan de continuidad (02) | A | C | C | **R** | I | I | R | I | I | I |
| Cambios de configuración (`odoo.conf`, `.env`) | I | I | A | R | C | I | C | I | **A** | I |
| Cambios de código (PR a `main`) | I | C | C | I | **A** | R | C | I | C | I |
| Cambios regulatorios SRI (hotfix) | I | **A** | C | I | R | R | I | C | A | I |
| Rotación/revisión de accesos (trimestral) | I | **A** | I | R | I | I | R | C | I | C |
| Operación de respaldos y restauraciones | I | C | I | **R** | I | I | R | I | I | I |
| Custodia y uso de certificado `.p12` | I | C | I | I | I | I | C | **R/A** | I | C |
| Aprobación de publicación/annulment vía agente MCP | I | C | C | I | C | I | **R** | I | I | **A** |
| CAPA y cierre de no conformidades | I | **A** | C | C | R | R | R | I | I | C |
| Auditoría interna y revisión por dirección | **A** | R | C | C | C | C | C | I | I | R |

*Segregación de duties ampliada en `07_GOBERNANZA_TIC.md` §4.*

## 6. Planificación (Planning)

| Elemento | Documento | Cadencia |
|---|---|---|
| Riesgos del SGC (≥20 registrados) | `06b_MATRIZ_DE_RIESGOS.md` | Trimestral + bajo detonante |
| Objetivos y metas (KPI) | `08_INDICADORES_Y_METAS.md` | Trimestral |
| Evaluación de seguridad (likelihood × impacto) | `01_POLITICA_DE_SEGURIDAD.md` §4 | Anual + bajo detonante |
| Plan de pruebas de restauración | `02_CONTINUIDAD_Y_RECUPERACION.md` §7 | Anual (ensayo completo) |

## 7. Soporte (Support) — 7.5 Control de la información documentada

### 7.1 Reglas de gestión documental

| Regla ID | Regla | Verificación |
|---|---|---|
| **Q-01** | Todo documento `docs/ISO/*` lleva: código, versión (formato `MAJOR.MINOR`), fecha, propietario, aprobador y fecha de próxima revisión | Revisión trimestral del índice (`README.md` §2) |
| **Q-02** | Un solo documento raíz (`00_MANUAL_DE_CALIDAD.md`); los demás son políticas/procedimientos que no lo contradicen | Auditoría interna |
| **Q-03** | Toda afirmación de cumplimiento cita un artefacto real (ruta de archivo, servicio, valor de configuración) o se marca `[VERIFY]` con dónde verificar | Oficial de Cumplimiento |
| **Q-04** | Ningún documento afirma "100% de cumplimiento" sin evidencia en código + prueba automatizada | Oficial de Cumplimiento + QA |
| **Q-05** | Los documentos fuera de `docs/ISO/` se modifican solo vía flujo de cambios (`04_CONTROL_DE_CAMBIOS.md` §4: rama `feature/*` → PR → `main`) | Líder de Desarrollo |
| **Q-06** | Los documentos vencidos en fecha de revisión se marcan `OBSOLETO` y no pueden usarse como evidencia | Oficial de Cumplimiento |
| **Q-07** | Los registros (evidencias) se conservan ≥ 7 años según obligación tributaria — ver `05_TRAZABILIDAD_Y_AUDITORIA.md` §8 `[VERIFY: artículo exacto del Código Tributario]` | Auditor |

**Evidencias/artefactos:** índice `README.md` con tabla de control documental; historial de revisiones (§12); registros CAPA (§10); actas de revisión por dirección (§9.3).

## 8. Operación (Operation) — Mapa de procesos

| # | Proceso | Entrada | Transformación clave | Salida | R | C | A | I | Control | Evidencia |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 | **Gestión documental** | Requisitos, cambios regulatorios | Redacción, revisión por pares, aprobación, publicación en `docs/ISO/` | Documentos vigentes v1.0 | Oficial Cumpl. | Arquitecto, QA | GG/CIO | Todos | Q-01…Q-07 | Tabla de control documental (`README.md`) |
| P2 | **Control de cambios** | Solicitud (issue/CR), Res. SRI | Clasificación estándar/normal/emergencia, CAB, PR a `main`, versionado `18.0.x.y.z` | Release con notas | Líder Dev | DBA, QA, OC | CAB | Ops | CHG-01…CHG-12 (`04`) | PR mergeados, actas CAB, git tags |
| P3 | **CAPA** | No conformidad, hallazgo de auditoría, KPI fuera de meta | Contención → Causa raíz → Acción correctiva → Verificación de eficacia | Cierre con eficacia demostrada | Oficial Cumpl. | Dev, QA, DBA | GG/CIO | CAB | Q-08 (§10) | Registro CAPA `CAPA-YYYY-NNN` |
| P4 | **Indicadores y metas** | Datos de operación (logs, pg_stat, SRI) | Cálculo de KPI, análisis de desviación, alerta | Informe trimestral | Oficial Cumpl. | Ops, DBA | GG/CIO | CAB | KPI-01…KPI-18 (`08`) | Informes trimestrales |
| P5 | **Desarrollo y pruebas** | Requisito regulatorio/spec | Código + prueba (`tests/unit`, `tests/regulatory`, `tests/` por módulo) con `--test-enable` | Módulo verificado | Líder Dev | QA | Arquitecto | OC | CHG-06, CHG-07 (`04`) | Suites verdes, reportes de prueba |
| P6 | **Operación del clúster** | `docker-compose.yml`, `config/*` | Despliegue, healthchecks, respaldo cada 6 h, monitoreo | Servicio disponible | Ops | DBA | Arquitecto | OC | CAP-01…CAP-12 (`03`), BC-01…BC-12 (`02`) | Logs `json-file` 50 MB×10, volúmenes `dbbackups` |
| P7 | **Cumplimiento regulatorio** | Norma/Resolución SRI, KB | Matriz → control → módulo → prueba → release | Estado de cumplimiento verificado | Oficial Cumpl. | Arquitecto, Dev | GG/CIO | Auditor | CM-01…CM-32 (`06`) | `06_MATRIZ_DE_CUMPLIMIENTO.md` |
| P8 | **Atención de incidentes** | Alerta/usuario | Clasificación S1–S4, contención, erradicación, lección aprendida | Resolución + CAPA | Ops | DBA, Dev | Arquitecto | OC | SEG-13…SEG-15 (`01`), §6 (`02`) | Registro de incidentes, post-mortem |

## 9. Evaluación del desempeño (Performance evaluation)

### 9.1 Monitoreo
KPI de `08_INDICADORES_Y_METAS.md`, con fórmula, meta, frecuencia y responsable por indicador.

### 9.2 Auditoría interna
| Campo | Definición |
|---|---|
| Frecuencia | Semestral (próxima: 2026-10-30 y 2027-04-30) |
| Alcance | Muestreo de: controles Q-*, SEG-*, CHG-*, AUD-*, muestra de ≥10 PR, ≥5 incidentes, ≥1 restauración simulada |
| Independencia | Auditor no participó en el proceso auditado (RACI §5.2) |
| Salida | Hallazgos → CAPA (§10) |

### 9.3 Revisión por dirección
Trimestral. Entradas: estado de la matriz de cumplimiento (06), riesgos (06b), KPI (08), incidentes, capacidad (03). Salidas: decisiones con responsable y fecha.

## 10. Mejora (Improvement) — CAPA

**Q-08 — Proceso CAPA (control del SGC)**

| Fase | Acción | Responsable | Plazo | Registro |
|---|---|---|---|---|
| 1. Contención | Detener el efecto (rollback, congelar release, notificar) | Ops/Dev | ≤4 h (S1/S2) | Registro incidente |
| 2. No conformidad | Registrar con ID `CAPA-YYYY-NNN`, evidencia, impacto regulatorio | Oficial Cumpl. | ≤24 h | Tablero CAPA |
| 3. Análisis de causa raíz | Ishikawa / 5 porqués; descartar "error humano" como causa final | Dev+QA+DBA | ≤5 días hábiles | Ficha CAPA |
| 4. Acción correctiva | Cambio de código/config/documento con PR y prueba que falla antes de pasar | Líder Dev | ≤10 días hábiles | PR + test |
| 5. Verificación de eficacia | Re-auditar o KPI ≥2 ciclos consecutivos en meta | Oficial Cumpl. | ≤90 días | Cierre CAPA |
| 6. Acción preventiva | Extender a procesos/riesgos similares (actualizar 06b/04/01) | Arquitecto | ≤30 días | Minuta |

**Disparadores obligatorios de CAPA:** KPI fuera de meta 2 ciclos; incidente S1/S2; rechazo SRI no esperado; hallazgo de auditoría; restauración fallida en simulacro (`02` §7).

## 11. Controles del SGC (resumen)

| ID | Control | Documento | Evidencia |
|---|---|---|---|
| Q-01…Q-07 | Control de información documentada | 00 §7 | Índice, historial |
| Q-08 | CAPA | 00 §10 | Registro CAPA |
| Q-09 | RACI y segregación de funciones | 00 §5.2 | Matriz firmada |
| Q-10 | Revisión por dirección trimestral | 00 §9.3 | Actas |
| Q-11 | Auditoría interna semestral | 00 §9.2 | Informes |
| Q-12 | Alineación de la matriz de cumplimiento con el código (estado honesto) | 06 | Diferencias detectadas/quarter |

## 12. Historial de revisiones

| Versión | Fecha | Autor | Cambio | Aprobador |
|---|---|---|---|---|
| 0.1 | 2026-10-15 | Oficial de Cumplimiento | Borrador inicial: alcance, RACI, mapa de procesos, CAPA | — |
| 1.0 | 2026-10-15 | Oficial de Cumplimiento | Emisión: controles Q-01…Q-12, jerarquía documental, historial | GG/CIO |
| 1.1 | 2027-04-15 (prevista) | Oficial de Cumplimiento | Revisión semestral obligatoria | GG/CIO |

---

*Documento raíz de la jerarquía `docs/ISO/`. Siguientes niveles: políticas (01, 07), procedimientos (02–05), registros/matrices (06, 06b, 08). Índice completo en `docs/ISO/README.md`.*
