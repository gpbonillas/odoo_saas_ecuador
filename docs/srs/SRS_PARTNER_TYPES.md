# SRS - Partner Types Definition
## Ecuador Localization - Complete Partner Classification

**Document ID:** SRS-L10N-EC-PARTNER-TYPES
**Version:** 1.0.0
**Date:** 2026-01-25

---

## 1. PARTNER CLASSIFICATION HIERARCHY

```
res.partner
├── company_type
│   ├── "person" → Persona Natural
│   └── "company" → Persona Jurídica
│
├── l10n_ec_identifier_type
│   ├── cedula → Cédula (10 dígitos)
│   ├── ruc → RUC (13 dígitos)
│   ├── pasaporte → Pasaporte
│   └── identificacion_exterior → ID Exterior
│
├── l10n_ec_taxpayer_type
│   ├── general → Contribuyente General
│   ├── special → Contribuyente Especial
│   ├── rimpe_e → RIMPE Emprendedor
│   ├── rimpe_p → RIMPE Negocio Popular
│   ├── nonprofit → Sin Fines de Lucro
│   ├── zede → Zona Especial
│   └── exporter → Exportador Habitual
│
└── l10n_ec_entity_type
    ├── persona → Persona Natural
    ├── sa → Sociedad Anónima (S.A.)
    ├── cia_ltda → Compañía Limitada
    ├── sas → S.A.S.
    ├── ep → Empresa Pública
    ├── fundacion → Fundación
    ├── ong → ONG
    ├── cooperativa → Cooperativa
    └── zede → ZEDE
```

---

## 2. PERSONA NATURAL TYPES

### 2.1 Regular Persons

| Type | RUC/CI | Fields | Tax Treatment |
|:-----|:-------|:-------|:--------------|
| Sin RUC | Cédula | vat (10 digits) | Normal |
| Con RUC | RUC Natural | vat (13, ends 001) | Normal |
| Obligado Contabilidad | RUC Natural | obligado_contabilidad=True | Full accounting |

### 2.2 Special Benefit Persons

| Type | Field | Condition | Benefit | Legal Base |
|:-----|:------|:----------|:--------|:-----------|
| **Tercera Edad** | l10n_ec_tercera_edad | edad >= 65 | IVA refund 5 canastas | LORTI Art. 74 |
| **Discapacidad** | l10n_ec_discapacidad | porcentaje >= 30% | IVA refund 3 SBU | Ley Disc. Art. 78 |
| **Artesano** | l10n_ec_artesano_calificado | Carnet JNDA | IVA 0% | LORTI Art. 56 |

### 2.3 Auto-Computed Fields

```python
# Age computed from birthdate
l10n_ec_edad = computed(l10n_ec_fecha_nacimiento)

# Tercera Edad auto-activated
l10n_ec_tercera_edad = computed(
    True if company_type == 'person' AND edad >= 65
)
```

---

## 3. PERSONA JURÍDICA TYPES

### 3.1 By Entity Type

| Entity Type | RUC 3rd Digit | Legal Base |
|:------------|:--------------|:-----------|
| Sociedad Privada (S.A., Cía. Ltda.) | 9 | Ley de Compañías |
| Empresa Pública (E.P.) | 6 | LOEP |
| Fundación | 9 | Código Civil Art. 564 |
| ONG | 6 o 9 | Convenios internacionales |
| Cooperativa | 9 | LOEPS |
| S.A.S. | 9 | Ley S.A.S. 2020 |
| ZEDE | 9 | COPCI Art. 34-47 |

### 3.2 Tax Treatment by Entity

| Entity | IR | IVA | Retención |
|:-------|:---|:----|:----------|
| Sociedad General | 25% | 15% | Normal |
| Contrib. Especial | 25% | 15% | Retiene 30%/70% |
| Fundación/ONG | Exento | 15% | No retiene |
| Cooperativa | Según LOEPS | 15% | Normal |
| ZEDE | Beneficios | 0% (interno) | Especial |
| Nueva Empresa | Exento 3 años | 15% | Normal |

---

## 4. SPECIAL REGIMES

### 4.1 RIMPE (Régimen Simplificado)

| Tipo | Rango Ingresos | IR | IVA |
|:-----|:---------------|:---|:----|
| RIMPE Emprendedor | $0 - $20,000 | 1-2% | 12% |
| RIMPE Negocio Popular | $0 - $20,000 | 0% | 0% |

### 4.2 Nueva Empresa (LORTI Art. 9.1 bis)

**Benefit:** IR exempt for 3 years
**Condition:** nueva_empresa=True AND fecha_constitucion < 3 years

### 4.3 ZEDE (COPCI Art. 34-47)

**Benefits:**
- IVA 0% on internal sales
- Reduced IR
- Customs exemptions

---

## 5. FIELD DEFINITIONS

### 5.1 Core Fields

```python
# Odoo standard
company_type = Selection(['person', 'company'])
vat = Char  # RUC or Cédula

# Ecuador extensions
l10n_ec_identifier_type = Selection([
    ('cedula', 'Cédula'),
    ('ruc', 'RUC'),
    ('pasaporte', 'Pasaporte'),
    ('identificacion_exterior', 'ID Exterior'),
])

l10n_ec_taxpayer_type = Selection([
    ('general', 'General'),
    ('special', 'Contribuyente Especial'),
    ('rimpe_e', 'RIMPE Emprendedor'),
    ('rimpe_p', 'RIMPE Negocio Popular'),
    ('nonprofit', 'Sin Fines de Lucro'),
    ('zede', 'Zona Especial'),
    ('exporter', 'Exportador Habitual'),
])

l10n_ec_entity_type = Selection([
    ('persona', 'Persona Natural'),
    ('sa', 'Sociedad Anónima'),
    ('cia_ltda', 'Compañía Limitada'),
    ('sas', 'S.A.S.'),
    ('ep', 'Empresa Pública'),
    ('fundacion', 'Fundación'),
    ('ong', 'ONG'),
    ('cooperativa', 'Cooperativa'),
    ('zede', 'ZEDE'),
])
```

### 5.2 Special Benefit Fields

```python
# Person benefits
l10n_ec_fecha_nacimiento = Date
l10n_ec_edad = Integer (computed)
l10n_ec_tercera_edad = Boolean (computed, age >= 65)
l10n_ec_discapacidad = Boolean
l10n_ec_discapacidad_porcentaje = Integer (30-100)
l10n_ec_discapacidad_carnet = Char
l10n_ec_artesano_calificado = Boolean

# Company benefits
l10n_ec_nueva_empresa = Boolean
l10n_ec_fecha_constitucion = Date
```

---

## 6. VALIDATION RULES

### 6.1 RUC/Cédula Validation (stdnum ground truth — FR-LE-50, ISO-EC-10 §3.5)

| Type | Digits | 3rd Digit | Check |
|:-----|:-------|:----------|:------|
| Cédula | 10 | 0–6 (provincia 01–24 + 30/50) | Módulo 10 (pesos 2,1) sobre 10 dígitos |
| RUC Natural | 13 | 0–5 | Válida como cédula + establecimiento (últimos 3 dígitos) ≠ `000` (`001` es el estándar, D-02) |
| RUC Sociedad | 13 | 9 | Módulo 11 primeros 10 (pesos 4,3,2,7,6,5,4,3,2,1) |
| RUC Público | 13 | 6 | Módulo 11 primeros 9 (pesos 3,2,7,6,5,4,3,2,1) + fallback natural |
| RUC (7/8) | 13 | 7 u 8 | **Inválido** |

Reglas de negocio (D-02/D-03): RUC natural = cédula + `001` **siempre**; se puede **comprar**
con cédula; **vender/emitir exige RUC ACTIVO** en el SRI. Evidencia de equivalencia `stdnum`:
20,195 casos → 0 diferencias (2026-10-16).

### 6.2 Business Rules

| Rule | Condition | Action |
|:-----|:----------|:-------|
| Tercera Edad | company_type != 'person' | Block |
| Discapacidad | porcentaje < 30% | Error |
| Nueva Empresa | fecha_constitucion > 3 years | Disable benefit |
| Fundación | selling goods | Warning |

---

## 7. DEMO PARTNERS SUMMARY

### 7.1 Personas Naturales (5)

| Partner | Type | Special |
|:--------|:-----|:--------|
| demo_customer_natural | Cédula | - |
| demo_customer_tercera_edad | Cédula | Age 65+ |
| demo_customer_discapacidad | Cédula | CONADIS |
| demo_customer_natural_obligado | RUC | Obligado Contab |
| demo_customer_artesano | RUC | JNDA |

### 7.2 Personas Jurídicas (13)

| Partner | Entity Type | Tax Type |
|:--------|:------------|:---------|
| demo_customer_sociedad | sa | general |
| demo_customer_especial | sa | special |
| demo_customer_rimpe_e | persona | rimpe_e |
| demo_customer_rimpe_p | persona | rimpe_p |
| demo_customer_final | - | general |
| demo_customer_exporter | sa | exporter |
| demo_customer_gobierno | ep | special |
| demo_customer_empresa_publica | ep | special |
| demo_customer_fundacion | fundacion | nonprofit |
| demo_customer_ong | ong | nonprofit |
| demo_customer_cooperativa | cooperativa | general |
| demo_customer_zede | zede | zede |
| demo_customer_nueva_empresa | sas | general |

---

## 8. FLOW IMPACT

### 8.1 Invoice Creation

```
Partner selected
    │
    ├─→ Check l10n_ec_taxpayer_type
    │   └─→ Apply tax rates
    │
    ├─→ Check l10n_ec_tercera_edad
    │   └─→ Mark for IVA refund report
    │
    └─→ Check l10n_ec_discapacidad
        └─→ Mark for IVA refund report
```

### 8.2 Retention Calculation

```
Purchase from supplier
    │
    ├─→ company_type == 'person'?
    │   └─→ Check profession → 303 (10%) or 307 (2%)
    │
    ├─→ l10n_ec_taxpayer_type == 'special'?
    │   └─→ Apply 725/727 (30%/70%)
    │
    └─→ l10n_ec_identifier_type == 'cedula'?
        └─→ Liquidación de Compra (03) + 729 (100%)
```

---

**END OF DOCUMENT**
