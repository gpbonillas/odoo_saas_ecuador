# -*- coding: utf-8 -*-
"""
Libro de Bancos — reusable data helpers.

SCOPE NOTE: the Libro de Bancos *report* (BCE format rendering, PDF/XLSX
export) is Agent D's scope (`l10n_ec_reports`). This module only exposes
the data layer a report can reuse, so both the report and any future
wizard/MCP tool get the same numbers:

  * `l10n_ec_get_bank_journals()`       -> every bank/cash journal
  * `l10n_ec_get_account_balance()`     -> debit/credit/balance of any account
  * `l10n_ec_get_journal_statement_rows()` -> per-bank "statement" rows with
    running balance (date, documento, concepto, ingreso, egreso, saldo)
  * `l10n_ec_get_bank_book_rows()`      -> all journals at once + totals

All amounts are company-currency, restricted to posted entries.
"""
from odoo import fields, models, api


class L10nEcBankBookHelper(models.AbstractModel):
    _name = "l10n_ec.bank.book.helper"
    _description = "Libro de Bancos Data Helpers (BCE)"

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------
    def l10n_ec_get_bank_journals(self, company=None):
        """Return the bank/cash journals of `company` (default: current)."""
        company = company or self.env.company
        return self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "in", ("bank", "cash"))],
            order="name",
        )

    def _l10n_ec_move_line_domain(self, account=None, journal=None, date_from=None, date_to=None, extra=None):
        domain = [("parent_state", "=", "posted")]
        if account:
            domain.append(("account_id", "=", account.id))
        if journal:
            domain.append(("journal_id", "=", journal.id))
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        return domain + (extra or [])

    # ------------------------------------------------------------------
    # Public API (documented, report-reusable)
    # ------------------------------------------------------------------
    def l10n_ec_get_account_balance(self, account, date_from=None, date_to=None):
        """
        Debit / credit / balance of one account (optionally period-bounded).

        :param account: account.account record
        :return: dict {debit, credit, balance, line_count}
        """
        lines = self.env["account.move.line"].search(
            self._l10n_ec_move_line_domain(account=account, date_from=date_from, date_to=date_to)
        )
        debit = sum(lines.mapped("debit"))
        credit = sum(lines.mapped("credit"))
        return {
            "debit": debit,
            "credit": credit,
            "balance": debit - credit,
            "line_count": len(lines),
        }

    def l10n_ec_get_journal_statement_rows(self, journal, date_from=None, date_to=None):
        """
        "Statement" rows of ONE bank journal, ordered by (date, id), with a
        running balance. This is the row set a Libro de Bancos page renders.

        :return: list of dicts {
            date, move_name, ref, partner, concept, account_code,
            debit (ingreso), credit (egreso), balance (saldo),
        }
        """
        lines = self.env["account.move.line"].search(
            self._l10n_ec_move_line_domain(journal=journal, date_from=date_from, date_to=date_to),
            order="date, id",
        )
        rows = []
        running = 0.0
        for line in lines:
            running += line.debit - line.credit
            rows.append(
                {
                    "date": line.date,
                    "journal": journal.display_name,
                    "move_name": line.move_id.display_name,
                    "ref": line.ref or line.move_id.ref or "",
                    "partner": line.partner_id.display_name or "",
                    "concept": line.payment_ref or line.name or "",
                    "account_code": line.account_id.code,
                    "debit": line.debit,
                    "credit": line.credit,
                    "balance": running,
                }
            )
        return rows

    def l10n_ec_get_bank_book_rows(self, date_from=None, date_to=None, company=None):
        """
        Full Libro de Bancos dataset for `company` in one call.

        :return: dict {
            journals: [ {journal, currency, opening_balance, rows,
                          closing_balance} ... ],
            totals: {debit, credit, balance},
        }
        """
        company = company or self.env.company
        journals_data = []
        totals = {"debit": 0.0, "credit": 0.0, "balance": 0.0}
        for journal in self.l10n_ec_get_bank_journals(company):
            # Opening balance: everything posted before date_from
            opening = 0.0
            if date_from:
                opening_lines = self.env["account.move.line"].search(
                    self._l10n_ec_move_line_domain(
                        journal=journal, date_to=date_from
                    ) + [("date", "<", date_from)]
                )
                opening = sum(opening_lines.mapped("debit")) - sum(
                    opening_lines.mapped("credit")
                )
            rows = self.l10n_ec_get_journal_statement_rows(
                journal, date_from=date_from, date_to=date_to
            )
            closing = opening + (rows[-1]["balance"] if rows else 0.0)
            journals_data.append(
                {
                    "journal": journal,
                    "currency": journal.company_id.currency_id.name,
                    "opening_balance": opening,
                    "rows": rows,
                    "closing_balance": closing,
                }
            )
            totals["debit"] += sum(r["debit"] for r in rows)
            totals["credit"] += sum(r["credit"] for r in rows)
        totals["balance"] = totals["debit"] - totals["credit"]
        return {"journals": journals_data, "totals": totals}
