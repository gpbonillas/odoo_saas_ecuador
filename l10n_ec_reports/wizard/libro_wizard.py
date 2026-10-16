# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Generic statutory-books wizard: Ventas, Compras, Retenciones, Bancos (BCE),
Caja, Diario, Mayor, Inventarios y Balances.

XLSX / CSV export for every book + QWeb PDF for all of them (a single
parameterized template renders rows/columns/totals produced by report_lib).
"""

import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .. import report_lib as lib


class L10nEcLibroWizard(models.TransientModel):
    _name = "l10n_ec.libro.wizard"
    _inherit = ["l10n.ec.report.common"]
    _description = "Libros Contables Ecuador (SRI / NEC / BCE)"

    BOOK_TYPES = [
        ("ventas", "Libro de Ventas"),
        ("compras", "Libro de Compras"),
        ("retenciones", "Libro de Retenciones"),
        ("bancos", "Libro de Bancos (BCE)"),
        ("caja", "Libro de Caja"),
        ("diario", "Libro Diario"),
        ("mayor", "Libro Mayor"),
        ("inventarios", "Libro de Inventarios y Balances"),
    ]

    book_type = fields.Selection(BOOK_TYPES, required=True, default="ventas")
    date_from = fields.Date(
        required=True, default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(
        required=True, default=lambda self: fields.Date.today()
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    journal_ids = fields.Many2many(
        "account.journal",
        string="Cuentas de banco/caja",
        help="Filtro opcional: solo estas cuentas (Libro de Bancos / Caja).",
    )

    xlsx_data = fields.Binary("XLSX", readonly=True)
    xlsx_filename = fields.Char(readonly=True)
    csv_data = fields.Binary("CSV", readonly=True)
    csv_filename = fields.Char(readonly=True)

    # ------------------------------------------------------------------
    # Data building (delegates ALL math to report_lib)
    # ------------------------------------------------------------------
    @api.onchange("date_from", "date_to")
    def _check_period(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise UserError(_("The start date cannot be after the end date."))

    @api.model
    def _book_title(self, book_type):
        return dict(self.BOOK_TYPES).get(book_type, _("Libro"))

    def _selected_accounts(self, journal_types):
        if self.journal_ids:
            accounts = self.journal_ids.mapped("default_account_id")
            if not accounts:
                raise UserError(
                    _(
                        "The selected journals have no default liquidity "
                        "account. Configure them first."
                    )
                )
            return accounts
        return self._liquidity_accounts(self.company_id, journal_types)

    def _opening_for(self, accounts):
        opening = self._opening_balances(
            self.company_id, self.date_from, accounts=accounts
        )
        return round(sum(opening.values()), 2)

    def get_book_payload(self):
        """Return {'title','columns','rows','totals'} for the PDF template,
        the XLSX writer and the CSV writer alike."""
        self.ensure_one()
        date_from, date_to = self.date_from, self.date_to
        company = self.company_id
        book = self.book_type

        if book == "ventas":
            payload = lib.libro_ventas_rows(
                self._sales_rows(date_from, date_to, company)
            )
        elif book == "compras":
            payload = lib.libro_compras_rows(
                self._purchase_rows(date_from, date_to, company)
            )
        elif book == "retenciones":
            payload = lib.libro_retenciones_rows(
                self._retention_flat_rows(date_from, date_to, company)
            )
        elif book in ("bancos", "caja"):
            journal_types = ("bank",) if book == "bancos" else ("cash",)
            accounts = self._selected_accounts(journal_types)
            lines = self._book_journal_lines(
                date_from, date_to, company,
                journal_types=journal_types, accounts=accounts,
            )
            payload = lib.libro_bancos_rows(
                lines, opening=self._opening_for(accounts)
            )
        elif book == "diario":
            payload = lib.libro_diario_rows(
                self._move_rows(date_from, date_to, company)
            )
        elif book == "mayor":
            openings = self._opening_balances(company, date_from)
            payload = lib.libro_mayor_rows(
                self._move_rows(date_from, date_to, company),
                openings=openings,
            )
            # flatten account blocks into rows for the generic renderer
            flat = []
            for account in payload["accounts"]:
                flat.extend(account["rows"])
            payload = {
                "columns": lib.COLS_MAYOR,
                "rows": flat,
                "totals": payload["totals"],
                "accounts": payload["accounts"],
            }
        elif book == "inventarios":
            trial = self._trial(company, date_to=date_to)
            payload = lib.inventarios_balances(
                trial, self._valuation_lines(date_to)
            )
            payload["columns"] = [
                ("group_label", "Grupo NEC"),
                ("code", "Cuenta"),
                ("name", "Nombre"),
                ("debit", "Debe"),
                ("credit", "Haber"),
                ("balance", "Saldo"),
            ]
            rows = []
            for group in payload["groups"]:
                for row in group["rows"]:
                    rows.append(
                        {
                            "group_label": "%s %s" % (
                                group["group"], group["label"]),
                            "code": row["code"],
                            "name": row["name"],
                            "debit": row["debit"],
                            "credit": row["credit"],
                            "balance": row["balance"],
                        }
                    )
            payload = {
                "columns": payload["columns"],
                "rows": rows,
                "totals": payload["totals"],
                "groups": payload["groups"],
                "valuation": payload["valuation"],
                "valuation_total": payload["valuation_total"],
            }
        else:  # pragma: no cover - selection is closed
            raise UserError(_("Unknown book type: %s") % book)

        payload["title"] = self._book_title(book)
        payload["period"] = "%s - %s" % (date_from, date_to)
        payload.setdefault("totals", {"count": len(payload.get("rows", []))})
        return payload

    @api.model
    def _valuation_lines(self, date_to):
        """Inventory valuation from stock.valuation.layer when stock is
        installed (guarded: l10n_ec_reports does not depend on stock)."""
        if "stock.valuation.layer" not in self.env:
            return []
        layers = self.env["stock.valuation.layer"].search(
            [("date", "<=", date_to)]
        )
        grouped = {}
        for layer in layers:
            product = layer.product_id
            entry = grouped.setdefault(
                product.id,
                {"name": product.display_name, "quantity": 0.0,
                 "value": 0.0},
            )
            entry["quantity"] += layer.quantity
            entry["value"] += layer.value
        return [
            {
                "name": entry["name"],
                "quantity": entry["quantity"],
                "unit_cost": (
                    entry["value"] / entry["quantity"]
                    if entry["quantity"]
                    else 0.0
                ),
                "value": entry["value"],
            }
            for entry in grouped.values()
        ]

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------
    def action_export_xlsx(self):
        self.ensure_one()
        payload = self.get_book_payload()
        content = lib.write_xlsx(
            payload.get("rows", []),
            payload.get("columns", []),
            sheet_name=self.book_type[:31],
            totals=payload.get("totals"),
        )
        self.xlsx_data = base64.b64encode(content)
        self.xlsx_filename = "%s_%s_%s.xlsx" % (
            self.book_type, self.date_from, self.date_to
        )
        return self._reopen()

    def action_export_csv(self):
        self.ensure_one()
        payload = self.get_book_payload()
        content = lib.write_csv(
            payload.get("rows", []),
            payload.get("columns", []),
            totals=payload.get("totals"),
        )
        self.csv_data = base64.b64encode(content.encode("utf-8"))
        self.csv_filename = "%s_%s_%s.csv" % (
            self.book_type, self.date_from, self.date_to
        )
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    # ------------------------------------------------------------------
    # PDF (single generic template bound to this wizard)
    # ------------------------------------------------------------------
    def action_print(self):
        self.ensure_one()
        payload = self.get_book_payload()  # validate before rendering
        if not payload.get("rows"):
            raise UserError(
                _("No data for '%(title)s' in the selected period.")
                % {"title": payload["title"]}
            )
        return self.env.ref(
            "l10n_ec_reports.action_report_libro"
        ).report_action(self)

    # ------------------------------------------------------------------
    # API for the QWeb template (called as o.get_book_payload())
    # ------------------------------------------------------------------
    def get_print_data(self):
        return self.get_book_payload()
