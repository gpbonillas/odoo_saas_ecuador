# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Gate de laboratorio en movimientos de stock — FR-AG-03.

Regla genérica: un lote con al menos un análisis NO conforme no puede
salir del stock interno (ventas, consumos MRP, salidas). Los movimientos
internos (traspasos entre locations internos) no se bloquean.
"""
from odoo import models, _
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_confirm(self, merge=True, merge_into=False):
        res = super()._action_confirm(merge=merge, merge_into=merge_into)
        self._l10n_ec_check_agro_lab_gate()
        return res

    def _action_done(self, cancel_backorder=False):
        # Backstop: flujos que se saltan _action_confirm (movimientos que
        # nacen 'assigned' con cantidad en la línea, POS, MRP...). El stock
        # sólo sale realmente aquí => gate obligatorio también en la salida.
        self._l10n_ec_check_agro_lab_gate()
        return super()._action_done(cancel_backorder=cancel_backorder)

    def _l10n_ec_check_agro_lab_gate(self):
        """Bloquea salidas de lotes con análisis reprobado (FR-AG-03)."""
        Analysis = self.env["l10n_ec.agro.analysis"]
        for move in self:
            if move.location_id.usage != "internal" or move.location_dest_id.usage == "internal":
                continue  # el gate aplica sólo a salidas de stock interno
            for lot in move.move_line_ids.mapped("lot_id"):
                failed = Analysis.search(
                    [("lot_id", "=", lot.id), ("passed", "=", False)], limit=1
                )
                if failed:
                    raise UserError(
                        _(
                            "Lote %(lot)s bloqueado: análisis '%(analyte)s' no conforme "
                            "(valor %(value)s, límite %(limit)s). Gate de laboratorio FR-AG-03."
                        )
                        % {
                            "lot": lot.display_name,
                            "analyte": failed.analyte,
                            "value": failed.value,
                            "limit": failed.limit or "-",
                        }
                    )
