# DATA MAPPING: IESS PLANILLA MENSUAL
## DM_06 - IESS Monthly Contribution File

**Document ID**: DM-006
**Version**: 1.0
**Effective Date**: 2026-01-22
**Owner**: HR Director (Expert Crew)
**Regulatory Reference**: [KB_IESS_CONTRIBUTIONS.md](../11_regulatory_knowledge_base/KB_IESS_CONTRIBUTIONS.md)

---

## 1. OVERVIEW

Monthly payroll contribution file submitted to IESS (Instituto Ecuatoriano de Seguridad Social) containing employee contributions, employer contributions, and Fondos de Reserva.

---

## 2. FILE SPECIFICATIONS

| Attribute | Value |
|:----------|:------|
| Format | CSV / TXT (pipe-delimited) |
| Encoding | UTF-8 |
| Line Ending | CRLF (Windows) |
| Submission | IESS Portal (monthly) |
| Deadline | 15th of following month |

---

## 3. FIELD MAPPING: PLANILLA NORMAL

| # | IESS Field | Odoo Source | Type | Length | Required | Notes |
|:--|:-----------|:------------|:-----|:-------|:---------|:------|
| 1 | Cédula | `employee.identification_id` | String | 10 | ✓ | Cédula or Pasaporte |
| 2 | Apellido Paterno | `employee.l10n_ec_last_name_1` | String | 50 | ✓ | |
| 3 | Apellido Materno | `employee.l10n_ec_last_name_2` | String | 50 | | Optional |
| 4 | Nombres | `employee.first_name` | String | 50 | ✓ | |
| 5 | Código Actividad | `contract.l10n_ec_sector_code` | String | 2 | ✓ | Sectoral code |
| 6 | Sueldo | `payslip.wage` | Decimal | 10,2 | ✓ | Base salary |
| 7 | Días Trabajados | `payslip.worked_days_count` | Integer | 2 | ✓ | 1-30 |
| 8 | Horas Extras 50% | `payslip.line['HE50'].quantity` | Decimal | 5,2 | | |
| 9 | Horas Extras 100% | `payslip.line['HE100'].quantity` | Decimal | 5,2 | | |
| 10 | Ingresos Adicionales | `payslip.line['COMIS'].total` | Decimal | 10,2 | | Commissions, bonuses |
| 11 | Total Ingresos | Calculated | Decimal | 10,2 | ✓ | Fields 6+8+9+10 |
| 12 | Aporte Personal 9.45% | `payslip.line['IESS_PERSONAL']` | Decimal | 10,2 | ✓ | |
| 13 | Aporte Patronal 12.15% | `payslip.line['IESS_PATRONAL']` | Decimal | 10,2 | ✓ | |
| 14 | Fondos Reserva 8.33% | `payslip.line['FONDOS_RESERVA']` | Decimal | 10,2 | | If mensualizado |
| 15 | Tipo Novedad | `contract.l10n_ec_novedad` | String | 2 | | Entry/Exit code |
| 16 | Fecha Novedad | `contract.date_start/end` | Date | 10 | | YYYY-MM-DD |

---

## 4. NOVEDAD CODES (Types)

| Code | Description | Odoo Trigger |
|:-----|:------------|:-------------|
| `EN` | Entrada (New hire) | `contract.date_start` in period |
| `SA` | Salida (Termination) | `contract.date_end` in period |
| `RA` | Reingreso (Rehire) | New contract same RUC |
| `AU` | Aumento Sueldo | Salary increase |
| `RE` | Reducción Sueldo | Salary decrease |
| `LI` | Licencia Sin Sueldo | Unpaid leave |
| `VA` | Vacaciones | Vacation (still contributes) |
| `EN` | Enfermedad | Sick leave |

---

## 5. CALCULATION FORMULAS

### 5.1 Total Ingresos (Base de Aportación)

```python
base_aportacion = (
    wage  # Sueldo base
    + overtime_50 * (hourly_rate * 1.5)  # Horas extras 50%
    + overtime_100 * (hourly_rate * 2.0)  # Horas extras 100%
    + commissions  # Comisiones
    + bonuses  # Bonos gravables
)
# Minimum: SBU * (days_worked / 30)
# Maximum: 25 * SBU (contribution ceiling 2026: $12,050)
```

### 5.2 Contribution Rates 2026

| Concept | Rate | Ceiling |
|:--------|:-----|:--------|
| Aporte Personal | 9.45% | 25 × SBU |
| Aporte Patronal | 12.15% | 25 × SBU |
| Fondos de Reserva | 8.33% | 25 × SBU |
| **Total Contribution** | **29.93%** | |

### 5.3 Proration for Partial Days

```python
if days_worked < 30:
    prorated_wage = wage * (days_worked / 30)
    aporte_personal = prorated_wage * 0.0945
    aporte_patronal = prorated_wage * 0.1215
```

---

## 6. SAMPLE FILE OUTPUT

```
1234567890|PEREZ|GARCIA|JUAN CARLOS|01|1200.00|30|10.00|5.00|200.00|1465.00|138.44|178.00|122.05||
1713488185|MARTINEZ|LOPEZ|MARIA ELENA|01|800.00|15|0.00|0.00|0.00|400.00|37.80|48.60|33.32|EN|2026-01-15
```

---

## 7. ODOO IMPLEMENTATION

### 7.1 Payslip Rule: IESS Personal

```python
# Code: IESS_PERSONAL
# Category: Deduction
# Sequence: 100

result = 0
base = categories.GROSS
ceiling = 25 * contract.company_id.l10n_ec_sbu  # $12,050 for 2026

if base > ceiling:
    base = ceiling

result = round(base * 0.0945, 2)
```

### 7.2 Payslip Rule: IESS Patronal

```python
# Code: IESS_PATRONAL
# Category: Employer Contribution
# Sequence: 101

result = 0
base = categories.GROSS
ceiling = 25 * contract.company_id.l10n_ec_sbu

if base > ceiling:
    base = ceiling

result = round(base * 0.1215, 2)
```

### 7.3 Payslip Rule: Fondos de Reserva

```python
# Code: FONDOS_RESERVA
# Category: Employer Contribution / Employee Payment
# Sequence: 102

result = 0
# Only applicable after 13 months of service
start_date = contract.date_start
months_worked = (payslip.date_to.year - start_date.year) * 12 + (payslip.date_to.month - start_date.month)

if months_worked >= 13:
    base = categories.GROSS
    ceiling = 25 * contract.company_id.l10n_ec_sbu

    if base > ceiling:
        base = ceiling

    result = round(base * 0.0833, 2)

    # Check if mensualizado or acumulado
    if contract.l10n_ec_fondos_reserva_mode == 'mensual':
        # Pay to employee directly
        pass
    else:
        # Deposit to IESS account
        pass
```

---

## 8. EXPORT FUNCTION

### 8.1 Python Export Logic

```python
def generate_iess_planilla(company_id, period_start, period_end):
    """
    Generate IESS monthly contribution file
    """
    payslips = env['hr.payslip'].search([
        ('company_id', '=', company_id),
        ('date_from', '>=', period_start),
        ('date_to', '<=', period_end),
        ('state', '=', 'done')
    ])

    lines = []
    for slip in payslips:
        emp = slip.employee_id
        contract = slip.contract_id

        line = '|'.join([
            emp.identification_id,
            emp.l10n_ec_last_name_1 or '',
            emp.l10n_ec_last_name_2 or '',
            emp.first_name,
            contract.l10n_ec_sector_code or '01',
            f"{slip.wage:.2f}",
            str(slip.worked_days_count),
            f"{slip.get_line_value('HE50'):.2f}",
            f"{slip.get_line_value('HE100'):.2f}",
            f"{slip.get_line_value('COMIS'):.2f}",
            f"{slip.get_line_value('GROSS'):.2f}",
            f"{slip.get_line_value('IESS_PERSONAL'):.2f}",
            f"{slip.get_line_value('IESS_PATRONAL'):.2f}",
            f"{slip.get_line_value('FONDOS_RESERVA'):.2f}",
            contract.l10n_ec_novedad or '',
            contract.l10n_ec_novedad_date or '',
        ])
        lines.append(line)

    return '\r\n'.join(lines)
```

---

## 9. VALIDATION RULES

| Rule | Validation | Error Code |
|:-----|:-----------|:-----------|
| Cédula Válida | Módulo 10 checksum | IESS-001 |
| Días 1-30 | days_worked between 1-30 | IESS-002 |
| Ceiling Check | base ≤ 25 × SBU | IESS-003 |
| Novedad Date | Required if novedad code present | IESS-004 |
| Sector Code | Valid IESS sector | IESS-005 |

---

## 10. SUBMISSION CALENDAR

| Period | Generation Date | Submission Deadline |
|:-------|:----------------|:--------------------|
| January | Feb 1 | Feb 15 |
| February | Mar 1 | Mar 15 |
| March | Apr 1 | Apr 15 |
| April | May 1 | May 15 |
| May | Jun 1 | Jun 15 |
| June | Jul 1 | Jul 15 |
| July | Aug 1 | Aug 15 |
| August | Sep 1 | Sep 15 |
| September | Oct 1 | Oct 15 |
| October | Nov 1 | Nov 15 |
| November | Dec 1 | Dec 15 |
| December | Jan 1 | Jan 15 |

---

## 11. ERROR HANDLING

| IESS Error | Cause | Resolution |
|:-----------|:------|:-----------|
| Cédula no registrada | Employee not in IESS | Register employee first |
| Sueldo inferior al mínimo | Wage < SBU pro-rated | Verify contract wage |
| Duplicado | Same employee twice | Check payslip overlap |
| Fecha novedad inválida | Date outside period | Correct novedad date |

---

**Data Mapping Classification**: ISO 9001:2015 Controlled Document
