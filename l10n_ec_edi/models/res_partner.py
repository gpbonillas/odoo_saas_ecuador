# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _l10n_ec_is_forced_to_keep_accounting(self):
        """
        SRI: is this contributor "obligado a llevar contabilidad"?

        Used to auto-select the purchase document type:
        * Forced (RUC company / special taxpayer) -> Factura de Compra (01)
        * Not forced (natural person below the threshold) ->
          Liquidación de Compra (03)

        Rules:
        * Contribuyente Especial -> always forced.
        * 10-digit identifier (cédula) -> natural person, not forced.
        * 13-digit RUC -> forced only when the 3rd digit is 6-9
          (public entity or private company). Natural-person RUCs
          (3rd digit 0-5) are not forced.
        * Otherwise -> companies are forced, persons are not.
        """
        self.ensure_one()

        if self.l10n_ec_taxpayer_type == "special":
            return True

        vat = (self.vat or "").strip()
        if vat.isdigit():
            if len(vat) == 10:
                return False
            if len(vat) == 13:
                return vat[2] in "6789"

        return self.company_type == "company"
