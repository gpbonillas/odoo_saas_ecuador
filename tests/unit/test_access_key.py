# -*- coding: utf-8 -*-
"""
Unit Tests: SRI Access Key generator (pure python, no Odoo runtime)
====================================================================

Run directly:
    python3 tests/unit/test_access_key.py

Covers:
* 49-digit structure and field slices of the generated key
* Modulo-11 check digit verified against an INDEPENDENT implementation
  (same approach as l10n_ec_sri/tests/test_xml_generator.py)
* padding/normalization of doc type, establishment, emission point and
  sequential
"""
import importlib.util
import os
import unittest
from datetime import date

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MODULE_PATH = os.path.join(_REPO_ROOT, "l10n_ec_edi", "models", "access_key.py")

_spec = importlib.util.spec_from_file_location("l10n_ec_edi_access_key", _MODULE_PATH)
access_key_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(access_key_mod)
AccessKey = access_key_mod.AccessKey


def independent_mod11(key_48):
    """Independent SRI Modulo-11 implementation (weights 2..7, reversed)."""
    total = 0
    for position, char in enumerate(reversed(key_48)):
        total += int(char) * (2 + position % 6)
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    elif check == 10:
        check = 1
    return str(check)


class TestAccessKey(unittest.TestCase):
    def _generate(self, **kwargs):
        params = {
            "invoice_date": date(2026, 10, 15),
            "doc_type": "01",
            "ruc": "1790017045001",
            "environment": "2",
            "establishment": "001",
            "emission_point": "001",
            "sequential": "123",
            "numeric_code": "12345678",
        }
        params.update(kwargs)
        return AccessKey.generate(**params)

    def test_length_and_digits(self):
        key = self._generate()
        self.assertEqual(len(key), 49, key)
        self.assertTrue(key.isdigit(), key)

    def test_field_slices(self):
        key = self._generate()
        self.assertEqual(key[0:8], "15102026")  # DDMMYYYY
        self.assertEqual(key[8:10], "01")  # doc type
        self.assertEqual(key[10:23], "1790017045001")  # RUC
        self.assertEqual(key[23:24], "2")  # environment (production)
        self.assertEqual(key[24:27], "001")  # establishment
        self.assertEqual(key[27:30], "001")  # emission point
        self.assertEqual(key[30:39], "000000123")  # sequential
        self.assertEqual(key[39:47], "12345678")  # numeric code
        self.assertEqual(key[47:48], "1")  # emission type

    def test_check_digit_matches_independent_mod11(self):
        for sequential in ("1", "12345", "999999999"):
            key = self._generate(sequential=sequential)
            self.assertEqual(key[48], independent_mod11(key[:48]), key)

    def test_mod11_helper_agrees_with_independent_implementation(self):
        for key_48 in ("1" * 48, "1234567890" * 4 + "12345678", "0" * 48):
            self.assertEqual(len(key_48), 48)
            self.assertEqual(
                AccessKey.compute_check_digit(key_48), independent_mod11(key_48)
            )

    def test_doc_type_padding(self):
        key = self._generate(doc_type="1")
        self.assertEqual(key[8:10], "01")

    def test_environment_test_digit(self):
        key = self._generate(environment="1")
        self.assertEqual(key[23:24], "1")

    def test_establishment_and_sequential_padding(self):
        key = self._generate(establishment="1", emission_point="9", sequential="7")
        self.assertEqual(key[24:27], "001")
        self.assertEqual(key[27:30], "009")
        self.assertEqual(key[30:39], "000000007")


if __name__ == "__main__":
    unittest.main()
