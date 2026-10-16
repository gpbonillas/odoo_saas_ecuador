# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Pure-Python report math library for Ecuadorian statutory books, financial
statements, SRI forms and the ATS.

IMPORTANT
=========
This module MUST NOT import Odoo.  Every function takes plain dicts / lists
of scalars so the math can be unit-tested standalone (no database, no Odoo):

    python3 tests/unit/test_reports_ats.py

The Odoo wizards (wizard/*.py) are only thin ORM extractors that convert
``account.move`` / ``account.retention`` records into the plain structures
documented below, call these functions and render the result.

Regulatory sources used (in-repo, authoritative for this sprint):
  * l10n_ec_sri/docs/03_module_specifications/09_l10n_ec_reports/SRS_MODULE_09_L10N_EC_REPORTS.md
    - ATS XML structure and Form 104 / 103 casilleros (codes 411, 412, 415,
      421, 422, 480, 520, 601, 699 / 302..320, 721, 723, 725).
  * l10n_ec_sri/docs/11_regulatory_knowledge_base/KB_TAX_RATES_WITHHOLDINGS.md
    - IVA rates (15/5/0/no objeto/exento), IR withholding codes & rates,
      IVA withholding rates (30/70/100), corporate income tax rate (25%).
  * l10n_ec_sri/docs/11_regulatory_knowledge_base/KB_SUPERCIAS.md
    - Required financial statements (5) and submission rules.
  * l10n_ec_income_tax/data/tax_table_2026_data.xml
    - Progressive income-tax brackets 2026 (Res. NAC-DGERCGC25-00000043).
  * l10n_ec_income_tax (L10nEcFamilyBasket) - Rebaja Tributaria formula:
    ``min(projected_expenses, n_baskets * basket_cost) * 18%``.

Numbers NOT stated in the in-repo docs (e.g. gastos personales caps in
SMMLV) are exposed as configurable parameters instead of being invented.
"""

from datetime import date

# ===========================================================================
# GENERIC HELPERS
# ===========================================================================

# SRI identifier-type codes --------------------------------------------------
# Proveedor (compras) - SRI ATS tpIdProv
TP_ID_PROV = {
    "ruc": "01",
    "cedula": "02",
    "pasaporte": "03",
    "consumidor_final": "07",
    None: "03",
    False: "03",
    "": "03",
}
# Cliente (ventas) - SRI ATS tpIdCliente
TP_ID_CLIENT = {
    "ruc": "04",
    "cedula": "05",
    "pasaporte": "06",
    "consumidor_final": "07",
    None: "07",
    False: "07",
    "": "07",
}


def round2(value):
    """Round to 2 decimals using SRI convention (half up for positives)."""
    try:
        value = float(value or 0.0)
    except (TypeError, ValueError):
        value = 0.0
    # avoid -0.00 in XML/PDF
    if abs(value) < 0.005:
        return 0.0
    return value + 0.0 if abs(value * 100 - int(value * 100)) < 1e-9 else _half_up(value)


def _half_up(value):
    from decimal import Decimal, ROUND_HALF_UP

    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def fmt_money(value):
    """Format for SRI XML (always 2 decimals, never '-0.00')."""
    return "%.2f" % (round2(value) + 0.0)


def month_bounds(year, month):
    """Return (first_day, first_day_of_next_month) for a YYYY/MM period."""
    year = int(year)
    month = int(month)
    if not 1 <= month <= 12:
        raise ValueError("Invalid month %r" % (month,))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def year_bounds(year):
    return date(int(year), 1, 1), date(int(year) + 1, 1, 1)


def parse_date(value):
    """Accept date / 'YYYY-MM-DD' / 'DD/MM/YYYY' and return a date.

    Missing values (Odoo ``False`` / ``None`` / ``''``) return the epoch
    sentinel ``1970-01-01`` so date comparisons and sortings downstream
    never raise on a record without date.
    """
    if value in (None, False, ""):
        return date(1970, 1, 1)
    if isinstance(value, date):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            from datetime import datetime as _dt

            return _dt.strptime(text[:19] if " " in text else text, fmt).date()
        except ValueError:
            continue
    return None


def _num(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def split_document_number(number):
    """Split a SRI document number into (estab, pto, secuencial).

    Accepts the printed form ``001-001-000000123``, the 15 digit compact
    form ``001001000000123`` (estab 3 + pto 3 + secuencial 9) and any other
    bare sequential, which is reported verbatim with ``000`` as the
    establishment / point of emission (not guessable from the number).
    """
    text = str(number or "").strip()
    parts = [part for part in text.split("-") if part]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    digits = text.replace("-", "")
    if digits.isdigit():
        if len(digits) >= 15:
            return digits[:3], digits[3:6], digits[6:15]
        return "000", "000", digits
    return "000", "000", text or "0"


# ===========================================================================
# INVOICE ROW NORMALIZATION (shared by books, forms and ATS)
# ===========================================================================
#
# A "raw invoice" is a plain dict with this contract (built by the wizards
# from account.move, or by unit tests synthetically):
#
# {
#   'id': int,
#   'fecha': '2026-01-15',            # invoice_date
#   'fecha_registro': '2026-01-15',   # accounting date (ATS fechaRegistro)
#   'doc_code': '01',                 # SRI codDoc (latam document type)
#   'doc_name': 'Factura',
#   'move_type': 'out_invoice',       # out_invoice/out_refund/in_invoice/in_refund
#   'tp_id': '04',                    # SRI counterparty identifier type
#   'identificacion': '1791234567001',
#   'razon_social': 'Cliente S.A.',
#   'clave_acceso': '49 digits....',  # SRI access key (nullable)
#   'estab': '001', 'pto': '001', 'secuencial': '000000123',
#   'autorizacion': '...',            # authorization number
#   'sustento': '01',                 # purchases sustento tributario
#   'lines': [{'base': 100.0, 'rates': [15.0], 'no_objeto': False}],
#   'tax_lines': [{'group': 'IVA', 'balance': 15.0, 'ice': False,
#                  'ret_kind': None}],        # balance = ABSOLUTE value
#   'total': 115.0,
#   'state': 'posted',
#   'is_export': False, 'is_import': False,
#   'emision_linea': True,            # comprobante emitido en linea (SRI)
#   'forma_pago': '20',
#   'retentions': [{'kind': 'ir'|'iva'|'isd', 'code': '303',
#                   'base': 100.0, 'percent': 1.75, 'amount': 1.75,
#                   'numero': '001-001-000000001', 'fecha': '2026-01-20',
#                   'autorizacion': '...', 'name': 'Honorarios 10%'}],
# }

REFUND_TYPES = ("out_refund", "in_refund")


def invoice_sign(raw):
    """+1 for invoices, -1 for credit notes (notes reduce the book totals)."""
    return -1.0 if raw.get("move_type") in REFUND_TYPES else 1.0


def invoice_report_row(raw):
    """Normalize one raw invoice into a flat book/form/ATS row (signed)."""
    sign = invoice_sign(raw)

    base_0 = base_5 = base_15 = base_exenta = base_no_objeto = 0.0
    base_other = 0.0
    rates_used = []
    for line in raw.get("lines") or []:
        base = _num(line.get("base"))
        rates = [r for r in (line.get("rates") or []) if _num(r) >= 0]
        if line.get("no_objeto"):
            base_no_objeto += base
        elif not rates:
            base_exenta += base
        else:
            rate = max(_num(r) for r in rates)
            rates_used.append(rate)
            if rate == 0:
                base_0 += base
            elif rate == 5:
                base_5 += base
            elif rate == 15:
                base_15 += base
            else:  # other statutory rate (configurable taxes)
                base_other += base

    iva = ice = 0.0
    tax_line_ret = {"ir": 0.0, "iva": 0.0, "isd": 0.0}
    for tax_line in raw.get("tax_lines") or []:
        amount = _num(tax_line.get("balance"))
        if tax_line.get("ice"):
            ice += amount
        elif tax_line.get("ret_kind"):
            # Withholdings also appear as invoice tax lines; they are kept
            # apart from ``iva`` and only used when the invoice has no
            # account.retention attached for that tax (see below).
            tax_line_ret[tax_line["ret_kind"]] = amount + tax_line_ret[
                tax_line["ret_kind"]
            ]
        else:
            iva += amount

    retention_rows = raw.get("retentions") or []
    listed = {"ir": 0.0, "iva": 0.0, "isd": 0.0}
    has_kind = {"ir": False, "iva": False, "isd": False}
    for ret in retention_rows:
        kind = ret.get("kind") if ret.get("kind") in listed else "ir"
        listed[kind] = _num(ret.get("amount")) + listed[kind]
        has_kind[kind] = True
    # account.retention is the authoritative source; the invoice tax lines
    # are only a fallback so the books work on databases where withholdings
    # are (also) configured as invoice taxes - never both (no double count).
    ret_iva = listed["iva"] if has_kind["iva"] else tax_line_ret["iva"]
    ret_isd = listed["isd"] if has_kind["isd"] else tax_line_ret["isd"]
    ret_ir = listed["ir"] if has_kind["ir"] else tax_line_ret["ir"]

    taxed = [r for r in rates_used if r > 0]
    tarifa = max(taxed) if taxed else 0.0

    total = _num(raw.get("total"))
    all_bases = base_0 + base_5 + base_15 + base_exenta + base_no_objeto + base_other

    return {
        "id": raw.get("id"),
        "fecha": raw.get("fecha") or "",
        "fecha_registro": raw.get("fecha_registro") or raw.get("fecha") or "",
        "doc_code": raw.get("doc_code") or "01",
        "doc_name": raw.get("doc_name") or "",
        "move_type": raw.get("move_type") or "out_invoice",
        "tp_id": raw.get("tp_id") or "07",
        "identificacion": raw.get("identificacion") or "",
        "razon_social": raw.get("razon_social") or "",
        "clave_acceso": raw.get("clave_acceso") or "",
        "estab": raw.get("estab") or "001",
        "pto": raw.get("pto") or "001",
        "secuencial": raw.get("secuencial") or "0",
        "autorizacion": raw.get("autorizacion") or "",
        # reported as-is: an empty sustento must stay empty so REQ-ATS-001
        # can flag it (ats_compras falls back to '01' for the XML value)
        "sustento": raw.get("sustento") or "",
        "state": raw.get("state") or "posted",
        "is_export": bool(raw.get("is_export")),
        "is_import": bool(raw.get("is_import")),
        "emision_linea": bool(raw.get("emision_linea")),
        "forma_pago": raw.get("forma_pago") or "20",
        # --- signed monetary values -----------------------------------------
        "base_0": sign * base_0,
        "base_5": sign * base_5,
        "base_15": sign * base_15,
        "base_exenta": sign * base_exenta,
        "base_no_objeto": sign * base_no_objeto,
        "base_other": sign * base_other,
        "base_total": sign * all_bases,
        "tarifa": tarifa,
        "iva": sign * iva,
        "ice": sign * ice,
        "ret_ir": sign * ret_ir,
        "ret_iva": sign * ret_iva,
        "ret_isd": sign * ret_isd,
        "total": sign * total,
        "sign": sign,
        "retentions": raw.get("retentions") or [],
    }


def normalize_invoices(raw_invoices):
    return [invoice_report_row(r) for r in raw_invoices]


# ===========================================================================
# STATUTORY BOOKS
# ===========================================================================

COLS_VENTAS = [
    ("fecha", "Fecha"),
    ("doc_code", "SRI codDoc"),
    ("doc_name", "Tipo Documento"),
    ("identificacion", "Identificacion"),
    ("razon_social", "Razon Social / Apellidos"),
    ("clave_acceso", "Clave de Acceso"),
    ("estab_pto", "Estab-Pto Emision"),
    ("secuencial", "Secuencial"),
    ("base_0", "Base Tarifa 0%"),
    ("base_5", "Base Tarifa 5%"),
    ("base_15", "Base Tarifa 15%"),
    ("base_exenta", "Base Exenta"),
    ("base_no_objeto", "Base No Objeto"),
    ("tarifa", "Tarifa %"),
    ("iva", "IVA Cobrado"),
    ("ice", "ICE"),
    ("ret_ir", "Ret. IR"),
    ("ret_iva", "Ret. IVA"),
    ("total", "Total"),
    ("estado_linea", "Comprobante en Linea"),
]

COLS_COMPRAS = [
    ("fecha_registro", "Fecha Registro"),
    ("fecha", "Fecha Emision"),
    ("tp_id", "Tipo Ident. Proveedor"),
    ("identificacion", "Identificacion"),
    ("razon_social", "Razon Social / Apellidos"),
    ("doc_code", "SRI codDoc"),
    ("doc_name", "Tipo Documento"),
    ("clave_acceso", "Clave de Acceso"),
    ("autorizacion", "Autorizacion"),
    ("sustento", "Sustento"),
    ("base_0", "Base Tarifa 0%"),
    ("base_5", "Base Tarifa 5%"),
    ("base_15", "Base Tarifa 15%"),
    ("base_exenta", "Base Exenta"),
    ("base_no_objeto", "Base No Objeto"),
    ("ice", "ICE"),
    ("iva", "IVA Pagado"),
    ("ret_ir", "Ret. IR Practicada"),
    ("ret_iva", "Ret. IVA Practicada"),
    ("importacion", "Importacion"),
    ("total", "Total"),
]

COLS_RETENCIONES = [
    ("fecha", "Fecha Retencion"),
    ("numero", "Comprobante Retencion"),
    ("autorizacion", "Autorizacion"),
    ("fecha_factura", "Fecha Comprobante"),
    ("tipo", "Tipo Retencion"),
    ("codigo", "Codigo"),
    ("concepto", "Concepto"),
    ("tercero", "Tercero"),
    ("identificacion", "Identificacion"),
    ("comprobante", "Comprobante Relacionado"),
    ("base", "Base Imponible"),
    ("percent", "Tarifa %"),
    ("amount", "Valor Retenido"),
]

COLS_BANCOS = [
    ("fecha", "Fecha"),
    ("documento", "Documento / Asiento"),
    ("cuenta", "Cuenta"),
    ("partner", "Tercero"),
    ("glosa", "Glosa / Referencia"),
    ("debit", "Valor Debito"),
    ("credit", "Valor Credito"),
    ("saldo", "Saldo"),
]

COLS_DIARIO = [
    ("asiento", "Asiento"),
    ("fecha", "Fecha"),
    ("cuenta", "Cuenta"),
    ("nombre_cuenta", "Nombre Cuenta"),
    ("detalle", "Detalle / Glosa"),
    ("debe", "Debe"),
    ("haber", "Haber"),
]

COLS_MAYOR = [
    ("cuenta", "Cuenta"),
    ("nombre_cuenta", "Nombre Cuenta"),
    ("asiento", "Asiento"),
    ("fecha", "Fecha"),
    ("detalle", "Detalle"),
    ("debe", "Debe"),
    ("haber", "Haber"),
    ("saldo", "Saldo"),
]


def libro_ventas_rows(raw_invoices):
    """Libro de Ventas: every outbound invoice (incl. credit notes, signed).

    Also carries the SRI 'comprobantes emitidos en linea' fields
    (clave de acceso, estado, tipo de emision).
    """
    rows = []
    for row in normalize_invoices(raw_invoices):
        rows.append(
            {
                "fecha": row["fecha"],
                "doc_code": row["doc_code"],
                "doc_name": row["doc_name"],
                "identificacion": row["identificacion"],
                "razon_social": row["razon_social"],
                "clave_acceso": row["clave_acceso"],
                "estab_pto": "%s-%s" % (row["estab"], row["pto"]),
                "secuencial": row["secuencial"],
                "base_0": round2(row["base_0"]),
                "base_5": round2(row["base_5"]),
                "base_15": round2(row["base_15"]),
                "base_exenta": round2(row["base_exenta"]),
                "base_no_objeto": round2(row["base_no_objeto"]),
                "tarifa": row["tarifa"],
                "iva": round2(row["iva"]),
                "ice": round2(row["ice"]),
                "ret_ir": round2(row["ret_ir"]),
                "ret_iva": round2(row["ret_iva"]),
                "total": round2(row["total"]),
                "estado_linea": "SI" if row["emision_linea"] else "NO",
                "is_export": row["is_export"],
                "tipo_emision": "E" if row["emision_linea"] else "F",
            }
        )
    totals = _sum_totals(rows, COLS_VENTAS)
    return {"rows": rows, "totals": totals, "columns": COLS_VENTAS}


def libro_compras_rows(raw_invoices):
    """Libro de Compras: inbound invoices incl. retentions, ICE, imports."""
    rows = []
    for row in normalize_invoices(raw_invoices):
        rows.append(
            {
                "fecha_registro": row["fecha_registro"],
                "fecha": row["fecha"],
                "tp_id": row["tp_id"],
                "identificacion": row["identificacion"],
                "razon_social": row["razon_social"],
                "doc_code": row["doc_code"],
                "doc_name": row["doc_name"],
                "clave_acceso": row["clave_acceso"],
                "autorizacion": row["autorizacion"],
                "sustento": row["sustento"],
                "base_0": round2(row["base_0"]),
                "base_5": round2(row["base_5"]),
                "base_15": round2(row["base_15"]),
                "base_exenta": round2(row["base_exenta"]),
                "base_no_objeto": round2(row["base_no_objeto"]),
                "ice": round2(row["ice"]),
                "iva": round2(row["iva"]),
                "ret_ir": round2(row["ret_ir"]),
                "ret_iva": round2(row["ret_iva"]),
                "importacion": "SI" if row["is_import"] else "NO",
                "total": round2(row["total"]),
            }
        )
    totals = _sum_totals(rows, COLS_COMPRAS)
    return {"rows": rows, "totals": totals, "columns": COLS_COMPRAS}


def libro_retenciones_rows(raw_retentions):
    """Libro de Retenciones: IR + IVA withheld, one row per comprobante."""
    rows = []
    for raw in raw_retentions:
        rows.append(
            {
                "fecha": raw.get("fecha") or "",
                "numero": raw.get("numero") or "",
                "autorizacion": raw.get("autorizacion") or "",
                "fecha_factura": raw.get("fecha_factura") or "",
                "tipo": {None: "IR", "ir": "IR", "iva": "IVA", "isd": "ISD"}.get(
                    raw.get("kind"), raw.get("kind") or "IR"
                ),
                "codigo": raw.get("code") or "",
                "concepto": raw.get("name") or "",
                "tercero": raw.get("partner") or "",
                "identificacion": raw.get("identificacion") or "",
                "comprobante": raw.get("comprobante") or "",
                "base": round2(raw.get("base")),
                "percent": _num(raw.get("percent")),
                "amount": round2(raw.get("amount")),
            }
        )
    totals = {
        "base": round2(sum(r["base"] for r in rows)),
        "amount": round2(sum(r["amount"] for r in rows)),
        "count": len(rows),
        "amount_ir": round2(
            sum(r["amount"] for r in rows if r["tipo"] in ("IR", "ISD"))
        ),
        "amount_iva": round2(sum(r["amount"] for r in rows if r["tipo"] == "IVA")),
    }
    return {"rows": rows, "totals": totals, "columns": COLS_RETENCIONES}


def _sum_totals(rows, columns):
    numeric = {key for key, _label in columns}
    totals = {"count": len(rows)}
    for key in numeric:
        if key in ("fecha", "doc_code", "doc_name", "identificacion",
                   "razon_social", "clave_acceso", "estab_pto", "secuencial",
                   "tarifa", "estado_linea", "tp_id", "autorizacion",
                   "sustento", "importacion", "fecha_registro", "tipo",
                   "codigo", "concepto", "tercero", "comprobante", "numero",
                   "autorizacion", "fecha_factura", "percent", "is_export",
                   "tipo_emision"):
            continue
        try:
            totals[key] = round2(sum(_num(r.get(key)) for r in rows))
        except TypeError:
            continue
    return totals


def libro_bancos_rows(raw_lines, opening=0.0):
    """Libro de Bancos (BCE): per-account movements with running balance.

    ``raw_lines``: [{'fecha', 'documento', 'cuenta', 'partner', 'glosa',
                     'debit', 'credit'}] already filtered by bank journal.
    ``opening``: balance brought forward (debit positive).
    """
    ordered = sorted(
        raw_lines, key=lambda l: (str(l.get("fecha") or ""), str(l.get("documento") or ""))
    )
    rows = []
    saldo = _num(opening)
    total_debit = total_credit = 0.0
    for line in ordered:
        debit = _num(line.get("debit"))
        credit = _num(line.get("credit"))
        total_debit += debit
        total_credit += credit
        saldo += debit - credit
        rows.append(
            {
                "fecha": line.get("fecha") or "",
                "documento": line.get("documento") or "",
                "cuenta": line.get("cuenta") or "",
                "partner": line.get("partner") or "",
                "glosa": line.get("glosa") or "",
                "debit": round2(debit),
                "credit": round2(credit),
                "saldo": round2(saldo),
            }
        )
    return {
        "rows": rows,
        "columns": COLS_BANCOS,
        "opening": round2(opening),
        "totals": {
            "debit": round2(total_debit),
            "credit": round2(total_credit),
            "saldo": round2(saldo),
            "count": len(rows),
        },
    }


def libro_caja_rows(raw_lines, opening=0.0):
    """Libro de Caja: same mechanics as bancos, cash journals."""
    result = libro_bancos_rows(raw_lines, opening=opening)
    result["columns"] = COLS_BANCOS
    return result


def libro_diario_rows(raw_moves):
    """Libro Diario: asiento / fecha / cuenta / detalle / debe / haber.

    ``raw_moves``: [{'name', 'date', 'ref', 'lines': [{'account_code',
    'account_name', 'label', 'debit', 'credit'}]}] ordered by date.
    """
    rows = []
    ordered = sorted(raw_moves, key=lambda m: (str(m.get("date") or ""),
                                               str(m.get("name") or "")))
    for move in ordered:
        for line in move.get("lines") or []:
            rows.append(
                {
                    "asiento": move.get("name") or "",
                    "fecha": move.get("date") or "",
                    "cuenta": line.get("account_code") or "",
                    "nombre_cuenta": line.get("account_name") or "",
                    "detalle": line.get("label")
                    or move.get("ref")
                    or move.get("name")
                    or "",
                    "debe": round2(line.get("debit")),
                    "haber": round2(line.get("credit")),
                }
            )
    totals = {
        "debe": round2(sum(r["debe"] for r in rows)),
        "haber": round2(sum(r["haber"] for r in rows)),
        "count": len(rows),
    }
    totals["difference"] = round2(totals["debe"] - totals["haber"])
    return {"rows": rows, "columns": COLS_DIARIO, "totals": totals}


def libro_mayor_rows(raw_moves, openings=None):
    """Libro Mayor: per-account ledger with running saldo.

    Returns {'accounts': [{'code','name','rows','debit','credit','balance'}],
             'columns': ..., 'totals': {...}}
    ``openings``: {account_code: balance brought forward (debit positive)}
    """
    openings = openings or {}
    grouped = {}
    order = []
    ordered = sorted(raw_moves, key=lambda m: (str(m.get("date") or ""),
                                               str(m.get("name") or "")))
    for move in ordered:
        for line in move.get("lines") or []:
            code = line.get("account_code") or ""
            if code not in grouped:
                grouped[code] = {
                    "code": code,
                    "name": line.get("account_name") or "",
                    "lines": [],
                }
                order.append(code)
            grouped[code]["lines"].append(
                {
                    "asiento": move.get("name") or "",
                    "fecha": move.get("date") or "",
                    "detalle": line.get("label") or move.get("ref") or "",
                    "debit": _num(line.get("debit")),
                    "credit": _num(line.get("credit")),
                }
            )

    accounts = []
    totals = {"debe": 0.0, "haber": 0.0}
    for code in order:
        account = grouped[code]
        saldo = _num(openings.get(code))
        rows = []
        debit = credit = 0.0
        for line in account["lines"]:
            debit += line["debit"]
            credit += line["credit"]
            saldo += line["debit"] - line["credit"]
            rows.append(
                {
                    "cuenta": code,
                    "nombre_cuenta": account["name"],
                    "asiento": line["asiento"],
                    "fecha": line["fecha"],
                    "detalle": line["detalle"],
                    "debe": round2(line["debit"]),
                    "haber": round2(line["credit"]),
                    "saldo": round2(saldo),
                }
            )
        totals["debe"] += debit
        totals["haber"] += credit
        accounts.append(
            {
                "code": code,
                "name": account["name"],
                "rows": rows,
                "debit": round2(debit),
                "credit": round2(credit),
                "balance": round2(saldo),
            }
        )
    return {
        "accounts": accounts,
        "columns": COLS_MAYOR,
        "totals": {
            "debe": round2(totals["debe"]),
            "haber": round2(totals["haber"]),
            "count": len(order),
        },
    }


# ===========================================================================
# TRIAL BALANCE (shared helper) + INVENTARIOS Y BALANCES
# ===========================================================================

# NEC / SUPERCIAS group mapping by first code digit (KB_SUPERCIAS 3.4.2)
GROUP_LABELS = {
    "1": "ACTIVO",
    "2": "PASIVO",
    "3": "PATRIMONIO",
    "4": "INGRESOS",
    "5": "COSTOS Y GASTOS",
}

CURRENT_ASSET_TYPES = (
    "asset_receivable", "asset_cash", "asset_current", "asset_prepayments",
)
NON_CURRENT_ASSET_TYPES = ("asset_fixed", "asset_non_current")
CURRENT_LIAB_TYPES = ("liability_payable", "liability_current",
                      "liability_credit_card")
NON_CURRENT_LIAB_TYPES = ("liability_non_current",)


def _code_group(code, account_type=""):
    """Return '1'..'5' NEC group for an account (code prefix, type fallback)."""
    first = str(code or "")[:1]
    if first in GROUP_LABELS:
        return first
    at = str(account_type or "")
    if at.startswith("asset"):
        return "1"
    if at.startswith("liability"):
        return "2"
    if at == "equity" or at.startswith("equity"):
        return "3"
    if at.startswith("income"):
        return "4"
    if at.startswith("expense"):
        return "5"
    return "?"


def trial_balance(raw_lines):
    """Aggregate journal lines into a trial balance.

    ``raw_lines``: [{'code','name','account_type','debit','credit'}]
    Returns rows sorted by code with debit, credit and balance (debit+).
    """
    grouped = {}
    for line in raw_lines:
        code = line.get("code") or ""
        entry = grouped.setdefault(
            code,
            {
                "code": code,
                "name": line.get("name") or "",
                "account_type": line.get("account_type") or "",
                "debit": 0.0,
                "credit": 0.0,
            },
        )
        entry["debit"] += _num(line.get("debit"))
        entry["credit"] += _num(line.get("credit"))
        if not entry["account_type"] and line.get("account_type"):
            entry["account_type"] = line.get("account_type")

    rows = []
    for code in sorted(grouped):
        entry = grouped[code]
        entry["balance"] = round2(entry["debit"] - entry["credit"])
        entry["debit"] = round2(entry["debit"])
        entry["credit"] = round2(entry["credit"])
        entry["group"] = _code_group(code, entry["account_type"])
        entry["group_label"] = GROUP_LABELS.get(entry["group"], "OTROS")
        rows.append(entry)

    totals = {
        "debit": round2(sum(r["debit"] for r in rows)),
        "credit": round2(sum(r["credit"] for r in rows)),
    }
    totals["difference"] = round2(totals["debit"] - totals["credit"])
    return {"rows": rows, "totals": totals}


def inventarios_balances(trial, valuation_lines=None):
    """Libro de Inventarios y Balances.

    - Closing trial balance grouped by NEC 6-group (per account).
    - Inventory valuation lines (optional): [{'name','quantity','unit_cost',
      'value'}] - normally from stock.valuation.layer when stock is present.
    """
    groups = {}
    for row in trial["rows"]:
        bucket = groups.setdefault(
            row["group"],
            {
                "group": row["group"],
                "label": row["group_label"],
                "rows": [],
                "debit": 0.0,
                "credit": 0.0,
            },
        )
        bucket["rows"].append(row)
        bucket["debit"] += row["debit"]
        bucket["credit"] += row["credit"]

    group_list = []
    for key in sorted(groups):
        bucket = groups[key]
        bucket["debit"] = round2(bucket["debit"])
        bucket["credit"] = round2(bucket["credit"])
        bucket["balance"] = round2(bucket["debit"] - bucket["credit"])
        group_list.append(bucket)

    valuation = []
    for line in valuation_lines or []:
        qty = _num(line.get("quantity"))
        cost = _num(line.get("unit_cost"))
        value = line.get("value")
        valuation.append(
            {
                "name": line.get("name") or "",
                "quantity": qty,
                "unit_cost": round2(cost),
                "value": round2(value if value is not None else qty * cost),
            }
        )
    return {
        "groups": group_list,
        "totals": trial["totals"],
        "valuation": valuation,
        "valuation_total": round2(sum(v["value"] for v in valuation)),
    }


# ===========================================================================
# SRI FORM 104  (IVA + ICE)  - codes per SRS_MODULE_09 section 3.2
# ===========================================================================

DEFAULT_IVA_RATE = 0.15  # KB_TAX_RATES_WITHHOLDINGS 1.1 (configurable)


def form104_calculate(ventas_raw, compras_raw, iva_rate=DEFAULT_IVA_RATE):
    """Real Form 104 (IVA + ICE) computation over raw invoices.

    Casilleros per SRS_MODULE_09 section 3.2:
        411 Ventas locales tarifa 15%      421 Adquisiciones tarifa 15%
        412 Ventas locales tarifa 0%       422 Adquisiciones tarifa 0%
        415 Exportaciones                  480 IVA en Ventas (debito)
        413 Ventas exentas                 520 IVA en Compras (credito)
        414 Ventas no objeto               601 Retenciones IVA recibidas
                                          699 Impuesto a pagar

    Returns a dict:
      {'sections': [{'title','lines': [{'code','label','amount','note'}]}],
       'debito': float, 'credito': float, 'saldo': float,
       'saldo_tipo': 'A PAGAR'|'A FAVOR'}
    """
    ventas = [invoice_report_row(r) for r in ventas_raw]
    compras = [invoice_report_row(r) for r in compras_raw]

    # --- Ventas (domestic) -------------------------------------------------
    domestic = [v for v in ventas if not v["is_export"]]
    export_rows = [v for v in ventas if v["is_export"]]

    ventas_grav_15 = sum(v["base_15"] for v in domestic)
    ventas_grav_5 = sum(v["base_5"] for v in domestic)
    ventas_tarifa_0 = sum(v["base_0"] for v in domestic)
    ventas_exentas = sum(v["base_exenta"] for v in domestic)
    ventas_no_objeto = sum(v["base_no_objeto"] for v in domestic)
    ventas_other = sum(v["base_other"] for v in domestic)
    exportaciones = sum(v["base_total"] for v in export_rows)

    iva_ventas = sum(v["iva"] for v in ventas)          # incluye exportaciones
    ice_ventas = sum(v["ice"] for v in ventas)

    # --- Compras -----------------------------------------------------------
    compras_grav_15 = sum(c["base_15"] for c in compras)
    compras_grav_5 = sum(c["base_5"] for c in compras)
    compras_tarifa_0 = sum(c["base_0"] for c in compras)
    compras_exentas = sum(c["base_exenta"] for c in compras)
    compras_no_objeto = sum(c["base_no_objeto"] for c in compras)
    iva_compras = sum(c["iva"] for c in compras)
    ice_compras = sum(c["ice"] for c in compras)

    # --- Withholdings ------------------------------------------------------
    # Retenciones de IVA "recibidas": las que NUESTROS CLIENTES nos practican
    # sobre nuestras ventas - el comprador ya deposito ese IVA a nuestro favor,
    # por lo tanto reduce el saldo del Formulario 104 (casillero 601).
    # Las retenciones que NOSOTROS practicamos en compras (depositadas como
    # agente de retencion) ya estan incluidas en el IVA pagado (520) y se
    # reportan en el Formulario 103 / 721-725: aqui van solo informativas.
    ret_iva_recibidas = sum(v["ret_iva"] for v in ventas)       # sales side
    ret_iva_practicadas = sum(c["ret_iva"] for c in compras)    # purchases
    ret_ir_practicadas = sum(v["ret_ir"] for v in ventas)

    debito = iva_ventas + ice_ventas
    credito = iva_compras + ice_compras + ret_iva_recibidas
    saldo = debito - credito
    saldo_tipo = "A PAGAR" if saldo >= 0 else "A FAVOR"

    def _line(code, label, amount, note=""):
        return {"code": code, "label": label, "amount": round2(amount),
                "note": note}

    grav = [
        _line("411", "Ventas locales grabadas tarifa 15%", ventas_grav_15),
        _line("411b", "Ventas locales grabadas tarifa 5%", ventas_grav_5,
              "Construccion / materiales (tarifa reducida)"),
        _line("412", "Ventas locales tarifa 0%", ventas_tarifa_0),
        _line("415", "Exportaciones de bienes y servicios", exportaciones),
    ]
    no_grav = [
        _line("413", "Ventas exentas", ventas_exentas),
        _line("414", "Ventas no objeto de IVA", ventas_no_objeto),
        _line("416", "Otras bases tarifarias", ventas_other),
    ]
    debito_lines = [
        _line("480", "IVA generado en ventas (debito)", iva_ventas,
              "Suma IVA cobrado del periodo"),
        _line("ICE-D", "ICE por ventas", ice_ventas,
              "Consumos especiales facturados"),
    ]
    compras_lines = [
        _line("421", "Adquisiciones locales grabadas 15%", compras_grav_15),
        _line("421b", "Adquisiciones locales grabadas 5%", compras_grav_5),
        _line("422", "Adquisiciones locales tarifa 0%", compras_tarifa_0),
        _line("423", "Adquisiciones exentas", compras_exentas),
        _line("424", "Adquisiciones no objeto de IVA", compras_no_objeto),
    ]
    credito_lines = [
        _line("520", "IVA pagado en compras (credito)", iva_compras),
        _line("ICE-C", "ICE pagado en compras", ice_compras,
              "Credito tributario ICE"),
        _line("601", "Retenciones de IVA recibidas", ret_iva_recibidas,
              "Practicadas por clientes sobre nuestras ventas (depositadas "
              "a nuestro favor)"),
    ]
    info_lines = [
        _line("605", "Retenciones de IVA practicadas en compras",
              ret_iva_practicadas, "Depositadas como agente - Formulario 103"),
        _line("RET-IR", "Retenciones en la fuente practicadas en ventas",
              ret_ir_practicadas, "Informativo (Formulario 103)"),
    ]
    saldo_lines = [
        _line("699", "Saldo del periodo (%s)" % saldo_tipo, saldo,
              "Debito tributario - Credito tributario"),
    ]

    return {
        "sections": [
            {"title": "VENTAS (DEBITO TRIBUTARIO)", "lines": grav},
            {"title": "VENTAS NO GRAVADAS", "lines": no_grav},
            {"title": "IVA / ICE DEL PERIODO", "lines": debito_lines},
            {"title": "ADQUISICIONES (CREDITO TRIBUTARIO)", "lines": compras_lines},
            {"title": "CREDITO TRIBUTARIO", "lines": credito_lines},
            {"title": "INFORMATIVO", "lines": info_lines},
            {"title": "SALDO", "lines": saldo_lines},
        ],
        "iva_rate": iva_rate,
        "debito": round2(debito),
        "credito": round2(credito),
        "saldo": round2(saldo),
        "saldo_tipo": saldo_tipo,
        "ventas_gravadas_15": round2(ventas_grav_15),
        "ventas_tarifa_0": round2(ventas_tarifa_0),
        "ventas_exentas": round2(ventas_exentas),
        "exportaciones": round2(exportaciones),
        "iva_ventas": round2(iva_ventas),
        "iva_compras": round2(iva_compras),
        "ice_ventas": round2(ice_ventas),
        "ice_compras": round2(ice_compras),
        "ret_iva_recibidas": round2(ret_iva_recibidas),
        "ret_iva_practicadas": round2(ret_iva_practicadas),
    }


def progressive_tax(taxable_base, brackets):
    """Impuesto causado by the official progressive table.

    ``brackets``: [{'basic_fraction','excess_until','basic_tax','marginal_rate'}]
    Formula (l10n_ec_income_tax.L10nEcTaxTable.get_tax_for_base):
        basic_tax + (base - basic_fraction) * marginal_rate / 100
    """
    base = _num(taxable_base)
    if not brackets:
        return 0.0
    rows = sorted(brackets, key=lambda b: _num(b.get("basic_fraction")))
    chosen = None
    for row in rows:
        low = _num(row.get("basic_fraction"))
        high = _num(row.get("excess_until"))
        if low <= base <= (high if high > 0 else float("inf")):
            chosen = row
            break
    if chosen is None:  # below the first bracket
        chosen = rows[0]
    if base <= _num(chosen.get("basic_fraction")):
        # e.g. base inside a gap between brackets -> use previous bracket
        previous = None
        for row in rows:
            if _num(row.get("basic_fraction")) <= base:
                previous = row
        chosen = previous or rows[0]
    excess = max(base - _num(chosen.get("basic_fraction")), 0.0)
    return _num(chosen.get("basic_tax")) + excess * (
        _num(chosen.get("marginal_rate")) / 100.0
    )


# Progressive brackets 2026 - source: l10n_ec_income_tax/data/tax_table_2026_data.xml
# (Resolucion NAC-DGERCGC25-00000043).  Used only as fallback when the
# l10n_ec.tax.table model is not installed; the wizard prefers the model.
DEFAULT_TAX_BRACKETS_2026 = [
    {"basic_fraction": 0.0, "excess_until": 12208.0, "basic_tax": 0.0, "marginal_rate": 0.0},
    {"basic_fraction": 12208.01, "excess_until": 15549.0, "basic_tax": 0.0, "marginal_rate": 5.0},
    {"basic_fraction": 15549.01, "excess_until": 20188.0, "basic_tax": 167.0, "marginal_rate": 10.0},
    {"basic_fraction": 20188.01, "excess_until": 26700.0, "basic_tax": 631.0, "marginal_rate": 12.0},
    {"basic_fraction": 26700.01, "excess_until": 35136.0, "basic_tax": 1412.0, "marginal_rate": 15.0},
    {"basic_fraction": 35136.01, "excess_until": 46575.0, "basic_tax": 2678.0, "marginal_rate": 20.0},
    {"basic_fraction": 46575.01, "excess_until": 62005.0, "basic_tax": 4965.0, "marginal_rate": 25.0},
    {"basic_fraction": 62005.01, "excess_until": 82679.0, "basic_tax": 8823.0, "marginal_rate": 30.0},
    {"basic_fraction": 82679.01, "excess_until": 109956.0, "basic_tax": 15025.0, "marginal_rate": 35.0},
    {"basic_fraction": 109956.01, "excess_until": 999999999.0, "basic_tax": 24572.0, "marginal_rate": 37.0},
]


# ===========================================================================
# SRI FORM 103  (Retenciones en la fuente) - codes per SRS_MODULE_09 3.3
# ===========================================================================

# Codes per SRI Tabla 19 (Res. NAC-DGERCGC26-00000009, RO 233) and
# Form 104 casilleros 721-731 (Res. NAC-DGERCGC20-00000061)
FORM103_LABELS = {
    "303": "Honorarios, comisiones, dietas",
    "304": "Servicios predomina el intelecto",
    "307": "Servicios donde predomina la mano de obra",
    "308": "Uso o aprovechamiento de la imagen o renombre",
    "309": "Publicidad y agencias de comunicación",
    "310": "Transporte privado de pasajeros o carga",
    "312": "Transferencia de bienes muebles de naturaleza corporal",
    "319": "Cuotas de arrendamiento mercantil",
    "320": "Arrendamiento de inmuebles",
    "322": "Seguros y reaseguros",
    "323": "Rendimientos financieros",
    "721": "Retencion IVA 10% (bienes)",
    "723": "Retencion IVA 20% (servicios)",
    "725": "Retencion IVA 30%",
    "727": "Retencion IVA 50%",
    "729": "Retencion IVA 70%",
    "731": "Retencion IVA 100% (liquidacion de compra / importacion servicios)",
}


def form103_calculate(withholding_lines):
    """Form 103: withholdings PRACTICADAS (as withholding agent), grouped by
    SRI code.  ``withholding_lines``: [{'code','name','kind','base',
    'percent','amount'}] - IR and IVA lines are separated (tax_type 1/2)."""
    grouped = {}
    for line in withholding_lines:
        kind = line.get("kind") or "ir"
        if kind == "iva":
            continue  # IVA withholdings belong to Form 104 (601/721-725)
        code = str(line.get("code") or "000")
        entry = grouped.setdefault(
            code,
            {
                "code": code,
                "name": line.get("name") or FORM103_LABELS.get(code, "Code %s" % code),
                "base": 0.0,
                "amount": 0.0,
                "percent": _num(line.get("percent")),
            },
        )
        entry["base"] += _num(line.get("base"))
        entry["amount"] += _num(line.get("amount"))
        if not entry["percent"]:
            entry["percent"] = _num(line.get("percent"))

    rows = []
    for code in sorted(grouped):
        entry = grouped[code]
        if not entry["percent"] and entry["base"]:
            entry["percent"] = round(entry["amount"] / entry["base"] * 100.0, 4)
        entry["base"] = round2(entry["base"])
        entry["amount"] = round2(entry["amount"])
        entry["label"] = FORM103_LABELS.get(code, entry["name"])
        rows.append(entry)

    return {
        "rows": rows,
        "total_base": round2(sum(r["base"] for r in rows)),
        "total_amount": round2(sum(r["amount"] for r in rows)),
    }


# ===========================================================================
# SRI FORM 101 / 102  (Impuesto a la Renta)
# ===========================================================================

# Corporate rate grounded in KB_TAX_RATES_WITHHOLDINGS 4.1 (configurable)
DEFAULT_CORPORATE_RATE = 0.25


def form101_calculate(data, corporate_rate=DEFAULT_CORPORATE_RATE):
    """Form 101 - Renta de sociedades (personas juridicas).

    ``data``: {'ingresos_gravados','ingresos_no_gravados','ingresos_no_sujetos',
               'costos_ventas','gastos_operacionales','otros_ingresos',
               'otros_gastos','retenciones','pagos_previos'}
    """
    ingresos_grav = _num(data.get("ingresos_gravados"))
    ingresos_nog = _num(data.get("ingresos_no_gravados"))
    ingresos_nosuj = _num(data.get("ingresos_no_sujetos"))
    costos = _num(data.get("costos_ventas"))
    gastos = _num(data.get("gastos_operacionales"))
    otros_ingresos = _num(data.get("otros_ingresos"))
    otros_gastos = _num(data.get("otros_gastos"))
    retenciones = _num(data.get("retenciones"))
    pagos_previos = _num(data.get("pagos_previos"))

    total_ingresos = ingresos_grav + ingresos_nog + ingresos_nosuj + otros_ingresos
    utilidad_bruta = total_ingresos - costos
    utilidad_operacional = utilidad_bruta - gastos
    base_imponible = utilidad_operacional - otros_gastos
    impuesto = max(base_imponible, 0.0) * corporate_rate
    saldo = impuesto - retenciones - pagos_previos
    saldo_tipo = "A PAGAR" if saldo >= 0 else "A FAVOR"

    def _line(code, label, amount, note=""):
        return {"code": code, "label": label, "amount": round2(amount),
                "note": note}

    return {
        "sections": [
            {"title": "INGRESOS", "lines": [
                _line("01", "Ingresos gravados", ingresos_grav),
                _line("02", "Ingresos no gravados (tarifa 0 / exentos)", ingresos_nog),
                _line("03", "Ingresos no sujetos", ingresos_nosuj),
                _line("04", "Otros ingresos", otros_ingresos),
                _line("05", "TOTAL INGRESOS", total_ingresos),
            ]},
            {"title": "COSTOS Y GASTOS", "lines": [
                _line("06", "Costos de ventas", costos),
                _line("07", "Utilidad bruta", utilidad_bruta),
                _line("08", "Gastos operacionales", gastos),
                _line("09", "Utilidad operacional", utilidad_operacional),
                _line("10", "Otros gastos (financieros, etc.)", otros_gastos),
            ]},
            {"title": "IMPUESTO", "lines": [
                _line("11", "BASE IMPONIBLE", base_imponible),
                _line("12", "Impuesto a la renta causado",
                      impuesto, "Tarifa: %.2f%%" % (corporate_rate * 100)),
                _line("13", "Retenciones en la fuente", retenciones),
                _line("14", "Pagos previos", pagos_previos),
                _line("15", "SALDO (%s)" % saldo_tipo, saldo),
            ]},
        ],
        "ingresos": round2(total_ingresos),
        "costos": round2(costos),
        "gastos": round2(gastos),
        "base_imponible": round2(base_imponible),
        "tarifa": corporate_rate,
        "impuesto": round2(impuesto),
        "retenciones": round2(retenciones),
        "saldo": round2(saldo),
        "saldo_tipo": saldo_tipo,
    }


def form102_calculate(data, brackets=None):
    """Form 102 - Renta de personas naturales / sucesiones (annual).

    Same structure as 101 but the tax is computed with the PROGRESSIVE
    table (Res. NAC-DGERCGC25-00000043) instead of the flat corporate rate.
    ``data``: same keys as form101 + optional 'aportes_iess'.
    """
    brackets = brackets or DEFAULT_TAX_BRACKETS_2026
    aportes = _num(data.get("aportes_iess"))

    # reuse form101 section structure (rate 0), then replace the tax block
    result = form101_calculate(data, corporate_rate=0.0)
    base_imponible = max(
        _num(data.get("ingresos_gravados")) + _num(data.get("otros_ingresos"))
        - _num(data.get("costos_ventas")) - _num(data.get("gastos_operacionales"))
        - _num(data.get("otros_gastos")) - aportes,
        0.0,
    )
    impuesto = progressive_tax(base_imponible, brackets)
    retenciones = _num(data.get("retenciones"))
    pagos_previos = _num(data.get("pagos_previos"))
    saldo = impuesto - retenciones - pagos_previos
    saldo_tipo = "A PAGAR" if saldo >= 0 else "A FAVOR"

    for section in result["sections"]:
        if section["title"] == "IMPUESTO":
            section["lines"] = [
                {"code": "11", "label": "APORTES IESS personal",
                 "amount": round2(aportes), "note": ""},
                {"code": "11b", "label": "BASE IMPONIBLE",
                 "amount": round2(base_imponible), "note": ""},
                {"code": "12", "label": "Impuesto a la renta causado (tabla progresiva)",
                 "amount": round2(impuesto),
                 "note": "Res. NAC-DGERCGC25-00000043"},
                {"code": "13", "label": "Retenciones en la fuente",
                 "amount": round2(retenciones), "note": ""},
                {"code": "14", "label": "Pagos previos",
                 "amount": round2(pagos_previos), "note": ""},
                {"code": "15", "label": "SALDO (%s)" % saldo_tipo,
                 "amount": round2(saldo), "note": ""},
            ]
    result["base_imponible"] = round2(base_imponible)
    result["impuesto"] = round2(impuesto)
    result["saldo"] = round2(saldo)
    result["saldo_tipo"] = saldo_tipo
    return result


# ===========================================================================
# SRI FORM 107 (personas naturales) + FORM 108 (notas de credito)
# ===========================================================================


def form107_calculate(data, brackets=None):
    """Form 107 - Renta de personas naturales.

    ``data``: {'ingresos': {'trabajo','tercera','cuarta','capital','otros'},
               'aportes_iess', 'retenciones', 'pagos_previos',
               'gastos_personales',           # deductible (capped) amount
               'rebaja': {'expenses','n_baskets','basket_cost','rate'} or None}
    """
    brackets = brackets or DEFAULT_TAX_BRACKETS_2026
    ingresos = data.get("ingresos") or {}
    ingreso_trabajo = _num(ingresos.get("trabajo"))
    ingreso_tercera = _num(ingresos.get("tercera"))
    ingreso_cuarta = _num(ingresos.get("cuarta"))
    ingreso_capital = _num(ingresos.get("capital"))
    ingreso_otros = _num(ingresos.get("otros"))
    total_ingresos = (ingreso_trabajo + ingreso_tercera + ingreso_cuarta +
                      ingreso_capital + ingreso_otros)

    aportes = _num(data.get("aportes_iess"))
    gastos = _num(data.get("gastos_personales"))
    retenciones = _num(data.get("retenciones"))
    pagos_previos = _num(data.get("pagos_previos"))

    base = max(total_ingresos - aportes - gastos, 0.0)
    impuesto_causado = progressive_tax(base, brackets)

    rebaja = data.get("rebaja")
    rebaja_value = 0.0
    rebaja_note = ""
    if rebaja:
        rebaja_value = rebaja_tributaria(
            _num(rebaja.get("expenses")),
            _num(rebaja.get("n_baskets")),
            _num(rebaja.get("basket_cost")),
            rate=_num(rebaja.get("rate")) or 0.18,
        )
        rebaja_note = "Res. NAC-DGERCGC25-00000043: min(gastos, %s x canasta) x 18%%" % (
            rebaja.get("n_baskets"),
        )

    impuesto = impuesto_causado - rebaja_value
    saldo = impuesto - retenciones - pagos_previos
    saldo_tipo = "A PAGAR" if saldo >= 0 else "A FAVOR"

    def _line(code, label, amount, note=""):
        return {"code": code, "label": label, "amount": round2(amount),
                "note": note}

    sections = [
        {"title": "INGRESOS", "lines": [
            _line("301", "Ingresos por trabajo personal (relacion de dependencia)",
                  ingreso_trabajo),
            _line("302", "Ingresos de terceras categorias (actividad economica)",
                  ingreso_tercera),
            _line("303", "Ingresos de cuarta categoria (trabajo independiente)",
                  ingreso_cuarta),
            _line("305", "Ingresos de capital (arrendamiento, rendimientos)",
                  ingreso_capital),
            _line("309", "Otros ingresos", ingreso_otros),
            _line("349", "TOTAL INGRESOS", total_ingresos),
            _line("351", "Aportes personales IESS", aportes),
        ]},
        {"title": "GASTOS PERSONALES Y CAUSADO", "lines": [
            _line("402", "Gastos personales deducibles", gastos,
                  "Tope configurable por categoria (SBU)"),
            _line("410", "BASE IMPONIBLE", base),
            _line("411", "Impuesto causado (tabla progresiva 0-37%)",
                  impuesto_causado),
            _line("412", "Rebaja tributaria", rebaja_value, rebaja_note),
            _line("413", "Impuesto a pagar antes de retenciones", impuesto),
        ]},
        {"title": "RETENCIONES Y SALDO", "lines": [
            _line("420", "Retenciones en la fuente practicadas", retenciones),
            _line("421", "Pagos previos / anticipos", pagos_previos),
            _line("422", "SALDO (%s)" % saldo_tipo, saldo),
        ]},
    ]
    return {
        "sections": sections,
        "total_ingresos": round2(total_ingresos),
        "aportes_iess": round2(aportes),
        "gastos_personales": round2(gastos),
        "base_imponible": round2(base),
        "impuesto_causado": round2(impuesto_causado),
        "rebaja": round2(rebaja_value),
        "impuesto": round2(impuesto),
        "retenciones": round2(retenciones),
        "saldo": round2(saldo),
        "saldo_tipo": saldo_tipo,
    }


def rebaja_tributaria(expenses, n_baskets, basket_cost, rate=0.18):
    """Rebaja Tributaria (LORTI / Res. NAC-DGERCGC25-00000043).

    ``min(projected_expenses, n_baskets * basket_cost) * 18%`` -
    formula mirrored from l10n_ec_income_tax.L10nEcFamilyBasket.
    """
    if not basket_cost or n_baskets is None:
        return 0.0
    max_base = _num(n_baskets) * _num(basket_cost)
    return min(_num(expenses), max_base) * _num(rate or 0.18)


# Family loads -> number of baskets (l10n_ec_income_tax, Res. 00000043)
BASKETS_BY_LOADS = {0: 7.0, 1: 9.0, 2: 11.0, 3: 14.0, 4: 17.0}
BASKETS_MAX = 20.0
BASKETS_CATASTROPHIC = 20.0


def n_baskets_for_loads(family_loads, catastrophic=False):
    if catastrophic:
        return BASKETS_CATASTROPHIC
    loads = int(family_loads or 0)
    return BASKETS_BY_LOADS.get(loads, BASKETS_MAX)


# Gastos personales caps: the in-repo docs DO NOT state the SMMLV limits
# (checked docs/srs/* and l10n_ec_sri/docs/11_regulatory_knowledge_base/*),
# therefore caps are CONFIGURABLE (ir.config_parameter) and a category with
# no configured cap is reported without limiting (flagged in the output).
GASTOS_PERSONALES_CATEGORIES = [
    ("vivienda", "Vivienda (alquiler, servicios basicos, mantenimiento)"),
    ("salud", "Salud (consultas, medicinas, seguros)"),
    ("educacion", "Educacion, arte y cultura"),
    ("alimentacion", "Alimentacion"),
    ("vestimenta", "Vestimenta y calzado"),
    ("turismo", "Turismo nacional"),
]
GASTOS_CAP_PARAM = "l10n_ec.gastos_personales.cap.%s_smmlv"


def gastos_personales_calculate(gastos, caps, sbu):
    """Compute deductible gastos personales per category.

    ``gastos``: {category: amount actually spent}
    ``caps``:   {category: cap_in_SMMLV or None}  (None = not configured)
    ``sbu``:    Salario Basico Unificado of the fiscal year.
    Returns rows with cap in USD and deducible = min(spent, cap*SBU).
    """
    rows = []
    for key, label in GASTOS_PERSONALES_CATEGORIES:
        spent = _num(gastos.get(key))
        cap = caps.get(key)
        configured = cap is not None
        cap_usd = _num(cap) * _num(sbu) if configured else None
        deducible = min(spent, cap_usd) if configured else spent
        rows.append({
            "code": key,
            "label": label,
            "spent": round2(spent),
            "cap_smmlv": cap if configured else None,
            "cap_usd": round2(cap_usd) if configured else None,
            "deducible": round2(deducible),
            "configured": configured,
        })
    total_spent = round2(sum(r["spent"] for r in rows))
    total_deducible = round2(sum(r["deducible"] for r in rows))
    return {
        "rows": rows,
        "sbu": round2(sbu),
        "total_spent": total_spent,
        "total_deducible": total_deducible,
        "unconfigured": [r["code"] for r in rows if not r["configured"]],
    }


def form108_calculate(credit_notes_raw):
    """Form 108 - Notas de credito emitidas (anulaciones / devoluciones).

    ``credit_notes_raw``: [{'fecha','identificacion','razon_social','doc_code',
                            'clave_acceso','total'}]  (positive totals)
    """
    rows = []
    for raw in credit_notes_raw:
        rows.append({
            "fecha": raw.get("fecha") or "",
            "identificacion": raw.get("identificacion") or "",
            "razon_social": raw.get("razon_social") or "",
            "doc_code": raw.get("doc_code") or "04",
            "clave_acceso": raw.get("clave_acceso") or "",
            "total": round2(abs(_num(raw.get("total")))),
        })
    return {
        "rows": rows,
        "count": len(rows),
        "total": round2(sum(r["total"] for r in rows)),
    }


# ===========================================================================
# ESTADOS FINANCIEROS (SUPERCIAS / NIIF) - KB_SUPERCIAS 3.2
# ===========================================================================

def _is_current_asset(row):
    return row.get("account_type") in CURRENT_ASSET_TYPES


def _is_current_liab(row):
    return row.get("account_type") in CURRENT_LIAB_TYPES


def balance_general(trial_rows, period_label=""):
    """Estado de Situacion Financiera (Balance General).

    ``trial_rows``: rows from trial_balance() - balance is DEBIT POSITIVE.
    Assets shown positive; liabilities & equity as credit balances.
    """
    activo_c, activo_nc = [], []
    pasivo_c, pasivo_nc, patrimonio = [], [], []
    for row in trial_rows:
        group = row.get("group")
        if group == "1":
            (activo_c if _is_current_asset(row) else activo_nc).append(row)
        elif group == "2":
            (pasivo_c if _is_current_liab(row) else pasivo_nc).append(row)
        elif group == "3":
            patrimonio.append(row)

    def _fmt(rows, sign):
        return [
            {"code": r["code"], "name": r["name"],
             "amount": round2(sign * r["balance"])}
            for r in rows
        ]

    activo_c_rows, activo_nc_rows = _fmt(activo_c, 1.0), _fmt(activo_nc, 1.0)
    pasivo_c_rows, pasivo_nc_rows = _fmt(pasivo_c, -1.0), _fmt(pasivo_nc, -1.0)
    patrimonio_rows = _fmt(patrimonio, -1.0)

    total_activo = round2(sum(r["amount"] for r in activo_c_rows + activo_nc_rows))
    total_pasivo = round2(sum(r["amount"] for r in pasivo_c_rows + pasivo_nc_rows))
    total_patrimonio = round2(sum(r["amount"] for r in patrimonio_rows))
    total_pp = round2(total_pasivo + total_patrimonio)

    return {
        "period_label": period_label,
        "sections": [
            {"title": "ACTIVO CORRIENTE", "rows": activo_c_rows,
             "total": round2(sum(r["amount"] for r in activo_c_rows))},
            {"title": "ACTIVO NO CORRIENTE", "rows": activo_nc_rows,
             "total": round2(sum(r["amount"] for r in activo_nc_rows))},
            {"title": "PASIVO CORRIENTE", "rows": pasivo_c_rows,
             "total": round2(sum(r["amount"] for r in pasivo_c_rows))},
            {"title": "PASIVO NO CORRIENTE", "rows": pasivo_nc_rows,
             "total": round2(sum(r["amount"] for r in pasivo_nc_rows))},
            {"title": "PATRIMONIO", "rows": patrimonio_rows,
             "total": round2(sum(r["amount"] for r in patrimonio_rows))},
        ],
        "total_activo": total_activo,
        "total_pasivo": total_pasivo,
        "total_patrimonio": total_patrimonio,
        "total_pasivo_patrimonio": total_pp,
        "balanced": abs(total_activo - total_pp) < 0.01,
        "difference": round2(total_activo - total_pp),
    }


def estado_resultados(trial_rows, tax_rate=DEFAULT_CORPORATE_RATE,
                      period_label=""):
    """Estado de Resultados Integral. Income accounts are credit positive."""
    ingresos = [r for r in trial_rows if r.get("group") == "4"]
    costos = [r for r in trial_rows
              if r.get("group") == "5"
              and r.get("account_type") == "expense_direct_cost"]
    gastos = [r for r in trial_rows
              if r.get("group") == "5"
              and r.get("account_type") != "expense_direct_cost"]

    total_ingresos = round2(sum(-r["balance"] for r in ingresos))
    total_costos = round2(sum(r["balance"] for r in costos))
    total_gastos = round2(sum(r["balance"] for r in gastos))
    utilidad_bruta = round2(total_ingresos - total_costos)
    utilidad_operacional = round2(utilidad_bruta - total_gastos)
    impuesto = round2(max(utilidad_operacional, 0.0) * tax_rate)
    utilidad_neta = round2(utilidad_operacional - impuesto)

    return {
        "period_label": period_label,
        "sections": [
            {"title": "INGRESOS", "rows": [
                {"code": r["code"], "name": r["name"],
                 "amount": round2(-r["balance"])} for r in ingresos],
             "total": total_ingresos},
            {"title": "COSTO DE VENTAS", "rows": [
                {"code": r["code"], "name": r["name"],
                 "amount": round2(r["balance"])} for r in costos],
             "total": total_costos},
            {"title": "GASTOS OPERACIONALES", "rows": [
                {"code": r["code"], "name": r["name"],
                 "amount": round2(r["balance"])} for r in gastos],
             "total": total_gastos},
        ],
        "total_ingresos": total_ingresos,
        "total_costos": total_costos,
        "total_gastos": total_gastos,
        "utilidad_bruta": utilidad_bruta,
        "utilidad_operacional": utilidad_operacional,
        "impuesto_renta": impuesto,
        "utilidad_neta": utilidad_neta,
        "tax_rate": tax_rate,
    }


def _group_delta(open_rows, close_rows, predicate):
    """Credit-positive delta (close - open) for rows matching predicate.

    Liabilities/equity are converted to credit-positive so an increase shows
    as a positive delta.
    """
    def _index(rows):
        index = {}
        for row in rows:
            group = row.get("group")
            sign = -1.0 if group in ("2", "3") else 1.0
            index[row["code"]] = sign * row["balance"]
        return index

    open_index, close_index = _index(open_rows), _index(close_rows)
    all_rows = {}
    for row in list(open_rows) + list(close_rows):
        all_rows.setdefault(row["code"], row)
    delta = 0.0
    for code in set(open_index) | set(close_index):
        row = all_rows.get(code)
        if row is None or not predicate(row):
            continue
        delta += close_index.get(code, 0.0) - open_index.get(code, 0.0)
    return delta


def flujo_efectivo(open_rows, close_rows, net_income, depreciation=0.0,
                   period_label=""):
    """Estado de Flujos de Efectivo - METODO INDIRECTO (simplified).

    Operating = net income + depreciation + WC movements (non-cash current
               assets down / current liabilities up = cash in)
    Investing  = -(increase of non-current assets + depreciation)
                 i.e. capital expenditure, so the depreciation add-back in
                 the operating section is not counted twice
    Financing  = increase of non-current liabilities + equity movement
                 excluding the net income already counted above

    With an internally consistent balance sheet (assets = liabilities +
    equity for both dates) the reconciliation line below is therefore 0;
    any difference stems from inconsistent input / simplified grouping and
    is displayed explicitly instead of being hidden.
    """
    def _cash(row):
        return row.get("account_type") == "asset_cash"

    def _non_cash_current_asset(row):
        return (row.get("group") == "1" and _is_current_asset(row)
                and not _cash(row))

    def _current_liab(row):
        return row.get("group") == "2" and _is_current_liab(row)

    def _non_current_asset(row):
        return row.get("group") == "1" and not _is_current_asset(row)

    def _non_current_liab(row):
        return row.get("group") == "2" and not _is_current_liab(row)

    def _equity(row):
        return row.get("group") == "3"

    d_ncca = _group_delta(open_rows, close_rows, _non_cash_current_asset)
    d_cl = _group_delta(open_rows, close_rows, _current_liab)
    d_nca = _group_delta(open_rows, close_rows, _non_current_asset)
    d_ncl = _group_delta(open_rows, close_rows, _non_current_liab)
    d_eq = _group_delta(open_rows, close_rows, _equity)

    operating_rows = [
        {"name": "Utilidad neta del ejercicio", "amount": round2(net_income)},
        {"name": "Depreciaciones y amortizaciones (no efectivo)",
         "amount": round2(depreciation)},
        {"name": "(+) Disminucion de activos corrientes no efectivo",
         "amount": round2(-d_ncca)},
        {"name": "(+) Aumento de pasivos corrientes", "amount": round2(d_cl)},
    ]
    investing_rows = [
        {"name": "(+) Variacion de activos no corrientes (capex - depreciacion)",
         "amount": round2(-(d_nca + depreciation))},
    ]
    financing_rows = [
        {"name": "(+) Aumento de pasivos no corrientes", "amount": round2(d_ncl)},
        {"name": "(+) Variacion de patrimonio (aportes y distribuciones)",
         "amount": round2(d_eq - net_income)},
    ]

    operacion = round2(sum(r["amount"] for r in operating_rows))
    inversion = round2(sum(r["amount"] for r in investing_rows))
    financiacion = round2(sum(r["amount"] for r in financing_rows))
    variacion = round2(operacion + inversion + financiacion)

    cash_open = round2(sum(r["balance"] for r in open_rows if _cash(r)))
    cash_close = round2(sum(r["balance"] for r in close_rows if _cash(r)))
    cash_delta = round2(cash_close - cash_open)

    return {
        "period_label": period_label,
        "operating": operating_rows,
        "investing": investing_rows,
        "financing": financing_rows,
        "operating_total": operacion,
        "investing_total": inversion,
        "financing_total": financiacion,
        "net_change": variacion,
        "cash_open": cash_open,
        "cash_close": cash_close,
        "cash_delta": cash_delta,
        "reconciliation_difference": round2(variacion - cash_delta),
    }


def cambios_patrimonio(open_rows, close_rows, net_income, distributions=0.0,
                       period_label=""):
    """Estado de Cambios en el Patrimonio (simplified roll-forward).

    All values credit-positive. 'otras variaciones' captures capital issues,
    reserves and other movements as the balancing figure so
    inicial + otras + utilidad - distribuciones = final always holds.
    """
    def _equity_total(rows):
        return round2(sum(-r["balance"] for r in rows if r.get("group") == "3"))

    inicial = _equity_total(open_rows)
    final = _equity_total(close_rows)
    distribuciones = round2(abs(distributions))
    utilidad = round2(net_income)
    otras = round2(final - inicial - utilidad + distribuciones)

    return {
        "period_label": period_label,
        "rows": [
            {"name": "Saldo al inicio del ejercicio", "amount": inicial},
            {"name": "(+) Otras variaciones (aportes, reservas, ajustes)",
             "amount": otras},
            {"name": "(+) Utilidad del ejercicio", "amount": utilidad},
            {"name": "(-) Distribucion de utilidades", "amount": -distribuciones},
            {"name": "Saldo al cierre del ejercicio", "amount": final},
        ],
        "saldo_inicial": inicial,
        "otras_variaciones": otras,
        "utilidad": utilidad,
        "distribuciones": distribuciones,
        "saldo_final": final,
        "check": round2(inicial + otras + utilidad - distribuciones - final),
    }


# Required headings for Notas a los Estados Financieros (NIIF / NIC 1 used
# by SUPERCIAS - KB_SUPERCIAS 3.2 item 5). Structured stub: headings with
# the expected note tables; content is filled by the accountant.
NOTAS_HEADINGS = [
    ("1", "Informacion de la entidad", ["Detalle"]),
    ("2", "Bases de presentacion y principios de contabilidad", ["Aspecto"]),
    ("3", "Resumen de politicas contables significativas", ["Politica", "Norma"]),
    ("4", "Estimaciones y juicios significativos", ["Tema", "Juicio aplicado"]),
    ("5", "Riesgos e incertidumbres", ["Riesgo", "Mitigacion"]),
    ("6", "Efecto de nuevas normas (NIIF emitidas/no aplicadas)", ["Norma", "Efecto"]),
    ("7", "Detalle de partidas del Estado de Situacion Financiera",
     ["Nota", "Detalle"]),
    ("8", "Detalle del Estado de Resultados Integral", ["Nota", "Detalle"]),
    ("9", "Detalle del Estado de Flujos de Efectivo", ["Nota", "Detalle"]),
    ("10", "Detalle del Estado de Cambios en el Patrimonio", ["Nota", "Detalle"]),
    ("11", "Contingencias, compromisos y garantias", ["Tipo", "Monto"]),
    ("12", "Operaciones con partes relacionadas", ["Parte", "Monto"]),
    ("13", "Eventos posteriores al cierre", ["Evento", "Monto"]),
    ("14", "Informacion por segmentos de operacion", ["Segmento", "Monto"]),
    ("15", "Ganancias por accion (si aplica)", ["Concepto", "Monto"]),
    ("16", "Capital de trabajo", ["Concepto", "Monto"]),
]


def notas_financieras_stub():
    return [
        {"number": number, "title": title, "columns": columns,
         "rows": [{"detail": ""} for _ in range(3)]}
        for number, title, columns in NOTAS_HEADINGS
    ]


# ===========================================================================
# ATS (Anexo Transaccional Simplificado) - structure per SRS_MODULE_09 3.1
# ===========================================================================

# IVA withholding tariff -> SRI ATS field (KB_TAX_RATES_WITHHOLDINGS 3.3):
#   30% -> valorRetBienes, 70% -> valorRetServicios, 100% -> valorRetServicios
#   (100% has no dedicated ATS field in the documented XSD snippet)
ATS_IVA_RET_FIELDS = {
    30.0: "valorRetBienes",
    70.0: "valorRetServicios",
    100.0: "valorRetServicios",
    10.0: "valRetBien10",
    20.0: "valRetServ20",
    50.0: "valRetServ50",
}


def ats_validate(ventas, compras, cancelled=None, retentions=None):
    """REQ-ATS-001 validations. Returns a list of human readable errors."""
    errors = []
    for row in compras:
        if not row.get("sustento"):
            errors.append(
                "Compra %s (%s): falta sustento tributario."
                % (row.get("secuencial"), row.get("identificacion")))
        if not row.get("clave_acceso") and not row.get("autorizacion"):
            errors.append(
                "Compra %s: falta clave de acceso / autorizacion."
                % row.get("secuencial"))
        if not row.get("identificacion"):
            errors.append(
                "Compra %s: proveedor sin identificacion (RUC/cedula)."
                % row.get("secuencial"))
    for row in ventas:
        if not row.get("identificacion"):
            errors.append(
                "Venta %s: cliente sin identificacion." % row.get("secuencial"))
    for ret in retentions or []:
        if not ret.get("comprobante"):
            errors.append(
                "Retencion %s: comprobante huerfano (sin factura vinculada)."
                % ret.get("numero"))
    return errors


def ats_ventas(ventas):
    """Group sales rows by (tpIdCliente, idCliente, tipoComprobante).

    Credit notes are already signed negative by invoice_report_row, so the
    aggregated base/IVA of a 04 group are negative (SRI convention).
    """
    grouped = {}
    for row in ventas:
        key = (row["tp_id"], row["identificacion"], row["doc_code"])
        entry = grouped.setdefault(
            key,
            {
                "tpIdCliente": row["tp_id"],
                "idCliente": row["identificacion"] or "9999999999999",
                "parteRelVtas": "NO",
                "tipoComprobante": row["doc_code"],
                "tipoEmision": "E" if row["emision_linea"] else "F",
                "numeroComprobantes": 0,
                "baseNoGraIva": 0.0,
                "baseImponible": 0.0,
                "baseImpGrav": 0.0,
                "baseImpExe": 0.0,
                "montoIva": 0.0,
                "montoIce": 0.0,
                "valorRetIva": 0.0,
                "valorRetRenta": 0.0,
            },
        )
        entry["numeroComprobantes"] += 1
        entry["baseImpGrav"] += row["base_15"] + row["base_5"]
        entry["baseImponible"] += row["base_0"]
        entry["baseNoGraIva"] += row["base_no_objeto"]
        entry["baseImpExe"] += row["base_exenta"]
        entry["montoIva"] += row["iva"]
        entry["montoIce"] += row["ice"]
        entry["valorRetIva"] += row["ret_iva"]
        entry["valorRetRenta"] += row["ret_ir"]

    result = []
    for entry in grouped.values():
        for key in ("baseNoGraIva", "baseImponible", "baseImpGrav",
                    "baseImpExe", "montoIva", "montoIce", "valorRetIva",
                    "valorRetRenta"):
            entry[key] = round2(entry[key])
        result.append(entry)
    return result


def ats_compras(compras):
    """One detalleCompras per invoice (documented SRS structure)."""
    result = []
    for row in compras:
        iva_ret = {"valorRetBienes": 0.0, "valorRetServicios": 0.0,
                   "valRetBien10": 0.0, "valRetServ20": 0.0,
                   "valRetServ50": 0.0}
        air = []
        for ret in row.get("retentions") or []:
            percent = round(_num(ret.get("percent")), 2)
            if ret.get("kind") == "iva":
                field = ATS_IVA_RET_FIELDS.get(percent, "valorRetServicios")
                iva_ret[field] = round2(iva_ret[field] + _num(ret.get("amount")))
            else:
                air.append({
                    "codRetAir": str(ret.get("code") or "000"),
                    "baseImpAir": round2(ret.get("base")),
                    "porcentajeAir": percent,
                    "valRetAir": round2(ret.get("amount")),
                })
        ret_numero = ""
        ret_fecha = ""
        ret_autorizacion = "0"
        for ret in row.get("retentions") or []:
            if ret.get("numero"):
                ret_numero = ret["numero"]
                ret_fecha = ret.get("fecha") or ""
                ret_autorizacion = ret.get("autorizacion") or "0"
                break
        if ret_numero:
            estab_ret, pto_ret, sec_ret = split_document_number(ret_numero)
        else:
            estab_ret, pto_ret, sec_ret = "000", "000", "0"

        entry = {
            "codSustento": row.get("sustento") or "01",
            "tpIdProv": row.get("tp_id") or "01",
            "idProv": row.get("identificacion") or "9999999999999",
            "tipoComprobante": row.get("doc_code") or "01",
            "parteRel": "NO",
            "fechaRegistro": row.get("fecha_registro") or row.get("fecha") or "",
            "establecimiento": row.get("estab") or "001",
            "puntoEmision": row.get("pto") or "001",
            "secuencial": row.get("secuencial") or "0",
            "fechaEmision": row.get("fecha") or "",
            "autorizacion": row.get("autorizacion")
            or row.get("clave_acceso") or "9999999999",
            "baseNoGraIva": round2(row.get("base_no_objeto")),
            "baseImponible": round2(row.get("base_0")),
            "baseImpGrav": round2(row.get("base_15") + row.get("base_5")),
            "baseImpExe": round2(row.get("base_exenta")),
            "montoIce": round2(row.get("ice")),
            "montoIva": round2(row.get("iva")),
            "valorRetBienes": iva_ret["valorRetBienes"],
            "valorRetServicios": iva_ret["valorRetServicios"],
            "valRetBien10": iva_ret["valRetBien10"],
            "valRetServ20": iva_ret["valRetServ20"],
            "valRetServ50": iva_ret["valRetServ50"],
            "pagoExterior": {"pagoLocExt": "01"},
            "formasDePago": [{"formaPago": row.get("forma_pago") or "20"}],
            "air": air,
            "estabRetencion1": estab_ret,
            "ptoEmiRetencion1": pto_ret,
            "secRetencion1": sec_ret,
            "autRetencion1": ret_autorizacion,
            "fechaEmiRet1": ret_fecha,
            "is_import": bool(row.get("is_import")),
        }
        result.append(entry)
    return result


def ats_anulados(cancelled_raw):
    """detalleAnulados for cancelled (anulados) comprobantes."""
    result = []
    for row in cancelled_raw:
        estab, pto, sec = split_document_number(row.get("numero"))
        result.append({
            "tipoComprobante": row.get("doc_code") or "01",
            "establecimiento": estab,
            "puntoEmision": pto,
            "secuencialInicio": sec,
            "secuencialFin": sec,
            "autorizacion": row.get("autorizacion") or "0",
        })
    return result


def ats_exportaciones(export_rows):
    """detalleExportaciones (SRI ATS 'exportaciones' section)."""
    result = []
    for row in export_rows:
        result.append({
            "tpIdCliente": row.get("tp_id") or "07",
            "idCliente": row.get("identificacion") or "9999999999999",
            "tipoComprobante": row.get("doc_code") or "18",
            "fechaEmision": row.get("fecha") or "",
            "autorizacion": row.get("autorizacion")
            or row.get("clave_acceso") or "0",
            "valorExport": round2(row.get("base_total")),
            "valorRetenido": round2(_num(row.get("ret_iva"))
                                    + _num(row.get("ret_ir"))),
            "montoIva": round2(row.get("iva")),
        })
    return result


def ats_retenciones(retentions):
    """<retenciones> section: every retention issued in the period
    (comprobante 07), regardless of the invoice direction."""
    result = []
    for ret in retentions:
        result.append({
            "codRetAir": str(ret.get("code") or "000"),
            "fechaEmision": ret.get("fecha_factura") or ret.get("fecha") or "",
            "identificacionRetenido": ret.get("identificacion") or "",
            "numComprobante": ret.get("comprobante")
            or ret.get("numero") or "",
            "porcentajeAir": round2(ret.get("percent")),
            "valRetAir": round2(ret.get("amount")),
            "tipoRet": ret.get("kind") or "ir",
        })
    return result


def ats_ventas_establecimiento(ventas, company_entity="001"):
    """ventasEstablecimiento block (sales per establishment + IVA generado)."""
    grouped = {}
    for row in ventas:
        estab = row.get("estab") or company_entity
        entry = grouped.setdefault(estab, {"codEstab": estab,
                                           "ventasEstab": 0.0,
                                           "ivaComp": 0.0})
        entry["ventasEstab"] += row.get("base_total") or 0.0
        entry["ivaComp"] += row.get("iva") or 0.0
    rows = []
    for entry in grouped.values():
        rows.append({
            "codEstab": entry["codEstab"],
            "ventasEstab": round2(entry["ventasEstab"]),
            "ivaComp": round2(entry["ivaComp"]),
        })
    if not rows:
        rows.append({"codEstab": company_entity, "ventasEstab": 0.0,
                     "ivaComp": 0.0})
    return rows


def ats_build(header, ventas_rows, compras_rows, cancelled_raw,
              retentions, export_rows):
    """Assemble the full ATS data structure consumed by the QWeb template.

    ``header``: {'year','month','entity','company_name', ...}
    ``ventas_rows`` / ``compras_rows``: output of invoice_report_row()
    """
    ventas = ats_ventas(ventas_rows)
    compras = ats_compras(compras_rows)
    anulados = ats_anulados(cancelled_raw)
    exportaciones = ats_exportaciones(export_rows)
    retenciones = ats_retenciones(retentions)
    establecimiento = ats_ventas_establecimiento(
        ventas_rows, header.get("entity") or "001")
    total_ventas = round2(sum(r["base_total"] for r in ventas_rows))
    errors = ats_validate(ventas_rows, compras_rows, cancelled_raw, retentions)
    return {
        "header": header,
        "ventas": ventas,
        "compras": compras,
        "anulados": anulados,
        "exportaciones": exportaciones,
        "retenciones": retenciones,
        "ventas_establecimiento": establecimiento,
        "total_ventas": total_ventas,
        "errors": errors,
    }


# ===========================================================================
# EXPORTERS (CSV stdlib / XLSX via xlsxwriter - ships with Odoo, no pip)
# ===========================================================================


def _cell(value):
    if isinstance(value, float):
        return "%.2f" % value
    return "" if value is None else value


def fmt_cell(value):
    """Human readable cell for the QWeb templates (same rules as _cell,
    with booleans rendered as SI/NO).  Exposed to the templates through
    ``l10n.ec.report.common.fmt_cell`` so the PDF/HTML output and the
    CSV/XLSX exporters agree on formatting."""
    if isinstance(value, bool):
        return "SI" if value else "NO"
    if isinstance(value, float):
        return "%.2f" % value
    if value is None:
        return ""
    return str(value)


def fmt_totals(totals, columns):
    """[(label, formatted_value)] for the footer of a book/form table.

    Extra totals that have no column (count, amount_ir, ...) are appended
    with a humanized label so nothing computed by the books is dropped.
    """
    labels = {key: label for key, label in columns or []}
    humanized = {
        "count": "Registros",
        "amount_ir": "Total ret. IR",
        "amount_iva": "Total ret. IVA",
        "difference": "Diferencia (debe - haber)",
        "opening": "Saldo inicial",
        "debit": "Total debito",
        "credit": "Total credito",
    }
    rows = []
    for key, label in columns or []:
        if key in (totals or {}):
            rows.append((label, fmt_cell(totals[key])))
    for key, value in (totals or {}).items():
        if key in labels:
            continue
        rows.append((humanized.get(key, key), fmt_cell(value)))
    return rows


def write_csv(rows, columns, totals=None):
    """Render rows as CSV text (stdlib only)."""
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([header for _key, header in columns])
    for row in rows:
        writer.writerow([_cell(row.get(key)) for key, _header in columns])
    if totals:
        writer.writerow([])
        writer.writerow(["TOTALES"] + ["" for _ in columns[1:]])
        writer.writerow([_cell(totals.get(key)) for key, _header in columns])
    return buffer.getvalue()


def write_xlsx(rows, columns, sheet_name="Libro", totals=None,
               extra_sheets=None):
    """Render rows to an XLSX workbook (bytes).

    ``extra_sheets``: [(sheet_name, rows, columns), ...] appended sheets.
    Uses xlsxwriter which ships inside the Odoo image - no pip installs.
    """
    import io

    try:
        import xlsxwriter
    except ImportError as exc:  # pragma: no cover - only outside Odoo
        raise RuntimeError(
            "xlsxwriter is not available in this environment; use CSV "
            "export instead (%s)" % exc)

    stream = io.BytesIO()
    workbook = xlsxwriter.Workbook(stream, {"in_memory": True})
    fmt_header = workbook.add_format(
        {"bold": True, "bg_color": "#D9E1F2", "border": 1})
    fmt_money = workbook.add_format({"num_format": "#,##0.00"})
    fmt_total = workbook.add_format({"bold": True, "num_format": "#,##0.00"})

    def _dump(sheet, data, cols, show_totals):
        sheet.write_row(0, 0, [h for _k, h in cols], fmt_header)
        for index, row in enumerate(data, start=1):
            for col, (key, _header) in enumerate(cols):
                value = row.get(key)
                if isinstance(value, float):
                    sheet.write_number(index, col, value, fmt_money)
                else:
                    sheet.write(index, col, _cell(value))
        if show_totals:
            total_row = len(data) + 2
            sheet.write(total_row, 0, "TOTALES", fmt_header)
            for col, (key, _header) in enumerate(cols):
                if key in (show_totals or {}):
                    sheet.write_number(total_row, col,
                                       _num(show_totals.get(key)), fmt_total)

    sheet = workbook.add_worksheet(sheet_name[:31])
    _dump(sheet, rows, columns, totals)
    for extra_name, extra_rows, extra_cols in extra_sheets or []:
        _dump(workbook.add_worksheet(extra_name[:31]), extra_rows,
              extra_cols, None)

    workbook.close()
    return stream.getvalue()
