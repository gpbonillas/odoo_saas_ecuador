# SOFTWARE REQUIREMENTS SPECIFICATION
## Module: l10n_ec (Ecuador Base Localization)

**Document Identifier**: SRS-L10N-EC-BASE-001
**Version**: 1.0
**Date**: 2026-01-22
**Status**: APPROVED
**Standard**: ISO/IEC/IEEE 29148:2018

---

## 1. INTRODUCTION

### 1.1 Purpose
This Software Requirements Specification (SRS) describes the functional and non-functional requirements for the `l10n_ec` Odoo module. This module provides the foundational localization components for Ecuador, including the Chart of Accounts, Tax Structures, and Partner Identity Validation.

### 1.2 Scope
The `l10n_ec` module SHALL:
1. Provide an NEC-compliant Chart of Accounts Template.
2. Define Tax Groups and Tax Templates for IVA, ICE, and Income Tax.
3. Extend `res.partner` to support Ecuadorian identity types (RUC, Cédula, Pasaporte).
4. Extend `res.company` to store SRI environment configuration.

This module SHALL NOT:
- Implement electronic signing (delegated to `l10n_ec_edi`).
- Implement withholding documents (delegated to `l10n_ec_withholding`).

### 1.3 Definitions, Acronyms, and Abbreviations
| Term | Definition |
|:---|:---|
| **NEC** | Normas Ecuatorianas de Contabilidad (Ecuadorian Accounting Standards) |
| **NIIF** | Normas Internacionales de Información Financiera (IFRS) |
| **RUC** | Registro Único de Contribuyentes (Taxpayer ID - 13 digits) |
| **Cédula** | Ecuadorian National ID (10 digits) |
| **SRI** | Servicio de Rentas Internas (Internal Revenue Service) |
| **CoA** | Chart of Accounts |

### 1.4 References
- SRI Resolución NAC-DGERCGC14-00790 (Identity Validation)
- Superintendencia de Compañías - Plan de Cuentas (NEC)
- Odoo 18.0 Technical Documentation - Localizations

---

## 2. OVERALL DESCRIPTION

### 2.1 Product Perspective
The `l10n_ec` module is part of the Odoo 18.0 ERP ecosystem. It inherits from and extends:
- `account` (Odoo Enterprise Accounting)
- `l10n_latam_invoice_document` (Latin America Document Types)
- `base` (Core Odoo)

### 2.2 Product Functions
1. **F-BASE-001**: Chart of Accounts Installation
2. **F-BASE-002**: Tax Template Provisioning
3. **F-BASE-003**: Partner Identity Validation
4. **F-BASE-004**: Company SRI Configuration

### 2.3 User Classes and Characteristics
| User Class | Characteristics |
|:---|:---|
| **Accountant** | Manages CoA, Taxes, Fiscal Positions |
| **Administrator** | Configures Company SRI Settings |
| **Sales/Purchase User** | Selects Partner, Views Tax Info |

### 2.4 Operating Environment
- Odoo 18.0 Community/Enterprise
- PostgreSQL 14+
- Python 3.10+

### 2.5 Design and Implementation Constraints
- All account codes MUST follow NEC 9-digit structure.
- All tax rates MUST be configurable (not hardcoded).
- Identity validation MUST use Modulo 10/11 algorithms.

---

## 3. EXTERNAL INTERFACE REQUIREMENTS

### 3.1 User Interfaces
| Screen | Description |
|:---|:---|
| **Partner Form** | Extended with `l10n_ec_identifier_type` field |
| **Company Form** | Extended with SRI Environment Selection |
| **Tax Configuration** | Standard Odoo Accounting > Configuration > Taxes |

### 3.2 Hardware Interfaces
None.

### 3.3 Software Interfaces
| Interface | Description |
|:---|:---|
| **Odoo ORM** | All data access via Odoo models |
| **PostgreSQL** | Database storage |

### 3.4 Communications Interfaces
None (this module has no external API calls).

---

## 4. SPECIFIC REQUIREMENTS

### 4.1 Functional Requirements

#### 4.1.1 Chart of Accounts Template (F-BASE-001)
**REQ-F-001.1**: The system SHALL define an `account.chart.template` record with:
- `name` = "Ecuador - Plan de Cuentas NEC"
- `code_digits` = 9
- `currency_id` = USD

**REQ-F-001.2**: The system SHALL provide `account.account.template` records for ALL accounts defined in the Superintendencia de Compañías standard chart. Minimum 300 accounts.

**REQ-F-001.3**: The system SHALL auto-assign `account_type` based on account code prefix:
| Prefix | Account Type |
|:---|:---|
| 101 | `asset_current` |
| 102 | `asset_non_current` |
| 201 | `liability_current` |
| 202 | `liability_non_current` |
| 3 | `equity` |
| 4 | `income` |
| 5 | `expense` |

#### 4.1.2 Tax Template Provisioning (F-BASE-002)
**REQ-F-002.1**: The system SHALL define `account.tax.group` records:
| ID | Name | Sequence |
|:---|:---|:---|
| `tax_group_iva` | IVA | 10 |
| `tax_group_ice` | ICE | 20 |
| `tax_group_ret_renta` | Ret. Renta | 30 |
| `tax_group_ret_iva` | Ret. IVA | 40 |

**REQ-F-002.2**: The system SHALL define `account.tax.template` records for:
- IVA 15% (Sale/Purchase)
- IVA 5% (Sale/Purchase)
- IVA 0% (Sale/Purchase)
- IVA No Objeto
- IVA Exento

**REQ-F-002.3**: Each tax template SHALL include:
- `l10n_ec_code`: SRI numeric code (e.g., 2, 0, 6, 7)
- `l10n_ec_tax_support`: Sustento Tributario applicability

#### 4.1.3 Partner Identity Validation (F-BASE-003)
**REQ-F-003.1**: The `res.partner` model SHALL be extended with:
| Field | Type | Constraint |
|:---|:---|:---|
| `l10n_ec_identifier_type` | Selection | Required if `country_id` = Ecuador |
| `l10n_ec_is_forced_accounting` | Boolean | Optional |
| `l10n_ec_taxpayer_type` | Selection | Optional |

**REQ-F-003.2**: The system SHALL validate `vat` field on save:
- If `l10n_ec_identifier_type` = 'ruc': Length = 13, Valid Modulo 11
- If `l10n_ec_identifier_type` = 'cedula': Length = 10, Valid Modulo 10
- If `l10n_ec_identifier_type` = 'pasaporte': Length >= 5, No special validation

**REQ-F-003.3**: Validation Algorithm for Cédula (Modulo 10):
```
1. First 2 digits = Province (01-24)
2. Third digit < 6
3. Sum of (digit * weight) where weight cycles [2,1,2,1...]
4. If digit*weight > 9, subtract 9
5. Check digit = (10 - (sum % 10)) % 10
```

**REQ-F-003.4**: Validation Algorithm for RUC (Modulo 11):
```
1. First 2 digits = Province (01-24 or 30)
2. Third digit determines entity type:
   - < 6: Natural Person (Modulo 10 on first 10 digits)
   - = 6: Public Entity (Modulo 11, coefficients [3,2,7,6,5,4,3,2])
   - = 9: Private Juridical (Modulo 11, coefficients [4,3,2,7,6,5,4,3,2])
3. Last 3 digits = Establishment (usually 001)
```

#### 4.1.4 Company SRI Configuration (F-BASE-004)
**REQ-F-004.1**: The `res.company` model SHALL be extended with:
| Field | Type | Description |
|:---|:---|:---|
| `l10n_ec_sri_environment` | Selection | 'test' or 'production' |
| `l10n_ec_emission_type` | Selection | '1' (Normal) |
| `l10n_ec_withhold_agent` | Boolean | Is Agent of Retention? |
| `l10n_ec_withhold_resolution` | Char | SRI Resolution Number |
| `l10n_ec_rimpe` | Boolean | Is RIMPE Contributor? |
| `l10n_ec_rimpe_type` | Selection | 'popular' or 'emprendedor' |

### 4.2 Data Requirements

#### 4.2.1 Data Dictionary
| Entity | Attributes | Constraints |
|:---|:---|:---|
| `account.chart.template` | name, code_digits, currency_id, country_id | Unique per country |
| `account.account.template` | code, name, account_type, chart_template_id | code unique per chart |
| `account.tax.template` | name, amount, type_tax_use, tax_group_id | - |

#### 4.2.2 Data Volume
- Accounts: ~500 records
- Taxes: ~100 records
- Fiscal Positions: ~20 records

### 4.3 Interface Requirements
None (internal Odoo module).

### 4.4 Security Requirements
**REQ-S-001**: Only users in group `account.group_account_manager` SHALL modify tax/account templates.

---

## 5. USE CASES

### 5.1 UC-001: Install Chart of Accounts
**Actor**: Administrator
**Precondition**: New database created
**Flow**:
1. User navigates to Invoicing > Configuration > Settings.
2. User selects "Ecuador - Plan de Cuentas NEC".
3. System creates all accounts, taxes, fiscal positions.
**Postcondition**: CoA installed and ready.

### 5.2 UC-002: Create Partner with RUC Validation
**Actor**: Salesperson
**Precondition**: CoA installed
**Flow**:
1. User creates new Partner.
2. User sets Country = Ecuador.
3. User selects Identifier Type = RUC.
4. User enters 13-digit RUC.
5. System validates Modulo 11.
6. If valid, Partner saved. If invalid, error displayed.
**Postcondition**: Partner created with validated RUC.

---

## 6. VALIDATION CRITERIA

### 6.1 Acceptance Tests
| Test ID | Description | Expected Result |
|:---|:---|:---|
| **T-001** | Install CoA on fresh database | All accounts created |
| **T-002** | Enter valid RUC (1793125212001) | Partner saves successfully |
| **T-003** | Enter invalid RUC (1234567890123) | Validation error displayed |
| **T-004** | Enter valid Cédula (1713488185) | Partner saves successfully |

---

## 7. APPENDICES

### 7.1 Modulo 10 Validation Code (Reference)
```python
def validate_cedula(cedula: str) -> bool:
    if len(cedula) != 10 or not cedula.isdigit():
        return False
    province = int(cedula[:2])
    if province < 1 or province > 24:
        return False
    third = int(cedula[2])
    if third >= 6:
        return False
    coefficients = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i in range(9):
        val = int(cedula[i]) * coefficients[i]
        total += val if val < 10 else val - 9
    check = (10 - (total % 10)) % 10
    return check == int(cedula[9])
```

---

**Document Control**:
| Version | Date | Author | Changes |
|:---|:---|:---|:---|
| 1.0 | 2026-01-22 | Antigravity | Initial Release |
