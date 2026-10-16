# -*- coding: utf-8 -*-
"""
produbanco — Planilla de Pagos (Multiacceso / produbanco Empresas).

# TODO: validate against bank spec — this layout is a DOCUMENTED
# HYPOTHESIS. produbanco's real "Multiacceso" batch format has NOT been
# available during development. Confirm every field against the official
"produbanco Empresas" manual or an exported sample file before use.

Record structure (fixed-width, positions are 1-based, inclusive):

  CABECERA
    cols  1- 2: '00' (record type)
    cols  3-15: RUC de la empresa (13)
    cols 16-23: fecha AAAAMMDD
    cols 24-26: moneda ('USD')
    cols 27-66: referencia del lote (40)
  DETALLE
    cols  1- 2: '01' (record type)
    cols  3-22: cuenta destino (20, left zero-padded)
    cols 23-24: tipo cuenta (AHO/CTA)
    cols 25-39: valor en centavos (15, zero-padded)
    cols 40-49: identificación (10)
    cols 50-99: beneficiario (50)
  PIE
    cols  1- 2: '99'
    cols  3-12: cantidad de registros (10, zero-padded)
    cols 13-32: valor total en centavos (20, zero-padded)
"""
from .base import BaseLayoutGenerator


class ProdubancoLayout(BaseLayoutGenerator):
    bank_code = "produbanco"
    bank_name = "produbanco (Multiacceso)"

    account_type_map = {"ahorro": "AHO", "corriente": "CTA"}

    def _header_line(self, header, lines):
        return (
            "00"
            + self.pad(header.company_vat, 13, "0", "r")
            + self.date_compact(header)
            + self.pad(header.currency, 3)
            + self.pad(header.batch_reference, 40)
        )

    def _detail_line(self, line, header):
        return (
            "01"
            + self.pad(line.account_number.replace(" ", ""), 20, "0", "r")
            + self.pad(self.account_code(line.account_type), 2)
            + self.amount_cents(line.amount, 15)
            + self.pad(line.beneficiary_id, 10)
            + self.pad(line.beneficiary_name, 50)
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "99" + str(len(lines)).zfill(10) + self.amount_cents(total, 20)
