# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
SRI forms wizard with REAL calculations: 101, 102, 103, 104, 107, 108 and
Gastos Personales (GP).  Every number comes from report_lib (pure python,
unit-tested); this wizard only extracts ORM data and supplies configurable
parameters (rates, caps, brackets).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .. import report_lib as lib


FORM_SELECTIONS = [
    ("101", "Formulario 101 - Impuesto a la Renta (sociedades)"),
    ("102", "Formulario 102 - Impuesto a la Renta (personas naturales)"),
    ("103", "Formulario 103 - Retenciones en la fuente"),
    ("104", "Formulario 104 - IVA y ICE"),
    ("107", "Formulario 107 - Renta personas naturales"),
    ("108", "Formulario 108 - Notas de credito emitidas"),
    ("gp", "Gastos Personales - Deducciones y topes"),
]

FORM_TITLES = dict(FORM_SELECTIONS)


class L10nEcFormWizard(models.TransientModel):
    _name = "l10n_ec.form.wizard"
    _inherit = ["l10n.ec.report.common"]
    _description = "Formularios SRI (101/102/103/104/107/108/GP)"

    form = fields.Selection(FORM_SELECTIONS, required=True, default="104")
    date_from = fields.Date(
        required=True, default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    # --- editable fiscal inputs (annual forms) --------------------------
    pagos_previos = fields.Float("Pagos previos / anticipos")
    aportes_iess = fields.Float("Aportes personales IESS")
    retenciones_fuente = fields.Float(
        "Retenciones en la fuente (ingresos)",
        help="Si es 0 se calcula automaticamente desde las ventas del "
             "periodo seleccionado.",
    )

    # --- Form 107 income inputs ----------------------------------------
    ingreso_trabajo = fields.Float("Ingresos trabajo (relacion dependencia)")
    ingreso_tercera = fields.Float("Ingresos tercera categoria")
    ingreso_cuarta = fields.Float("Ingresos cuarta categoria")
    ingreso_capital = fields.Float("Ingresos de capital")
    ingreso_otros = fields.Float("Otros ingresos")

    # --- Gastos personales ---------------------------------------------
    g_vivienda = fields.Float("Vivienda")
    g_salud = fields.Float("Salud")
    g_educacion = fields.Float("Educacion, arte y cultura")
    g_alimentacion = fields.Float("Alimentacion")
    g_vestimenta = fields.Float("Vestimenta y calzado")
    g_turismo = fields.Float("Turismo nacional")
    cargas_familiares = fields.Integer("Cargas familiares")
    enfermedad_catastrofica = fields.Boolean("Enfermedad catastrofica")

    # ==================================================================
    # COMPUTATION - all math delegated to report_lib
    # ==================================================================
    @api.model
    def _year(self, date_value):
        return (date_value or fields.Date.context_today(self)).year

    def _gastos_map(self):
        return {
            "vivienda": self.g_vivienda,
            "salud": self.g_salud,
            "educacion": self.g_educacion,
            "alimentacion": self.g_alimentacion,
            "vestimenta": self.g_vestimenta,
            "turismo": self.g_turismo,
        }

    def _gastos_result(self):
        return lib.gastos_personales_calculate(
            self._gastos_map(),
            self._get_gastos_caps(),
            self._get_sbu(self._year(self.date_to)),
        )

    def _retenciones_on_sales(self):
        """IR withheld from us by customers on our sales in the period."""
        rows = self._sales_rows(self.date_from, self.date_to, self.company_id)
        normalized = [lib.invoice_report_row(r) for r in rows]
        return round(sum(r["ret_ir"] for r in normalized), 2)

    def _build_data(self):
        self.ensure_one()
        date_from, date_to, company = self.date_from, self.date_to, self.company_id
        year = self._year(date_to)
        period = "%s - %s" % (date_from, date_to)

        if self.form == "104":
            result = lib.form104_calculate(
                self._sales_rows(date_from, date_to, company),
                self._purchase_rows(date_from, date_to, company),
                iva_rate=self._get_iva_rate(),
            )
        elif self.form == "101":
            er = lib.estado_resultados(
                self._trial(company, date_from, date_to)["rows"],
                tax_rate=self._get_corporate_rate(),
            )
            retenciones = self.retenciones_fuente or self._retenciones_on_sales()
            result = lib.form101_calculate(
                {
                    "ingresos_gravados": er["total_ingresos"],
                    "costos_ventas": er["total_costos"],
                    "gastos_operacionales": er["total_gastos"],
                    "retenciones": retenciones,
                    "pagos_previos": self.pagos_previos,
                },
                corporate_rate=self._get_corporate_rate(),
            )
        elif self.form == "102":
            er = lib.estado_resultados(
                self._trial(company, date_from, date_to)["rows"],
                tax_rate=self._get_corporate_rate(),
            )
            retenciones = self.retenciones_fuente or self._retenciones_on_sales()
            result = lib.form102_calculate(
                {
                    "ingresos_gravados": er["total_ingresos"],
                    "costos_ventas": er["total_costos"],
                    "gastos_operacionales": er["total_gastos"],
                    "aportes_iess": self.aportes_iess,
                    "retenciones": retenciones,
                    "pagos_previos": self.pagos_previos,
                },
                brackets=self._get_tax_brackets(year),
            )
        elif self.form == "103":
            rows = self._retention_flat_rows(date_from, date_to, company)
            result = lib.form103_calculate(rows)
            result["columns"] = [
                ("code", "Codigo"),
                ("label", "Concepto (casillero)"),
                ("base", "Base imponible"),
                ("percent", "Tarifa %"),
                ("amount", "Valor retenido"),
            ]
            result["rows"] = result["rows"]
            result["totals"] = {
                "base": result["total_base"],
                "amount": result["total_amount"],
                "percent": 0.0,
            }
        elif self.form == "107":
            gastos = self._gastos_result()
            rebaja = {
                "expenses": gastos["total_spent"],
                "n_baskets": lib.n_baskets_for_loads(
                    self.cargas_familiares, self.enfermedad_catastrofica
                ),
                "basket_cost": self._get_basket_cost(year),
            }
            result = lib.form107_calculate(
                {
                    "ingresos": {
                        "trabajo": self.ingreso_trabajo,
                        "tercera": self.ingreso_tercera,
                        "cuarta": self.ingreso_cuarta,
                        "capital": self.ingreso_capital,
                        "otros": self.ingreso_otros,
                    },
                    "aportes_iess": self.aportes_iess,
                    "gastos_personales": gastos["total_deducible"],
                    "retenciones": self.retenciones_fuente,
                    "pagos_previos": self.pagos_previos,
                    "rebaja": rebaja if rebaja["basket_cost"] else None,
                },
                brackets=self._get_tax_brackets(year),
            )
        elif self.form == "108":
            rows = self._sales_rows(
                date_from, date_to, company, state="posted"
            )
            credit_notes = [
                r for r in rows if r["move_type"] == "out_refund"
            ]
            result = lib.form108_calculate(credit_notes)
            result["columns"] = [
                ("fecha", "Fecha"),
                ("identificacion", "Identificacion"),
                ("razon_social", "Cliente"),
                ("doc_code", "codDoc"),
                ("clave_acceso", "Clave de acceso"),
                ("total", "Valor NC"),
            ]
            result["totals"] = {"total": result["total"]}
        elif self.form == "gp":
            result = self._gastos_result()
            result["columns"] = [
                ("label", "Categoria"),
                ("spent", "Gasto proyectado"),
                ("cap_smmlv", "Tope (SMMLV)"),
                ("cap_usd", "Tope USD"),
                ("deducible", "Deducible"),
            ]
            result["totals"] = {
                "spent": result["total_spent"],
                "deducible": result["total_deducible"],
            }
        else:  # pragma: no cover - selection is closed
            raise UserError(_("Unknown form: %s") % self.form)

        result["form"] = self.form
        result["title"] = FORM_TITLES.get(self.form, self.form)
        result["period"] = period
        return result

    def get_form_data(self):
        """Called from the QWeb templates as ``o.get_form_data()``."""
        return self._build_data()

    def action_print(self):
        self.ensure_one()
        data = self._build_data()  # fail early on bad config
        report_xmlid = {
            "101": "l10n_ec_reports.action_report_form_101",
            "102": "l10n_ec_reports.action_report_form_102",
            "103": "l10n_ec_reports.action_report_form_103",
            "104": "l10n_ec_reports.action_report_form_104",
            "107": "l10n_ec_reports.action_report_form_107",
            "108": "l10n_ec_reports.action_report_form_108",
            "gp": "l10n_ec_reports.action_report_form_gastos_personales",
        }[self.form]
        if self.form == "gp" and data.get("unconfigured"):
            # not an error: report clearly flags the missing caps
            pass
        return self.env.ref(report_xmlid).report_action(self)
