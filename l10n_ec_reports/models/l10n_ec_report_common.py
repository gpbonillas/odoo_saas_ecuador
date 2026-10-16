# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Shared ORM -> plain-dict extraction helpers for every statutory book, form
and the ATS.  All *math* lives in ``l10n_ec_reports.report_lib`` (pure
python, unit tested standalone); this model only converts Odoo records into
the plain structures that library consumes.
"""

from odoo import models, api

from .. import report_lib as lib


class L10nEcReportCommon(models.AbstractModel):
    _name = "l10n.ec.report.common"
    _description = "Ecuador Reports - Shared Extraction Helpers"

    # ------------------------------------------------------------------
    # Config helpers (all values configurable, no invented numbers)
    # ------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default=None, cast=float):
        value = self.env["ir.config_parameter"].sudo().get_param(key)
        if value in (None, False, ""):
            return default
        try:
            return cast(value)
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------------
    # QWeb helpers (single formatting source shared with the exporters)
    # ------------------------------------------------------------------
    @api.model
    def fmt_cell(self, value):
        return lib.fmt_cell(value)

    @api.model
    def fmt_totals(self, totals, columns):
        return lib.fmt_totals(totals, columns)

    @api.model
    def _get_iva_rate(self):
        """General IVA rate (percent) -> fraction. Param l10n_ec.iva_rate."""
        rate = self._get_param("l10n_ec.iva_rate", default=None)
        if rate is None:
            return lib.DEFAULT_IVA_RATE
        return rate / 100.0

    @api.model
    def _get_corporate_rate(self):
        """Form 101 flat rate. KB_TAX_RATES_WITHHOLDINGS 4.1 = 25%."""
        rate = self._get_param("l10n_ec.form101.corporate_rate", default=None)
        if rate is None:
            return lib.DEFAULT_CORPORATE_RATE
        return rate / 100.0 if rate > 1 else rate

    @api.model
    def _get_sbu(self, year):
        config = False
        if "l10n_ec.config" in self.env:
            config = self.env["l10n_ec.config"].search(
                [("year", "=", year), ("active", "=", True)], limit=1
            )
        if config and config.sbu:
            return config.sbu
        return self._get_param("l10n_ec.sbu", default=0.0)

    @api.model
    def _get_gastos_caps(self):
        """Gastos personales caps in SMMLV per category.

        NOT stated in the in-repo docs -> fully configurable via
        ``l10n_ec.gastos_personales.cap.<category>_smmlv``. Missing param
        returns None (report shows the category as unlimited / unconfigured).
        """
        caps = {}
        for key, _label in lib.GASTOS_PERSONALES_CATEGORIES:
            caps[key] = self._get_param(
                lib.GASTOS_CAP_PARAM % key, default=None
            )
        return caps

    @api.model
    def _get_tax_brackets(self, year):
        """Progressive table: prefer l10n_ec.tax.table (l10n_ec_income_tax),
        fall back to the table embedded in report_lib (same resolution)."""
        if "l10n_ec.tax.table" in self.env:
            rows = self.env["l10n_ec.tax.table"].search(
                [("year", "=", year)], order="basic_fraction"
            )
            if rows:
                return [
                    {
                        "basic_fraction": r.basic_fraction,
                        "excess_until": r.excess_until,
                        "basic_tax": r.basic_tax,
                        "marginal_rate": r.marginal_rate,
                    }
                    for r in rows
                ]
        return lib.DEFAULT_TAX_BRACKETS_2026

    @api.model
    def _get_basket_cost(self, year):
        """Canasta basica cost for the Rebaja Tributaria."""
        if "l10n_ec.family.basket" in self.env:
            basket = self.env["l10n_ec.family.basket"].search(
                [("year", "=", year)], limit=1
            )
            if basket and basket.basket_cost:
                return basket.basket_cost
        if "l10n_ec.config" in self.env:
            config = self.env["l10n_ec.config"].search(
                [("year", "=", year), ("active", "=", True)], limit=1
            )
            if config and config.canasta_basica:
                return config.canasta_basica
        return self._get_param("l10n_ec.canasta_basica", default=0.0)

    # ------------------------------------------------------------------
    # Invoice extraction
    # ------------------------------------------------------------------
    @api.model
    def _retention_kind(self, line):
        """account.retention.line -> 'ir' | 'iva' | 'isd'.

        Note: tax_type uses SRI codes ('1','2','6') while tax_id.type uses
        labels ('renta','iva','isd') in the current data model - both are
        accepted here so the reports work with either shape.
        """
        code = str(line.tax_type or "")
        if code == "1":
            return "ir"
        if code == "2":
            return "iva"
        if code == "6":
            return "isd"
        label = str(getattr(line.tax_id, "type", "") or "")
        return {"renta": "ir", "iva": "iva", "isd": "isd"}.get(label, "ir")

    @api.model
    def _extract_retention_lines(self, retention, invoice=None):
        """Flatten one account.retention into report rows (one per line)."""
        invoice = invoice if invoice is not None else retention.invoice_id
        fecha_factura = ""
        comprobante = ""
        if invoice:
            fecha_factura = (
                invoice.invoice_date.strftime("%Y-%m-%d")
                if invoice.invoice_date
                else ""
            )
            comprobante = (
                invoice.l10n_latam_document_number or invoice.name or ""
            )
        rows = []
        for line in retention.retention_line_ids:
            rows.append(
                {
                    "kind": self._retention_kind(line),
                    "code": line.tax_code or "",
                    "name": line.tax_id.name or line.tax_code or "",
                    "base": line.base,
                    "percent": line.percentage,
                    "amount": line.amount,
                    "numero": retention.name or "",
                    "fecha": (
                        retention.date.strftime("%Y-%m-%d")
                        if retention.date
                        else ""
                    ),
                    "autorizacion": retention.l10n_ec_sri_access_key or "",
                    "partner": retention.partner_id.name or "",
                    "identificacion": retention.partner_id.vat or "",
                    "comprobante": comprobante,
                    "fecha_factura": fecha_factura,
                    "state": retention.state,
                }
            )
        return rows

    @api.model
    def _extract_invoice_row(self, inv):
        """account.move -> raw invoice dict for report_lib (see its docs)."""
        partner = inv.partner_id
        is_sale = inv.move_type.startswith("out")
        latam = inv.l10n_latam_document_type_id
        doc_code = latam.code if latam else "01"
        doc_name = latam.name if latam else ""

        clave = inv.l10n_ec_sri_access_key or ""
        estab, pto, sec = lib.split_document_number(
            inv.l10n_latam_document_number or inv.name or ""
        )

        if is_sale:
            tp_id = lib.TP_ID_CLIENT.get(
                partner.l10n_ec_identifier_type, "07"
            )
        else:
            tp_id = lib.TP_ID_PROV.get(partner.l10n_ec_identifier_type, "03")

        # --- invoice lines: base + tariff buckets -------------------------
        lines = []
        for line in inv.invoice_line_ids:
            rates = []
            no_objeto = False
            for tax in line.tax_ids:
                group_name = (tax.tax_group_id.name or "").upper()
                tax_name = (tax.name or "").upper()
                if "NO OBJETO" in group_name or "NO OBJETO" in tax_name:
                    no_objeto = True
                if tax.amount_type == "percent" and tax.amount >= 0:
                    rates.append(tax.amount)
            lines.append(
                {
                    "base": line.price_subtotal,
                    "rates": rates,
                    "no_objeto": no_objeto,
                }
            )

        # --- tax lines: IVA / ICE / withholdings --------------------------
        tax_lines = []
        for line in inv.line_ids:
            tax = line.tax_line_id
            if not tax:
                continue
            group_name = (
                tax.tax_group_id.name or tax.name or ""
            ).upper()
            is_ice = "ICE" in group_name or bool(
                getattr(tax, "l10n_ec_ice_category_id", False)
            )
            ret_kind = None
            if not is_ice and ("RETEN" in group_name or group_name.startswith("RET")):
                ret_kind = "iva" if "IVA" in group_name else "ir"
            tax_lines.append(
                {
                    "group": group_name,
                    "balance": abs(line.balance),
                    "ice": is_ice,
                    "ret_kind": ret_kind,
                }
            )

        # --- retentions linked to the invoice -----------------------------
        retentions = []
        if "account.retention" in self.env:
            retention_objs = self.env["account.retention"].search(
                [
                    ("invoice_id", "=", inv.id),
                    ("state", "=", "posted"),
                    ("company_id", "=", inv.company_id.id),
                ]
            )
            for retention in retention_objs:
                retentions.extend(self._extract_retention_lines(retention, inv))

        # --- flags --------------------------------------------------------
        country_code = partner.country_id.code or "EC"
        is_export = bool(is_sale and country_code != "EC") or bool(
            getattr(inv, "l10n_ec_is_export", False)
        )
        is_import = False
        if not is_sale and country_code != "EC":
            is_import = True
        if not is_sale and "l10n_ec.import.dau" in self.env:
            is_import = is_import or bool(
                self.env["l10n_ec.import.dau"]
                .search([("invoice_id", "=", inv.id)], limit=1)
            )

        return {
            "id": inv.id,
            "fecha": (
                inv.invoice_date.strftime("%Y-%m-%d")
                if inv.invoice_date
                else (inv.date.strftime("%Y-%m-%d") if inv.date else "")
            ),
            "fecha_registro": (
                inv.date.strftime("%Y-%m-%d") if inv.date else ""
            ),
            "doc_code": doc_code,
            "doc_name": doc_name,
            "move_type": inv.move_type,
            "tp_id": tp_id,
            "identificacion": partner.vat or "",
            "razon_social": partner.name or "",
            "clave_acceso": clave,
            "estab": estab,
            "pto": pto,
            "secuencial": sec,
            "autorizacion": clave,
            # no default here: an empty sustento must reach report_lib so
            # REQ-ATS-001 can flag it before the ATS is generated
            "sustento": inv.l10n_ec_sustento_code or "",
            "lines": lines,
            "tax_lines": tax_lines,
            "total": inv.amount_total,
            "state": inv.state,
            "is_export": is_export,
            "is_import": is_import,
            "emision_linea": bool(clave)
            or inv.l10n_ec_sri_status in ("sent", "authorized"),
            "forma_pago": getattr(inv, "l10n_ec_forma_pago", False) or "20",
            "retentions": retentions,
        }

    # ------------------------------------------------------------------
    # Invoice searches
    # ------------------------------------------------------------------
    @api.model
    def _search_invoices(self, date_from, date_to, move_types, company,
                         state="posted"):
        return self.env["account.move"].search(
            [
                ("move_type", "in", list(move_types)),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
                ("state", "=", state),
                ("company_id", "=", company.id),
            ],
            order="invoice_date, id",
        )

    @api.model
    def _sales_rows(self, date_from, date_to, company, state="posted"):
        moves = self._search_invoices(
            date_from, date_to, ("out_invoice", "out_refund"), company, state
        )
        return [self._extract_invoice_row(m) for m in moves]

    @api.model
    def _purchase_rows(self, date_from, date_to, company, state="posted"):
        moves = self._search_invoices(
            date_from, date_to, ("in_invoice", "in_refund"), company, state
        )
        return [self._extract_invoice_row(m) for m in moves]

    @api.model
    def _cancelled_rows(self, date_from, date_to, company):
        moves = self._search_invoices(
            date_from,
            date_to,
            ("out_invoice", "out_refund", "in_invoice", "in_refund"),
            company,
            state="cancel",
        )
        rows = []
        for move in moves:
            clave = move.l10n_ec_sri_access_key or ""
            rows.append(
                {
                    "doc_code": (
                        move.l10n_latam_document_type_id.code
                        if move.l10n_latam_document_type_id
                        else "01"
                    ),
                    "numero": move.l10n_latam_document_number or move.name or "",
                    "autorizacion": clave or "0",
                }
            )
        return rows

    @api.model
    def _retention_flat_rows(self, date_from, date_to, company):
        """Every retention issued by the company in the period."""
        if "account.retention" not in self.env:
            return []
        retentions = self.env["account.retention"].search(
            [
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("state", "=", "posted"),
                ("company_id", "=", company.id),
            ],
            order="date, id",
        )
        rows = []
        for retention in retentions:
            rows.extend(self._extract_retention_lines(retention))
        return rows

    # ------------------------------------------------------------------
    # Journal / trial balance extraction
    # ------------------------------------------------------------------
    @api.model
    def _line_domain(self, date_from=None, date_to=None, company=None,
                     accounts=None):
        domain = [("move_id.state", "=", "posted")]
        if company:
            domain.append(("company_id", "=", company.id))
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        if accounts is not None:
            domain.append(("account_id", "in", accounts.ids))
        return domain

    @api.model
    def _liquidity_accounts(self, company, journal_types=("bank", "cash")):
        journals = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "in", list(journal_types))]
        )
        return journals.mapped("default_account_id")

    @api.model
    def _book_journal_lines(self, date_from, date_to, company,
                            journal_types=("bank",), accounts=None):
        """Lines ON the liquidity accounts of the given journal types.

        This is what BCE (Libro de Bancos) and Caja require: every movement
        of the bank/cash account itself, not its counterparts.
        ``accounts`` overrides the journal-type lookup (wizard journal filter).
        """
        if accounts is None:
            accounts = self._liquidity_accounts(company, journal_types)
        if not accounts:
            return []
        lines = self.env["account.move.line"].search(
            self._line_domain(date_from, date_to, company, accounts),
            order="date, id",
        )
        return [
            {
                "fecha": line.date.strftime("%Y-%m-%d") if line.date else "",
                "documento": line.move_id.name or "",
                "cuenta": line.account_id.code or "",
                "partner": line.partner_id.name or "",
                "glosa": line.name or line.move_id.ref or "",
                "debit": line.debit,
                "credit": line.credit,
            }
            for line in lines
        ]

    @api.model
    def _opening_balances(self, company, date_from, accounts=None):
        """{account_code: debit-credit} for everything before date_from."""
        lines = self.env["account.move.line"].search(
            [
                ("move_id.state", "=", "posted"),
                ("company_id", "=", company.id),
                ("date", "<", date_from),
            ]
            + ([("account_id", "in", accounts.ids)] if accounts else [])
        )
        opening = {}
        for line in lines:
            code = line.account_id.code
            opening[code] = opening.get(code, 0.0) + line.debit - line.credit
        return {code: round(value, 2) for code, value in opening.items()}

    @api.model
    def _move_rows(self, date_from, date_to, company, accounts=None):
        """Moves (with lines) for the Libro Diario / Libro Mayor."""
        lines = self.env["account.move.line"].search(
            self._line_domain(date_from, date_to, company, accounts),
            order="date, id",
        )
        moves = {}
        order = []
        for line in lines:
            move = line.move_id
            if move.id not in moves:
                moves[move.id] = {
                    "name": move.name or "",
                    "date": move.date.strftime("%Y-%m-%d") if move.date else "",
                    "ref": move.ref or "",
                    "lines": [],
                }
                order.append(move.id)
            if getattr(line.account_id, "exclude_from_journal_entry", False):
                continue
            moves[move.id]["lines"].append(
                {
                    "account_code": line.account_id.code or "",
                    "account_name": line.account_id.name or "",
                    "label": line.name or "",
                    "debit": line.debit,
                    "credit": line.credit,
                }
            )
        return [moves[mid] for mid in order]

    @api.model
    def _trial_lines(self, company, date_from=None, date_to=None,
                     accounts=None):
        """Trial balance raw lines [{'code','name','account_type',
        'debit','credit'}]."""
        lines = self.env["account.move.line"].search(
            self._line_domain(date_from, date_to, company, accounts)
        )
        return [
            {
                "code": line.account_id.code or "",
                "name": line.account_id.name or "",
                "account_type": line.account_id.account_type or "",
                "debit": line.debit,
                "credit": line.credit,
            }
            for line in lines
        ]

    @api.model
    def _trial(self, company, date_from=None, date_to=None, accounts=None):
        return lib.trial_balance(
            self._trial_lines(company, date_from, date_to, accounts)
        )

    @api.model
    def _distribution_amount(self, company, date_from, date_to):
        """Net debit on retained-earnings style accounts = distributions.

        Heuristic over equity accounts (name/code) because no dedicated
        account mapping exists yet; overridable per company with the
        parameter ``l10n_ec.ef.distribution_accounts`` (comma codes).
        """
        codes_param = self.env["ir.config_parameter"].sudo().get_param(
            "l10n_ec.ef.distribution_accounts", ""
        )
        codes = [c.strip() for c in codes_param.split(",") if c.strip()]
        trial = self._trial(company, date_from, date_to)
        total = 0.0
        for row in trial["rows"]:
            if row.get("group") != "3":
                continue
            name = (row["name"] or "").upper()
            match_name = any(
                token in name
                for token in ("DIVIDEND", "DISTRIB", "RETENIDAS", "ACUMULADAS")
            )
            if row["code"] in codes or (not codes and match_name):
                # net debit movement during the period = distributions
                total += row["balance"]
        return round(max(total, 0.0), 2)

    @api.model
    def _depreciation_amount(self, company, date_from, date_to):
        """Non-cash charges proxy: debits on expense_depreciation accounts."""
        accounts = self.env["account.account"].search(
            [
                ("company_id", "=", company.id),
                ("account_type", "=", "expense_depreciation"),
            ]
        )
        if not accounts:
            return 0.0
        trial = self._trial(company, date_from, date_to, accounts=accounts)
        return round(trial["totals"]["debit"], 2)
