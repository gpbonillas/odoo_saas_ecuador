# -*- coding: utf-8 -*-
"""
Banco Guayaquil — Multicash.

# TODO: validate against bank spec. Structure REUSED from the previous
# (stub) implementation of this module and regularized; NOT certified by
# Banco Guayaquil. Validate against the official "Multicash Empresas"
# manual (or an exported sample file) before real use.

Record structure (pipe-separated):

  CABECERA (1 por archivo)
    CAB | RUC | FECHA(AAAAMMDD) | MONEDA | REFERENCIA
  DETALLE (1 por pago)
    DET | CUENTA | TIPO_CUENTA(AHO/CTA) | VALOR(9999.99) | IDENTIFICACION | BENEFICIARIO | REFERENCIA
  PIE (1 por archivo)
    FIN | CANTIDAD | VALOR_TOTAL

Notes:
  * Guayaquil accounts are usually 10-12 digits; validation keeps >= 6.
  * TODO: some Multicash products require the beneficiary bank code for
    transfers to third-party banks — extend here when confirmed.
"""
from .base import BaseLayoutGenerator


class GuayaquilMulticashLayout(BaseLayoutGenerator):
    bank_code = "guayaquil"
    bank_name = "Banco Guayaquil (Multicash)"

    account_type_map = {"ahorro": "AHO", "corriente": "CTA"}

    def _header_line(self, header, lines):
        # TODO: validate against bank spec — Multicash may require the
        # contracting company account in the header.
        return "|".join(
            [
                "CAB",
                header.company_vat,
                self.date_compact(header),
                header.currency,
                self.clean(header.batch_reference, 30),
            ]
        )

    def _detail_line(self, line, header):
        return "|".join(
            [
                "DET",
                line.account_number.replace(" ", ""),
                self.account_code(line.account_type),
                self.format_amount(line.amount),
                line.beneficiary_id,
                self.clean(line.beneficiary_name, 60),
                self.clean(line.reference or header.batch_reference, 30),
            ]
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "|".join(["FIN", str(len(lines)), self.format_amount(total)])
