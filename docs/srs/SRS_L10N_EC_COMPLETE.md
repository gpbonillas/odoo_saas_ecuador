# Software Requirements Specification (SRS)
## Ecuador Localization Module - Complete Reference

**Document ID:** SRS-L10N-EC-2026-COMPLETE
**Version:** 3.0.0
**Date:** 2026-01-25
**Status:** PRODUCTION

---

## 1. MODULE LOAD ORDER

```
┌─────────────────────────────────────────────────────┐
│  STEP 1: l10n_ec_base (CATALOGS + CONFIG)          │
│  ├── security/l10n_ec_groups.xml                   │
│  ├── security/ir.model.access.csv (22 rules)       │
│  ├── data/l10n_ec_sri_config.xml                   │
│  ├── data/l10n_ec_config_data.xml                  │
│  ├── data/l10n_ec_catalogs_data.xml                │
│  ├── data/l10n_ec_provinces.xml (24)               │
│  ├── data/l10n_ec.canton.csv (221)                 │
│  ├── data/account_chart_template.xml               │
│  └── data/l10n_latam.document.type.csv             │
├─────────────────────────────────────────────────────┤
│  STEP 2: l10n_ec (WIZARD)                          │
│  └── depends: l10n_ec_base                         │
│  └── wizard/l10n_ec_company_setup_wizard_views.xml │
│  └── Demo data: WIZARD-CONTROLLED (optional)       │
└─────────────────────────────────────────────────────┘
```

---

## 2. DATA LOADED AT INSTALLATION

### 2.1 Configuration Parameters

| Parameter | Value | Source |
|:----------|:------|:-------|
| SBU 2026 | $482.00 | MDT |
| IESS Personal | 9.45% | IESS |
| IESS Patronal | 11.15% | IESS |
| IESS SECAP | 0.50% | IESS |
| IESS IECE | 0.50% | IESS |
| Total Empleador | 12.15% | Computed |
| Techo IESS | $12,050 | 25 SBU |
| IVA General | 15% | SRI |
| IVA Construcción | 5% | SRI |
| Fondos Reserva | 8.33% | MDT |
| Canasta Básica | $808.95 | INEC |

### 2.2 Retention Codes

**IR Retenciones (14):**
| Code | Rate | Description |
|:-----|:-----|:------------|
| 303 | 10% | Honorarios Profesionales |
| 304 | 8% | Servicios Predomina Intelecto |
| 307 | 2% | Servicios Mano de Obra |
| 308 | 2% | Servicios Entre Sociedades |
| 309 | 1% | Publicidad y Comunicación |
| 310 | 1% | Transporte Privado |
| 312 | 1% | Transferencia Bienes Muebles |
| 319 | 1% | Arrendamiento Mercantil |
| 320 | 1.75% | Arrendamiento Inmuebles |
| 322 | 1% | Seguros y Reaseguros |
| 323 | 2% | Rendimientos Financieros |
| 340 | 1% | Artes Gráficas |
| 344 | 25% | Dividendos Residentes |
| 500 | 25% | Pagos al Exterior |

**IVA Retenciones (6):**
| Code | Rate | Description |
|:-----|:-----|:------------|
| 721 | 10% | Bienes IVA 10% |
| 723 | 20% | Servicios IVA 20% |
| 725 | 30% | Bienes Contrib. Especial |
| 727 | 70% | Servicios Contrib. Especial |
| 729 | 100% | Liquidación de Compra |
| 731 | 100% | Profesionales |

### 2.3 Catalogs

| Catalog | Count | Model |
|:--------|:------|:------|
| Payment Methods | 8 | l10n_ec.payment.method |
| ID Types | 5 | l10n_ec.identification.type |
| Tax Supports | 11 | l10n_ec.tax.support |
| Contributor Types | 8 | l10n_ec.contributor.type |
| Provinces | 24 | l10n_ec.province |
| Cantons | 221 | l10n_ec.canton |
| Tax Rates | 5 | account.tax |

### 2.4 Geographic Data

**Provinces by Region:**

| Region | Count | Décimo 4to |
|:-------|:------|:-----------|
| Sierra | 10 | Agosto 15 |
| Costa | 7 | Marzo 15 |
| Oriente | 6 | Agosto 15 |
| Insular | 1 | Marzo 15 |

---

## 3. DEMO DATA (WIZARD-CONTROLLED)

### 3.1 Demo Partners Summary

| Category | Count | Wizard Option |
|:---------|:------|:--------------|
| Company | 1 | Always with demo |
| Customers | 8 | demo_customers |
| Suppliers | 7 | demo_suppliers |
| Employees | 3 | demo_employees |
| Foreign | 2 | demo_foreign |
| **TOTAL** | **21** | - |

### 3.2 Customer Types

| XML ID | Name | Type | RUC/CI |
|:-------|:-----|:-----|:-------|
| demo_customer_natural | Juan Carlos Pérez | Cédula | 1713488185 |
| demo_customer_natural_obligado | María López | RUC Natural | 1713488185001 |
| demo_customer_sociedad | CANNACHAIN S.A.S. | Sociedad | 1793125212001 |
| demo_customer_especial | Distribuidora Nacional | Especial | PENDIENTE (D-04: sin ID aprobado) |
| demo_customer_rimpe_e | Artesanías Andinas | RIMPE Emprendedor | PENDIENTE (D-04) |
| demo_customer_rimpe_p | Tienda Don Pedro | RIMPE Popular | PENDIENTE (D-04) |
| demo_customer_final | Consumidor Final | Final | 9999999999999 |
| demo_customer_exporter | Exportadora Bananera | Exportador | PENDIENTE (D-04) |

> **D-04 (2026-10-16):** solo existen IDs de prueba aprobados `1713488185` (cédula),
> `1713488185001` (natural) y `1793125212001` (jurídica). El XML demo del código
> (`l10n_ec_base/demo/l10n_ec_demo_partners.xml`) aún contiene RUCs inventados — pendiente
> de limpieza (bloqueado en fase "solo docs").

### 3.3 Supplier Types (Retention Testing)

| XML ID | Name | Retention Code | Rate |
|:-------|:-----|:---------------|:-----|
| demo_supplier_profesional | Dr. Roberto Torres | 303 | 10% |
| demo_supplier_comercial | Importadora Andina | 312 | 1% |
| demo_supplier_especial | Proveedora Estatal | 725/727 | 30%/70% |
| demo_supplier_informal | Pedro Campoverde | 729 | 100% |
| demo_supplier_arrendador | Inmobiliaria Costa | 320 | 1.75% |
| demo_supplier_transporte | Transportes Nacional | 310 | 1% |
| demo_supplier_gobierno | Constructora Estado | UAF Required | DE 045 |

### 3.4 Employees (Payroll Testing)

| XML ID | Region | Décimo 4to |
|:-------|:-------|:-----------|
| demo_employee_sierra | Quito | Agosto |
| demo_employee_costa | Guayaquil | Marzo |
| demo_employee_galapagos | Santa Cruz | Marzo |

### 3.5 Foreign Partners (ISD Testing)

| XML ID | Country | Purpose |
|:-------|:--------|:--------|
| demo_supplier_usa | USA | ISD 5% |
| demo_customer_colombia | Colombia | Exports |

---

## 4. WIZARD FLOW

```
1. User opens Company Setup Wizard
2. Enters RUC → API SRI called
3. Data auto-filled from SRI response
4. User configures:
   - SRI Environment (Test/Production)
   - Obligado Contabilidad
   - Contribuyente Especial
   - Agente Retención
5. OPTIONAL: Demo Data
   ☐ Install Demo Data
   ├── ☑ Customers (8)
   ├── ☑ Suppliers (7)
   ├── ☑ Employees (3)
   └── ☑ Foreign (2)
6. Click "Configurar Empresa"
7. Company + selected demo data created
```

---

## 5. VALIDATION ALGORITHMS

### 5.1 RUC/Cédula Validation

**Cédula (10 digits) - Módulo 10:**
```
Coefficients: [2, 1, 2, 1, 2, 1, 2, 1, 2]
Sum products (if >= 10, subtract 9)
Check digit = (10 - sum % 10) % 10
```

**RUC Sociedad (13 digits, 3rd digit = 9) - Módulo 11:**
```
Coefficients: [4, 3, 2, 7, 6, 5, 4, 3, 2]
Check digit = 11 - (sum % 11)
```

**RUC Público (13 digits, 3rd digit = 6) - Módulo 11:**
```
Coefficients: [3, 2, 7, 6, 5, 4, 3, 2]
Check digit = 11 - (sum % 11)
```

---

## 6. API SRI INTEGRATION

**Endpoint:**
```
GET https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/
    rest/ConsolidadoContribuyente/obtenerPorNumerosRuc?ruc={RUC}
```

**Response Mapping:**
| API Field | Odoo Field |
|:----------|:-----------|
| razonSocial | name |
| nombreComercial | company_registry |
| estadoContribuyente | sri_estado |
| obligadoContabilidad | obligado_contabilidad |
| contribuyenteEspecial | contribuyente_especial |
| regimenRimpe | l10n_ec_taxpayer_type |
| direccionMatriz | street |
| nombreCanton | city |
| nombreProvincia | province |
| telefono1 | phone |
| correo | email |

---

## 7. TOTALS

| Category | Count |
|:---------|:------|
| Configuration Parameters | 12 |
| Retention Codes | 20 |
| Catalog Records | 57 |
| Provinces | 24 |
| Cantons | 221 |
| Tax Templates | 5 |
| Demo Partners | 21 |
| Security Rules | 22 |
| **TOTAL DATA RECORDS** | **362** |

---

**END OF DOCUMENT**
