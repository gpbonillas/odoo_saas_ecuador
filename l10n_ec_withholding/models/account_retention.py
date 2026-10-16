# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64

# =========================================================================
# FERIADOS ECUATORIANOS (Código del Trabajo art. 65, RO Supl. 906,
# 20-dic-2016). Fixed holidays by law. Movable holidays (Carnaval,
# Viernes Santo) are computed from Easter every year.
# (El 27 de febrero y el 3 de mayo NO son feriados nacionales.)
# =========================================================================
_EC_FIXED_HOLIDAYS = {
    (1, 1),   # Año Nuevo
    (5, 1),   # Día del Trabajo
    (5, 24),  # Batalla de Pichincha
    (8, 10),  # Independencia del 10 de Agosto
    (10, 9),  # Independencia de Guayaquil
    (11, 2),  # Día de los Difuntos
    (11, 3),  # Independencia de Cuenca
    (12, 25), # Navidad
}


def _ec_easter_sunday(year):
    """Anonymous Gregorian algorithm - Easter Sunday date."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Comprobante de Retención (Ecuador)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, name desc"

    name = fields.Char(
        string="Document Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default="Draft",
    )
    company_id = fields.Many2one(
        "res.company", index=True, required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one(
        "res.partner", string="Vendor", required=True, index=True
    )
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)

    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env["account.journal"].search(
            [
                ("type", "=", "general"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        ),
        help="Journal used for the withholding accounting entry.",
    )
    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="Accounting entry generated when the withholding is posted "
             "(IR and IVA liabilities payable to the SRI).",
    )

    # SRI Integration Fields (Direct Link to Shared Logic)
    l10n_ec_sri_access_key = fields.Char(string="SRI Access Key", copy=False)
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("signed", "Signed"),
            ("sent", "Sent"),
            ("authorized", "Authorized"),
            ("rejected", "Rejected"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    l10n_ec_sri_response = fields.Text("SRI Response")
    l10n_ec_xml_data = fields.Binary("XML File", attachment=True)
    l10n_ec_authorization_date = fields.Datetime(
        string="Authorization Date", copy=False
    )

    # Lines
    retention_line_ids = fields.One2many(
        "account.retention.line", "retention_id", string="Withholding Lines"
    )

    invoice_id = fields.Many2one(
        "account.move", string="Related Bill", domain=[("move_type", "=", "in_invoice")]
    )

    state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted"), ("cancel", "Cancelled")],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    # =========================================================================
    # REGLA DE LOS 5 DÍAS HÁBILES (LRTI art. 50 + Código Tributario art. 12)
    # La retención se efectúa al momento del pago o crédito en cuenta, y el
    # comprobante de retención debe entregarse dentro de los 5 días de
    # RECIBIDO el comprobante de venta (días hábiles: Código Tributario
    # art. 12). Este módulo computa el plazo desde la fecha de la factura
    # como aproximación conservadora; el reloj legal corre desde la
    # recepción del comprobante. Los días inhábiles (fines de semana +
    # feriados ecuatorianos) NO se cuentan.
    # =========================================================================

    @api.model
    def _l10n_ec_holidays_for_year(self, year):
        """Set of Ecuadorian holidays (datetime.date) for ``year``."""
        holidays = {date(year, month, day) for (month, day) in _EC_FIXED_HOLIDAYS}
        easter = _ec_easter_sunday(year)
        holidays.add(easter - timedelta(days=2))   # Viernes Santo
        holidays.add(easter - timedelta(days=47))  # Carnaval (martes)
        holidays.add(easter - timedelta(days=48))  # Carnaval (lunes)
        return holidays

    @api.model
    def _l10n_ec_extra_holidays(self, company=None):
        """
        Company-configured leaves (resource.calendar.leaves) also count as
        non-business days, so locally declared holidays are honored too.
        """
        extra = set()
        if "resource.calendar.leave" not in self.env:
            return extra
        company = company or self.env.company
        leaves = self.env["resource.calendar.leave"].search(
            [("company_id", "in", (False, company.id))], limit=366
        )
        for leave in leaves:
            start = leave.date_from.date()
            end = leave.date_to.date() if leave.date_to else start
            # Cap ranges to avoid huge loops on open-ended leaves
            for offset in range(0, (end - start).days + 1):
                extra.add(start + timedelta(days=offset))
        return extra

    @api.model
    def _l10n_ec_count_business_days(self, start_date, end_date, company=None):
        """
        Business days strictly after ``start_date`` up to and including
        ``end_date``, excluding weekends, Ecuadorian statutory holidays
        and company leaves.
        """
        if not start_date or not end_date or end_date <= start_date:
            return 0
        holidays = set()
        for year in range(start_date.year, end_date.year + 1):
            holidays |= self._l10n_ec_holidays_for_year(year)
        holidays |= self._l10n_ec_extra_holidays(company)

        count = 0
        current = start_date + timedelta(days=1)
        while current <= end_date:
            if current.weekday() < 5 and current not in holidays:
                count += 1
            current += timedelta(days=1)
        return count

    @api.constrains("date", "invoice_id")
    def _check_5_day_rule(self):
        """
        LRTI art. 50 (días hábiles según Código Tributario art. 12): the
        comprobante de retención must be delivered within 5 BUSINESS days
        of receipt of the vendor's sales voucher.  Weekends and Ecuadorian
        holidays are not counted.  This check starts the count at the
        vendor invoice date (conservative approximation of "receipt").
        """
        for record in self:
            if not record.invoice_id or not record.date:
                continue
            inv_date = record.invoice_id.invoice_date
            if not inv_date:
                continue
            if record.date < inv_date:
                continue  # reported by _check_retention_date
            elapsed = self._l10n_ec_count_business_days(
                inv_date, record.date, record.company_id
            )
            if elapsed > 5:
                raise ValidationError(
                    _(
                        "Regla de los 5 días hábiles (LRTI art. 50; días "
                        "hábiles: Código Tributario art. 12).\n\n"
                        "La factura del proveedor tiene fecha %s y esta retención "
                        "se emite el %s: han transcurrido %s días hábiles "
                        "(máximo permitido: 5).\n\n"
                        "Los fines de semana y feriados ecuatorianos no se "
                        "computan como días hábiles."
                    )
                    % (inv_date, record.date, elapsed)
                )

    @api.constrains("date", "invoice_id")
    def _check_retention_date(self):
        """
        Valida que la fecha de retención sea coherente con la factura:
        no puede ser anterior a la factura (la regla de 5 días hábiles
        se valida en _check_5_day_rule).
        """
        for record in self:
            if record.invoice_id and record.date:
                inv_date = record.invoice_id.invoice_date
                if not inv_date:
                    continue
                if record.date < inv_date:
                    raise ValidationError(
                        _(
                            "La fecha de retención (%s) no puede ser anterior "
                            "a la fecha de la factura (%s)."
                        )
                        % (record.date, inv_date)
                    )

    @api.model
    def create(self, vals):
        if vals.get("name", "Draft") == "Draft":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("account.retention") or "Draft"
            )
        return super(AccountRetention, self).create(vals)

    # =========================================================================
    # ACCOUNTING: POSTING (retained amount is owed in FULL to the SRI)
    # =========================================================================

    @api.model
    def _l10n_ec_find_account(self, company, codes, name_patterns):
        """
        Resolve an account of the company chart by code first, then by
        name pattern (both dotted NEC codes from the CSV templates and
        the python chart template codes are tried).
        """
        Account = self.env["account.account"].with_company(company)
        domain = [("company_id", "in", (False, company.id))]
        account = Account.search(domain + [("code", "in", codes)], limit=1)
        if not account:
            for pattern in name_patterns:
                account = Account.search(domain + [("name", "ilike", pattern)], limit=1)
                if account:
                    break
        return account

    @api.model
    def _l10n_ec_get_iva_split(self):
        """
        Distribution of the withheld IVA. The retained amount goes in FULL
        to the SRI (Formulario 104 casillero 721-731); there is NO legal
        split with the IESS (the former "30% SRI / 70% IESS" cited as
        "Decreto 745" had no legal basis and was corrected in the 2026
        legal audit — see docs/legal_audit_2026.md). Ratios remain as
        ir.config_parameter for backward compatibility (default 100/0).
        """
        ICP = self.env["ir.config_parameter"].sudo()
        sri_pct = float(ICP.get_param("l10n_ec.withholding_iva_sri_pct", "100"))
        iess_pct = float(ICP.get_param("l10n_ec.withholding_iva_iess_pct", "0"))
        return sri_pct, iess_pct

    def _l10n_ec_get_liability_accounts(self):
        """Returns (ir_account, iva_sri_account, iess_account). Raises if the
        SRI accounts are missing; the IESS account is only required when a
        legacy IVA split share > 0 is configured (deprecated)."""
        self.ensure_one()
        company = self.company_id
        ir_account = self._l10n_ec_find_account(
            company,
            codes=["2010402", "2.01.03.02"],
            name_patterns=["%fuente%por pagar%"],
        )
        iva_sri_account = self._l10n_ec_find_account(
            company,
            codes=["2010403", "2010503", "2.01.03.03"],
            name_patterns=["%retenc%iva%por pagar%"],
        )
        iess_account = self._l10n_ec_find_account(
            company,
            codes=["2010301", "2.01.04.01"],
            name_patterns=["%aporte personal%"],
        )
        missing = [
            label
            for label, account in (
                (_("Retención en la Fuente por Pagar (SRI)"), ir_account),
                (_("Retención IVA por Pagar (SRI)"), iva_sri_account),
            )
            if not account
        ]
        if missing:
            raise UserError(
                _(
                    "Cannot post withholding %s: chart of accounts is missing "
                    "the following account(s):\n- %s\n\n"
                    "Install/configure the Ecuador NEC chart of accounts first."
                )
                % (self.name, "\n- ".join(missing))
            )
        return ir_account, iva_sri_account, iess_account

    def _l10n_ec_create_journal_entry(self):
        """
        Generates the accounting entry of the withholding document:

        * IR (renta):  Dr Accounts Payable (vendor)
                       Cr Retención en la Fuente por Pagar (SRI)
        * IVA:         Dr Accounts Payable (vendor)
                       Cr Retención IVA por Pagar (SRI) — full amount
                       [deprecated legacy split (30/70 SRI/IESS, "Decreto
                       745") had no legal basis; the whole retained IVA is
                       deposited to the SRI — docs/legal_audit_2026.md]

        The IVA amount applies to every IVA withholding, including the
        100% cases (codes 729/731).
        """
        self.ensure_one()
        if self.move_id:
            if self.move_id.state == "draft":
                self.move_id.action_post()
            return self.move_id

        journal = self.journal_id or self.env["account.journal"].search(
            [
                ("type", "=", "general"),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if not journal:
            raise UserError(
                _(
                    "No Miscellaneous (general) journal found for company %s. "
                    "Configure one before posting withholdings."
                )
                % self.company_id.name
            )

        ir_account, iva_sri_account, iess_account = (
            self._l10n_ec_get_liability_accounts()
        )

        currency = self.company_id.currency_id
        ir_total = currency.round(
            sum(line.amount for line in self.retention_line_ids
                if line.tax_type == "1")
        )
        iva_total = currency.round(
            sum(line.amount for line in self.retention_line_ids
                if line.tax_type == "2")
        )
        unsupported = [
            line.tax_code for line in self.retention_line_ids
            if line.tax_type not in ("1", "2")
        ]
        if unsupported:
            raise UserError(
                _(
                    "Withholding %s: unsupported tax type for journal entry: %s. "
                    "Only Renta (1) and IVA (2) are supported."
                )
                % (self.name, ", ".join(unsupported))
            )
        if not ir_total and not iva_total:
            raise UserError(
                _("Withholding %s has no withholdable amount.") % self.name
            )

        payable = self.partner_id.with_company(
            self.company_id
        ).property_account_payable_id
        if not payable:
            raise UserError(
                _(
                    "Vendor %s has no payable account defined."
                )
                % self.partner_id.display_name
            )

        line_vals = []
        partner_id = self.partner_id.id

        def _add(account, debit, credit):
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "name": self.name,
                        "account_id": account.id,
                        "debit": debit,
                        "credit": credit,
                        "partner_id": partner_id,
                    },
                )
            )

        if ir_total:
            _add(payable, ir_total, 0.0)
            _add(ir_account, 0.0, ir_total)

        if iva_total:
            sri_pct, _iess_pct = self._l10n_ec_get_iva_split()
            sri_amount = currency.round(iva_total * sri_pct / 100.0)
            iess_amount = currency.round(iva_total - sri_amount)
            _add(payable, iva_total, 0.0)
            _add(iva_sri_account, 0.0, sri_amount)
            if iess_amount:
                # Legacy configurable split (>0) only; not the legal rule.
                if not iess_account:
                    raise UserError(
                        _(
                            "Chart of accounts is missing the account for "
                            "'Aporte Personal IESS por Pagar' required by the "
                            "configured legacy IVA split."
                        )
                    )
                _add(iess_account, 0.0, iess_amount)

        move = (
            self.env["account.move"]
            .with_company(self.company_id)
            .create(
                {
                    "move_type": "entry",
                    "journal_id": journal.id,
                    "date": self.date,
                    "ref": self.name,
                    "company_id": self.company_id.id,
                    "line_ids": line_vals,
                }
            )
        )
        move.action_post()
        self.move_id = move
        return move

    def action_post(self):
        for record in self:
            if record.state == "posted":
                continue
            if not record.retention_line_ids:
                raise UserError(
                    _("Cannot post withholding %s without lines.") % record.name
                )
            if not record.move_id:
                record._l10n_ec_create_journal_entry()
            record.state = "posted"

    # =========================================================================
    # SRI ELECTRONIC TRANSMISSION (codDoc 07, same reception/authorization
    # path used by invoices: l10n_ec.sri.service + l10n_ec.sri.signer)
    # =========================================================================

    def _generate_access_key(self):
        """Generates the 49-digit SRI access key (doc type 07)."""
        from odoo.addons.l10n_ec_edi.models.access_key import AccessKey

        for record in self:
            if record.l10n_ec_sri_access_key:
                continue
            env = (
                "2"
                if record.company_id.l10n_ec_sri_environment == "production"
                else "1"
            )
            parts = record.name.split("-")
            if len(parts) == 3 and all(parts):
                estab, pto, seq = parts
            else:
                estab, pto, seq = "001", "001", record.id
            key = AccessKey.generate(
                invoice_date=record.date,
                doc_type="07",
                ruc=record.company_id.vat,
                environment=env,
                establishment=estab,
                emission_point=pto,
                sequential=seq,
            )
            record.l10n_ec_sri_access_key = key

    def _l10n_ec_render_xml(self):
        """Renders the codDoc 07 comprobanteRetencion XML (v2.0.0)."""
        self.ensure_one()
        identifier_type = self.partner_id.l10n_ec_identifier_type
        if identifier_type == "cedula":
            identifier_code = "05"
        elif identifier_type == "pasaporte":
            identifier_code = "06"
        else:
            identifier_code = "04"
        values = {
            "retention": self,
            "company": self.company_id,
            "partner": self.partner_id,
            "environment": (
                "1" if self.company_id.l10n_ec_sri_environment == "test" else "2"
            ),
            "access_key": self.l10n_ec_sri_access_key,
            "format_monetary": lambda x: "%.2f" % x,
            "format_float": lambda x, p: ("%." + str(p) + "f") % x,
            "identifier_code": identifier_code,
        }
        return self.env["ir.qweb"]._render(
            "l10n_ec_withholding.l10n_ec_retention_xml", values
        )

    def _l10n_ec_process_reception(self, response, signed_xml_bytes=None):
        """
        Applies the SRI reception (RecepcionComprobantesOffline) response.
        Same semantics as invoices: RECIBIDA -> sent, DEVUELTA/ERROR ->
        rejected.
        """
        for record in self:
            if response.get("status") == "RECIBIDA":
                record.l10n_ec_sri_status = "sent"
                record.l10n_ec_sri_response = "RECIBIDA. Waiting for Authorization..."
                if signed_xml_bytes:
                    record.l10n_ec_xml_data = base64.b64encode(signed_xml_bytes)
            else:
                record.l10n_ec_sri_status = "rejected"
                msgs = "\n".join(response.get("messages", []))
                record.l10n_ec_sri_response = "%s: %s" % (
                    response.get("status"),
                    msgs,
                )

    def _l10n_ec_process_authorization(self, response):
        """
        Applies the SRI authorization (AutorizacionComprobantesOffline)
        response. AUTORIZADO -> authorized, NO AUTORIZADO -> rejected,
        PENDING -> keep waiting (same as invoices).
        """
        for record in self:
            status = response.get("status")
            if status == "AUTORIZADO":
                record.l10n_ec_sri_status = "authorized"
                if response.get("date"):
                    try:
                        record.l10n_ec_authorization_date = response["date"]
                    except (ValueError, TypeError):
                        pass
                xml = response.get("xml")
                if xml:
                    if isinstance(xml, str):
                        xml = xml.encode("utf-8")
                    record.l10n_ec_xml_data = base64.b64encode(xml)
                record.l10n_ec_sri_response = "AUTORIZADO"
            elif status == "NO AUTORIZADO":
                record.l10n_ec_sri_status = "rejected"
                msgs = "\n".join(response.get("messages", []))
                record.l10n_ec_sri_response = "NO AUTORIZADO: %s" % msgs
            else:
                msgs = "\n".join(response.get("messages", []))
                record.l10n_ec_sri_response = "%s: %s" % (status, msgs)

    def action_send_sri(self):
        """
        Renders the XML, signs it (XAdES-BES) and sends it to the SRI
        reception web service - the exact same path used by invoices.
        """
        for record in self:
            if record.state != "posted":
                raise UserError(
                    _(
                        "The withholding %s must be posted before sending to SRI."
                    )
                    % record.name
                )
            if record.l10n_ec_sri_status in ("sent", "authorized"):
                continue

            if not record.l10n_ec_sri_access_key:
                record._generate_access_key()

            try:
                xml_content = record._l10n_ec_render_xml()

                certificate = record.company_id.l10n_ec_certificate_id
                if not certificate or certificate.state != "active":
                    raise UserError(
                        _("SRI Error: No active Signing Certificate configured.")
                    )

                signer = self.env["l10n_ec.sri.signer"]
                service = self.env["l10n_ec.sri.service"]
                signed_xml_bytes = signer.sign_xml(
                    xml_content.encode("utf-8"),
                    certificate.content,
                    certificate.password,
                )

                env_code = (
                    "1"
                    if record.company_id.l10n_ec_sri_environment == "test"
                    else "2"
                )
                response_data = service.send_document(signed_xml_bytes, env_code)
                record._l10n_ec_process_reception(response_data, signed_xml_bytes)
            except UserError:
                raise
            except Exception as e:
                record.l10n_ec_sri_response = "System Error: %s" % str(e)

    def action_check_sri(self):
        """
        Checks the authorization status of the retention at the SRI
        (same AutorizacionComprobantesOffline service used by invoices).
        """
        service = self.env["l10n_ec.sri.service"]
        for record in self:
            if not record.l10n_ec_sri_access_key:
                raise UserError(
                    _("No access key generated for %s yet.") % record.name
                )
            response = service.check_authorization(record.l10n_ec_sri_access_key)
            record._l10n_ec_process_authorization(response)
