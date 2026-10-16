# SOFTWARE REQUIREMENTS SPECIFICATION
## Module: l10n_ec_reports (Ecuador Compliance Reporting)

**Document Identifier**: SRS-L10N-EC-REPORTS-001
**Version**: 1.0
**Date**: 2026-01-22
**Status**: APPROVED
**Standard**: ISO/IEC/IEEE 29148:2018

---

## 1. INTRODUCTION

### 1.1 Purpose
This SRS describes the requirements for the `l10n_ec_reports` module, which generates all mandatory tax and financial reports required by SRI, IESS, and Superintendencia de Compañías.

### 1.2 Scope
The module SHALL generate:
1. **ATS** - Anexo Transaccional Simplificado (Monthly)
2. **Form 103** - Retenciones en la Fuente (Monthly)
3. **Form 104** - Declaración IVA (Monthly)
4. **Form 101** - Impuesto a la Renta Sociedades (Annual)
5. **Form 102** - Impuesto a la Renta Personas (Annual)
6. **RDEP** - Reporte de Dividendos (Annual)
7. **Supercias** - Estados Financieros NIIF (Annual)

### 1.3 Legal References
- SRI Resolución NAC-DGERCGC12-00001
- Supercias Resolución SCVS-INC-DNCDN-2019-0010
- Código Tributario

---

## 2. EXPERT CREW PERSPECTIVES

### 2.1 CFO Perspective (María Finanzas)
> "ATS is the most critical report. Any mismatch between our invoices and what we declare triggers an audit. The system must cross-check before generating."

### 2.2 Compliance Officer Perspective (Sofía Cumplimiento)
> "We have until the 28th of the following month to file. The system should alert us 5 days before deadline. Late filing = 3% monthly penalty."

### 2.3 Legal Counsel Perspective (Elena Derecho)
> "Form 101 affects our tax liability for the entire year. Every deduction must be justified. The report should flag any suspicious items."

---

## 3. SPECIFIC REQUIREMENTS

### 3.1 ATS (Anexo Transaccional Simplificado)

#### 3.1.1 Structure
```xml
<ats version="1.0">
    <TipoIDInformante>R</TipoIDInformante>
    <IdInformante>1793125212001</IdInformante>
    <razonSocial>MI EMPRESA S.A.</razonSocial>
    <Anio>2026</Anio>
    <Mes>01</Mes>
    <numEstabRuc>001</numEstabRuc>
    <totalVentas>150000.00</totalVentas>
    <codigoOperativo>IVA</codigoOperativo>
    <compras>
        <detalleCompras>
            <codSustento>01</codSustento>
            <tpIdProv>01</tpIdProv>
            <idProv>1793125212001</idProv>
            <tipoComprobante>01</tipoComprobante>
            <parteRel>NO</parteRel>
            <fechaRegistro>22/01/2026</fechaRegistro>
            <establecimiento>001</establecimiento>
            <puntoEmision>001</puntoEmision>
            <secuencial>000000123</secuencial>
            <fechaEmision>20/01/2026</fechaEmision>
            <autorizacion>2001202601179312521200110010010000001231234567811</autorizacion>
            <baseNoGraIva>0.00</baseNoGraIva>
            <baseImponible>1000.00</baseImponible>
            <baseImpGrav>1000.00</baseImpGrav>
            <baseImpExe>0.00</baseImpExe>
            <montoIce>0.00</montoIce>
            <montoIva>150.00</montoIva>
            <valorRetBienes>0.00</valorRetBienes>
            <valorRetServicios>17.50</valorRetServicios>
            <valRetBien10>0.00</valRetBien10>
            <valRetServ20>0.00</valRetServ20>
            <valorRetBienes>0.00</valorRetBienes>
            <valRetServ50>0.00</valRetServ50>
            <pagoExterior>
                <pagoLocExt>01</pagoLocExt>
            </pagoExterior>
            <formasDePago>
                <formaPago>20</formaPago>
            </formasDePago>
            <air>
                <detalleAir>
                    <codRetAir>312</codRetAir>
                    <baseImpAir>1000.00</baseImpAir>
                    <porcentajeAir>1.75</porcentajeAir>
                    <valRetAir>17.50</valRetAir>
                </detalleAir>
            </air>
        </detalleCompras>
    </compras>
    <ventas>
        <detalleVentas>
            <tpIdCliente>04</tpIdCliente>
            <idCliente>1793125212001</idCliente>
            <parteRelVtas>NO</parteRelVtas>
            <tipoComprobante>18</tipoComprobante>
            <tipoEmision>E</tipoEmision>
            <numeroComprobantes>50</numeroComprobantes>
            <baseNoGraIva>0.00</baseNoGraIva>
            <baseImponible>50000.00</baseImponible>
            <baseImpGrav>50000.00</baseImpGrav>
            <montoIva>7500.00</montoIva>
            <montoIce>0.00</montoIce>
            <valorRetIva>0.00</valorRetIva>
            <valorRetRenta>500.00</valorRetRenta>
        </detalleVentas>
    </ventas>
    <ventasEstablecimiento>
        <ventaEst>
            <codEstab>001</codEstab>
            <ventasEstab>150000.00</ventasEstab>
            <ivaComp>22500.00</ivaComp>
        </ventaEst>
    </ventasEstablecimiento>
</ats>
```

#### 3.1.2 Data Sources
| ATS Section | Odoo Source |
|:---|:---|
| `compras` | `account.move` where `move_type` in ['in_invoice', 'in_refund'] |
| `ventas` | `account.move` where `move_type` in ['out_invoice', 'out_refund'] |
| `retenciones` | `account.retention` |
| `exportaciones` | `account.move` where `l10n_ec_is_export = True` |

#### 3.1.3 Validation Rules
**REQ-ATS-001**: Before generating, validate:
- All invoices have `l10n_ec_sustento_id` set.
- All invoices have valid `l10n_ec_auth_number`.
- All retentions are authorized.
- No orphan retentions (retention without linked invoice).

**REQ-ATS-002**: Cross-check totals:
- Sum of `baseImponible` must match GL account movements.
- Sum of `montoIva` must match tax account movements.

### 3.2 Form 104 (IVA Declaration)

#### 3.2.1 Structure
| Field | Description | Source |
|:---|:---|:---|
| **411** | Ventas Locales Tarifa 15% | `account.move` (sales, tax 15%) |
| **412** | Ventas Locales Tarifa 0% | `account.move` (sales, tax 0%) |
| **415** | Exportaciones | `l10n_ec_is_export = True` |
| **421** | Adquisiciones Tarifa 15% | `account.move` (purchases, tax 15%) |
| **422** | Adquisiciones Tarifa 0% | `account.move` (purchases, tax 0%) |
| **480** | IVA en Ventas | Computed |
| **520** | IVA en Compras | Computed |
| **601** | Retenciones Recibidas | `account.retention` (received) |
| **699** | Impuesto a Pagar | Computed |

### 3.3 Form 103 (Withholding Declaration)

#### 3.3.1 Structure
| Field | Description | Source |
|:---|:---|:---|
| **302** | Honorarios Profesionales | Tax code 303 |
| **303** | Servicios Intelecto | Tax code 304 |
| **307** | Servicios Mano Obra | Tax code 307 |
| **310** | Transporte | Tax code 310 |
| **312** | Transferencia Bienes | Tax code 312 |
| **320** | Arrendamiento | Tax code 320 |
| **721** | Retención IVA 30% | Tax code 721 |
| **723** | Retención IVA 70% | Tax code 723 |
| **725** | Retención IVA 100% | Tax code 725 |

### 3.4 Supercias Financial Statements

#### 3.4.1 Required Statements
| Statement | Format | Reference |
|:---|:---|:---|
| Estado de Situación Financiera | Balance | NIIF NIC 1 |
| Estado de Resultados Integral | P&L | NIIF NIC 1 |
| Estado de Cambios Patrimonio | Equity | NIIF NIC 1 |
| Estado de Flujos de Efectivo | Cash Flow | NIIF NIC 7 |

#### 3.4.2 Account Mapping
| Supercias Code | Description | Odoo Account Type |
|:---|:---|:---|
| 1 | ACTIVO | asset_current, asset_non_current |
| 1.01 | Activo Corriente | asset_current |
| 1.02 | Activo No Corriente | asset_non_current, asset_fixed |
| 2 | PASIVO | liability_current, liability_non_current |
| 3 | PATRIMONIO | equity |
| 4 | INGRESOS | income |
| 5 | COSTOS Y GASTOS | expense |

---

## 4. USE CASES

### 4.1 UC-001: Generate Monthly ATS
**Actor**: Accountant
**Flow**:
1. User navigates to Accounting > Reports > ATS.
2. User selects Year/Month.
3. User clicks "Generate".
4. System validates all source data.
5. System displays validation errors (if any).
6. User corrects errors.
7. System generates XML.
8. User downloads and uploads to SRI portal.

### 4.2 UC-002: Generate Annual Form 101
**Actor**: CFO
**Flow**:
1. User navigates to Accounting > Reports > Form 101.
2. User selects Fiscal Year.
3. System aggregates all income/expense.
4. System computes taxable income.
5. System shows draft form.
6. CFO reviews and adjusts.
7. System generates PDF for filing.

---

## 5. VALIDATION CRITERIA

| Test ID | Description | Expected |
|:---|:---|:---|
| **T-RPT-001** | ATS XML validates against XSD | Valid |
| **T-RPT-002** | Form 104 totals match GL | Balanced |
| **T-RPT-003** | Supercias Balance Sheet | A = P + E |
| **T-RPT-004** | ATS with orphan retention | Error shown |

---

## 6. DEADLINE CALENDAR

| Report | Period | Deadline | Penalty |
|:---|:---|:---|:---|
| **ATS** | Monthly | 28th of following month | 3%/month |
| **Form 104** | Monthly | 28th of following month | 3%/month |
| **Form 103** | Monthly | 28th of following month | 3%/month |
| **Form 101** | Annual | April | 3%/month |
| **Supercias** | Annual | April | Company status issue |

---

**Document Control**:
| Version | Date | Author |
|:---|:---|:---|
| 1.0 | 2026-01-22 | Expert Crew (CFO, Compliance, Legal) |
