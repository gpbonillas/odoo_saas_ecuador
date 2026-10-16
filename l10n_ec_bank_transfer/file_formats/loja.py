# -*- coding: utf-8 -*-
"""
Banco del Loja — Planilla de Pagos.

# TODO: validate against bank spec — DOCUMENTED HYPOTHESIS only, not
# certified by Banco del Loja. Confirm against the official manual or an
# exported sample file before real use.

Record structure (fixed-width):

  CABECERA
    1-  2: '10'
    3- 15: RUC empresa
    16- 23: fecha AAAAMMDD
    24- 63: referencia (40)
  DETALLE
    1-  2: '20'
    3- 17: cuenta (15, zero-padded)
    18- 19: tipo ('SA' ahorro, 'CC' corriente)
    20- 34: valor centavos (15)
    35- 44: identificación (10)
    45- 89: beneficiario (45)
  PIE
    1-  2: '90'
    3- 12: cantidad
    13- 32: valor total centavos (20)
"""
from .base import BaseLayoutGenerator


class LojaLayout(BaseLayoutGenerator):
    bank_code = "loja"
    bank_name = "Banco del Loja"

    # TODO: confirm codes with the bank.
    account_type_map = {"ahorro": "SA", "corriente": "CC"}

    def _header_line(self, header, lines):
        return (
            "10"
            + self.pad(header.company_vat, 13, "0", "r")
            + self.date_compact(header)
            + self.pad(header.batch_reference, 40)
        )

    def _detail_line(self, line, header):
        return (
            "20"
            + self.pad(line.account_number.replace(" ", ""), 15, "0", "r")
            + self.pad(self.account_code(line.account_type), 2)
            + self.amount_cents(line.amount, 15)
            + self.pad(line.beneficiary_id, 10)
            + self.pad(line.beneficiary_name, 45)
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "90" + str(len(lines)).zfill(10) + self.amount_cents(total, 20)
