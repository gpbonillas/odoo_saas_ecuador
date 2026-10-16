# DATA MAPPING SPECIFICATION: ELECTRONIC INVOICE
## Field-by-Field Transformation from Odoo to SRI XML

**Document ID**: DM-EINV-001
**Version**: 1.0
**Classification**: Big 4 Professional Grade

---

## 1. DOCUMENT SCOPE

| Attribute | Value |
|:----------|:------|
| **Source System** | Odoo 18.0 ERP |
| **Target Format** | SRI XML Schema v2.1.0 |
| **Document Type** | Factura (codDoc = 01) |
| **XSD Reference** | `factura.xsd` |

---

## 2. INFORIBUTARIA MAPPING

### 2.1 Tax Information Header
| XML Element | Odoo Model | Odoo Field | Transformation | Validation |
|:------------|:-----------|:-----------|:---------------|:-----------|
| `ambiente` | res.company | `l10n_ec_sri_environment` | Direct: '1'=Test, '2'=Prod | Required |
| `tipoEmision` | res.company | `emission_code` | Direct: '1'=Normal | Required |
| `razonSocial` | res.company | `name` | Max 300 chars, uppercase | Required |
| `nombreComercial` | res.company | `name` | Max 300 chars | Optional |
| `ruc` | res.partner (company) | `vat` | 13 digits | `stdnum.ec.ruc.is_valid()` |
| `claveAcceso` | account.move | `clave_acceso` | 49-digit computed | Módulo 11 |
| `codDoc` | - | - | Constant: '01' | - |
| `estab` | account.journal | `l10n_ec_entity` | 3 digits | Required |
| `ptoEmi` | account.journal | `l10n_ec_emission` | 3 digits | Required |
| `secuencial` | account.move | `name` (parsed) | 9 digits, zero-padded | Unique sequence |
| `dirMatriz` | res.company | `street` | Max 300 chars | Required |

### 2.2 Access Key (claveAcceso) Composition
| Position | Length | Source | Description |
|:---------|:-------|:-------|:------------|
| 1-8 | 8 | `invoice.date_invoice` | Date as DDMMYYYY |
| 9-10 | 2 | Constant | Document type '01' |
| 11-23 | 13 | `company.partner_id.vat` | Company RUC |
| 24 | 1 | `company.l10n_ec_sri_environment` | Environment |
| 25-27 | 3 | `journal.l10n_ec_entity` | Establishment |
| 28-30 | 3 | `journal.l10n_ec_emission` | Emission point |
| 31-39 | 9 | `invoice.name` (parsed) | Sequential |
| 40-47 | 8 | `ir.sequence.next_by_code('edocuments.code')` | Random code |
| 48 | 1 | `company.emission_code` | Emission type |
| 49 | 1 | Computed | Módulo 11 check digit |

---

## 3. INFOFACTURA MAPPING

### 3.1 Invoice Information
| XML Element | Odoo Model | Odoo Field | Transformation | Validation |
|:------------|:-----------|:-----------|:---------------|:-----------|
| `fechaEmision` | account.move | `invoice_date` | Format: DD/MM/YYYY | Required |
| `dirEstablecimiento` | res.company | `street2` | Max 300 chars | Optional |
| `obligadoContabilidad` | res.company | `l10n_ec_obligado_contabilidad` | 'SI' / 'NO' | Required |
| `tipoIdentificacionComprador` | res.partner | See mapping table | Per SRI catalog | Required |
| `razonSocialComprador` | res.partner | `name` | Max 300 chars | Required |
| `identificacionComprador` | res.partner | `vat` | Per type rules | Required |
| `totalSinImpuestos` | account.move | `amount_untaxed` | Decimal 2 places | Required |
| `totalDescuento` | Computed | Sum of line discounts | Decimal 2 places | Required |
| `propina` | - | - | Default '0.00' | Optional |
| `importeTotal` | account.move | `amount_total` | Decimal 2 places | Required |
| `moneda` | - | - | Constant 'DOLAR' | Required |

### 3.2 Identification Type Mapping
| Partner `l10n_latam_identification_type_id` | XML `tipoIdentificacionComprador` |
|:--------------------------------------------|:----------------------------------|
| ec_ruc (out_invoice) | 04 |
| ec_dni (out_invoice) | 05 |
| passport (out_invoice) | 06 |
| Consumidor Final (vat='9999999999999') | 07 |
| foreign (out_invoice) | 08 |

### 3.3 Payment Method Mapping
| Odoo `l10n_ec_sri_payment_id.code` | XML `formaPago` |
|:-----------------------------------|:----------------|
| 01 | SIN UTILIZACION DEL SISTEMA FINANCIERO |
| 15 | COMPENSACIÓN DE DEUDAS |
| 16 | TARJETA DE DÉBITO |
| 17 | DINERO ELECTRÓNICO |
| 18 | TARJETA PREPAGO |
| 19 | TARJETA DE CRÉDITO |
| 20 | OTROS CON UTILIZACIÓN DEL SISTEMA FINANCIERO |

---

## 4. TOTALCONIMPUESTOS MAPPING

### 4.1 Tax Totals by Type
| XML Element | Odoo Source | Transformation |
|:------------|:------------|:---------------|
| `codigo` | `tax.tax_group_id.code` | tabla17 lookup |
| `codigoPorcentaje` | `tax.percent_report` | tabla18 lookup |
| `baseImponible` | `tax_line.base` | Decimal 2 places |
| `tarifa` | `tax.amount` | Integer percentage |
| `valor` | `tax_line.amount` | Decimal 2 places |

### 4.2 tabla17 (Tax Type Codes)
| Odoo `tax_group_id.code` | XML `codigo` |
|:-------------------------|:-------------|
| vat | 2 |
| vat0 | 2 |
| ice | 3 |
| irbpnr | 5 |

### 4.3 tabla18 (Tax Rate Codes)
| Odoo `percent_report` | XML `codigoPorcentaje` |
|:----------------------|:-----------------------|
| 0 | 0 |
| 5 | 5 |
| 12 | 2 |
| 14 | 3 |
| 15 | 4 |
| novat | 6 |
| excento | 7 |

---

## 5. DETALLES (LINE ITEMS) MAPPING

### 5.1 Line-Level Mapping
| XML Element | Odoo Model | Odoo Field | Transformation |
|:------------|:-----------|:-----------|:---------------|
| `codigoPrincipal` | product.product | `default_code` | Max 25 chars, sanitized |
| `codigoAuxiliar` | product.product | `barcode` | Optional |
| `descripcion` | account.move.line | `name` | Max 300 chars, sanitized |
| `cantidad` | account.move.line | `quantity` | Decimal 6 places |
| `precioUnitario` | account.move.line | `price_unit` | Decimal 6 places |
| `descuento` | Computed | `(price_unit - priced) * quantity` | Decimal 2 places |
| `precioTotalSinImpuesto` | account.move.line | `price_subtotal` | Decimal 2 places |

### 5.2 Character Sanitization
```python
def fix_chars(code: str) -> str:
    """Remove special characters not allowed in SRI XML"""
    replacements = [
        ('%', ' '),
        ('º', ' '),
        ('Ñ', 'N'),
        ('ñ', 'n'),
        ('&', 'Y'),
        ('<', ' '),
        ('>', ' '),
    ]
    for old, new in replacements:
        code = code.replace(old, new)
    return code.strip()[:300]
```

---

## 6. IMPUESTOS (LINE TAXES) MAPPING

### 6.1 Per-Line Tax Mapping
| XML Element | Source | Transformation |
|:------------|:-------|:---------------|
| `codigo` | `tax.tax_group_id.code` | tabla17 lookup |
| `codigoPorcentaje` | `tax.percent_report` | tabla18 lookup |
| `tarifa` | `tax.amount` | Integer |
| `baseImponible` | `line.price_subtotal` | Decimal 2 places |
| `valor` | `price_subtotal * tax.amount / 100` | Decimal 2 places |

---

## 7. VALIDATION RULES

### 7.1 Pre-Transmission Validation
| Rule ID | Field | Validation | Error Message |
|:--------|:------|:-----------|:--------------|
| VAL-001 | `claveAcceso` | Exactly 49 chars | "Clave de acceso inválida" |
| VAL-002 | `ruc` | 13 digits + valid check | "RUC del emisor inválido" |
| VAL-003 | `identificacionComprador` | Per type (10/13 digits) | "Identificación comprador inválida" |
| VAL-004 | `totalSinImpuestos` | Sum of line subtotals | "Totales no cuadran" |
| VAL-005 | `importeTotal` | untaxed + taxes = total | "Importe total incorrecto" |
| VAL-006 | CF + >$50 | Block if vat='9999...' AND total>50 | "Monto excede límite CF" |

### 7.2 XSD Validation
```python
def validate_xml(self) -> bool:
    schema_path = 'schemas/factura.xsd'
    xmlschema = etree.XMLSchema(etree.parse(schema_path))
    try:
        xmlschema.assertValid(self.document)
        return True
    except DocumentInvalid as e:
        self.logger.error(f"XSD validation failed: {e}")
        return False
```

---

## 8. SAMPLE XML OUTPUT

```xml
<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="2.1.0">
  <infoTributaria>
    <ambiente>2</ambiente>
    <tipoEmision>1</tipoEmision>
    <razonSocial>EMPRESA DEMO S.A.</razonSocial>
    <nombreComercial>EMPRESA DEMO</nombreComercial>
    <ruc>1793125212001</ruc>
    <claveAcceso>2201202601179312521200120010010000000011234567811</claveAcceso>
    <codDoc>01</codDoc>
    <estab>001</estab>
    <ptoEmi>001</ptoEmi>
    <secuencial>000000001</secuencial>
    <dirMatriz>Av. Principal 123, Quito</dirMatriz>
  </infoTributaria>
  <infoFactura>
    <fechaEmision>22/01/2026</fechaEmision>
    <obligadoContabilidad>SI</obligadoContabilidad>
    <tipoIdentificacionComprador>04</tipoIdentificacionComprador>
    <razonSocialComprador>CLIENTE EJEMPLO CIA. LTDA.</razonSocialComprador>
    <identificacionComprador>1793125212001</identificacionComprador>
    <totalSinImpuestos>1000.00</totalSinImpuestos>
    <totalDescuento>0.00</totalDescuento>
    <totalConImpuestos>
      <totalImpuesto>
        <codigo>2</codigo>
        <codigoPorcentaje>4</codigoPorcentaje>
        <baseImponible>1000.00</baseImponible>
        <tarifa>15</tarifa>
        <valor>150.00</valor>
      </totalImpuesto>
    </totalConImpuestos>
    <propina>0.00</propina>
    <importeTotal>1150.00</importeTotal>
    <moneda>DOLAR</moneda>
    <pagos>
      <pago>
        <formaPago>20</formaPago>
        <total>1150.00</total>
      </pago>
    </pagos>
  </infoFactura>
  <detalles>
    <detalle>
      <codigoPrincipal>PROD-001</codigoPrincipal>
      <descripcion>PRODUCTO DE EJEMPLO</descripcion>
      <cantidad>10.000000</cantidad>
      <precioUnitario>100.000000</precioUnitario>
      <descuento>0.00</descuento>
      <precioTotalSinImpuesto>1000.00</precioTotalSinImpuesto>
      <impuestos>
        <impuesto>
          <codigo>2</codigo>
          <codigoPorcentaje>4</codigoPorcentaje>
          <tarifa>15</tarifa>
          <baseImponible>1000.00</baseImponible>
          <valor>150.00</valor>
        </impuesto>
      </impuestos>
    </detalle>
  </detalles>
</factura>
```

---

**Document Classification**: Data Mapping Specification
**Owner**: IT / Integration Team
**Last Updated**: 2026-01-22
