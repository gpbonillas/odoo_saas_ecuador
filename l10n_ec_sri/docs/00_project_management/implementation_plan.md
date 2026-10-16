# Implementation Plan - Module 1: l10n_ec_base (Foundation)

## Goal Description
Implement the `l10n_ec_base` module for Odoo 18.0 to serve as the foundation for the Ecuador Localization. This module will provide the NEC-compliant Chart of Accounts, Tax Templates (SRI 2026), and Partner Identity Validation (RUC/Cedula).

## User Review Required
> [!IMPORTANT]
> **Regulatory Compliance**: This implementation enforces strict SRI 2026 rules (15% IVA, Non-Cancellation).
> **Audit Findings**: Per our Big 4 Audit (SOMA-AUDIT-001), we are proceeding with **Modular Execution** but must strictly maintain "Separation of Concerns" (Ghezzi, Springer).
> **Data Migration**: A Data Migration Strategy must be developed in parallel with this module.

## Proposed Changes

### New Module: `odoo_custom_addons/l10n_ec_sri/odoo_custom_addons/l10n_ec_base`
**Note**: The directory structure in the repo is `odoo_custom_addons/l10n_ec_sri`. Based on the blueprint, we might need to structure it such that `l10n_ec_sri` is the repo name and the modules are inside, or `l10n_ec_sri` IS the module.
*Clarification from Docs*: The docs mention `l10n_ec` as the base module name in SRS, but the repo structure shows `l10n_ec_sri`. The Blueprint mentions a "9-module suite".
*Decision*: I will follow the standard Odoo pattern where `l10n_ec` (or `l10n_ec_base` if `l10n_ec` is taken by Odoo official) is a subdirectory in `odoo_custom_addons`.
*Observation*: `odoo_custom_addons` currently contains `l10n_ec_sri` which has an `__init__.py`. It seems `l10n_ec_sri` might be intended as the monolithic container OR the repo was structured flat.
*Correction*: The `DEFINITIVE_LOCALIZATION_BLUEPRINT.md` assumes a modular structure (`l10n_ec_base`, `l10n_ec_edi`, etc.). I will create these as sub-modules if possible, or robust separate modules if `l10n_ec_sri` is just a namespace.
*Current Structure*: `odoo_custom_addons/l10n_ec_sri` exists. I will propose creating `l10n_ec_base` **inside** `odoo_custom_addons` if allowed, or verify if `l10n_ec_sri` is meant to be the single module.
*Re-reading Blueprint*: "What We Are Building: A 9-module Odoo 18.0 localization suite".
*Action*: I will create `l10n_ec_base` as a new directory under `odoo_custom_addons`.

#### [NEW] `odoo_custom_addons/l10n_ec_base` (Directory)
- `__manifest__.py`: Dependencies on `account`, `l10n_latam_invoice_document`, `base`.
- `__init__.py`

#### [NEW] Models
- `models/res_partner.py`: Extensions for `l10n_ec_identifier_type`, `l10n_ec_taxpayer_type` and Mod10/Mod11 validation logic.
- `models/res_company.py`: Extensions for SRI environment type.
- `models/account_chart_template.py`: Logic to load the NEC CoA.
- `models/account_tax.py`: Extensions for SRI tax codes.

#### [NEW] Data
- `data/account.chart.template.csv`: The NEC Chart of Accounts headers.
- `data/account.account.template.csv`: The 500+ account codes (to be generated/imported).
- `data/account.tax.group.csv`: IVA, ICE, Retentions.
- `data/account.tax.template.csv`: 15% IVA, etc.
- `data/l10n_latam.document.type.csv`: SRI Document types (01, 03, etc.).

## Verification Plan

### Automated Tests (PyTest)
I will create a standard Odoo test suite in `tests/test_l10n_ec_base.py`.
- **RUC Validation Test**:
    - Create partner with valid RUC (1793125212001) -> Assert Success.
    - Create partner with invalid RUC -> Assert `ValidationError`.
    - Create partner with valid Cedula (1713488185) -> Assert Success.
- **Tax Creation Test**:
    - Install module -> Check `account.tax` for "IVA 15%".
- **CoA Installation Test**:
    - Create new company -> Install "Ecuador - Plan de Cuentas NEC" -> Verify accounts exist.

### User Acceptance Testing (UAT) Protocol
> **Springer Best Practice**: "Test early, test often."
1. **Boot Odoo**: `docker-compose up`
2. **Install Module**: Log in as admin, install `l10n_ec_base`.
3. **Check Partner**: Go to Contacts, try to save a partner with an invalid RUC.
4. **Check Taxes**: Go to Invoicing > Configuration > Taxes, verify 15% rate.
