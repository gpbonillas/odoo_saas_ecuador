# -*- coding: utf-8 -*-
"""
ECUAPASS (SENAE) integration — STUB.

ECUAPASS is SENAE's foreign-trade platform (declaraciones, DUI/DAU,
tributación aduanera). A real integration requires:

  * SENAE web-service credentials (usuario/clave de agente aduanero),
  * a signed SOAP/REST client against the ECUAPASS endpoints, and
  * the declaration-status message catalogue.

None of that can be built/tested offline, so this module provides the
LINKAGE POINTS only:

  * `l10n_ec.import.dau` fields: `ecuapass_dui_number`, `ecuapass_folio`,
    `ecuapass_state`, `ecuapass_last_check`, `ecuapass_response`;
  * this abstract service with a documented interface
    (`get_declaration_status`) that currently raises
    `NotImplementedError` — the DAU button catches it and stores a clear
    "integration pending" message instead of crashing.

TODO: implement the real ECUAPASS client (credentials on res.company +
SOAP against SENAE) and flip `is_available` to True.
"""
from odoo import models, _


class L10nEcEcuapassService(models.AbstractModel):
    _name = "l10n_ec.ecuapass.service"
    _description = "ECUAPASS (SENAE) Integration - Stub"

    def is_available(self):
        """False while the real client is not implemented."""
        return False

    def get_declaration_status(self, dau):
        """
        Query ECUAPASS for the status of a customs declaration.

        :param dau: l10n_ec.import.dau record
        :return: dict {state, dui_number, folio, raw_response}
        """
        raise NotImplementedError(
            _(
                "The ECUAPASS integration is a stub: the SENAE web-service "
                "client is not implemented yet. Declaration: %s "
                "(folia: %s). See l10n_ec_customs/models/l10n_ec_ecuapass.py."
            )
            % (dau.name, dau.ecuapass_folio or "-")
        )
