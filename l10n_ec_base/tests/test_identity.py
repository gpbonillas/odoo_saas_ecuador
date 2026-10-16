# -*- coding: utf-8 -*-
"""
Identidad ecuatoriana (CHG-2026-004): _validate_ec_document de res.partner
debe ser equivalente a stdnum (stdnum.ec.ci / stdnum.ec.ruc).

IDs de prueba EXCLUSIVOS (D-04) — únicos que pueden existir como partner:
  cédula      1713488185           (persona natural)
  RUC natural 1713488185001        (= cédula + "001", SRI: CADENA PEÑA ADRIAN RAFAEL)
  RUC jurídico 1793125212001       (SRI: CANNACHAIN S.A.S.)

Los números "mutados" que aparecen aquí son SINTÉTICOS: existen solo para
medir la equivalencia del dígito verificador contra stdnum, nunca se usan
como datos de contribuyentes.
"""
import unittest

from odoo.tests import common, tagged
from odoo.exceptions import ValidationError

try:  # stdnum vive dentro del contenedor Odoo (dependencia oficial de Odoo)
    from stdnum.ec import ci as _std_ci
    from stdnum.ec import ruc as _std_ruc
except ImportError:  # pragma: no cover
    _std_ci = _std_ruc = None

CEDULA_OK = "1713488185"
RUC_NATURAL_OK = "1713488185001"      # cédula + 001
RUC_JURIDICA_OK = "1793125212001"     # CANNACHAIN S.A.S. (3er dígito 9)


def _stdnum_ok(number):
    """Validación oficial stdnum para el largo correspondiente."""
    if len(number) == 10:
        return _std_ci.is_valid(number)
    if len(number) == 13:
        return _std_ruc.is_valid(number)
    return False


@tagged("post_install", "-at_install")
class TestEcIdentity(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestEcIdentity, cls).setUpClass()
        cls.ec = cls.env.ref("base.ec")

    def test_valid_ruc_natural(self):
        """RUC natural: cédula real + sufijo 001 (D-02)."""
        partner = self.env["res.partner"].create(
            {
                "name": "Valid RUC Natural",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "ruc",
                "vat": RUC_NATURAL_OK,
            }
        )
        self.assertTrue(partner)

    def test_valid_ruc_juridica(self):
        """RUC jurídico real (3er dígito 9): CANNACHAIN S.A.S."""
        partner = self.env["res.partner"].create(
            {
                "name": "Valid RUC Juridica",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "ruc",
                "vat": RUC_JURIDICA_OK,
            }
        )
        self.assertTrue(partner)

    def test_valid_cedula(self):
        """Cédula real (10 dígitos)."""
        partner = self.env["res.partner"].create(
            {
                "name": "Valid Cedula",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "cedula",
                "vat": CEDULA_OK,
            }
        )
        self.assertTrue(partner)

    def test_invalid_length(self):
        """Longitud inválida para RUC."""
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Invalid Length",
                    "country_id": self.ec.id,
                    "l10n_ec_identifier_type": "ruc",
                    "vat": "123",
                }
            )

    def test_invalid_mod10(self):
        """Cédula aprobada con el dígito verificador corrompido."""
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Invalid Check Digit",
                    "country_id": self.ec.id,
                    "l10n_ec_identifier_type": "cedula",
                    "vat": CEDULA_OK[:-1] + "6",   # ...85 valido -> ...86 no
                }
            )

    def test_pasaporte(self):
        """Pasaporte acepta alfanumérico > 5 caracteres."""
        partner = self.env["res.partner"].create(
            {
                "name": "Foreigner",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "pasaporte",
                "vat": "PASS123456",
            }
        )
        self.assertTrue(partner)


@unittest.skipUnless(_std_ci is not None,
                     "stdnum no instalado (correr dentro del contenedor)")
@tagged("post_install", "-at_install")
class TestStdnumEquivalenceResPartner(common.TransactionCase):
    """CHG-2026-004: res_partner._validate_ec_document == stdnum, dígito a
    dígito, sobre los IDs aprobados + todas sus mutaciones sintéticas.

    Evidencia complementaria: mcp_server/test_server.py
    TestStdnumEquivalence (rules.py vs stdnum, mismo algoritmo).
    """

    def test_approved_ids_valid_in_both(self):
        partner_model = self.env["res.partner"]
        for number in (CEDULA_OK, RUC_NATURAL_OK, RUC_JURIDICA_OK):
            self.assertTrue(partner_model._validate_ec_document(number),
                            number)
            self.assertTrue(_stdnum_ok(number), number)

    def test_single_digit_mutations_match_stdnum(self):
        """~360 mutaciones de los IDs aprobados: ambas partes coinciden."""
        partner_model = self.env["res.partner"]
        checked = 0
        for base in (CEDULA_OK, RUC_NATURAL_OK, RUC_JURIDICA_OK):
            for pos in range(len(base)):
                for digit in "0123456789":
                    candidate = base[:pos] + digit + base[pos + 1:]
                    ours = partner_model._validate_ec_document(candidate)
                    theirs = _stdnum_ok(candidate)
                    self.assertEqual(
                        ours, theirs,
                        "%s: res.partner=%s stdnum=%s" % (candidate, ours,
                                                          theirs),
                    )
                    checked += 1
        self.assertGreaterEqual(checked, 360)

    def test_length_out_of_range(self):
        partner_model = self.env["res.partner"]
        for candidate in ("171348818", CEDULA_OK + "0", RUC_JURIDICA_OK + "0"):
            self.assertFalse(partner_model._validate_ec_document(candidate))
