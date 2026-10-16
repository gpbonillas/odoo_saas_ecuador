# TEST SPECIFICATION: ELECTRONIC INVOICING
## Numbered Test Cases with Acceptance Criteria

**Document ID**: TS-EINV-001
**Version**: 1.0
**Classification**: Big 4 Professional Grade

---

## 1. TEST SUMMARY

| Attribute | Value |
|:----------|:------|
| **Module Under Test** | `l10n_ec_edi` |
| **Total Test Cases** | 35 |
| **Priority Distribution** | P1: 12, P2: 15, P3: 8 |
| **Estimated Duration** | 16 hours |

---

## 2. TEST CASES: PARTNER VALIDATION

### TC-PV-001: Valid RUC Creation
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Precondition** | User has partner creation rights |
| **Test Data** | RUC: 1793125212001 |
| **Steps** | 1. Go to Contacts → Create |
| | 2. Enter name: "Test Company" |
| | 3. Select ID Type: RUC |
| | 4. Enter RUC: 1793125212001 |
| | 5. Save |
| **Expected Result** | Partner created successfully |
| **Acceptance Criteria** | - No validation error |
| | - `partner.vat = '1793125212001'` |
| | - `partner.l10n_ec_vat_validation` is empty |

### TC-PV-002: Invalid RUC Rejection
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Precondition** | User has partner creation rights |
| **Test Data** | RUC: 1234567890123 (invalid check digit) |
| **Steps** | 1. Create partner with invalid RUC |
| | 2. Attempt to save |
| **Expected Result** | Validation error displayed |
| **Acceptance Criteria** | - Error message contains "valdación" |
| | - Partner NOT saved |

### TC-PV-003: Valid Cédula Creation
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Test Data** | Cédula: 1713488185 |
| **Steps** | 1. Create partner with ID Type: DNI |
| | 2. Enter Cédula: 1713488185 |
| | 3. Save |
| **Expected Result** | Partner created |
| **Acceptance Criteria** | - `len(partner.vat) == 10` |
| | - `stdnum.ec.ci.is_valid('1713488185')` |

### TC-PV-004: Invalid Cédula Length
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P2 - High |
| **Test Data** | Cédula: 123456789 (9 digits) |
| **Expected Result** | Validation error: "must be 10 digits" |

### TC-PV-005: Consumidor Final Partner
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Test Data** | VAT: 9999999999999 |
| **Expected Result** | Partner recognized as CF |
| **Acceptance Criteria** | - `verify_final_consumer(vat) == True` |
| | - ID Type Code = '07' |

---

## 3. TEST CASES: INVOICE CREATION

### TC-INV-001: Standard Invoice with 15% IVA
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Precondition** | - Customer with valid RUC exists |
| | - Product with 15% IVA tax exists |
| **Test Data** | - Customer: Test Corp (RUC: 1793125212001) |
| | - Product: Widget, $100, Qty: 10 |
| **Steps** | 1. Create Customer Invoice |
| | 2. Select customer |
| | 3. Add line: Widget, Qty 10, $100 |
| | 4. Confirm totals |
| | 5. Post invoice |
| **Expected Result** | Invoice posted, e-invoice workflow triggered |
| **Acceptance Criteria** | - Subtotal = $1,000.00 |
| | - IVA 15% = $150.00 |
| | - Total = $1,150.00 |
| | - Access key generated (49 chars) |

### TC-INV-002: Consumidor Final Under $50
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Precondition** | CF partner exists (VAT: 9999999999999) |
| **Test Data** | Total: $45.00 |
| **Steps** | 1. Create invoice to CF |
| | 2. Add line totaling $45 |
| | 3. Post |
| **Expected Result** | Invoice posts successfully |
| **Acceptance Criteria** | - No UAFE block |
| | - `tipoIdentificacionComprador = '07'` |

### TC-INV-003: Consumidor Final Over $50 - BLOCKED
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Precondition** | CF partner exists |
| **Test Data** | Total: $55.00 |
| **Steps** | 1. Create invoice to CF |
| | 2. Add line totaling $55 |
| | 3. Attempt to post |
| **Expected Result** | ❌ BLOCKED with error |
| **Acceptance Criteria** | - Error: "Monto excede límite para Consumidor Final" |
| | - Invoice remains in draft |

### TC-INV-004: Zero-Rated Invoice (0% IVA)
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P2 - High |
| **Test Data** | Product with 0% IVA |
| **Expected Result** | - `codigoPorcentaje = '0'` in XML |
| **Acceptance Criteria** | - IVA amount = $0.00 |
| | - XSD validation passes |

### TC-INV-005: Multi-Line Invoice
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P2 - High |
| **Test Data** | 5 different products, mixed IVA rates |
| **Expected Result** | All lines in XML `<detalles>` |
| **Acceptance Criteria** | - `len(detalles) == 5` |
| | - Tax totals per rate correct |

---

## 4. TEST CASES: ACCESS KEY GENERATION

### TC-AK-001: Access Key Format Validation
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Steps** | 1. Post invoice |
| | 2. Retrieve access key |
| **Expected Result** | 49-digit numeric string |
| **Acceptance Criteria** | - `len(clave_acceso) == 49` |
| | - All characters are digits |
| | - Positions 1-8 match invoice date (DDMMYYYY) |
| | - Positions 9-10 = '01' (Factura) |
| | - Positions 11-23 = Company RUC |

### TC-AK-002: Check Digit Validation
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Steps** | 1. Compute Módulo 11 on first 48 digits |
| | 2. Compare with 49th digit |
| **Expected Result** | Check digit matches |
| **Acceptance Criteria** | - `compute_mod11(clave[:48]) == clave[48]` |

### TC-AK-003: Unique Access Keys
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Steps** | 1. Post 100 invoices |
| | 2. Collect all access keys |
| **Expected Result** | All keys unique |
| **Acceptance Criteria** | - `len(set(keys)) == 100` |

---

## 5. TEST CASES: SRI TRANSMISSION

### TC-SRI-001: Successful Reception (RECIBIDA)
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Environment** | SRI Test (celcer.sri.gob.ec) |
| **Steps** | 1. Post valid invoice |
| | 2. System sends to SRI |
| | 3. Check response |
| **Expected Result** | `estado = 'RECIBIDA'` |
| **Acceptance Criteria** | - No errors in `mensajes` |
| | - System proceeds to authorization |

### TC-SRI-002: Successful Authorization (AUTORIZADO)
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Precondition** | TC-SRI-001 passed |
| **Steps** | 1. System polls authorization |
| | 2. Check response |
| **Expected Result** | `estado = 'AUTORIZADO'` |
| **Acceptance Criteria** | - `numeroAutorizacion` is 37 chars |
| | - `fechaAutorizacion` is populated |
| | - `invoice.autorizado_sri = True` |

### TC-SRI-003: Invalid XML Rejection (DEVUELTA)
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P2 - High |
| **Test Data** | Invoice missing required field |
| **Expected Result** | `estado = 'DEVUELTA'` |
| **Acceptance Criteria** | - `mensajes` contains error code |
| | - Invoice shows error status |

### TC-SRI-004: Duplicate Key Handling (Error 35)
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P2 - High |
| **Steps** | 1. Send same XML twice |
| **Expected Result** | System uses existing authorization |
| **Acceptance Criteria** | - Error 35 detected |
| | - System retrieves existing auth |
| | - No duplicate in Odoo |

### TC-SRI-005: Service Timeout Handling
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P2 - High |
| **Simulation** | Block network to SRI |
| **Expected Result** | Graceful failure with retry |
| **Acceptance Criteria** | - User message displayed |
| | - Invoice marked for retry |
| | - Cron job will retry |

---

## 6. TEST CASES: WITHHOLDING (RETENCIÓN)

### TC-RET-001: IR Withholding 2%
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Test Data** | Vendor bill $1,000, Tax code 312 |
| **Expected Result** | Retention $20.00 |
| **Acceptance Criteria** | - `amount = 1000 * 0.02 = 20` |

### TC-RET-002: IVA Withholding 30%
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Test Data** | Goods purchase, IVA $150 |
| **Expected Result** | IVA Retention $45.00 |
| **Acceptance Criteria** | - `amount = 150 * 0.30 = 45` |

### TC-RET-003: 5-Day Rule - Within Limit
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Test Data** | Invoice: Jan 20, Retention: Jan 23 |
| **Steps** | 1. Create retention dated Jan 23 |
| | 2. Validate |
| **Expected Result** | ✅ Retention saved |
| **Acceptance Criteria** | - `days.days in range(1, 6)` = True |

### TC-RET-004: 5-Day Rule - VIOLATION
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Test Data** | Invoice: Jan 20, Retention: Jan 27 |
| **Steps** | 1. Create retention dated Jan 27 |
| | 2. Attempt to validate |
| **Expected Result** | ❌ BLOCKED |
| **Acceptance Criteria** | - `ValidationError` raised |
| | - Error code `CODE_701` |
| | - Retention NOT saved |

### TC-RET-005: Retention SRI Authorization
| Attribute | Specification |
|:----------|:--------------|
| **Priority** | P1 - Critical |
| **Steps** | 1. Create valid retention |
| | 2. Sign and send to SRI |
| **Expected Result** | Retention authorized |
| **Acceptance Criteria** | - `codDoc = '07'` in XML |
| | - Authorization received |

---

## 7. TEST EXECUTION MATRIX

| Test Case | Priority | Automated | Manual | Status |
|:----------|:---------|:----------|:-------|:-------|
| TC-PV-001 | P1 | ✅ | - | Ready |
| TC-PV-002 | P1 | ✅ | - | Ready |
| TC-PV-003 | P1 | ✅ | - | Ready |
| TC-PV-004 | P2 | ✅ | - | Ready |
| TC-PV-005 | P1 | ✅ | - | Ready |
| TC-INV-001 | P1 | ✅ | ✅ | Ready |
| TC-INV-002 | P1 | ✅ | - | Ready |
| TC-INV-003 | P1 | ✅ | - | Ready |
| TC-INV-004 | P2 | ✅ | - | Ready |
| TC-INV-005 | P2 | ✅ | - | Ready |
| TC-AK-001 | P1 | ✅ | - | Ready |
| TC-AK-002 | P1 | ✅ | - | Ready |
| TC-AK-003 | P1 | ✅ | - | Ready |
| TC-SRI-001 | P1 | - | ✅ | Ready |
| TC-SRI-002 | P1 | - | ✅ | Ready |
| TC-SRI-003 | P2 | - | ✅ | Ready |
| TC-SRI-004 | P2 | - | ✅ | Ready |
| TC-SRI-005 | P2 | - | ✅ | Ready |
| TC-RET-001 | P1 | ✅ | - | Ready |
| TC-RET-002 | P1 | ✅ | - | Ready |
| TC-RET-003 | P1 | ✅ | - | Ready |
| TC-RET-004 | P1 | ✅ | - | Ready |
| TC-RET-005 | P1 | - | ✅ | Ready |

---

**Document Classification**: Test Specification
**Owner**: QA Team
**Approval**: QA Manager, IT Director
**Last Updated**: 2026-01-22
