# CONFIGURATION CHECKLIST: SRI ELECTRONIC INVOICING
## Step-by-Step Setup Guide

**Document ID**: CC-SRI-001
**Version**: 1.0
**Classification**: Big 4 Professional Grade

---

## 1. PRE-REQUISITES CHECKLIST

### 1.1 Infrastructure Requirements
| # | Requirement | Status | Verified By |
|:--|:------------|:-------|:------------|
| 1.1.1 | Odoo 18.0 installed | ☐ | |
| 1.1.2 | PostgreSQL 14+ running | ☐ | |
| 1.1.3 | Python 3.10+ with pip | ☐ | |
| 1.1.4 | Internet connectivity to SRI | ☐ | |
| 1.1.5 | `stdnum` library installed | ☐ | |
| 1.1.6 | `zeep` or `suds-jurko` for SOAP | ☐ | |
| 1.1.7 | `lxml` for XML processing | ☐ | |
| 1.1.8 | `cryptography` for XAdES | ☐ | |

### 1.2 Legal Requirements
| # | Requirement | Status | Verified By |
|:--|:------------|:-------|:------------|
| 1.2.1 | Valid RUC for company | ☐ | |
| 1.2.2 | Electronic signature (P12 file) | ☐ | |
| 1.2.3 | P12 password documented | ☐ | |
| 1.2.4 | SRI online authorization (emisor electrónico) | ☐ | |
| 1.2.5 | Establishment registered in SRI | ☐ | |
| 1.2.6 | Emission point registered in SRI | ☐ | |

---

## 2. MODULE INSTALLATION

### 2.1 Install Official Localization
| Step | Action | Menu Path | Verification |
|:-----|:-------|:----------|:-------------|
| 2.1.1 | Apps → Update Apps List | Apps → Update Apps List | "Apps list updated" message |
| 2.1.2 | Search "l10n_ec" | Apps → Search | Module appears |
| 2.1.3 | Install "Ecuadorian Accounting" | Apps → Install | Status: Installed |
| 2.1.4 | Verify COA loaded | Accounting → Configuration → Chart of Accounts | ~500 accounts visible |
| 2.1.5 | Verify taxes loaded | Accounting → Configuration → Taxes | IVA 15%, 0% visible |

### 2.2 Install Custom SRI Module
| Step | Action | Command / Path | Verification |
|:-----|:-------|:---------------|:-------------|
| 2.2.1 | Copy module to addons | `cp -r l10n_ec_sri /odoo/addons/` | Directory exists |
| 2.2.2 | Update Apps List | Apps → Update Apps List | Module visible |
| 2.2.3 | Install l10n_ec_sri | Apps → Install | Status: Installed |
| 2.2.4 | Restart Odoo | `systemctl restart odoo` | No errors in log |

---

## 3. COMPANY CONFIGURATION

### 3.1 Company Basic Setup
| Step | Field | Value | Menu Path |
|:-----|:------|:------|:----------|
| 3.1.1 | Company Name | [Legal name as in RUC] | Settings → Companies |
| 3.1.2 | Country | Ecuador | Settings → Companies |
| 3.1.3 | TIN/VAT | [13-digit RUC] | Settings → Companies |
| 3.1.4 | Address | [Registered address] | Settings → Companies |

### 3.2 SRI-Specific Configuration
| Step | Field | Value | Menu Path |
|:-----|:------|:------|:----------|
| 3.2.1 | SRI Environment | `Test` (initially) | Settings → Companies → SRI |
| 3.2.2 | Electronic Signature | [Upload P12 file] | Settings → Companies → SRI |
| 3.2.3 | P12 Password | [Secure password] | Settings → Companies → SRI |
| 3.2.4 | Emission Code | `1` (normal) | Settings → Companies → SRI |
| 3.2.5 | Obligado Contabilidad | `SI` or `NO` | Settings → Companies → SRI |
| 3.2.6 | Contribuyente Especial | [Resolution # or empty] | Settings → Companies → SRI |

### 3.3 Verification Steps
| # | Check | Expected Result | Status |
|:--|:------|:----------------|:-------|
| 3.3.1 | P12 upload successful | No error message | ☐ |
| 3.3.2 | Certificate expiry > 30 days | Warning if < 30 days | ☐ |
| 3.3.3 | RUC validated | No validation error | ☐ |

---

## 4. JOURNAL CONFIGURATION

### 4.1 Sales Journal
| Step | Field | Value | Menu Path |
|:-----|:------|:------|:----------|
| 4.1.1 | Open Sales Journal | - | Accounting → Configuration → Journals |
| 4.1.2 | Establishment Code | [3 digits: 001] | Journal → Ecuador tab |
| 4.1.3 | Emission Point | [3 digits: 001] | Journal → Ecuador tab |
| 4.1.4 | Use Documents | ☑ Enabled | Journal → Advanced |
| 4.1.5 | Electronic Invoicing | ☑ Enabled | Journal → Ecuador tab |

### 4.2 Purchase Journal
| Step | Field | Value | Menu Path |
|:-----|:------|:------|:----------|
| 4.2.1 | Open Purchase Journal | - | Accounting → Configuration → Journals |
| 4.2.2 | Use Documents | ☑ Enabled | Journal → Advanced |
| 4.2.3 | Withholding Journal | [Link to Ret. journal] | Journal → Ecuador tab |

### 4.3 Withholding Journal
| Step | Field | Value | Menu Path |
|:-----|:------|:------|:----------|
| 4.3.1 | Create Retention Journal | Name: "Retenciones" | Accounting → Configuration → Journals |
| 4.3.2 | Type | Miscellaneous | Journal → Type |
| 4.3.3 | Establishment Code | [3 digits: 001] | Journal → Ecuador tab |
| 4.3.4 | Emission Point | [3 digits: 001] | Journal → Ecuador tab |

---

## 5. TAX CONFIGURATION

### 5.1 Verify IVA Taxes
| Step | Tax Name | Rate | Tax Group | Status |
|:-----|:---------|:-----|:----------|:-------|
| 5.1.1 | IVA 15% Ventas | 15% | VAT | ☐ Active |
| 5.1.2 | IVA 15% Compras | 15% | VAT | ☐ Active |
| 5.1.3 | IVA 0% Ventas | 0% | VAT 0% | ☐ Active |
| 5.1.4 | IVA 0% Compras | 0% | VAT 0% | ☐ Active |
| 5.1.5 | IVA 5% (Construcción) | 5% | VAT | ☐ Active |

### 5.2 Configure Withholding Taxes
| Step | Tax Name | Rate | Tax Code | Status |
|:-----|:---------|:-----|:---------|:-------|
| 5.2.1 | Ret. IR 1% | 1% | 340 | ☐ Active |
| 5.2.2 | Ret. IR 1.75% | 1.75% | 312 | ☐ Active |
| 5.2.3 | Ret. IR 2% | 2% | 341 | ☐ Active |
| 5.2.4 | Ret. IR 2.75% | 2.75% | 320 | ☐ Active |
| 5.2.5 | Ret. IR 8% | 8% | 304 | ☐ Active |
| 5.2.6 | Ret. IR 10% | 10% | 303 | ☐ Active |
| 5.2.7 | Ret. IVA 30% | 30% | - | ☐ Active |
| 5.2.8 | Ret. IVA 70% | 70% | - | ☐ Active |
| 5.2.9 | Ret. IVA 100% | 100% | - | ☐ Active |

---

## 6. PARTNER CONFIGURATION

### 6.1 Consumidor Final Setup
| Step | Field | Value | Menu Path |
|:-----|:------|:------|:----------|
| 6.1.1 | Open/Create Partner | Name: "CONSUMIDOR FINAL" | Contacts → Create |
| 6.1.2 | Identification Type | Final Consumer | Partner → ID Type |
| 6.1.3 | VAT | 9999999999999 | Partner → VAT |
| 6.1.4 | Country | Ecuador | Partner → Country |

### 6.2 Tax Authority Partners
| # | Partner | VAT | Purpose |
|:--|:--------|:----|:--------|
| 6.2.1 | SRI | 1793125212001 | Tax filings |
| 6.2.2 | IESS | 1793125212001 | Social security |

---

## 7. SEQUENCE CONFIGURATION

### 7.1 Document Sequences
| Step | Sequence | Format | Menu Path |
|:-----|:---------|:-------|:----------|
| 7.1.1 | Invoice | `001-001-000000001` | Settings → Technical → Sequences |
| 7.1.2 | Credit Note | `001-001-000000001` | Settings → Technical → Sequences |
| 7.1.3 | Retention | `001-001-000000001` | Settings → Technical → Sequences |
| 7.1.4 | Guía | `001-001-000000001` | Settings → Technical → Sequences |

---

## 8. SRI CONNECTION TEST

### 8.1 Test Environment Verification
| Step | Action | Expected Result | Status |
|:-----|:-------|:----------------|:-------|
| 8.1.1 | Set Environment = Test | Saved | ☐ |
| 8.1.2 | Create test invoice | Invoice created | ☐ |
| 8.1.3 | Post invoice | Access key generated | ☐ |
| 8.1.4 | Check SRI response | RECIBIDA or AUTORIZADO | ☐ |
| 8.1.5 | View authorization | 37-char auth number | ☐ |

### 8.2 Production Cutover
| Step | Action | Verification | Status |
|:-----|:-------|:-------------|:-------|
| 8.2.1 | Complete all test cases | All passed | ☐ |
| 8.2.2 | Change Environment = Production | Saved | ☐ |
| 8.2.3 | First production invoice | Authorized | ☐ |
| 8.2.4 | Verify in SRI portal | Document visible | ☐ |

---

## 9. FINAL VERIFICATION

### 9.1 Complete Checklist
| # | Area | Verified | Sign-Off |
|:--|:-----|:---------|:---------|
| 9.1.1 | Company configuration | ☐ | |
| 9.1.2 | Journal setup | ☐ | |
| 9.1.3 | Tax configuration | ☐ | |
| 9.1.4 | Partner defaults | ☐ | |
| 9.1.5 | Sequences | ☐ | |
| 9.1.6 | SRI test successful | ☐ | |
| 9.1.7 | Production ready | ☐ | |

---

**Document Classification**: Configuration Checklist
**Owner**: IT / Implementation Team
**Last Updated**: 2026-01-22
