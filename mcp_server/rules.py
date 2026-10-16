# -*- coding: utf-8 -*-
"""
Ecuadorian rule engine for the MCP gateway.

PURE PYTHON STDLIB ONLY.  This module must be importable and unit-testable
WITHOUT Odoo (no `odoo` imports here, ever).  Every mutating MCP tool runs
its inputs through these rules before touching the ERP.

Regulatory references:
  * SRI Res. NAC-DGERCGC25-00000017 — electrónica, anulación día 7, CF $50.
  * SRI Tabla 19 (Res. NAC-DGERCGC26-00000009, RO 233, 27-feb-2026) —
    códigos de retención IR; F.104 / Res. NAC-DGERCGC20-00000061 —
    retención IVA (casilleros 721-731).
  * LRTI Art. 50 — la retención se aplica dentro de los 5 días hábiles
    de recibido el comprobante de pago (días hábiles: Código
    Tributario Art. 12; no se cuenta desde la fecha de la factura
    sino desde la recepción del comprobante).
  * Código del Trabajo — décimo tercero (art. 111), décimo cuarto
    (art. 113), fondos de reserva 8.33% (art. 195).
"""
import datetime
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CF_RUC_DEFAULT = "9999999999999"        # SRI Consumidor Final RUC
CF_LIMIT_DEFAULT = 50.0                 # USD, Res. NAC-DGERCGC25-00000017
ANNULMENT_DAY_DEFAULT = 7               # día del mes siguiente a la emisión
RETENTION_BUSINESS_DAYS = 5             # LRTI Art. 50 (hábiles, CT Art. 12)

# SRI Res. NAC-DGERCGC25-00000017 (RO 92, 30-jul-2025), vigente 01-ene-2026:
#   * TODOS los comprobantes electrónicos (facturas, notas, retenciones)
#     deben TRANSMITIRSE al SRI en el MISMO momento de su generación.
#     Se eliminó la antigua ventanilla de 4 días hábiles de emisión.
#   * Anulación: hasta el día 7 del mes siguiente (no día 10).
#   * NC / ND / retención: requieren aceptación del receptor (5 días hábiles).
#   * Facturas a consumidor final: NO anulables.
TRANSMISSION_SAME_DAY = True            # Res. ...25-00000017, art. transitorio
TRANSMISSION_GRACE_DAYS_LEGACY = 4      # derogado desde 01-ene-2026

# IVA rates in force 2026 per Ficha Técnica SRI v2.33 Tabla 17:
#   15% = tarifa general (DE 198, vigente desde 01-abr-2024) → código "4"
#   5%  = materiales de construcción                          → código "5"
#   0%  = exentos / tarifa cero                               → código "0"
#   8%  = sector turístico, solo por decreto ejecutivo        → código "8"
#   12% = histórica (operaciones hasta 31-mar-2024; NC sobre facturas
#         antiguas)                                           → código "2"
#   14% = histórica (2011)                                     → código "3"
# (El 13% → código "10" quedó superado desde abril 2024.)
IVA_RATES = (0.0, 5.0, 8.0, 12.0, 14.0, 15.0)

# Withholding (SRI Tabla 19 – Renta / F.104 721-731 – IVA)
VALID_IR_SERVICIOS = (1.0, 1.75, 2.0, 3.0, 5.0, 10.0, 12.0, 14.0, 15.0,
                      25.0, 37.0)
VALID_IR_BIENES = (0.0, 1.0, 2.0, 3.0, 10.0)
DEFAULT_IR_SERVICIOS = 10.0             # honorarios (cod. 303, Tabla 19)
DEFAULT_IR_BIENES = 2.0                 # transferencia bienes muebles (cod. 312)
DEFAULT_IR_SERVICIOS_GENERALES = 3.0    # servicios mano de obra (cod. 307)
VALID_IVA_RETENTION = (10.0, 20.0, 30.0, 50.0, 70.0, 100.0)  # F.104 721-731

# IESS rates (MinTrabajo/IESS; configurable via ir.config_parameter on Odoo
# side, these are the statutory defaults used for offline computation).
# Tasas oficiales sector privado 2026 (iess.gob.ec "Tasas de aportación"):
#   personal 9.45% / patronal 11.15% / total 20.60%.
# SECAP 0.5% y IECE 0.5% son aportes patronales adicionales recaudados vía
# IESS (costo empleador total 12.15%); en abril-2026 existen proyectos de
# ley (en trámite) para redirigir el 0.5% del SECAP — vigentes mientras no
# se publiquen en el Registro Oficial.
IESS_PERSONAL_RATE = 9.45
IESS_PATRONAL_RATE = 11.15
IESS_SECAP_RATE = 0.5
IESS_IECE_RATE = 0.5
IESS_BASE_MULTIPLIER_CAP = 25           # techo = 25 × SBU (NO_VERIFICADO:
                                        # pendiente confirmar norma vigente)
SBU_2026 = 482.0

DOC_TYPES = {
    "01": "Factura",
    "03": "Liquidación de Compra",
    "04": "Nota de Crédito",
    "05": "Nota de Débito",
    "06": "Guía de Remisión",
    "07": "Comprobante de Retención",
}

_EC_ID_RE = re.compile(r"^\d{10,13}$")


# ---------------------------------------------------------------------------
# Identification: cédula (mod-10) and RUC — official SRI validation formula
#
# The SRI publishes ONE formula, implemented canonically by the `stdnum`
# library (stdnum.ec.ci / stdnum.ec.ruc). stdnum is not installed on the MCP
# host, so the exact algorithm is replicated here in pure stdlib — NO new
# dependencies. It is proven byte-equivalent to stdnum by the cross-check in
# mcp_server/test_server.py (TestStdnumEquivalence).
# ---------------------------------------------------------------------------

_EC_SPECIAL_PROVINCES = ("30", "50")   # non-geographic codes stdnum accepts


def _province_ok(first2):
    """Province code 01..24 plus the special 30/50 stdnum accepts."""
    return "01" <= first2 <= "24" or first2 in _EC_SPECIAL_PROVINCES


def _ci_ok(number):
    """stdnum.ec.ci: 10 digits, valid province, third digit <= 6, mod-10 == 0."""
    if not (isinstance(number, str) and number.isdigit() and len(number) == 10):
        return False
    if not _province_ok(number[:2]):
        return False
    if number[2] > "6":
        return False  # third digit wrong
    total = 0
    for i, n in enumerate(number):
        p = (2, 1)[i % 2] * int(n)   # alternating weights 2,1,2,1,...
        total += p - 9 if p > 9 else p
    return total % 10 == 0


def _sum_mod11(number, weights):
    """stdnum.ec.ruc._checksum: weighted sum modulo 11 (valid when == 0)."""
    return sum(w * int(n) for w, n in zip(weights, number)) % 11


def cedula_check_digit_ok(cedula):
    """True when `cedula` is a valid Ecuadorian cédula (stdnum.ec.ci)."""
    return _ci_ok(cedula)


def ruc_check_digit_ok(ruc):
    """True when `ruc` is a valid Ecuadorian RUC (stdnum.ec.ruc).

    Official dispatch on the 3rd digit:
      0-5 -> persona natural : cedula(first10) and establecimiento != '000'
      6   -> sector publico  : mod-11 checksum, else natural fallback
      9   -> persona juridica: mod-11 checksum
      7,8 -> invalid
    """
    if not (isinstance(ruc, str) and ruc.isdigit() and len(ruc) == 13):
        return False
    if not _province_ok(ruc[:2]):
        return False
    third = ruc[2]
    if third < "6":                                    # natural
        return ruc[-3:] != "000" and _ci_ok(ruc[:10])
    if third == "6":                                   # publico (or natural)
        if (ruc[-4:] != "0000"
                and _sum_mod11(ruc[:9], (3, 2, 7, 6, 5, 4, 3, 2, 1)) == 0):
            return True
        return ruc[-3:] != "000" and _ci_ok(ruc[:10])   # stdnum fallback
    if third == "9":                                   # juridica
        return (ruc[-3:] != "000"
                and _sum_mod11(ruc[:10], (4, 3, 2, 7, 6, 5, 4, 3, 2, 1)) == 0)
    return False                                       # third digit 7 or 8


def validate_vat(vat):
    """
    Structural + checksum validation of an Ecuadorian identification.
    Returns: {input, id_type ('ruc'|'cedula'|'pasaporte'|None), valid,
              checksum_ok, errors:[...]}
    """
    raw = (vat or "").strip()
    errors = []
    if not raw:
        return {"input": vat, "id_type": None, "valid": False,
                "checksum_ok": False, "errors": ["identificación vacía"]}
    digits = raw.replace(" ", "")
    if not _EC_ID_RE.match(digits):
        if digits.isdigit():
            return {"input": raw, "id_type": None, "valid": False,
                    "checksum_ok": False,
                    "errors": ["debe ser cédula (10 dígitos) o RUC (13 dígitos)"]}
        if re.match(r"^[A-Za-z0-9\-]{1,20}$", raw):
            return {"input": raw, "id_type": "pasaporte", "valid": True,
                    "checksum_ok": None, "errors": []}
        return {"input": raw, "id_type": None, "valid": False,
                "checksum_ok": False,
                "errors": ["formato de identificación inválido"]}
    if len(digits) == 10:
        ok = cedula_check_digit_ok(digits)
        return {"input": digits, "id_type": "cedula", "valid": ok,
                "checksum_ok": ok,
                "errors": [] if ok else ["dígito verificador mod-10 inválido"]}
    ok = ruc_check_digit_ok(digits)
    return {"input": digits, "id_type": "ruc", "valid": ok,
            "checksum_ok": ok,
            "errors": [] if ok else ["dígito verificador RUC inválido "
                                     "(mod-11 jurídica / mod-10 cédula)"]}


def classify_ruc(ruc):
    """
    Persona natural vs jurídica vs sector público from the 3rd RUC digit.
    Returns: {third_digit, person_type ('natural'|'juridica'|'publico'|None)}
    """
    if not (isinstance(ruc, str) and ruc.isdigit() and len(ruc) == 13):
        return {"third_digit": None, "person_type": None}
    d = int(ruc[2])
    if d <= 5:
        pt = "natural"
    elif d == 6:
        pt = "publico"
    elif d == 9:
        pt = "juridica"
    else:
        pt = None
    return {"third_digit": ruc[2], "person_type": pt}


def taxpayer_profile(vat, sri_data=None):
    """
    Full taxpayer profile used by detect_taxpayer / create_invoice.
    `sri_data` is the (optional) payload returned by
    l10n_ec.sri.ruc.service.consultar_ruc -> ['data'].
    """
    v = validate_vat(vat)
    profile = {
        "vat": v["input"],
        "id_type": v["id_type"],
        "valid_checksum": v["valid"],
        "checksum_errors": v["errors"],
        "person_type": None,
        "obligado_contabilidad": None,
        "contribuyente_especial": False,
        "agente_retencion": False,
        "regimen_rimpe": None,
        "sri_estado": None,
        "sri_available": False,
        "razon_social": None,
        "direccion": None,
        "errors": list(v["errors"]),
    }
    if v["id_type"] == "ruc":
        profile.update(classify_ruc(v["input"]))
    elif v["id_type"] == "cedula":
        profile["person_type"] = "natural"

    if isinstance(sri_data, dict) and sri_data:
        profile["sri_available"] = True
        profile["sri_estado"] = (sri_data.get("estado") or "").upper() or None
        profile["razon_social"] = sri_data.get("razon_social") or None
        profile["direccion"] = sri_data.get("direccion") or None
        ob = sri_data.get("obligado_contabilidad")
        profile["obligado_contabilidad"] = bool(ob) if ob is not None else None
        ce = str(sri_data.get("contribuyente_especial") or "")
        profile["contribuyente_especial"] = ce.strip().upper() not in ("", "NO", "FALSE", "NONE")
        ar = str(sri_data.get("agente_retencion") or "")
        profile["agente_retencion"] = ar.strip().upper() not in ("", "NO", "FALSE", "NONE")
        rimpe = sri_data.get("regimen_rimpe")
        profile["regimen_rimpe"] = rimpe or None
        if profile["sri_estado"] and profile["sri_estado"] != "ACTIVO":
            profile["errors"].append(
                "contribuyente SRI en estado %s (no activo)" % profile["sri_estado"])
    if profile["id_type"] == "ruc" and not profile["valid_checksum"]:
        # A RUC with a broken checksum must never be invoiced.
        pass
    return profile


# ---------------------------------------------------------------------------
# Access key (49 digits) — mirrors l10n_ec_edi AccessKey
# ---------------------------------------------------------------------------
def compute_check_digit_48(key_48):
    """Mod-11 check digit (weights 2..7) for the 48-digit access-key base."""
    if len(key_48) != 48 or not key_48.isdigit():
        return None
    weights = [2, 3, 4, 5, 6, 7]
    total = 0
    for i, ch in enumerate(reversed(key_48)):
        total += int(ch) * weights[i % 6]
    remainder = total % 11
    check = 11 - remainder
    if check == 11:
        check = 0
    elif check == 10:
        check = 1
    return str(check)


def generate_access_key(invoice_date, doc_type, ruc, environment,
                        establishment, emission_point, sequential,
                        numeric_code=None):
    """Generate the 49-digit SRI clave de acceso (doc types 01/03/04/05/07)."""
    if invoice_date is None:
        invoice_date = datetime.date.today()
    date_str = invoice_date.strftime("%d%m%Y")
    doc_type = str(doc_type).zfill(2)
    ruc = str(ruc).zfill(13)
    env = "2" if str(environment) in ("production", "prod", "2") else "1"
    estab = str(establishment).zfill(3)
    pto = str(emission_point).zfill(3)
    seq = str(sequential).zfill(9)
    num = (str(numeric_code).zfill(8) if numeric_code else "99999999")
    emission_type = "1"
    base = f"{date_str}{doc_type}{ruc}{env}{estab}{pto}{seq}{num}{emission_type}"
    check = compute_check_digit_48(base)
    if check is None:
        raise ValueError("no se pudo generar la clave: base inválida")
    return base + check


def validate_access_key(key):
    """Validate a 49-digit clave de acceso (structure + mod-11 + real date)."""
    errors = []
    if not key or not str(key).isdigit() or len(str(key)) != 49:
        return {"valid": False, "errors": ["la clave debe tener 49 dígitos"]}
    key = str(key)
    dd, mm, yyyy = key[0:2], key[2:4], key[4:8]
    try:
        datetime.date(int(yyyy), int(mm), int(dd))
    except ValueError:
        errors.append("fecha de emisión inválida en la clave")
    doc = key[8:10]
    if doc not in DOC_TYPES:
        errors.append("código de documento inválido: %s" % doc)
    if key[23] not in ("1", "2"):
        errors.append("ambiente inválido (debe ser 1=test, 2=producción)")
    check = compute_check_digit_48(key[:48])
    if check is None or check != key[48]:
        errors.append("dígito verificador mod-11 de la clave inválido")
    return {"valid": not errors, "errors": errors, "doc_type": doc,
            "doc_name": DOC_TYPES.get(doc), "emission_date": f"{yyyy}-{mm}-{dd}",
            "ruc_emisor": key[10:23], "ambiente": key[23] if len(key) > 23 else None}


# ---------------------------------------------------------------------------
# Consumidor Final / anulación rules
# ---------------------------------------------------------------------------
def is_consumidor_final(vat, cf_ruc=CF_RUC_DEFAULT):
    return (vat or "").strip() == cf_ruc


def cf_limit_check(total, cf_limit=CF_LIMIT_DEFAULT):
    ok = float(total) <= float(cf_limit) + 1e-9
    return {"ok": ok, "total": round(float(total), 2),
            "limit": round(float(cf_limit), 2),
            "error": None if ok else
            ("Factura a Consumidor Final no puede superar $%.2f (total $%.2f). "
             "Emita a un contribuyente identificado." % (cf_limit, total))}


def annulment_deadline(invoice_date, day=ANNULMENT_DAY_DEFAULT):
    """Authorized documents can only be annulled until `day` of the next month."""
    y, m = invoice_date.year, invoice_date.month
    if m == 12:
        y, m = y + 1, 1
    else:
        m += 1
    return datetime.date(y, m, day)


def check_annul_allowed(invoice_date, today=None, is_cf=False,
                        day=ANNULMENT_DAY_DEFAULT):
    """SRI 2026: CF documents are NOT annulable; everyone else until day 7."""
    today = today or datetime.date.today()
    if is_cf:
        return {"allowed": False,
                "error": "Facturas a Consumidor Final autorizadas NO pueden "
                         "anularse (Res. NAC-DGERCGC25-00000017)."}
    if invoice_date is None:
        return {"allowed": True, "deadline": None, "warning": None}
    deadline = annulment_deadline(invoice_date, day)
    if today > deadline:
        return {"allowed": False, "deadline": deadline.isoformat(),
                "error": ("Anulación vencida: límite %s (día %s del mes "
                          "siguiente), hoy %s. Corrija mediante nota de "
                          "crédito dentro del plazo fiscal."
                          % (deadline.isoformat(), day, today.isoformat()))}
    return {"allowed": True, "deadline": deadline.isoformat(), "warning": None}


# ---------------------------------------------------------------------------
# Ecuadorian holidays & business days
# ---------------------------------------------------------------------------
def easter_sunday(year):
    """Gregorian computus (Meeus/Jones/Butcher) — no dependencies."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)


def ec_holidays(year):
    """Ecuadorian national holidays for `year` (fixed + Carnaval + Viernes
    Santo). Returns a set of datetime.date.

    Base legal: art. 65 del Código del Trabajo (RO Supl. 906, 20-dic-2016):
    1 de enero, lunes y martes de Carnaval, viernes santo, 1 de mayo,
    24 de mayo, 10 de agosto, 9 de octubre, 2 y 3 de noviembre y
    25 de diciembre.  (El 27 de febrero "Día del Civismo" — DE 324 de
    1948 — y el 3 de mayo "Fiesta de la Santa Cruz" NO son feriados
    nacionales.)"""
    fixed = [(1, 1), (5, 1), (5, 24), (8, 10), (10, 9),
             (11, 2), (11, 3), (12, 25)]
    days = {datetime.date(year, m, d) for m, d in fixed}
    easter = easter_sunday(year)
    days.add(easter - datetime.timedelta(days=48))  # Carnaval lunes
    days.add(easter - datetime.timedelta(days=47))  # Carnaval martes
    days.add(easter - datetime.timedelta(days=2))   # Viernes Santo
    return days


def is_business_day(day, holidays=None):
    if day.weekday() >= 5:
        return False
    if holidays is None:
        holidays = ec_holidays(day.year)
    return day not in holidays


def add_business_days(start, n, holidays=None):
    """Return the date `n` business days after `start` (start excluded).
    Weekends and Ecuadorian holidays are skipped."""
    if holidays is None:
        holidays = set()
        for y in (start.year, start.year + 1):
            holidays |= ec_holidays(y)
    current = start
    added = 0
    while added < n:
        current += datetime.timedelta(days=1)
        if is_business_day(current, holidays):
            added += 1
    return current


def retention_deadline(invoice_date, today=None, days=RETENTION_BUSINESS_DAYS):
    """LRTI Art. 50: the agent must DELIVER the retention voucher within
    5 days of receipt of the sales voucher (the retention itself is due at
    payment or credit, whichever comes first); days are business days per
    Código Tributario Art. 12.  The repo computes from the invoice date;
    note the legal clock starts on RECEIPT of the voucher.  Returns due
    date + overdue flag."""
    today = today or datetime.date.today()
    if invoice_date is None:
        return {"due_date": None, "overdue": False,
                "warning": "factura sin fecha; no se puede calcular el plazo"}
    due = add_business_days(invoice_date, days)
    overdue = today > due
    warning = None
    if overdue:
        warning = ("Retención fuera de plazo: vencía el %s (%s días hábiles "
                   "desde %s, excluyendo fines de semana y feriados). Hoy %s. "
                   "Emítala igualmente e indique la fecha real; el mora es "
                   "objeto de sanción."
                   % (due.isoformat(), days, invoice_date.isoformat(),
                      today.isoformat()))
    return {"due_date": due.isoformat(), "overdue": overdue, "warning": warning,
            "business_days": days}


def transmission_deadline(issue_date, today=None, doc_type="retention"):
    """SRI Res. NAC-DGERCGC25-00000017 (RO 92, 30-jul-2025), in force
    2026-01-01: EVERY electronic voucher (invoice, credit note, debit note,
    retention) must be TRANSMITTED to the SRI in the SAME moment it is
    generated.  The legacy 4-business-day transmission window was repealed.

    This is distinct from `retention_deadline` above, which is the 5-day
    window to DELIVER the retention voucher to the counterparty (LRTI Art.
    50).  Transmission to the SRI is immediate; delivery to the client keeps
    its 5-day window.

    Returns same_day_required flag, whether it is late, and a warning."""
    today = today or datetime.date.today()
    if issue_date is None:
        return {"same_day_required": TRANSMISSION_SAME_DAY, "late": False,
                "warning": "comprobante sin fecha; no se puede evaluar"}
    late = today > issue_date
    warning = None
    if late:
        warning = ("Comprobante %s emitido el %s aún NO transmitido al SRI "
                   "(hoy %s). La Res. NAC-DGERCGC25-00000017 exige transmisión "
                   "en el mismo momento de la generación desde 01-ene-2026; no "
                   "existe ventanilla de días hábiles. Transmita de inmediato: "
                   "la mora es falta sancionable (Tipo A)."
                   % (doc_type, issue_date.isoformat(), today.isoformat()))
    return {"same_day_required": TRANSMISSION_SAME_DAY, "late": late,
            "warning": warning, "issue_date": issue_date.isoformat()}


def annulment_ok(doc_type, issued_date, today=None):
    """SRI Res. NAC-DGERCGC25-00000017: electronic vouchers may be annulled
    up to DAY 7 of the month following emission (was day 10).  Invoices to
    consumidor final are NOT annulable.  Credit/debit notes and retention
    vouchers additionally require receptor acceptance (5 business days).
    Returns allowed flag + reason."""
    today = today or datetime.date.today()
    if doc_type == "consumidor_final":
        return {"allowed": False,
                "reason": "Las facturas a consumidor final no son anulables "
                          "ni admiten nota de crédito (Res. ...25-00000017, "
                          "vigente 01-ene-2026)."}
    if issued_date is None:
        return {"allowed": False, "reason": "comprobante sin fecha"}
    # deadline = day 7 of month following emission
    y, m = issued_date.year, issued_date.month
    nxt = datetime.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    deadline = nxt + datetime.timedelta(days=ANNULMENT_DAY_DEFAULT - 1)
    allowed = today <= deadline
    reason = None
    if not allowed:
        reason = ("Fuera de plazo de anulación: el día 7 del mes siguiente "
                  "fue el %s. Hoy %s." % (deadline.isoformat(),
                                          today.isoformat()))
    return {"allowed": allowed, "deadline": deadline.isoformat(),
            "reason": reason}


# ---------------------------------------------------------------------------
# Withholding computation
# ---------------------------------------------------------------------------
def ir_retention_pct(base, category="servicios", override=None):
    """IR retention percentage; validates against the SRI table."""
    if override is not None:
        pct = round(float(override), 2)
        valid = VALID_IR_SERVICIOS if category == "servicios" else VALID_IR_BIENES
        if pct not in valid:
            return {"percentage": pct, "valid": False,
                    "warning": ("%.2f%% no está en la Tabla 19 para %s "
                                "(valores típicos: %s)"
                                % (pct, category, ", ".join("%.2f" % v for v in valid)))}
        return {"percentage": pct, "valid": True, "warning": None}
    if category == "servicios":
        pct = DEFAULT_IR_SERVICIOS
    elif category == "bienes":
        pct = DEFAULT_IR_BIENES
    else:
        pct = DEFAULT_IR_SERVICIOS_GENERALES
    return {"percentage": pct, "valid": True, "warning": None}


def iva_retention_amount(iva_amount, pct=30.0):
    """Compute the IVA withholding for a given IVA amount and percentage.

    The retained amount goes ENTIRELY to the SRI under the matching
    Formulario 104 casillero (721=10%, 723=20%, 725=30%, 727=50%,
    729=70%, 731=100%).  There is NO SENAE/IESS split of the IVA
    retention; the `iess_share` key is kept for backward compatibility
    and is always 0.0.
    """
    pct = float(pct)
    if pct not in VALID_IVA_RETENTION:
        pct = 30.0
    retained = round(float(iva_amount) * pct / 100.0, 2)
    return {"base_iva": round(float(iva_amount), 2),
            "percentage": pct,
            "retained": retained,
            "sri_share": retained,
            "iess_share": 0.0,
            "warning": None}


# Map IVA retention percentage -> Formulario 104 casillero.
IVA_CASILLERO = {10.0: "721", 20.0: "723", 30.0: "725",
                 50.0: "727", 70.0: "729", 100.0: "731"}


def iva_retention_bucket(category="bienes", agent_especial=False,
                         counterparty_especial=False,
                         counterparty_obligated=False,
                         is_exportador=False):
    """Select the IVA withholding percentage + Formulario 104 casillero.

    Implements the DUAL SCALE of Resolución NAC-DGERCGC20-00000061 (RO
    473, 29-sep-2020) and its reforms (NAC-DGERCGC21-00000037,
    NAC-DGERCGC23-00000026), still in force in 2026 (the March-2026
    reform only touched Impuesto a la Renta).

    `category` (nature of the acquisition):
      * "bienes"             transferencia de bienes muebles gravados
      * "servicios"          adquisición de servicios, comisiones
      * "consultoria"        contratos de consultoría (treated as servicios)
      * "construccion"       contratos de construcción (ALWAYS 30%)
      * "honorarios"         servicios profesionales de personas naturales
                             (excepto consultoría), dietas, directorios
                             (ALWAYS 100%)
      * "arrendamiento"      arrendamiento de inmuebles (100% a personas
                             NO obligadas a llevar contabilidad; 70% a
                             obligadas)
      * "liquidacion_compra" / "importacion_servicios" / "combustibles"
                             ALWAYS 100%

    Selection order (Art. 11 > Art. 5 > Art. 3):
      1. Exportador habitual (agente/especial): 100% on EVERYTHING.
      2. Absolute-100% operations (honorarios, importación de servicios,
         liquidación de compra, combustibles, arrendamiento a no
         obligados).
      3. Contratos de construcción: 30% (general y entre especiales).
      4. Entre contribuyentes ESPECIALES (agente especial → especial):
         10% bienes, 20% servicios/consultoría.
      5. Escala general: 30% bienes, 70% servicios/consultoría/arrendamiento.

    Returns {casillero, percentage, scale, reason}."""
    cat = (category or "bienes").strip().lower()

    # 1) Exportador habitual -> 100% SIEMPRE (Art. 11).
    if is_exportador:
        pct = 100.0
        return {"casillero": IVA_CASILLERO[pct], "percentage": pct,
                "scale": "exportador",
                "reason": ("Exportador habitual agente de retención: "
                           "retiene 100% del IVA en todas sus "
                           "adquisiciones (Res. 61 Art. 11).")}

    # 2) Operaciones de retención absoluta al 100% (Art. 3.c / 3.d).
    absolute_100 = ("honorarios", "liquidacion_compra",
                    "importacion_servicios", "combustibles")
    if cat in absolute_100 or cat == "arrendamiento" and not counterparty_obligated:
        pct = 100.0
        return {"casillero": IVA_CASILLERO[pct], "percentage": pct,
                "scale": "absoluta",
                "reason": ("Retención del 100%% del IVA causado: "
                           "%s (Res. 61, Art. 3)." % cat)}

    # 3) Arrendamiento a persona obligada a llevar contabilidad -> 70%.
    if cat == "arrendamiento" and counterparty_obligated:
        pct = 70.0
        return {"casillero": IVA_CASILLERO[pct], "percentage": pct,
                "scale": "general",
                "reason": ("Arrendamiento a persona obligada a llevar "
                           "contabilidad: 70% del IVA (Res. 61, Art. 3.b).")}

    # 4) Contratos de construcción -> 30% SIEMPRE (general y especiales).
    if cat == "construccion":
        pct = 30.0
        return {"casillero": IVA_CASILLERO[pct], "percentage": pct,
                "scale": "construccion",
                "reason": ("Contrato de construcción: 30% del IVA causado, "
                           "tanto en escala general como entre "
                           "contribuyentes especiales (Res. 61).")}

    # 5) Escala ENTRE CONTRIBUYENTES ESPECIALES (agente especial -> especial).
    if agent_especial and counterparty_especial:
        if cat in ("bienes",):
            pct = 10.0
            why = "bienes (Res. 61 Art. 5.a)"
        else:  # servicios / consultoria
            pct = 20.0
            why = "servicios y consultoría (Res. 61 Art. 5.b)"
        return {"casillero": IVA_CASILLERO[pct], "percentage": pct,
                "scale": "especial",
                "reason": ("Contribuyente especial retiene a otro "
                           "contribuyente especial: %s." % why)}

    # 6) Escala GENERAL (todo lo demás).
    if cat in ("bienes",):
        pct = 30.0
        why = "bienes (Res. 61 Art. 3.a)"
    else:  # servicios / consultoria
        pct = 70.0
        why = "servicios y consultoría (Res. 61 Art. 3.b)"
    return {"casillero": IVA_CASILLERO[pct], "percentage": pct,
            "scale": "general",
            "reason": "Escala general: %s." % why}


# ---------------------------------------------------------------------------
# Missing legally-required data for a valid e-invoice
# ---------------------------------------------------------------------------
def missing_invoice_data(partner, company):
    """
    `partner`/`company` are plain dicts (may be None or partially filled).
    Returns a list of missing items: {field, label, question, severity}
    severity: 'blocker' stops the operation, 'warning' degrades quality.
    """
    missing = []
    cf = False
    if partner:
        cf = is_consumidor_final(partner.get("vat"))

    if not partner:
        missing.append({"field": "partner", "label": "Cliente",
                        "question": "¿Para qué cliente es la factura? Necesito "
                                    "nombre o RUC/cédula para identificarlo.",
                        "severity": "blocker"})
        return missing
    if not cf:
        if not partner.get("vat"):
            missing.append({"field": "vat", "label": "Identificación (RUC/Cédula)",
                            "question": "¿Cuál es el RUC o cédula del cliente? "
                                        "Sin identificación no se puede emitir "
                                        "una factura electrónica válida.",
                            "severity": "blocker"})
        elif partner.get("id_type") in ("ruc", "cedula") and \
                partner.get("valid_checksum") is False:
            missing.append({"field": "vat", "label": "Identificación (RUC/Cédula)",
                            "question": "El número %s no pasa la validación del "
                                        "SRI (dígito verificador). ¿Puede "
                                        "confirmarlo?" % partner.get("vat"),
                            "severity": "blocker"})
    if not partner.get("name") and not partner.get("razon_social"):
        missing.append({"field": "name", "label": "Nombre / Razón social",
                        "question": "¿Cuál es el nombre o razón social que "
                                    "debe aparecer en la factura?",
                        "severity": "blocker" if not cf else "warning"})
    if not partner.get("street") and not partner.get("direccion"):
        missing.append({"field": "street", "label": "Dirección",
                        "question": "¿Cuál es la dirección del cliente? Es "
                                    "obligatoria en la factura electrónica.",
                        "severity": "blocker" if not cf else "warning"})

    # Company (emisor) side
    if not company:
        missing.append({"field": "company", "label": "Empresa emisora",
                        "question": "No hay empresa configurada en Odoo; "
                                    "configure la compañía antes de facturar.",
                        "severity": "blocker"})
    else:
        if not company.get("vat"):
            missing.append({"field": "company_vat", "label": "RUC de la empresa",
                            "question": "La empresa emisora no tiene RUC "
                                        "configurado (Configuración > "
                                        "Compañías).",
                            "severity": "blocker"})
        if not company.get("ambiente"):
            missing.append({"field": "ambiente", "label": "Ambiente SRI",
                            "question": "Defina el ambiente SRI (test/"
                                        "producción) de la compañía.",
                            "severity": "blocker"})
        if not company.get("establishment"):
            missing.append({"field": "establishment", "label": "Establecimiento",
                            "question": "¿Cuál es el código de establecimiento "
                                        "(ej. 001)?",
                            "severity": "warning"})
        if not company.get("emission_point"):
            missing.append({"field": "emission_point", "label": "Punto de emisión",
                            "question": "¿Cuál es el punto de emisión (ej. 001)?",
                            "severity": "warning"})
        if company.get("certificate_active") is False:
            missing.append({"field": "certificate", "label": "Certificado firmador",
                            "question": "No hay certificado P12 activo: la "
                                        "factura se guardará en borrador pero "
                                        "NO podrá firmarse ni enviarse al SRI.",
                            "severity": "warning"})
    return missing


def build_question(missing):
    """Compose a single human question to send back to the agent/user."""
    blockers = [m for m in missing if m["severity"] == "blocker"]
    asked = blockers or missing
    if not asked:
        return None
    return " ".join(m["question"] for m in asked)


# ---------------------------------------------------------------------------
# Payroll / liquidation (pure math; parameters come from Odoo config)
# ---------------------------------------------------------------------------
def progressive_tax(taxable_base, rows):
    """
    Impuesto a la Renta from bracket rows:
    rows = [{'basic_fraction','excess_until','basic_tax','marginal_rate'}, ...]
    (the shape of l10n_ec.tax.table).  No embedded fake table.
    """
    if not rows:
        return None  # caller must surface "no table configured"
    rows = sorted(rows, key=lambda r: r["basic_fraction"])
    for row in rows:
        if row["basic_fraction"] <= taxable_base <= row["excess_until"]:
            excess = taxable_base - row["basic_fraction"]
            return round(row["basic_tax"] + excess * row["marginal_rate"] / 100.0, 2)
    last = rows[-1]
    if taxable_base > last["excess_until"]:
        excess = taxable_base - last["basic_fraction"]
        return round(last["basic_tax"] + excess * last["marginal_rate"] / 100.0, 2)
    return 0.0


def iess_amounts(gross, sbu=None,
                 personal_rate=IESS_PERSONAL_RATE, patronal_rate=IESS_PATRONAL_RATE,
                 secap_rate=IESS_SECAP_RATE, iece_rate=IESS_IECE_RATE):
    """IESS personal/patronal with the 25×SBU ceiling."""
    ceiling = None
    capped_gross = gross
    warnings = []
    if sbu:
        ceiling = sbu * IESS_BASE_MULTIPLIER_CAP
        if gross > ceiling:
            capped_gross = ceiling
            warnings.append("salario base (%.2f) supera el techo 25×SBU "
                            "(%.2f); aporte calculado sobre el techo"
                            % (gross, ceiling))
    personal = round(capped_gross * personal_rate / 100.0, 2)
    patronal = round(capped_gross * patronal_rate / 100.0, 2)
    secap = round(capped_gross * secap_rate / 100.0, 2)
    iece = round(capped_gross * iece_rate / 100.0, 2)
    return {"base": round(capped_gross, 2), "techo_25_sbu": ceiling,
            "personal": personal, "patronal": patronal,
            "secap": secap, "iece": iece,
            "total_empleador": round(patronal + secap + iece, 2),
            "warnings": warnings}


def calculate_liquidation(wage, days_worked=30, sbu=SBU_2026,
                          personal_rate=IESS_PERSONAL_RATE,
                          patronal_rate=IESS_PATRONAL_RATE,
                          extra_income=0.0, advances=0.0, income_tax=0.0):
    """
    Décimo tercero / décimo cuarto / fondos de reserva + neto.
    Mirrors l10n_ec.payslip computes. Base legal: Código del Trabajo —
    décimo tercero art. 111 (1/12), décimo cuarto art. 113 (SBU/360 ×
    días), fondos de reserva art. 195 (8.33% ≈ 1/12).
    """
    days_worked = min(max(float(days_worked), 0.0), 30.0)
    total_income = float(wage) + float(extra_income)
    decimo_tercero = round(total_income / 12.0, 2)
    decimo_cuarto = round(float(sbu) / 360.0 * days_worked, 2)
    fondos = round(total_income * (1.0 / 12.0), 2)
    iess = iess_amounts(total_income, sbu=sbu,
                        personal_rate=personal_rate, patronal_rate=patronal_rate)
    net = round(total_income + decimo_tercero + decimo_cuarto + fondos
                - iess["personal"] - float(income_tax) - float(advances), 2)
    return {"wage": round(float(wage), 2), "extra_income": round(float(extra_income), 2),
            "days_worked": days_worked, "total_income": round(total_income, 2),
            "decimo_tercero": decimo_tercero, "decimo_cuarto": decimo_cuarto,
            "fondos_reserva": fondos, "iess_personal": iess["personal"],
            "iess_patronal": iess["patronal"],
            "income_tax": round(float(income_tax), 2),
            "advances": round(float(advances), 2),
            "net": net, "warnings": iess["warnings"]}


def estimate_lines_total(lines):
    """Pre-flight total of [{quantity, unit_price}] without Odoo compute."""
    total = 0.0
    for line in lines or []:
        qty = float(line.get("quantity", 1) or 1)
        price = float(line.get("unit_price", 0) or 0)
        total += qty * price
    return round(total, 2)
