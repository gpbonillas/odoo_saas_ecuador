# -*- coding: utf-8 -*-
"""
Banco Pichincha — Cash Management ("Carga de Pagos" / Transferencias).

# TODO: validate against bank spec. The structure below is a REASONABLE
# DOCUMENTED HYPOTHESIS kept from the previous implementation of this
# module; it is NOT certified by Banco Pichincha. Before uploading real
# files, validate every field against the official "Cash Management"
# manual of the company's portal (Pichincha Empresas) or against a file
# exported by the portal itself.

Record structure (tab-separated):

  CABECERA (1 por archivo)
    PA | RUC_EMPRESA | MONEDA | FECHA(AAAAMMDD) | REFERENCIA_LOTE
  DETALLE (1 por pago)
    BENEFICIARIO | IDENTIFICACION | CUENTA | TIPO_CUENTA(AHO/CTA) | VALOR(9999.99) | REFERENCIA
  PIE (1 por archivo)
    TOT | CANTIDAD_REGISTROS | VALOR_TOTAL

Notes:
  * 'AHO' = ahorro, 'CTA' = corriente (per employee/partner bank account).
  * Amounts with two decimals, dot as decimal separator.
"""
from .base import BaseLayoutGenerator


class PichinchaCashManagementLayout(BaseLayoutGenerator):
    bank_code = "pichincha"
    bank_name = "Banco Pichincha (Cash Management)"

    account_type_map = {"ahorro": "AHO", "corriente": "CTA"}

    def _header_line(self, header, lines):
        # TODO: validate against bank spec — Pichincha may require the
        # company account number and/or a fixed 'PA' transaction code per
        # product type (nómina vs proveedores).
        return "\t".join(
            [
                "PA",
                header.company_vat,
                header.currency,
                self.date_compact(header),
                self.clean(header.batch_reference, 40),
            ]
        )

    def _detail_line(self, line, header):
        # TODO: validate against bank spec — confirm field order and
        # whether the identification must be type-prefixed (e.g. C:017...).
        return "\t".join(
            [
                self.clean(line.beneficiary_name, 60),
                line.beneficiary_id,
                line.account_number.replace(" ", ""),
                self.account_code(line.account_type),
                self.format_amount(line.amount),
                self.clean(line.reference or header.batch_reference, 40),
            ]
        )

    def _footer_line(self, header, lines):
        total = sum(line.amount for line in lines)
        return "\t".join(["TOT", str(len(lines)), self.format_amount(total)])
