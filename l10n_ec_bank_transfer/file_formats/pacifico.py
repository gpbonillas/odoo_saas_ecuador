# -*- coding: utf-8 -*-
"""
Banco Pacífico — Transferencias por Lote (PacificoNet Empresas).

# TODO: validate against bank spec — DOCUMENTED HYPOTHESIS only, not
# certified by Banco Pacífico. Confirm against the official manual or an
# exported sample file before real use.

Record structure (comma-separated, all money fields in cents):

  CABECERA
    1: 'CAB'
    2: RUC empresa
    3: fecha AAAAMMDD
    4: moneda
    5: referencia
    6: cantidad de registros (informational)
  DETALLE
    1: 'DET'
    2: identificación beneficiario
    3: cuenta destino
    4: tipo cuenta (AH=ahorro, CO=corriente)   <-- Pacifico uses 2-letter codes
    5: valor en centavos
    6: beneficiario
    7: referencia
  PIE
    1: 'FIN'
    2: cantidad de registros
    3: valor total en centavos
"""
from .base import BaseLayoutGenerator


class PacificoLayout(BaseLayoutGenerator):
    bank_code = "pacifico"
    bank_name = "Banco Pacífico"

    account_type_map = {"ahorro": "AH", "corriente": "CO"}

    def _header_line(self, header, lines):
        return ",".join(
            [
                "CAB",
                header.company_vat,
                self.date_compact(header),
                header.currency,
                self.clean(header.batch_reference, 30),
                str(len(lines)),
            ]
        )

    def _detail_line(self, line, header):
        return ",".join(
            [
                "DET",
                line.beneficiary_id,
                line.account_number.replace(" ", ""),
                self.account_code(line.account_type),
                self.amount_cents(line.amount, 15),
                '"%s"' % self.clean(line.beneficiary_name, 60),
                self.clean(line.reference or header.batch_reference, 30),
            ]
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return ",".join(["FIN", str(len(lines)), self.amount_cents(total, 20)])
