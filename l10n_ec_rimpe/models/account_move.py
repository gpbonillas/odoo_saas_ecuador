# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_rimpe_retention_code(self, partner):
        """
        Returns the correct retention code based on RIMPE type.
        SRI Tabla 19 (Res. NAC-DGERCGC26-00000009, RO 233):
        332: Negocio Popular (0%) — "Otras compras ... (incluye régimen
             RIMPE - Negocios Populares)"
        343: Emprendedor (1%) — "régimen RIMPE - Emprendedores"
        (Los códigos 332B/343A corresponden a energía eléctrica, 0%/2%,
        no a RIMPE.)
        """
        if partner.l10n_ec_rimpe_type == "popular_business":
            return "332"
        elif partner.l10n_ec_rimpe_type == "entrepreneur":
            return "343"
        return None

    # Logic to override retention application would go here
    # For now, we define the helper that will be used by the withholding module integration
