# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
SUPERCIAS financial statements wizard: Balance General, Estado de
Resultados, Flujo de Efectivo (indirect method), Cambios en el Patrimonio
and Notas (structured stub with the required NIC 1 headings).

Source: l10n_ec_sri/docs/11_regulatory_knowledge_base/KB_SUPERCIAS.md 3.2.
All math is in report_lib (pure python).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .. import report_lib as lib


STATEMENT_SELECTIONS = [
    ("balance", "Estado de Situacion Financiera (Balance General)"),
    ("resultados", "Estado de Resultados Integral"),
    ("flujo", "Estado de Flujos de Efectivo (metodo indirecto)"),
    ("patrimonio", "Estado de Cambios en el Patrimonio"),
    ("notas", "Notas a los Estados Financieros"),
]

STATEMENT_TITLES = dict(STATEMENT_SELECTIONS)


class L10nEcFinancialsWizard(models.TransientModel):
    _name = "l10n_ec.financials.wizard"
    _inherit = ["l10n.ec.report.common"]
    _description = "Estados Financieros SUPERCIAS"

    statement = fields.Selection(
        STATEMENT_SELECTIONS, required=True, default="balance"
    )
    date_from = fields.Date(
        string="Desde (apertura)",
        required=True,
        default=lambda self: fields.Date.today().replace(
            month=1, day=1
        ),
    )
    date_to = fields.Date(
        string="Hasta (cierre)", required=True, default=fields.Date.context_today
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    # ------------------------------------------------------------------
    def _period_label(self):
        return "%s - %s" % (self.date_from, self.date_to)

    def _net_income_period(self):
        """Utilidad neta del periodo desde el Estado de Resultados."""
        er = lib.estado_resultados(
            self._trial(self.company_id, self.date_from, self.date_to)["rows"],
            tax_rate=self._get_corporate_rate(),
        )
        return er

    def build_statement(self):
        self.ensure_one()
        company = self.company_id
        period = self._period_label()

        # Cumulative balances (as of a date) for the balance sheet
        close_trial = self._trial(company, date_to=self.date_to)
        open_trial = self._trial(company, date_to=self.date_from)
        period_er = self._net_income_period()

        if self.statement == "balance":
            result = lib.balance_general(
                close_trial["rows"], period_label=period
            )
        elif self.statement == "resultados":
            result = period_er
            result["period_label"] = period
        elif self.statement == "flujo":
            result = lib.flujo_efectivo(
                open_trial["rows"],
                close_trial["rows"],
                net_income=period_er["utilidad_neta"],
                depreciation=self._depreciation_amount(
                    company, self.date_from, self.date_to
                ),
                period_label=period,
            )
        elif self.statement == "patrimonio":
            result = lib.cambios_patrimonio(
                open_trial["rows"],
                close_trial["rows"],
                net_income=period_er["utilidad_neta"],
                distributions=self._distribution_amount(
                    company, self.date_from, self.date_to
                ),
                period_label=period,
            )
        elif self.statement == "notas":
            result = {
                "period_label": period,
                "notes": lib.notas_financieras_stub(),
            }
        else:  # pragma: no cover - selection is closed
            raise UserError(_("Unknown statement: %s") % self.statement)

        result["statement"] = self.statement
        result["title"] = STATEMENT_TITLES.get(self.statement, "")
        return result

    def get_statement_data(self):
        """Called from the QWeb templates as ``o.get_statement_data()``."""
        return self.build_statement()

    def action_print(self):
        self.ensure_one()
        self.build_statement()  # validate early
        report_xmlid = {
            "balance": "l10n_ec_reports.action_report_estado_balance",
            "resultados": "l10n_ec_reports.action_report_estado_resultados",
            "flujo": "l10n_ec_reports.action_report_estado_flujo",
            "patrimonio": "l10n_ec_reports.action_report_estado_patrimonio",
            "notas": "l10n_ec_reports.action_report_estado_notas",
        }[self.statement]
        return self.env.ref(report_xmlid).report_action(self)
