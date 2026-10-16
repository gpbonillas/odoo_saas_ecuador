# Documentación ISO / Estándares y Controles — Odoo 18 Ecuador Localization

Colección de documentos de estandarización, controles y cumplimiento para la plataforma
**Odoo 18 Ecuador Localization** (`odoo_saas_ecuador`). Cada documento tiene código `ISO-EC-XX-NN`,
responsable, fecha de emisión y próxima revisión. Los controles se cruzan entre documentos por ID
(`Q-*`, `SEG-*`, `BC-*`, `DR-P*`, `CAP-*`, `CHG-*`, `AUD-*`, `CM-*`, `R-*`, `GOV-*`, `KPI-*`).

**Versión de la colección:** 1.1 · **Fecha:** 2026-10-16 · **Próxima revisión:** 2027-04-15

## Índice de documentos

| Archivo | Código | Contenido principal |
|---|---|---|
| `00_MANUAL_DE_CALIDAD.md` | ISO-EC-00 | Sistema de gestión de calidad, roles, controles Q-01..Q-12 |
| `01_POLITICA_DE_SEGURIDAD.md` | ISO-EC-01 | Política de seguridad (ISO/IEC 27001 Annex A), controles SEG-01..SEG-20 |
| `02_CONTINUIDAD_Y_RECUPERACION.md` | ISO-EC-02 | BC/DR, RPO ≤ 6h, procedimientos DR-P1..DR-P5, pruebas anuales |
| `03_GESTION_DE_CAPACIDAD.md` | ISO-EC-03 | Dimensionamiento (workers, conexiones), monitoreo, scaling, CAP-01..CAP-10 |
| `04_CONTROL_DE_CAMBIOS.md` | ISO-EC-04 | Flujo de cambios, hotfix SRI, migraciones, versionado, CHG-01..CHG-12 |
| `05_TRAZABILIDAD_Y_AUDITORIA.md` | ISO-EC-05 | Inmutabilidad, logs, retención de evidencias, auditoría, AUD-01..AUD-14 |
| `06_MATRIZ_DE_CUMPLIMIENTO.md` | ISO-EC-06 | Matriz regulatoria (SRI, IESS, MDT, BCE, SENAE, datos), CM-01..CM-39 |
| `06b_MATRIZ_DE_RIESGOS.md` | ISO-EC-06b | Matriz de riesgos R-001..R-020 con heatmap y plan trimestral |
| `07_GOBERNANZA_TIC.md` | ISO-EC-07 | ISO/IEC 38500, SoD, terceros, gobierno de agentes IA/MCP |
| `08_INDICADORES_Y_METAS.md` | ISO-EC-08 | KPI-01..KPI-18 con fórmula, meta y responsable |
| `09_ARQUITECTURA_VERTICALES_WIZARD.md` | ISO-EC-09 | Arquitectura vertical/wizard, controles DES-*, TEN-*, WIZ-*, AGT-*, SEC-*, DOC-* (v1.1) |
| `10_ESPECIFICACION_MOTOR_LEGAL.md` | ISO-EC-10 | Especificación de requisitos del motor legal (ISO/IEC/IEEE 29148): FR-LE-10..50, escala doble IVA, IR, transmisión/anulación, identidad EC, parámetros |
| `11_DOCUMENTACION_DE_PRUEBAS.md` | ISO-EC-11 | Documentación de pruebas (ISO/IEC/IEEE 29119): suites, cobertura, criterios de aceptación, huecos |
| `README.md` | — | Este índice |

### Documentos SRS registrados desde v1.1 (DOC-05)

| Archivo | Código | Contenido principal |
|---|---|---|
| `docs/srs/SRS_VERTICAL_AGRO_TRACEABILITY.md` | SRS-VERT-AGRO-2026-001 (v1.1) | Vertical **agro multi-crop** (cualquier cultivo, D-05): tenant CANNACHAIN `1793125212001`, diseño seed-to-sale, módulo propio `l10n_ec_agro`, FR-AG-01..14, parámetros N-01 v1.1, plan MCP |
| `docs/srs/RESEARCH_TRACEABILITY_FEATURE_CATALOG.md` | RES-VERT-2026-001 (v1.0) | Investigación: 29 módulos OpenTHC + catálogo trazabilidad agroalimentaria (Verdnt/FSMA-204) → mapa de 28 features → Odoo-core vs capa propia (D-06) |
| `docs/srs/SRS_SOMATECH_ODOO_BRIDGE.md` | SRS-BRIDGE-2026-001 (v1.0) | Capa **SOMATECH-ODOO-BRIDGE** (D-08) + UI/UX de verticalización encima (D-09): arquitectura L0–L3, FR-BR-01..12, lecciones del demo FAME/YACHAQ, plan P1–P5 |

## Estándares ISO cubiertos por la colección

| Norma ISO | Título (abrev.) | Documento(s) que la implementan |
|---|---|---|
| ISO 9001:2015 | Sistemas de gestión de calidad (información documentada §7.5) | ISO-EC-00, ISO-EC-04 |
| ISO/IEC 27001:2022 | Seguridad de la información (Annex A) | ISO-EC-01, ISO-EC-05 |
| ISO/IEC 38500 | Gobierno de las TI | ISO-EC-07 |
| ISO 22301 | Continuidad de negocio | ISO-EC-02 |
| ISO/IEC/IEEE 29148:2018 | Ingeniería de requisitos (ciclo de vida) | ISO-EC-10 |
| ISO/IEC/IEEE 29119:2022 | Pruebas de software | ISO-EC-11 |
| ISO/IEC 25010 | Calidad de sistemas/software (SQuaRE) | ISO-EC-08 (KPIs) |
| ISO 31000 | Gestión de riesgos | ISO-EC-06b |

## Jerarquía documental

```
00_MANUAL_DE_CALIDAD          (rector: alcance, roles, referencias)
├── 01_POLITICA_DE_SEGURIDAD  (seguridad de la información)
├── 02_CONTINUIDAD_Y_RECUPERACION
├── 03_GESTION_DE_CAPACIDAD
├── 04_CONTROL_DE_CAMBIOS
├── 05_TRAZABILIDAD_Y_AUDITORIA
├── 06_MATRIZ_DE_CUMPLIMIENTO ── 06b_MATRIZ_DE_RIESGOS
├── 07_GOBERNANZA_TIC
├── 08_INDICADORES_Y_METAS    (medición transversal)
├── 10_ESPECIFICACION_MOTOR_LEGAL  (requisitos software — ISO/IEC/IEEE 29148)
└── 11_DOCUMENTACION_DE_PRUEBAS    (pruebas — ISO/IEC/IEEE 29119)
```

## Fuentes de verdad del sistema (no modificar sin proceso de cambio)

| Artefacto | Ruta | Uso en esta colección |
|---|---|---|
| Plan de desarrollo | `DEVELOPMENT_PLAN.md` | Roadmap, sprints, bloqueos |
| Cumplimiento regulatorio | `docs/CUMPLIMIENTO_REGULATORIO.md` | Obligaciones (§ matriz 06) |
| Matriz SRS-regulatoria | `docs/srs/SRS_ERP_REGULATION_MATRIX.md` | Requisitos vs regulación |
| Orquestación | `docker-compose.yml` | Servicios, volúmenes, backups, logging |
| Configuración Odoo | `config/odoo.conf`, `config/entrypoint.sh` | Workers, parámetros |
| Configuración Postgres | `config/postgresql.conf` | `max_connections`, logs |
| Módulos `l10n_ec*` | raíz del repo | Evidencia de implementación |
| Matriz de roles | `l10n_ec_sri/docs/09_security_matrix/SECURITY_ROLE_MATRIX.md` | Permisos y retención |
| KB regulatoria | `l10n_ec_sri/docs/11_regulatory_knowledge_base/` | Hotfix regulatorio (04 §3.2) |
| Contribución | `CONTRIBUIR.md` | Flujo de ramas/PRs (04 §4) |

## Uso de `[VERIFY]`

Todo dato legal ecuatoriano incierto se marca `[VERIFY: fuente a confirmar]` en lugar de inventar
artículos o números de resolución. Antes de cualquier auditoría externa, ejecutar el inventario de
`[VERIFY]` (§ "Índice de verificaciones" al final de cada documento) y sustituir por la cita oficial.

## Estadísticas de la colección

| Métrica | Valor |
|---|---|
| Documentos | 14 ISO (incluye este README) + 2 SRS registrados (v1.1) |
| Controles totales | 12 (Q) + 20 (SEG) + 12+5 (BC/DR) + 10 (CAP) + 12 (CHG) + 14 (AUD) + 42 (CM) + 20 (R) + 3 (GOV) + 18 (KPI) + 5 (FR-LE) + 5 (NFR) |
| Estado de la matriz 06 | 1 Implementado · 18 Parcial · 23 Pendiente (honesto, no 100%) |
| Riesgos | 20 (R-001..R-020); críticos: R-002, R-003 |
| Pruebas (ISO-EC-11) | 440 definidas; motor legal MCP 54/54 OK (2026-10-16) + equivalencia stdnum 20,195→0 y permanente 22,727→0 |

## Mantenimiento de la colección

| Actividad | Frecuencia | Responsable |
|---|---|---|
| Revisión de contenidos (todas las fechas "Próxima revisión") | Semestral | Cada dueño de documento |
| Actualización tras cambio regulatorio | Bajo demanda | Fiscal / Cumplimiento |
| Actualización de estados en 06 y 06b | Trimestral | Cumplimiento / Gerencia |
| Reporte de KPIs (08) | Mensual/Trimestral | Calidad |
