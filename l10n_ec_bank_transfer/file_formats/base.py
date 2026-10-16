# -*- coding: utf-8 -*-
"""
Base classes for Ecuadorian bank Cash-Management file generators.
===============================================================

IMPORTANT: This package is PURE PYTHON (stdlib only). It must NOT import
`odoo`, so the file-format generators can be unit-tested standalone
(`python3 -m unittest tests.unit.test_bank_transfer`) without a running
Odoo instance.

Each bank layout lives in its own module/class (one class per bank) with
the record structure documented in the class docstring. None of the
layouts below are certified by any bank: every generator carries
`# TODO: validate against bank spec` markers at the points where the
structure is an educated hypothesis that MUST be confirmed against the
official bank manual (or a file exported by the bank portal itself)
before real upload.

Usage:
    from file_formats import BatchHeader, PaymentLine, get_generator

    header = BatchHeader(company_name="ACME", company_vat="1790000001001",
                         payment_date=date(2026, 10, 15), batch_reference="NOMINA OCT")
    lines = [PaymentLine("Juan Perez", "1712345678", "1234567890", 450.50)]
    txt = get_generator("pichincha").generate(header, lines)
"""
from datetime import date as _date

# Canonical account types (Ecuador). Each bank layout maps these to its
# own codes via `account_type_map` (e.g. ahorro -> "AHO").
ACCOUNT_TYPE_SAVINGS = "ahorro"
ACCOUNT_TYPE_CURRENT = "corriente"
VALID_ACCOUNT_TYPES = (ACCOUNT_TYPE_SAVINGS, ACCOUNT_TYPE_CURRENT)


class BankFileError(Exception):
    """Raised when the input data cannot produce a valid bank file."""


class PaymentLine(object):
    """One beneficiary payment. Bank-agnostic representation."""

    __slots__ = (
        "beneficiary_name",
        "beneficiary_id",
        "account_number",
        "amount",
        "account_type",
        "reference",
        "concept",
    )

    def __init__(
        self,
        beneficiary_name,
        beneficiary_id,
        account_number,
        amount,
        account_type=ACCOUNT_TYPE_SAVINGS,
        reference="",
        concept="",
    ):
        self.beneficiary_name = str(beneficiary_name or "").strip()
        self.beneficiary_id = str(beneficiary_id or "").strip()
        self.account_number = str(account_number or "").strip()
        try:
            self.amount = round(float(amount), 2)
        except (TypeError, ValueError):
            self.amount = 0.0
        if account_type not in VALID_ACCOUNT_TYPES:
            account_type = ACCOUNT_TYPE_SAVINGS
        self.account_type = account_type
        self.reference = str(reference or "").strip()
        self.concept = str(concept or "").strip()


class BatchHeader(object):
    """Batch-level data shared by every layout."""

    __slots__ = (
        "company_name",
        "company_vat",
        "payment_date",
        "batch_reference",
        "currency",
        "company_account",
    )

    def __init__(
        self,
        company_name,
        company_vat,
        payment_date,
        batch_reference,
        currency="USD",
        company_account="",
    ):
        self.company_name = str(company_name or "").strip()
        self.company_vat = str(company_vat or "").strip()
        self.payment_date = payment_date
        self.batch_reference = str(batch_reference or "").strip()
        self.currency = str(currency or "USD").strip().upper()
        self.company_account = str(company_account or "").strip()


class BaseLayoutGenerator(object):
    """
    Template-method base: validate() -> _header_line/_detail_line/_footer_line.

    Subclasses only override the line builders and the per-bank mappings;
    validation, amount formatting and assembly are shared.
    """

    bank_code = "generic"
    bank_name = "Generico"
    file_extension = ".txt"
    encoding = "utf-8"
    newline = "\n"

    # Ecuadorian account type -> per-bank code. Override per bank.
    account_type_map = {
        ACCOUNT_TYPE_SAVINGS: "AHO",
        ACCOUNT_TYPE_CURRENT: "CTA",
    }

    # ------------------------------------------------------------------
    # Helpers available to subclasses
    # ------------------------------------------------------------------
    def account_code(self, account_type):
        return self.account_type_map.get(account_type, self.account_type_map[ACCOUNT_TYPE_SAVINGS])

    def format_amount(self, amount):
        """1234.5 -> '1234.50'."""
        return "%.2f" % amount

    def amount_cents(self, amount, width, fill="0"):
        """1234.5 -> '0000000000123450' (integer cents, zero padded)."""
        cents = int(round(float(amount) * 100))
        return str(cents).rjust(width, fill)

    def pad(self, value, width, fill=" ", align="l"):
        value = self.clean(value)
        return value.ljust(width, fill) if align == "l" else value.rjust(width, fill)

    def clean(self, value, max_len=None):
        """Collapse whitespace / strip control chars; optionally truncate."""
        text = " ".join(str(value or "").split())
        if max_len:
            text = text[:max_len]
        return text

    def date_compact(self, header):
        """payment_date -> 'AAAAMMDD'. TODO: some banks want DDMMYYYY."""
        d = header.payment_date
        if isinstance(d, _date):
            return d.strftime("%Y%m%d")
        return str(d or "")

    def date_iso(self, header):
        d = header.payment_date
        if isinstance(d, _date):
            return d.strftime("%Y-%m-%d")
        return str(d or "")

    # ------------------------------------------------------------------
    # Validation (shared, override only if a bank demands extra rules)
    # ------------------------------------------------------------------
    def validate(self, header, lines):
        """
        Returns a list of human-readable errors (empty list == valid).
        NEVER emits placeholder accounts such as '0000000000': a beneficiary
        without a bank account must be fixed upstream, not masked here.
        """
        errors = []
        if not isinstance(header, BatchHeader):
            errors.append("Cabecera inválida (se esperaba BatchHeader).")
            return errors
        if not header.company_vat or not header.company_vat.isdigit() or len(header.company_vat) != 13:
            errors.append(
                "La empresa debe tener un RUC válido de 13 dígitos (obtiene: %r)." % header.company_vat
            )
        if not isinstance(header.payment_date, _date):
            errors.append("Fecha de pago inválida: %r." % (header.payment_date,))
        if not lines:
            errors.append("El lote no contiene ninguna línea de pago.")
        seen = set()
        for idx, line in enumerate(lines, start=1):
            prefix = "Línea %d (%s):" % (idx, line.beneficiary_name or "sin nombre")
            if not line.beneficiary_name:
                errors.append(prefix + " beneficiario vacío.")
            if not line.beneficiary_id:
                errors.append(prefix + " identificación vacía.")
            if not line.account_number:
                errors.append(prefix + " cuenta bancaria vacía.")
            elif len(line.account_number.replace(" ", "")) < 6:
                errors.append(prefix + " cuenta bancaria demasiado corta: %r." % line.account_number)
            if line.amount <= 0:
                errors.append(prefix + " valor debe ser > 0 (obtiene %.2f)." % line.amount)
            dedupe_key = (line.account_number, line.amount, line.beneficiary_id)
            if dedupe_key in seen:
                errors.append(prefix + " línea duplicada (misma cuenta/valor/identificación).")
            seen.add(dedupe_key)
        return errors

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------
    def generate(self, header, lines):
        """Validate and build the full file content (str)."""
        errors = self.validate(header, lines)
        if errors:
            raise BankFileError(
                "No se puede generar el archivo del banco %s:\n- %s"
                % (self.bank_name, "\n- ".join(errors))
            )
        out = [self._header_line(header, lines)]
        for line in lines:
            out.append(self._detail_line(line, header))
        out.append(self._footer_line(header, lines))
        return self.newline.join(out) + self.newline

    # ------------------------------------------------------------------
    # Per-bank record builders (each subclass MUST implement)
    # ------------------------------------------------------------------
    def _header_line(self, header, lines):
        raise NotImplementedError

    def _detail_line(self, line, header):
        raise NotImplementedError

    def _footer_line(self, header, lines):
        raise NotImplementedError
