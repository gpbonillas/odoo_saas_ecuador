# -*- coding: utf-8 -*-
"""
Declaración Aduanera Única de Importación (DAU/DUI) — SENAE.

Legal basis:
- COPCI Art. 108-190: DAU requirements
- LORTI Art. 75: ISD (Impuesto a la Salida de Divisas)
- Arancel de Gravámenes: Ad Valorem 0-40% by tariff heading
- FODINFA: 0.5% on CIF (Fondo de Desarrollo e Infraestructura)
- IVA a la importación: 15% sobre (CIF + arancel + FODINFA)

Taxes are:
  1. computed on the DAU (this model, `action_calculate`), and
  2. materialized as REAL per-company `account.tax` definitions + a real
     journal entry on the import journal via `action_post`
     (`_l10n_ec_ensure_import_taxes` / `_l10n_ec_post_import_entry`).

ECUAPASS linkage: declaration fields + stub service (see
models/l10n_ec_ecuapass.py) — the external SENAE integration itself is
NOT implemented.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class L10nEcImportDau(models.Model):
    _name = "l10n_ec.import.dau"
    _description = "Declaración Aduanera Única (Import)"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("DAU Number", required=True, tracking=True)
    date = fields.Date("Declaration Date", default=fields.Date.context_today)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one("res.partner", string="Customs Broker/Supplier")

    picking_id = fields.Many2one("stock.picking", string="Related Receipt")
    invoice_id = fields.Many2one("account.move", string="Commercial Invoice")

    # Values
    fob_value = fields.Float(
        "FOB Value", compute="_compute_fob_total", store=True, tracking=True
    )
    freight = fields.Float("Freight")
    insurance = fields.Float("Insurance")
    cif_value = fields.Float("CIF Value", compute="_compute_cif", store=True)

    # Taxes (computed on the declaration)
    total_ad_valorem = fields.Float(
        "Total Ad Valorem", compute="_compute_taxes", store=True
    )
    total_fodinfa = fields.Float("Total FODINFA", compute="_compute_taxes", store=True)
    total_iva = fields.Float(
        "Total IVA Importación", compute="_compute_taxes", store=True
    )

    # ISD - LORTI Art. 75
    isd_applicable = fields.Boolean(
        string="ISD Aplicable",
        default=True,
        help="LORTI Art. 75: 5% standard, 2.5% monetary remittances, 0% exempt goods",
    )
    isd_rate = fields.Selection(
        [
            ("0.05", "5% - Standard"),
            ("0.025", "2.5% - Monetary remittances"),
            ("0", "0% - Exempt (goods, study abroad, health)"),
        ],
        string="ISD Rate",
        default="0.05",
    )
    isd_exemption_reason = fields.Text(
        string="ISD Exemption Reason", help="If 0%, document the legal exemption reason"
    )
    total_isd = fields.Float(
        "Total ISD",
        compute="_compute_isd",
        store=True,
        help="LORTI Art. 75: applied to the payment value sent abroad "
        "(CIF + duties + taxes).",
    )

    # Accounting (import journal entry)
    journal_id = fields.Many2one(
        "account.journal",
        string="Import Journal",
        domain=[("type", "=", "general")],
        help="Journal for the customs entry; a 'Importaciones' general "
        "journal is created if not set.",
    )
    move_id = fields.Many2one(
        "account.move", string="Customs Journal Entry", readonly=True, copy=False
    )

    # ECUAPASS linkage (integration is a STUB — see l10n_ec_ecuapass.py)
    ecuapass_dui_number = fields.Char(
        "DUI Number (ECUAPASS)", copy=False,
        help="Declaración Única de Importación number as registered in ECUAPASS.",
    )
    ecuapass_folio = fields.Char("ECUAPASS Folio", copy=False)
    ecuapass_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("submitted", "Submitted"),
            ("in_transit", "In Transit"),
            ("cleared", "Cleared (Levante)"),
            ("rejected", "Rejected"),
        ],
        string="ECUAPASS State",
        default="pending",
        copy=False,
    )
    ecuapass_last_check = fields.Datetime("Last ECUAPASS Check", copy=False, readonly=True)
    ecuapass_response = fields.Text("ECUAPASS Response", copy=False, readonly=True)

    state = fields.Selection(
        [("draft", "Draft"), ("calculated", "Calculated"), ("done", "Done")],
        default="draft",
        tracking=True,
    )

    line_ids = fields.One2many("l10n_ec.import.dau.line", "dau_id", string="Lines")

    # ------------------------------------------------------------------
    # Computations
    # ------------------------------------------------------------------
    @api.depends("line_ids.valor_fob_line")
    def _compute_fob_total(self):
        for rec in self:
            rec.fob_value = sum(line.valor_fob_line for line in rec.line_ids)

    @api.depends("fob_value", "freight", "insurance")
    def _compute_cif(self):
        for rec in self:
            rec.cif_value = rec.fob_value + rec.freight + rec.insurance

    @api.depends("line_ids.ad_valorem_amount", "line_ids.cif_line", "cif_value")
    def _compute_taxes(self):
        ICP = self.env["ir.config_parameter"].sudo()

        # Get rates from config - NO HARDCODED FALLBACKS
        fodinfa_param = ICP.get_param("l10n_ec.fodinfa")
        iva_param = ICP.get_param("l10n_ec.customs_iva")

        if not fodinfa_param or not iva_param:
            raise UserError(
                _(
                    "Missing customs configuration. Please configure the "
                    "system parameters 'l10n_ec.fodinfa' and "
                    "'l10n_ec.customs_iva' (Settings > Parameters)."
                )
            )

        default_fodinfa_rate = float(fodinfa_param)
        iva_rate = float(iva_param)

        for rec in self:
            rec.total_ad_valorem = sum(line.ad_valorem_amount for line in rec.line_ids)
            # FODINFA: per-heading override (l10n_ec.tariff.heading.fodinfa)
            # when the line points to a tariff heading, else the global
            # l10n_ec.fodinfa parameter. Summed per line so a mix of headings
            # (and a legitimate 0% heading) is handled correctly.
            if rec.line_ids:
                rec.total_fodinfa = sum(
                    line.cif_line
                    * (
                        (line.tariff_id.fodinfa / 100.0)
                        if line.tariff_id
                        else default_fodinfa_rate
                    )
                    for line in rec.line_ids
                )
            else:
                rec.total_fodinfa = rec.cif_value * default_fodinfa_rate

            # IVA Base = CIF + AdValorem + Fodinfa (SENAE import IVA rule)
            base_iva = rec.cif_value + rec.total_ad_valorem + rec.total_fodinfa
            rec.total_iva = base_iva * iva_rate

    @api.depends(
        "cif_value",
        "total_ad_valorem",
        "total_fodinfa",
        "total_iva",
        "isd_applicable",
        "isd_rate",
    )
    def _compute_isd(self):
        """
        ISD — LORTI Art. 75.

        Base = total payment value sent abroad = CIF + duties + taxes
        (IVA importación included).
        Rates: 5% standard / 2.5% monetary remittances / 0% exempt.
        """
        for rec in self:
            if not rec.isd_applicable or not rec.isd_rate:
                rec.total_isd = 0.0
                continue
            isd_base = (
                rec.cif_value
                + rec.total_ad_valorem
                + rec.total_fodinfa
                + rec.total_iva
            )
            rec.total_isd = isd_base * float(rec.isd_rate)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_calculate(self):
        for rec in self:
            rec._compute_cif()
            rec._compute_taxes()
            rec._compute_isd()
        self.write({"state": "calculated"})

    def action_check_ecuapass(self):
        """
        Query ECUAPASS for the declaration status.

        STUB: the SENAE client is not implemented (see
        models/l10n_ec_ecuapass.py); the button stores a clear
        "integration pending" note instead of crashing.
        """
        service = self.env["l10n_ec.ecuapass.service"]
        for rec in self:
            try:
                result = service.get_declaration_status(rec)
            except NotImplementedError as err:
                rec.write(
                    {
                        "ecuapass_last_check": fields.Datetime.now(),
                        "ecuapass_response": "%s" % err,
                    }
                )
                _logger.info("ECUAPASS stub called for DAU %s", rec.name)
                continue
            rec.write(
                {
                    "ecuapass_state": result.get("state", rec.ecuapass_state),
                    "ecuapass_dui_number": result.get("dui_number")
                    or rec.ecuapass_dui_number,
                    "ecuapass_folio": result.get("folio") or rec.ecuapass_folio,
                    "ecuapass_last_check": fields.Datetime.now(),
                    "ecuapass_response": str(result.get("raw_response", "")),
                }
            )
        return True

    # ------------------------------------------------------------------
    # Real tax definitions + import journal entry
    # ------------------------------------------------------------------
    def _l10n_ec_ensure_import_taxes(self):
        """
        Find or create the REAL per-company purchase-tax definitions for
        the three import duties, so they exist in the CoA and can be
        referenced from the ATS/books:

          * "Ad Valorem Aduana"     — amount set per declaration (0-40%)
          * "FODINFA 0.5% (Aduana)" — from l10n_ec.fodinfa parameter
          * "IVA Importación 15% (Aduana)" — from l10n_ec.customs_iva

        :return: dict {'ad_valorem': tax, 'fodinfa': tax, 'iva': tax}
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        fodinfa_rate = float(ICP.get_param("l10n_ec.fodinfa", "0.005")) * 100.0
        iva_rate = float(ICP.get_param("l10n_ec.customs_iva", "0.15")) * 100.0

        specs = {
            "ad_valorem": {
                "name": _("Ad Valorem Aduana (0-40%)"),
                "amount": 0.0,  # varies per tariff heading/declaration
            },
            "fodinfa": {
                "name": "FODINFA %.2f%% (Aduana)" % fodinfa_rate,
                "amount": fodinfa_rate,
            },
            "iva": {
                "name": "IVA Importación %.2f%% (Aduana)" % iva_rate,
                "amount": iva_rate,
            },
        }
        Tax = self.env["account.tax"].sudo()
        taxes = {}
        for key, spec in specs.items():
            tax = Tax.search(
                [
                    ("name", "=", spec["name"]),
                    ("type_tax_use", "=", "purchase"),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if not tax:
                tax = Tax.create(
                    {
                        "name": spec["name"],
                        "type_tax_use": "purchase",
                        "amount_type": "percent",
                        "amount": spec["amount"],
                        "company_id": self.company_id.id,
                        "description": spec["name"],
                    }
                )
            taxes[key] = tax
        return taxes

    def _l10n_ec_account_domain(self, company, code):
        """
        Domain matching an account.account usable by `company` with `code`.

        Odoo 18 removed account.account.company_id (a company-dependent
        Many2one) in favour of company_ids (Many2many) + a record rule, so
        filtering on company_id raises "Invalid field company_id on model
        account.account". Filter on company_ids instead; accounts shared
        with several companies still match.
        """
        return [("code", "=", code), ("company_ids", "in", company.id)]

    def _l10n_ec_resolve_account(self, param_key, role_label, candidate_codes):
        """
        Resolve an account by (1) the code in system parameter
        `param_key`, or (2) the first matching NEC candidate code.
        """
        company = self.company_id or self.env.company
        Account = self.env["account.account"].sudo()
        code = self.env["ir.config_parameter"].sudo().get_param(param_key)
        if code:
            account = Account.search(
                self._l10n_ec_account_domain(company, code), limit=1
            )
            if account:
                return account
            raise UserError(
                _(
                    "System parameter %s points to account code '%s' which "
                    "does not exist for company %s."
                )
                % (param_key, code, company.name)
            )
        for candidate in candidate_codes:
            account = Account.search(
                self._l10n_ec_account_domain(company, candidate), limit=1
            )
            if account:
                return account
        raise UserError(
            _(
                "Cannot resolve the %s account. Configure the system "
                "parameter '%s' with the account code to use (NEC code, "
                "e.g. from your CoA)."
            )
            % (role_label, param_key)
        )

    def action_post(self):
        """
        Post the import journal entry: debit the three import duties and
        credit the customs broker / supplier.

        ISD is NOT part of this entry — it is paid on the foreign
        transfer (LORTI Art. 75), not on the customs assessment.
        """
        for rec in self:
            if rec.state == "draft":
                rec.action_calculate()
            if rec.move_id and rec.move_id.state == "posted":
                raise UserError(
                    _("%s already has a posted customs entry (%s).")
                    % (rec.name, rec.move_id.display_name)
                )
            if not rec.partner_id:
                raise UserError(
                    _("%s: set the Customs Broker/Supplier before posting.")
                    % rec.name
                )

            taxes = rec._l10n_ec_ensure_import_taxes()

            # Accounts (system parameter first, NEC candidates as fallback)
            duty_account = rec._l10n_ec_resolve_account(
                "l10n_ec.customs_duty_account",
                _("Ad Valorem/FOB duty expense"),
                [],  # TODO: add the definitive NEC code once CoA (Agent C) lands
            )
            fodinfa_account = rec._l10n_ec_resolve_account(
                "l10n_ec.customs_fodinfa_account",
                _("FODINFA expense"),
                [],
            )
            iva_account = rec._l10n_ec_resolve_account(
                "l10n_ec.customs_iva_account",
                _("Import IVA (creditable)"),
                [],
            )

            journal = rec.journal_id
            if not journal:
                journal = self.env["account.journal"].search(
                    [
                        ("type", "=", "general"),
                        ("code", "=", "ADUAN"),
                        ("company_id", "=", rec.company_id.id),
                    ],
                    limit=1,
                )
            if not journal:
                journal = self.env["account.journal"].create(
                    {
                        "name": _("Importaciones (EC)"),
                        "code": "ADUAN",
                        "type": "general",
                        "company_id": rec.company_id.id,
                    }
                )

            payable_account = rec.partner_id.property_account_payable_id
            if not payable_account:
                raise UserError(
                    _("%s: supplier %s has no payable account configured.")
                    % (rec.name, rec.partner_id.name)
                )

            line_cmds = []
            duty_total = 0.0
            # NOTE: the duty amounts below are ALREADY the final SENAE
            # amounts (IVA base = CIF + Ad Valorem + FODINFA — a cascade the
            # standard tax engine does not reproduce by itself, and Ad Valorem
            # is 0-40% per tariff heading so it cannot be a fixed-percent tax).
            # Attaching tax_ids to these lines would make Odoo compute the
            # taxes a SECOND time on top of the debit, silently double-
            # counting the duty and forcing an "Automatic Balancing Line".
            # The real account.tax records are still created above (they live
            # in the CoA for books/ATS and for use on commercial invoices);
            # they are only referenced here by name for traceability.
            for amount, account, label, tax in (
                (rec.total_ad_valorem, duty_account, _("Ad Valorem"), taxes["ad_valorem"]),
                (rec.total_fodinfa, fodinfa_account, _("FODINFA"), taxes["fodinfa"]),
                (rec.total_iva, iva_account, _("IVA Importación"), taxes["iva"]),
            ):
                if amount <= 0:
                    continue
                duty_total += amount
                line_cmds.append(
                    (
                        0,
                        0,
                        {
                            "name": "%s %s [%s]" % (label, rec.name, tax.name),
                            "account_id": account.id,
                            "debit": amount,
                            "credit": 0.0,
                        },
                    )
                )
            if duty_total <= 0:
                raise UserError(
                    _("%s: no customs duties to post (all totals are zero).")
                    % rec.name
                )
            line_cmds.append(
                (
                    0,
                    0,
                    {
                        "name": _("Cuenta por pagar aduanas %s") % rec.name,
                        "account_id": payable_account.id,
                        "debit": 0.0,
                        "credit": duty_total,
                        "partner_id": rec.partner_id.id,
                    },
                )
            )

            move = self.env["account.move"].create(
                {
                    "journal_id": journal.id,
                    "date": rec.date or fields.Date.today(),
                    "ref": rec.ecuapass_dui_number or rec.name,
                    "partner_id": rec.partner_id.id,
                    "line_ids": line_cmds,
                }
            )
            move.action_post()
            rec.write({"move_id": move.id, "state": "done"})
        return True


class L10nEcImportDauLine(models.Model):
    _name = "l10n_ec.import.dau.line"
    _description = "DAU Line"

    dau_id = fields.Many2one("l10n_ec.import.dau", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product")
    tariff_id = fields.Many2one(
        "l10n_ec.tariff.heading",
        string="Tariff Heading",
        help="Partida arancelaria; defines the Ad Valorem rate (0-40%).",
    )

    valor_fob_line = fields.Float("FOB (Line)")
    cif_line = fields.Float("CIF (Line)", compute="_compute_cif_line", store=True)

    ad_valorem_amount = fields.Float(
        "Ad Valorem", compute="_compute_duties", store=True
    )

    @api.depends("dau_id.cif_value", "dau_id.fob_value", "valor_fob_line")
    def _compute_cif_line(self):
        for rec in self:
            header = rec.dau_id
            if header.fob_value and header.fob_value > 0:
                # Ratio: Header CIF / Header FOB
                ratio = header.cif_value / header.fob_value
                rec.cif_line = rec.valor_fob_line * ratio
            else:
                # Fallback if no FOB (shouldn't happen if lines exist)
                rec.cif_line = rec.valor_fob_line

    @api.depends("tariff_id", "cif_line")
    def _compute_duties(self):
        for rec in self:
            if rec.tariff_id:
                # Ad Valorem applied to CIF Line (rate per tariff, 0-40%)
                rec.ad_valorem_amount = rec.cif_line * (
                    rec.tariff_id.ad_valorem / 100.0
                )
            else:
                rec.ad_valorem_amount = 0.0
