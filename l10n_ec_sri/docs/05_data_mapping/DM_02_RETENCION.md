# DATA MAPPING: RETENCIÓN (WITHHOLDING)
## Field-by-Field Transformation from Odoo to SRI XML

**Document ID**: DM-RET-002
**Version**: 1.0
**Classification**: Big 4 Professional Grade

---

## 1. DOCUMENT SCOPE

| Attribute | Value |
|:----------|:------|
| **Source System** | Odoo 18.0 ERP |
| **Target Format** | SRI XML Schema v2.0.0 |
| **Document Type** | Comprobante de Retención (codDoc = 07) |
| **XSD Reference** | `comprobanteRetencion.xsd` |
| **KB Reference** | KB_TAX_RATES_WITHHOLDINGS |

---

## 2. INFOTRIBUTARIA MAPPING

| XML Element | Odoo Model | Odoo Field | Transformation |
|:------------|:-----------|:-----------|:---------------|
| `ambiente` | res.company | `l10n_ec_sri_environment` | '1'=Test, '2'=Prod |
| `tipoEmision` | res.company | `emission_code` | '1'=Normal |
| `razonSocial` | res.company | `name` | Max 300 chars |
| `ruc` | res.partner (company) | `vat` | 13 digits |
| `claveAcceso` | account.retention | `clave_acceso` | 49-digit computed |
| `codDoc` | - | - | Constant: '07' |
| `estab` | account.journal | `l10n_ec_entity` | 3 digits |
| `ptoEmi` | account.journal | `l10n_ec_emission` | 3 digits |
| `secuencial` | account.retention | `name` (parsed) | 9 digits |
| `dirMatriz` | res.company | `street` | Max 300 chars |

---

## 3. INFORETENCION MAPPING

| XML Element | Odoo Model | Odoo Field | Transformation |
|:------------|:-----------|:-----------|:---------------|
| `fechaEmision` | account.retention | `date` | DD/MM/YYYY |
| `obligadoContabilidad` | res.company | `l10n_ec_obligado_contabilidad` | 'SI' / 'NO' |
| `tipoIdentificacionSujetoRetenido` | res.partner | See mapping | Per SRI catalog |
| `razonSocialSujetoRetenido` | res.partner (vendor) | `name` | Max 300 chars |
| `identificacionSujetoRetenido` | res.partner | `vat` | Per type rules |
| `periodoFiscal` | account.retention | `date` | MM/YYYY |

### 3.1 Identification Type Mapping
| Partner Type | XML `tipoIdentificacionSujetoRetenido` |
|:-------------|:---------------------------------------|
| RUC | 04 |
| Cédula | 05 |
| Pasaporte | 06 |

---

## 4. IMPUESTOS (RETENTION LINES) MAPPING

### 4.1 Per-Line Mapping
| XML Element | Odoo Model | Odoo Field | Transformation |
|:------------|:-----------|:-----------|:---------------|
| `codigo` | account.retention.line | `tax_type` | 1=IR, 2=IVA |
| `codigoRetencion` | account.retention.line | `tax_code` | tabla19/tabla21 |
| `baseImponible` | account.retention.line | `base` | Decimal 2 places |
| `porcentajeRetener` | account.retention.line | `percentage` | Integer |
| `valorRetenido` | account.retention.line | `amount` | Decimal 2 places |
| `codDocSustento` | account.move (bill) | Document type | tabla4 |
| `numDocSustento` | account.move (bill) | `l10n_latam_document_number` | 15 chars |
| `fechaEmisionDocSustento` | account.move (bill) | `invoice_date` | DD/MM/YYYY |

### 4.2 tabla19 (IR Retention Codes)
| Odoo Tax Code | XML `codigoRetencion` | Description |
|:--------------|:----------------------|:------------|
| 303 | 303 | Honorarios profesionales 10% |
| 304 | 304 | Servicios predomina intelecto 8% |
| 307 | 307 | Publicidad 2% |
| 309 | 309 | Transporte privado 1% |
| 310 | 310 | Bienes muebles 1.75% |
| 312 | 312 | Bienes no producidos 1.75% |
| 320 | 320 | Arrendamiento inmuebles 2.75% |
| 322 | 322 | Seguros 8% |
| 323 | 323 | Rendimientos financieros 2% |
| 340 | 340 | Otras retenciones 1% |
| 341 | 341 | Otras retenciones 2% |

### 4.3 tabla21 (IVA Retention Codes)
| Odoo Percentage | XML `codigoRetencion` |
|:----------------|:----------------------|
| 10% | 9 |
| 20% | 10 |
| 30% | 1 |
| 50% | 11 |
| 70% | 2 |
| 100% | 3 |

### 4.4 tabla4 (Supporting Document Types)
| Document Type | XML `codDocSustento` |
|:--------------|:---------------------|
| Factura | 01 |
| Nota de Venta | 02 |
| Liquidación de Compra | 03 |
| Nota de Crédito | 04 |
| Nota de Débito | 05 |

---

## 5. 5-DAY RULE VALIDATION

### 5.1 Business Rule
```python
def validate_5_day_rule(invoice_date, retention_date):
    """
    Per SRI regulations, retention must be issued within
    5 days of the invoice date (business days typically).
    """
    days_diff = (retention_date - invoice_date).days
    if days_diff > 5:
        raise ValidationError(
            get_message("CODE_701",
                invoice_date=invoice_date,
                retention_date=retention_date,
                days=days_diff
            )
        )
    return True
```

### 5.2 System Behavior
| Scenario | System Action |
|:---------|:--------------|
| Within 5 days | ✅ Allow creation |
| Day 6+ | ❌ Block with error CODE_701 |
| Force override | Requires supervisor role |

---

## 6. XML STRUCTURE EXAMPLE

```xml
<?xml version="1.0" encoding="UTF-8"?>
<comprobanteRetencion id="comprobante" version="2.0.0">
  <infoTributaria>
    <ambiente>2</ambiente>
    <tipoEmision>1</tipoEmision>
    <razonSocial>EMPRESA DEMO S.A.</razonSocial>
    <ruc>1793125212001</ruc>
    <claveAcceso>2201202607179312521200120010010000000011234567811</claveAcceso>
    <codDoc>07</codDoc>
    <estab>001</estab>
    <ptoEmi>001</ptoEmi>
    <secuencial>000000001</secuencial>
    <dirMatriz>Av. Principal 123, Quito</dirMatriz>
  </infoTributaria>
  <infoCompRetencion>
    <fechaEmision>22/01/2026</fechaEmision>
    <obligadoContabilidad>SI</obligadoContabilidad>
    <tipoIdentificacionSujetoRetenido>04</tipoIdentificacionSujetoRetenido>
    <razonSocialSujetoRetenido>PROVEEDOR ABC CIA. LTDA.</razonSocialSujetoRetenido>
    <identificacionSujetoRetenido>1793125212001</identificacionSujetoRetenido>
    <periodoFiscal>01/2026</periodoFiscal>
  </infoCompRetencion>
  <impuestos>
    <impuesto>
      <codigo>1</codigo>
      <codigoRetencion>312</codigoRetencion>
      <baseImponible>1000.00</baseImponible>
      <porcentajeRetener>1.75</porcentajeRetener>
      <valorRetenido>17.50</valorRetenido>
      <codDocSustento>01</codDocSustento>
      <numDocSustento>001-001-000000001</numDocSustento>
      <fechaEmisionDocSustento>20/01/2026</fechaEmisionDocSustento>
    </impuesto>
    <impuesto>
      <codigo>2</codigo>
      <codigoRetencion>1</codigoRetencion>
      <baseImponible>150.00</baseImponible>
      <porcentajeRetener>30</porcentajeRetener>
      <valorRetenido>45.00</valorRetenido>
      <codDocSustento>01</codDocSustento>
      <numDocSustento>001-001-000000001</numDocSustento>
      <fechaEmisionDocSustento>20/01/2026</fechaEmisionDocSustento>
    </impuesto>
  </impuestos>
</comprobanteRetencion>
```

---

## 7. VALIDATION RULES

| Rule ID | Field | Validation | Error |
|:--------|:------|:-----------|:------|
| VAL-R01 | `claveAcceso` | 49 chars, valid mod11 | "Clave inválida" |
| VAL-R02 | `fechaEmision` | ≤ 5 days from invoice | CODE_701 |
| VAL-R03 | `identificacion` | Valid per type | "RUC inválido" |
| VAL-R04 | `valorRetenido` | base × rate | "Cálculo incorrecto" |
| VAL-R05 | `numDocSustento` | Exists in system | "Documento no existe" |

---

**Document Classification**: Data Mapping Specification
**Owner**: IT / Integration Team
**Last Updated**: 2026-01-22
