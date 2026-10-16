# -*- coding: utf-8 -*-
"""
Banco Internacional — Transferencias Masivas.

# TODO: validate against bank spec — DOCUMENTED HYPOTHESIS only, not
# certified by Banco Internacional. Confirm against the official manual
# or an exported sample file before real use.

Record structure (pipe-separated, money in cents):

  CABECERA
    1: 'CABE'
    2: 'PAGO'
    3: RUC empresa
    4: fecha AAAAMMDD
    5: moneda
    6: referencia
  DETALLE
    1: 'DETA'
    2: cuenta destino
    3: tipo cuenta (1 ahorro, 2 corriente)
    4: valor centavos
    5: identificación
    6: beneficiario
    7: referencia
  PIE
    1: 'FINO'
    2: cantidad registros
    3: valor total centavos
"""
from .base import BaseLayoutGenerator


class InternacionalLayout(BaseLayoutGenerator):
    bank_code = "internacional"
    bank_name = "Banco Internacional"

    # TODO: confirm codes with the bank.
    account_type_map = {"ahorro": "1", "corriente": "2"}

    def _header_line(self, header, lines):
        return "|".join(
            [
                "CABE",
                "PAGO",
                header.company_vat,
                self.date_compact(header),
                header.currency,
                self.clean(header.batch_reference, 30),
            ]
        )

    def _detail_line(self, line, header):
        return "|".join(
            [
                "DETA",
                line.account_number.replace(" ", ""),
                self.account_code(line.account_type),
                self.amount_cents(line.amount, 15),
                line.beneficiary_id,
                self.clean(line.beneficiary_name, 60),
                self.clean(line.reference or header.batch_reference, 30),
            ]
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "|".join(["FINO", str(len(lines)), self.amount_cents(total, 20)])
