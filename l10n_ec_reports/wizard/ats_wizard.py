# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
ATS (Anexo Transaccional Simplificado) wizard - SRI monthly return.

Structure generated (per SRS_MODULE_09_L10N_EC_REPORTS.md section 3.1):
  compras (+air, retenciones IVA, pagoExterior, formasDePago),
  ventas, ventasEstablecimiento, anulados, exportaciones, retenciones.

Validation REQ-ATS-001 runs before generation; errors are shown in the
wizard and generation can be forced explicitly.
"""

import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .. import report_lib as lib


class L10nEcAtsWizard(models.TransientModel):
    _name = "l10n_ec.ats.wizard"
    _inherit = ["l10n.ec.report.common"]
    _description = "Anexo Transaccional Simplificado (ATS) Wizard"

    date_month = fields.Selection(
        [
            ("01", "January"), ("02", "February"), ("03", "March"),
            ("04", "April"), ("05", "May"), ("06", "June"),
            ("07", "July"), ("08", "August"), ("09", "September"),
            ("10", "October"), ("11", "November"), ("12", "December"),
        ],
        string="Month",
        required=True,
        default=lambda self: fields.Date.context_today(self).strftime("%m"),
    )
    date_year = fields.Char(
        string="Year",
        required=True,
        default=lambda self: fields.Date.context_today(self).strftime("%Y"),
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    validation_errors = fields.Text("Validaciones (REQ-ATS-001)", readonly=True)
    allow_warnings = fields.Boolean(
        string="Generar igualmente",
        help="Permite generar el XML aun con advertencias de validacion.",
    )

    # Result
    xml_data = fields.Binary("ATS XML", readonly=True)
    xml_filename = fields.Char(string="Filename", readonly=True)

    # ------------------------------------------------------------------
    def _period(self):
        try:
            date_start, date_end = lib.month_bounds(
                int(self.date_year), int(self.date_month)
            )
        except (ValueError, TypeError):
            raise UserError(_("Invalid year/month configuration"))
        from datetime import timedelta as _td

        # month_bounds returns an exclusive end; make it inclusive
        return date_start, date_end - _td(days=1)

    @api.model
    def _num_estab(self, company):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.num_estab_ruc", "001")
            or "001"
        )

    def _ats_payload(self):
        """Full ATS structure via report_lib (pure python, tested)."""
        self.ensure_one()
        date_start, date_end = self._period()
        company = self.company_id

        ventas_rows = [
            lib.invoice_report_row(r)
            for r in self._sales_rows(date_start, date_end, company)
        ]
        compras_rows = [
            lib.invoice_report_row(r)
            for r in self._purchase_rows(date_start, date_end, company)
        ]
        export_rows = [r for r in ventas_rows if r["is_export"]]
        retentions = self._retention_flat_rows(date_start, date_end, company)
        cancelled = self._cancelled_rows(date_start, date_end, company)

        header = {
            "year": self.date_year,
            "month": self.date_month,
            "entity": self._num_estab(company),
            "company_name": company.name or "",
            "vat": company.vat or "",
        }
        return lib.ats_build(
            header, ventas_rows, compras_rows, cancelled, retentions,
            export_rows,
        )

    def action_validate(self):
        """Run REQ-ATS-001 validations without generating."""
        self.ensure_one()
        payload = self._ats_payload()
        self.validation_errors = "\n".join(payload["errors"]) or _(
            "OK - no validation errors."
        )
        return self._reopen()

    def action_generate_ats(self):
        self.ensure_one()
        payload = self._ats_payload()
        self.validation_errors = "\n".join(payload["errors"])
        if payload["errors"] and not self.allow_warnings:
            return self._reopen()

        xml_content = self._render_xml(payload)
        self.xml_data = base64.b64encode(xml_content)
        self.xml_filename = "ATS_%s_%s_%s.xml" % (
            self.date_month, self.date_year, company_vat(self.company_id)
        )
        return self._reopen()

    def _render_xml(self, payload):
        values = {
            "wizard": self,
            "company": self.company_id,
            "header": payload["header"],
            "compras": payload["compras"],
            "ventas": payload["ventas"],
            "ventas_establecimiento": payload["ventas_establecimiento"],
            "anulados": payload["anulados"],
            "exportaciones": payload["exportaciones"],
            "retenciones": payload["retenciones"],
            "total_ventas": payload["total_ventas"],
            "format_float": lambda value, precision=2: (
                "%." + str(int(precision)) + "f"
            ) % float(value or 0.0),
        }
        xml_body = self.env["ir.qweb"]._render(
            "l10n_ec_reports.l10n_ec_ats_xml", values
        )
        if isinstance(xml_body, bytes):
            xml_body = xml_body.decode("utf-8")
        # SRI expects an XML declaration before the <iva> root
        xml_body = xml_body.lstrip()
        if not xml_body.startswith("<?xml"):
            xml_body = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body
        return xml_body.encode("utf-8")

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Form shortcuts (delegate to the real forms wizard)
    # ------------------------------------------------------------------
    def _print_form(self, form_code):
        self.ensure_one()
        date_start, date_end = self._period()
        wizard = self.env["l10n_ec.form.wizard"].create(
            {
                "form": form_code,
                "date_from": date_start,
                "date_to": date_end,
                "company_id": self.company_id.id,
            }
        )
        return wizard.action_print()

    def action_print_form103(self):
        return self._print_form("103")

    def action_print_form104(self):
        return self._print_form("104")


def company_vat(company):
    return company.vat or "NA"
