# -*- coding: utf-8 -*-
"""
Unit Tests: Bank Cash-Management file-format generators
=======================================================

PURE PYTHON (stdlib `unittest` only) — no Odoo runtime required, because
the generators in `l10n_ec_bank_transfer/file_formats/` are deliberately
importable standalone.

Run directly:
    python3 tests/unit/test_bank_transfer.py
or via unittest/pytest from the repo root.

Covers:
* every bank layout listed in the plan produces a structurally-valid file
* validation aborts instead of emitting placeholder accounts (audit 1b)
* per-bank account-type codes from the partner-bank field (audit 1c)
* unknown bank codes fail loudly
"""
import os
import sys
import unittest
from datetime import date

# Make l10n_ec_bank_transfer/file_formats importable without Odoo.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MODULE_DIR = os.path.join(_REPO_ROOT, "l10n_ec_bank_transfer")
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

from file_formats import (  # noqa: E402
    LAYOUTS,
    BankFileError,
    BatchHeader,
    PaymentLine,
    available_bank_codes,
    get_generator,
)

# Banks required by the development plan (Sprint 5).
PLAN_BANKS = (
    "pichincha",
    "guayaquil",
    "produbanco",
    "pacifico",
    "austro",
    "bolivariano",
    "loja",
    "internacional",
    "ib",
    "generic",
)


def _header():
    return BatchHeader(
        company_name="ACME COMERCIAL ECUADOR CIA. LTDA.",
        company_vat="1793125212001",
        payment_date=date(2026, 10, 15),
        batch_reference="NOMINA OCTUBRE",
    )


def _lines():
    return [
        # 'BBBB-CUENTA' so the IB/CENPE interbank layout is also satisfied
        PaymentLine("Juan Perez", "1713488185", "0019-1234567890", 450.50, "ahorro"),
        PaymentLine("Maria Lopez", "1713488185001", "0019-0123456789", 1000.00, "corriente",
                    reference="REC-002"),
    ]


class TestRegistry(unittest.TestCase):
    def test_all_plan_banks_registered(self):
        for code in PLAN_BANKS:
            self.assertIn(code, LAYOUTS, "missing bank generator: %s" % code)

    def test_available_bank_codes_sorted(self):
        codes = available_bank_codes()
        self.assertEqual(codes, sorted(codes))
        self.assertTrue(set(PLAN_BANKS).issubset(codes))

    def test_get_generator_unknown_raises(self):
        with self.assertRaises(BankFileError):
            get_generator("no-existe")


class TestEveryLayout(unittest.TestCase):
    """Structural sanity for every registered bank layout."""

    def test_generate_one_header_details_footer(self):
        for code in available_bank_codes():
            gen = get_generator(code)
            lines = _lines()
            content = gen.generate(_header(), lines)
            self.assertTrue(content, "empty file for %s" % code)
            records = [r for r in content.split(gen.newline) if r]
            self.assertEqual(
                len(records), 2 + len(lines),
                "%s: expected header + %d details + footer" % (code, len(lines)),
            )
            # Header carries RUC + payment date (compact or dd/mm/yyyy)
            self.assertIn("1793125212001", records[0], code)
            self.assertTrue(
                "20261015" in records[0] or "15/10/2026" in records[0],
                "%s: header missing payment date: %s" % (code, records[0]),
            )
            # Footer carries record count
            self.assertIn(str(len(lines)), records[-1], code)
            # Detail carries the amounts (either 2-decimal or integer-cents form)
            self.assertTrue(
                "450.50" in content or "45050" in content, "%s: missing 450.50" % code
            )
            self.assertTrue(
                "1000.00" in content or "100000" in content, "%s: missing 1000.00" % code
            )
            # Every beneficiary present
            self.assertIn("Juan Perez", content, code)
            self.assertIn("Maria Lopez", content, code)

    def test_footer_total_matches_sum(self):
        for code in available_bank_codes():
            gen = get_generator(code)
            lines = _lines()
            content = gen.generate(_header(), lines)
            footer = [r for r in content.split(gen.newline) if r][-1]
            # 450.50 + 1000.00 = 1450.50 -> '1450.50' or cents '145050'
            self.assertTrue(
                "1450.50" in footer or "145050" in footer,
                "%s footer total wrong: %s" % (code, footer),
            )


class TestValidation(unittest.TestCase):
    """Audit item 1b: missing data must ABORT with a clear error,
    never emit placeholder accounts like '0'*10 (todo ceros)."""

    def test_no_placeholder_account_in_any_layout(self):
        bad = [PaymentLine("Sin Cuenta", "1713488185", "", 50.0)]
        for code in available_bank_codes():
            gen = get_generator(code)
            with self.assertRaises(BankFileError, msg=code):
                content = gen.generate(_header(), bad)
                self.assertNotIn("0" * 10, content, code)

    def test_empty_account_error_message_lists_beneficiary(self):
        gen = get_generator("pichincha")
        bad = [PaymentLine("Pedro Sin Cuenta", "1713488185", "", 50.0)]
        with self.assertRaises(BankFileError) as ctx:
            gen.generate(_header(), bad)
        self.assertIn("Pedro Sin Cuenta", str(ctx.exception))
        self.assertIn("cuenta bancaria vacía", str(ctx.exception))

    def test_zero_amount_rejected(self):
        gen = get_generator("pichincha")
        bad = [PaymentLine("Juan", "1713488185", "1234567890", 0.0)]
        with self.assertRaises(BankFileError):
            gen.generate(_header(), bad)

    def test_short_account_rejected(self):
        gen = get_generator("generic")
        bad = [PaymentLine("Juan", "1713488185", "123", 10.0)]
        with self.assertRaises(BankFileError):
            gen.generate(_header(), bad)

    def test_missing_identification_rejected(self):
        gen = get_generator("guayaquil")
        bad = [PaymentLine("Juan", "", "1234567890", 10.0)]
        with self.assertRaises(BankFileError):
            gen.generate(_header(), bad)

    def test_invalid_ruc_rejected(self):
        gen = get_generator("pichincha")
        header = BatchHeader("ACME", "123", date(2026, 10, 15), "LOTE")
        with self.assertRaises(BankFileError):
            gen.generate(header, _lines())

    def test_no_lines_rejected(self):
        for code in available_bank_codes():
            with self.assertRaises(BankFileError, msg=code):
                get_generator(code).generate(_header(), [])

    def test_duplicate_lines_flagged(self):
        gen = get_generator("pichincha")
        line = PaymentLine("Juan", "1713488185", "1234567890", 25.0)
        with self.assertRaises(BankFileError) as ctx:
            gen.generate(_header(), [line, line])
        self.assertIn("duplicada", str(ctx.exception))


class TestAccountTypeMapping(unittest.TestCase):
    """Audit item 1c: account type comes from the per-bank-account field
    (ahorro/corriente), mapped by each layout — not hardcoded."""

    def test_pichincha_aho_cta(self):
        gen = get_generator("pichincha")
        self.assertEqual(gen.account_code("ahorro"), "AHO")
        self.assertEqual(gen.account_code("corriente"), "CTA")

    def test_unknown_type_falls_back_to_ahorro(self):
        gen = get_generator("pichincha")
        self.assertEqual(gen.account_code("desconocido"), "AHO")

    def test_every_layout_has_codes_for_both_types(self):
        for code in available_bank_codes():
            gen = get_generator(code)
            for acc_type in ("ahorro", "corriente"):
                mapped = gen.account_code(acc_type)
                self.assertTrue(mapped, "%s/%s -> empty code" % (code, acc_type))

    def test_payment_line_normalizes_invalid_type(self):
        line = PaymentLine("Juan", "1", "1234567890", 1.0, "bitcoin")
        self.assertEqual(line.account_type, "ahorro")

    def test_corriente_reaches_the_file(self):
        content = get_generator("guayaquil").generate(_header(), _lines())
        self.assertIn("CTA", content)


class TestInterbank(unittest.TestCase):
    """IB/CENPE requires destination bank code prefix."""

    def test_missing_bank_code_rejected(self):
        gen = get_generator("ib")
        bad = [PaymentLine("Juan", "1713488185", "1234567890", 10.0)]
        with self.assertRaises(BankFileError) as ctx:
            gen.generate(_header(), bad)
        self.assertIn("CODIGO_BANCO", str(ctx.exception))

    def test_bank_code_split(self):
        gen = get_generator("ib")
        self.assertEqual(gen._bank_account_split("19-1234567890"), ("0019", "1234567890"))
        self.assertEqual(gen._bank_account_split("0019-1234567890"), ("0019", "1234567890"))

    def test_valid_ib_file(self):
        gen = get_generator("ib")
        lines = [PaymentLine("Juan", "1713488185", "0019-1234567890", 10.0)]
        content = gen.generate(_header(), lines)
        detail = content.split(gen.newline)[1]
        self.assertTrue(detail.startswith("IB0019"), detail)


class TestHelpers(unittest.TestCase):
    def test_amount_cents_padding(self):
        gen = get_generator("produbanco")
        self.assertEqual(gen.amount_cents(12.34, 15), "0" * 11 + "1234")
        self.assertEqual(gen.amount_cents(1234.5, 15), "0" * 9 + "123450")

    def test_pad_and_clean(self):
        gen = get_generator("produbanco")
        self.assertEqual(gen.pad("AB", 5), "AB   ")
        self.assertEqual(gen.pad("AB", 5, "0", "r"), "000AB")
        self.assertEqual(gen.clean("  hola \n mundo  "), "hola mundo")
        self.assertEqual(gen.clean("abcdef", 3), "abc")

    def test_payment_line_amount_normalization(self):
        line = PaymentLine("Juan", "1", "1234567890", "99.999")
        self.assertEqual(line.amount, 100.0)
        line = PaymentLine("Juan", "1", "1234567890", "not-a-number")
        self.assertEqual(line.amount, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
