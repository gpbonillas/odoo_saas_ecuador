# -*- coding: utf-8 -*-
"""
Generic fallback layout ("cualquier banco").

Used when the target bank has no dedicated generator yet, or explicitly
selected for banks that accept a simple delimited file (or whose real
format will be mapped later). Always safe to fall back to — it carries
every field the other layouts use.

Record structure (pipe-separated, UTF-8):

  CABECERA
    1: 'GEN'
    2: RUC ordenante
    3: fecha AAAAMMDD
    4: moneda
    5: referencia
  DETALLE
    1: 'PAGO'
    2: cuenta destino
    3: tipo cuenta (ahorro/corriente, spelled out)
    4: valor 9999.99
    5: identificación
    6: beneficiario
    7: concepto
    8: referencia
  PIE
    1: 'FIN'
    2: cantidad registros
    3: valor total
"""
from .base import BaseLayoutGenerator


class GenericLayout(BaseLayoutGenerator):
    bank_code = "generic"
    bank_name = "Genérico (fallback)"

    # Spell out the canonical types — no code table to guess.
    account_type_map = {"ahorro": "ahorro", "corriente": "corriente"}

    def _header_line(self, header, lines):
        return "|".join(
            [
                "GEN",
                header.company_vat,
                self.date_compact(header),
                header.currency,
                self.clean(header.batch_reference, 40),
            ]
        )

    def _detail_line(self, line, header):
        return "|".join(
            [
                "PAGO",
                line.account_number.replace(" ", ""),
                self.account_code(line.account_type),
                self.format_amount(line.amount),
                line.beneficiary_id,
                self.clean(line.beneficiary_name, 60),
                self.clean(line.concept, 40),
                self.clean(line.reference or header.batch_reference, 40),
            ]
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "|".join(["FIN", str(len(lines)), self.format_amount(total)])
