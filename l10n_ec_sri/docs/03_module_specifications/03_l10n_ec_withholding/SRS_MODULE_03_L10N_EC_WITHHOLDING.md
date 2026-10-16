# SOFTWARE REQUIREMENTS SPECIFICATION
## Module: l10n_ec_withholding (Ecuador Withholding Taxes)

**Document Identifier**: SRS-L10N-EC-WITHHOLDING-001
**Version**: 1.0
**Date**: 2026-01-22
**Status**: APPROVED
**Standard**: ISO/IEC/IEEE 29148:2018

---

## 1. INTRODUCTION

### 1.1 Purpose
This SRS describes the requirements for the `l10n_ec_withholding` module, which implements the generation, electronic signing, and transmission of "Comprobantes de Retención" (Withholding Certificates) to the SRI.

### 1.2 Scope
The module SHALL:
1. Define a new model `account.retention` for withholding documents.
2. Support withholding on both Income Tax (Renta) and IVA.
3. Validate the "5-day rule" for retention date vs invoice date.
4. Generate XML compliant with SRI schema `comprobanteRetencion_v2.0.0.xsd`.
5. Integrate with `l10n_ec_edi` for signing and transmission.

### 1.3 Definitions
| Term | Definition |
|:---|:---|
| **Retención** | Withholding certificate issued when paying a vendor |
| **Base Imponible** | Taxable base amount before tax |
| **Código de Retención** | SRI Code for the withholding type (e.g., 303, 312) |
| **5-Day Rule** | Retention must be issued within 5 days of invoice date |

### 1.4 References
- SRI Resolución NAC-DGERCGC15-00000284
- Ficha Técnica - Comprobante de Retención v2.0.0
- Odoo 18.0 Account Module Documentation

---

## 2. OVERALL DESCRIPTION

### 2.1 Product Perspective
This module creates a new document type that links to `account.move` (Vendor Bills). When a company pays a vendor, they may be required to withhold a percentage of the payment and remit it to SRI.

### 2.2 Product Functions
1. **F-RET-001**: Create Retention Document
2. **F-RET-002**: Validate Date Constraints
3. **F-RET-003**: Compute Retention Amounts
4. **F-RET-004**: Generate Retention XML
5. **F-RET-005**: Electronic Authorization

### 2.3 User Classes
| User | Role |
|:---|:---|
| **Accountant** | Creates and validates retentions |
| **Auditor** | Reviews retention history |

### 2.4 Constraints
- Retention MUST link to exactly one Vendor Bill.
- Date MUST be within 5 calendar days of invoice date.
- Retention sequential MUST be unique per establishment.

---

## 3. EXTERNAL INTERFACE REQUIREMENTS

### 3.1 User Interfaces
| Screen | Elements |
|:---|:---|
| **Vendor Bill Form** | Button "Create Retention" |
| **Retention Form** | Header (Date, Sequential), Lines (Tax Code, Base, Amount) |
| **Retention List** | Filterable by State (Draft/Authorized/Rejected) |

### 3.2 Software Interfaces
| Interface | Module |
|:---|:---|
| `account.move` | Link to source invoice |
| `l10n_ec_edi` | Signing and transmission |

---

## 4. SPECIFIC REQUIREMENTS

### 4.1 Functional Requirements

#### 4.1.1 Data Model: `account.retention`
**REQ-F-001.1**: The model SHALL contain:
| Field | Type | Constraints | Description |
|:---|:---|:---|:---|
| `name` | Char | Computed | Format: `001-001-000000001` |
| `date` | Date | Required | Retention issue date |
| `invoice_id` | Many2one | Required | Link to `account.move` |
| `partner_id` | Many2one | Related | From invoice |
| `company_id` | Many2one | Required | Issuing company |
| `state` | Selection | Default='draft' | `draft`, `done`, `cancelled` |
| `l10n_ec_access_key` | Char(49) | Computed | SRI Access Key |
| `l10n_ec_edi_state` | Selection | - | `draft`, `signed`, `authorized`, `rejected` |
| `line_ids` | One2many | - | Retention lines |
| `total_retained` | Monetary | Computed | Sum of line amounts |

#### 4.1.2 Data Model: `account.retention.line`
**REQ-F-001.2**: The line model SHALL contain:
| Field | Type | Description |
|:---|:---|:---|
| `retention_id` | Many2one | Parent retention |
| `tax_id` | Many2one | Link to `account.tax` (withholding type) |
| `base` | Monetary | Base imponible |
| `percentage` | Float | Retention percentage |
| `amount` | Monetary | Computed: base * percentage / 100 |
| `l10n_ec_code` | Char | SRI Tax Code (from tax) |

#### 4.1.3 Date Validation (F-RET-002)
**REQ-F-002.1**: On save, the system SHALL validate:
```python
@api.constrains('date', 'invoice_id')
def _check_retention_date(self):
    for rec in self:
        invoice_date = rec.invoice_id.invoice_date
        retention_date = rec.date
        delta = (retention_date - invoice_date).days
        if delta < 0 or delta > 5:
            raise ValidationError(
                "La retención debe emitirse dentro de los 5 días "
                "posteriores a la fecha de la factura."
            )
```

#### 4.1.4 Amount Computation (F-RET-003)
**REQ-F-003.1**: Line amounts SHALL compute:
```python
@api.depends('base', 'percentage')
def _compute_amount(self):
    for line in self:
        line.amount = line.base * line.percentage / 100
```

**REQ-F-003.2**: Total retained SHALL compute:
```python
@api.depends('line_ids.amount')
def _compute_total(self):
    for rec in self:
        rec.total_retained = sum(rec.line_ids.mapped('amount'))
```

#### 4.1.5 XML Generation (F-RET-004)
**REQ-F-004.1**: XML Structure:
```xml
<comprobanteRetencion id="comprobante" version="2.0.0">
    <infoTributaria>
        <!-- Same as Invoice -->
        <codDoc>07</codDoc>
    </infoTributaria>
    <infoCompRetencion>
        <fechaEmision>22/01/2026</fechaEmision>
        <dirEstablecimiento>...</dirEstablecimiento>
        <obligadoContabilidad>SI</obligadoContabilidad>
        <tipoIdentificacionSujetoRetenido>04</tipoIdentificacionSujetoRetenido>
        <razonSocialSujetoRetenido>Proveedor XYZ</razonSocialSujetoRetenido>
        <identificacionSujetoRetenido>1793125212001</identificacionSujetoRetenido>
        <periodoFiscal>01/2026</periodoFiscal>
    </infoCompRetencion>
    <docsSustento>
        <docSustento>
            <codSustento>01</codSustento>
            <codDocSustento>01</codDocSustento>
            <numDocSustento>001-001-000000123</numDocSustento>
            <fechaEmisionDocSustento>20/01/2026</fechaEmisionDocSustento>
            <fechaRegistroContable>22/01/2026</fechaRegistroContable>
            <numAutDocSustento>22012026011793125212001...</numAutDocSustento>
            <pagoLocExt>01</pagoLocExt>
            <totalSinImpuestos>1000.00</totalSinImpuestos>
            <importeTotal>1150.00</importeTotal>
            <impuestosDocSustento>
                <impuestoDocSustento>
                    <codImpuestoDocSustento>2</codImpuestoDocSustento>
                    <codigoPorcentaje>4</codigoPorcentaje>
                    <baseImponible>1000.00</baseImponible>
                    <tarifa>15</tarifa>
                    <valorImpuesto>150.00</valorImpuesto>
                </impuestoDocSustento>
            </impuestosDocSustento>
            <retenciones>
                <retencion>
                    <codigo>1</codigo>
                    <codigoRetencion>312</codigoRetencion>
                    <baseImponible>1000.00</baseImponible>
                    <porcentajeRetener>1.75</porcentajeRetener>
                    <valorRetenido>17.50</valorRetenido>
                </retencion>
                <retencion>
                    <codigo>2</codigo>
                    <codigoRetencion>725</codigoRetencion>
                    <baseImponible>150.00</baseImponible>
                    <porcentajeRetener>30</porcentajeRetener>
                    <valorRetenido>45.00</valorRetenido>
                </retencion>
            </retenciones>
            <pagos>
                <pago>
                    <formaPago>20</formaPago>
                    <total>1087.50</total>
                </pago>
            </pagos>
        </docSustento>
    </docsSustento>
    <infoAdicional>
        <campoAdicional nombre="Email">proveedor@example.com</campoAdicional>
    </infoAdicional>
</comprobanteRetencion>
```

#### 4.1.6 Sequencing (F-RET-006)
**REQ-F-006.1**: The retention number SHALL follow format:
`{establishment}-{emission_point}-{9_digit_sequential}`

**REQ-F-006.2**: The system SHALL create `ir.sequence` per company:
```python
sequence = self.env['ir.sequence'].create({
    'name': 'Retención Ecuador',
    'code': 'l10n_ec.retention',
    'prefix': '%(l10n_ec_establishment)s-%(l10n_ec_emission)s-',
    'padding': 9,
})
```

---

## 5. USE CASES

### 5.1 UC-001: Create Retention from Vendor Bill
**Actor**: Accountant
**Precondition**: Vendor Bill in state 'posted'
**Flow**:
1. User opens Vendor Bill.
2. User clicks "Create Retention".
3. System creates draft retention linked to bill.
4. System pre-fills partner, date (today), and proposes taxes based on fiscal position.
5. User reviews/adjusts retention lines.
6. User clicks "Validate".
7. System validates 5-day rule.
8. System assigns sequential number.
9. System triggers EDI signing and transmission.
**Postcondition**: Retention authorized by SRI.

### 5.2 UC-002: Reject Invalid Retention Date
**Actor**: Accountant
**Precondition**: Invoice dated 10 days ago
**Flow**:
1. User attempts to create retention.
2. System raises ValidationError: "5-day rule violated".
**Postcondition**: Retention not created.

---

## 6. VALIDATION CRITERIA

| Test ID | Description | Expected |
|:---|:---|:---|
| **T-RET-001** | Create retention within 5 days | Success |
| **T-RET-002** | Create retention after 5 days | ValidationError |
| **T-RET-003** | Verify XML against XSD | Valid |
| **T-RET-004** | Send to SRI Test | Authorized |
| **T-RET-005** | Duplicate sequential | Constraint Error |

---

## 7. APPENDICES

### 7.1 Retention Tax Codes Reference
| Type | Code | Description |
|:---|:---|:---|
| **Renta** | 1 | Impuesto a la Renta |
| **IVA** | 2 | Retención de IVA |
| **ISD** | 6 | Impuesto Salida Divisas |

### 7.2 Retention Percentage Codes (Renta)
| Code | % | Concept |
|:---|:---|:---|
| 303 | 10% | Honorarios Profesionales |
| 304 | 8% | Servicios Intelecto |
| 312 | 1% | Bienes Muebles |
| 320 | 1.75% | Arrendamiento |

---

**Document Control**:
| Version | Date | Author |
|:---|:---|:---|
| 1.0 | 2026-01-22 | Antigravity (World's #1 Odoo Expert) |
