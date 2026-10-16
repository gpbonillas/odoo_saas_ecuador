# -*- coding: utf-8 -*-
"""
Banco Bolivariano — Pago Masivo (Bolivariano Empresas).

# TODO: validate against bank spec — DOCUMENTED HYPOTHESIS only, not
# certified by Banco Bolivariano. Confirm against the official manual or
# an exported sample file before real use.

Record structure (semicolon-separated — Bolivariano exports commonly use ';'):

  CABECERA
    1: 'H00'
    2: RUC empresa
    3: fecha DD/MM/AAAA           <-- TODO: confirm date format
    4: moneda
    5: referencia
  DETALLE
    1: 'D01'
    2: cuenta destino
    3: tipo cuenta (AHO/CTA)
    4: valor con 2 decimales
    5: identificación
    6: beneficiario
    7: referencia
  PIE
    1: 'T00'
    2: cantidad registros
    3: valor total
"""
from .base import BaseLayoutGenerator


class BolivarianoLayout(BaseLayoutGenerator):
    bank_code = "bolivariano"
    bank_name = "Banco Bolivariano"

    account_type_map = {"ahorro": "AHO", "corriente": "CTA"}

    def _header_line(self, header, lines):
        d = header.payment_date
        date_str = d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)
        return ";".join(
            ["H00", header.company_vat, date_str, header.currency,
             self.clean(header.batch_reference, 30)]
        )

    def _detail_line(self, line, header):
        return ";".join(
            [
                "D01",
                line.account_number.replace(" ", ""),
                self.account_code(line.account_type),
                self.format_amount(line.amount),
                line.beneficiary_id,
                '"%s"' % self.clean(line.beneficiary_name, 60),
                self.clean(line.reference or header.batch_reference, 30),
            ]
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return ";".join(["T00", str(len(lines)), self.format_amount(total)])
