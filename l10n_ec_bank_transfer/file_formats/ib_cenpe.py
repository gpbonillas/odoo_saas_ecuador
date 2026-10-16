# -*- coding: utf-8 -*-
"""
Transferencia Interbancaria — IB / CENPE (Banco Central del Ecuador).

The "IB" (Interbancario) circuit operated by BCE/CENPE moves money
between accounts of DIFFERENT banks; the beneficiary account therefore
carries the destination bank code (4-digit BCE bank code) plus the
account.

# TODO: validate against bank spec — the BCE "CENPE" format is published
by Banco Central and changes by resolution; the fixed-width structure
below is a DOCUMENTED HYPOTHESIS based on the general BCE conventions
and must be confirmed against the current "Formato de archivo de
transferencias interbancarias" resolution before real use.

Record structure (fixed-width):

  CABECERA
    1-  2: 'IB'
    3- 15: RUC ordenante (13)
    16- 23: fecha AAAAMMDD
    24- 26: moneda ('840' = USD ISO-4217)  <-- TODO: confirm table
    27- 66: referencia (40)
  DETALLE
    1-  2: 'IB'
    3-  6: código banco destino (4, BCE table)  <-- TODO: confirm table
    7- 21: cuenta destino (15, zero-padded)
    22- 36: valor centavos (15, zero-padded)
    37- 46: identificación beneficiario (10)
    47- 86: beneficiario (40)
    87- 87: tipo cuenta origen (A=ahorro, C=corriente)
  PIE
    1-  2: 'IB'
    3- 12: cantidad registros
    13- 32: valor total centavos
"""
from .base import BaseLayoutGenerator


class IbCenpeLayout(BaseLayoutGenerator):
    bank_code = "ib"
    bank_name = "IB / CENPE (Transferencia Interbancaria BCE)"

    # TODO: confirm codes with BCE (documented hypothesis A/C).
    account_type_map = {"ahorro": "A", "corriente": "C"}

    CURRENCY_CODE = "840"  # ISO-4217 USD. TODO: confirm BCE table.

    def validate(self, header, lines):
        errors = super(IbCenpeLayout, self).validate(header, lines)
        # Extra rule: the destination bank code (first 4 chars of the
        # reference-free field) is mandatory for interbank transfers.
        # We carry it as account_number prefix "BBBB-CCCCCCCCCCC".
        for idx, line in enumerate(lines, start=1):
            if "-" not in line.account_number:
                errors.append(
                    "Línea %d (%s): transferencia interbancaria requiere "
                    "cuenta 'CODIGO_BANCO-CUENTA' (p. ej. '0019-1234567890'); "
                    "obtiene %r." % (idx, line.beneficiary_name, line.account_number)
                )
        return errors

    def _bank_account_split(self, account_number):
        bank_code, _, account = account_number.replace(" ", "").partition("-")
        return bank_code.zfill(4), account

    def _header_line(self, header, lines):
        return (
            "IB"
            + self.pad(header.company_vat, 13, "0", "r")
            + self.date_compact(header)
            + self.CURRENCY_CODE
            + self.pad(header.batch_reference, 40)
        )

    def _detail_line(self, line, header):
        bank_code, account = self._bank_account_split(line.account_number)
        return (
            "IB"
            + bank_code
            + self.pad(account, 15, "0", "r")
            + self.amount_cents(line.amount, 15)
            + self.pad(line.beneficiary_id, 10)
            + self.pad(line.beneficiary_name, 40)
            + self.account_code(line.account_type)
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "IB" + str(len(lines)).zfill(10) + self.amount_cents(total, 20)
