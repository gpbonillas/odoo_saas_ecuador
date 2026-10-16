# -*- coding: utf-8 -*-
"""
Banco del Austro — Planilla de Pagos (Austro Empresas).

# TODO: validate against bank spec — DOCUMENTED HYPOTHESIS only, not
# certified by Banco del Austro. Confirm against the official manual or
# an exported sample file before real use.

Record structure (fixed-width):

  CABECERA
    1-  2: 'HP' (header planilla)
    3- 15: RUC empresa (13)
    16- 23: fecha AAAAMMDD
    24- 24: moneda ('D' = USD)          <-- TODO: confirm code table
    25- 64: referencia (40)
  DETALLE
    1-  2: 'DP' (detalle planilla)
    3- 17: cuenta destino (15, zero-padded)
    18- 18: tipo ('1' ahorro, '2' corriente)  <-- TODO: confirm code table
    19- 33: valor centavos (15, zero-padded)
    34- 43: identificación (10)
    44- 83: beneficiario (40)
  PIE
    1-  2: 'FP' (fin planilla)
    3- 12: cantidad registros (10)
    13- 32: valor total centavos (20)
"""
from .base import BaseLayoutGenerator


class AustroLayout(BaseLayoutGenerator):
    bank_code = "austro"
    bank_name = "Banco del Austro"

    # TODO: confirm codes with the bank (documented hypothesis: 1/2).
    account_type_map = {"ahorro": "1", "corriente": "2"}

    def _header_line(self, header, lines):
        return (
            "HP"
            + self.pad(header.company_vat, 13, "0", "r")
            + self.date_compact(header)
            + self.pad("D", 1)
            + self.pad(header.batch_reference, 40)
        )

    def _detail_line(self, line, header):
        return (
            "DP"
            + self.pad(line.account_number.replace(" ", ""), 15, "0", "r")
            + self.account_code(line.account_type)
            + self.amount_cents(line.amount, 15)
            + self.pad(line.beneficiary_id, 10)
            + self.pad(line.beneficiary_name, 40)
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "FP" + str(len(lines)).zfill(10) + self.amount_cents(total, 20)
