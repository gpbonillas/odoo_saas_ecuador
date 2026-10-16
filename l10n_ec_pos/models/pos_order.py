# -*- coding: utf-8 -*-
"""
SRI electronic transmission for POS tickets (facturación en línea).

State machine (`l10n_ec_sri_status`):

    draft ──transmit()──► sent ──check_authorization()──► authorized
      │                    │                                  │
      └──(rejected)◄──────┘ (DEVUELTA)      request_annulment()►
                                                   │
    authorized ──(CF ticket: NEVER)──► cancel forbidden
    authorized ──(factura, before day 7)──► annulled

Rules implemented (SRI 2026 / Res. NAC-DGERCGC25-00000017):
  * Every ticket must be transmitted inside the mandatory window
    (`l10n_ec_transmission_window_hours`, default 24h).
  * Consumidor Final tickets (CF RUC) that were transmitted CANNOT be
    cancelled/annulled — validation raises with a clear message.
  * Other authorized tickets are annulable only until day
    `l10n_ec.annulment_day_limit` (default 7) of the following month.
  * Offline contingency is allowed (mode/manual) but does NOT extend the
    transmission window.

NETWORK NOTE: the actual SOAP calls are performed by the shared
`l10n_ec.sri.service` (zeep) and `l10n_ec.sri.signer` (XAdES-BES) from
`l10n_ec_edi`; this module only wires them for POS. The remaining piece
is validation against the live celcer/cel endpoints (requires network
access + a real .p12 certificate).
"""
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    # --- SRI access key / authorization --------------------------------
    l10n_ec_sri_access_key = fields.Char(
        string="SRI Access Key", copy=False, help="49-digit Access Key"
    )
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Draft (no transmitido)"),
            ("signed", "Signed"),
            ("sent", "Sent (recibido SRI)"),
            ("authorized", "Authorized"),
            ("rejected", "Rejected (devuelto SRI)"),
            ("annul_requested", "Anulación solicitada"),
            ("annulled", "Anulado"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    l10n_ec_authorization_date = fields.Datetime(
        string="Authorization Date", copy=False
    )
    l10n_ec_last_transmission_date = fields.Datetime(
        string="Last Transmission", copy=False, readonly=True
    )
    l10n_ec_transmission_error = fields.Text(
        string="Transmission Error", copy=False, readonly=True
    )
    l10n_ec_is_contingency = fields.Boolean(
        string="Contingency Voucher",
        copy=False,
        readonly=True,
        help="Ticket emitted in offline contingency mode; it must still be "
        "transmitted within the mandatory window.",
    )
    l10n_ec_annul_reason = fields.Text(string="Annulment Reason", copy=False)
    l10n_ec_annul_date = fields.Datetime(string="Annulment Date", copy=False)

    # ==================================================================
    # Helpers
    # ==================================================================
    def _l10n_ec_get_param(self, key, default):
        return (
            self.env["ir.config_parameter"].sudo().get_param(key) or default
        )

    def _l10n_ec_get_cf_ruc(self):
        """Consumidor Final RUC (shared config key with l10n_ec_edi)."""
        return self._l10n_ec_get_param("l10n_ec.consumidor_final_ruc", "9999999999999")

    def _l10n_ec_is_consumidor_final(self):
        """
        Consumidor Final ticket?

        A CF sale normally has NO partner at all (that is what makes it
        CF), and some flows instead set a partner carrying the generic CF
        RUC. Both cases must count as CF, consistently with
        _l10n_ec_identifier_code() which returns SRI code 07 for either.
        Treating "no partner" as non-CF made every ordinary CF ticket
        annulable, breaking the SRI 2026 rule that transmitted CF tickets
        can never be annulled.
        """
        self.ensure_one()
        return (not self.partner_id) or (
            self.partner_id.vat == self._l10n_ec_get_cf_ruc()
        )

    def _l10n_ec_identifier_code(self, partner):
        """SRI Table 07: RUC=04, Cedula=05, Pasaporte=06, CF=07."""
        if not partner or partner.vat == self._l10n_ec_get_cf_ruc():
            return "07"
        return {"ruc": "04", "cedula": "05", "pasaporte": "06"}.get(
            partner.l10n_ec_identifier_type, "05"
        )

    def _l10n_ec_annulment_deadline(self):
        """Day N of the month following emission (default 7)."""
        self.ensure_one()
        import calendar

        day = int(self._l10n_ec_get_param("l10n_ec.annulment_day_limit", "7"))
        emission = self.date_order.date() if self.date_order else fields.Date.today()
        if emission.month == 12:
            year, month = emission.year + 1, 1
        else:
            year, month = emission.year, emission.month + 1
        day = min(day, calendar.monthrange(year, month)[1])
        return datetime(year, month, day).date()

    def _l10n_ec_is_annulable(self):
        """
        (annulable, reason) for a ticket already sent/authorized.

        * Consumidor Final transmitted tickets: NEVER annulable
          (SRI 2026 mandate — CF has no annulment mechanism).
        * Other tickets: only until day 7 of the following month.
        """
        self.ensure_one()
        if self.l10n_ec_sri_status not in ("sent", "authorized", "annul_requested"):
            return True, ""
        if self._l10n_ec_is_consumidor_final():
            return False, _(
                "Consumidor Final tickets (%s) that were transmitted to the "
                "SRI CANNOT be cancelled or annulled. Emit a nota de crédito "
                "is also forbidden for CF; only internal records may adjust."
            ) % self._l10n_ec_get_cf_ruc()
        deadline = self._l10n_ec_annulment_deadline()
        if fields.Date.context_today(self) > deadline:
            return False, _(
                "The annulment deadline has passed (day %s of the following "
                "month: %s)."
            ) % (
                self._l10n_ec_get_param("l10n_ec.annulment_day_limit", "7"),
                deadline,
            )
        return True, ""

    # ==================================================================
    # Access key (kept from previous implementation, sequential fixed)
    # ==================================================================
    def _generate_pos_access_key(self):
        """49-digit access key for the POS ticket (codDoc 01)."""
        for order in self:
            if order.l10n_ec_sri_access_key:
                continue
            from odoo.addons.l10n_ec_edi.models.access_key import AccessKey

            env = (
                "2" if order.company_id.l10n_ec_sri_environment == "production" else "1"
            )
            # Extract the 9-digit sequential from the POS reference
            # ('Order 00001-001-0001' -> last digits) and zero-pad to 9.
            seq_raw = order.pos_reference or order.name or ""
            seq_num = "".join(filter(str.isdigit, seq_raw))[-9:]
            seq_num = seq_num.zfill(9)

            key = AccessKey.generate(
                invoice_date=order.date_order.date() if order.date_order else fields.Date.today(),
                doc_type="01",
                ruc=order.company_id.vat,
                environment=env,
                establishment=order.config_id.l10n_ec_entity or "001",
                emission_point=order.config_id.l10n_ec_emission_point or "001",
                sequential=seq_num,
            )
            order.l10n_ec_sri_access_key = key

    # ==================================================================
    # XML generation (integration hook)
    # ==================================================================
    def _l10n_ec_prepare_tax_groups(self):
        """SRI Table 16/17 aggregates from POS lines (codigo, base, impuesto)."""
        from collections import defaultdict

        grouped = defaultdict(lambda: {"base": 0.0, "impuesto": 0.0})
        for line in self.lines:
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line.price_unit * (1 - (line.discount or 0.0) / 100.0),
                    currency=self.currency_id,
                    quantity=line.qty,
                    product=line.product_id,
                    partner=self.partner_id,
                )
                for tax_val in taxes_res["taxes"]:
                    tax = self.env["account.tax"].browse(tax_val["id"])
                    sri_code = "3" if "ICE" in tax.name else "2"
                    sri_perc = "0"
                    if "15%" in tax.name:
                        sri_perc = "4"
                    elif "0%" in tax.name:
                        sri_perc = "0"
                    key = (sri_code, sri_perc)
                    grouped[key]["base"] += tax_val["base"]
                    grouped[key]["impuesto"] += tax_val["amount"]
            else:
                # No tax -> IVA 0% (codigo 2, porcentaje 0)
                grouped[("2", "0")]["base"] += line.price_subtotal
        return [
            {"codigo": c, "codigo_porcentaje": p, "base": v["base"], "impuesto": v["impuesto"]}
            for (c, p), v in grouped.items()
        ]

    def _l10n_ec_prepare_payment_codes(self):
        """Distinct SRI formaPago codes used by the ticket's payments."""
        codes = []
        for payment in self.payment_ids:
            code = (
                payment.payment_method_id.l10n_ec_payment_code
                or "20"  # efectivo fallback
            )
            # TODO: validate against SRI Table 01 with real payment methods
            if code not in codes:
                codes.append(code)
        return codes or ["20"]

    def _l10n_ec_build_comprobante_xml(self):
        """
        Render the electronic factura XML (codDoc 01) for this POS ticket.
        Returns bytes (utf-8). Reuses the l10n_ec_edi signer afterwards.
        """
        self.ensure_one()
        if not self.l10n_ec_sri_access_key:
            self._generate_pos_access_key()
        date_order = self.date_order or fields.Datetime.now()
        total_descuento = sum(
            (l.price_unit * l.qty * (l.discount or 0.0) / 100.0) for l in self.lines
        )
        values = {
            "order": self,
            "company": self.company_id,
            "environment": (
                "1" if self.company_id.l10n_ec_sri_environment == "test" else "2"
            ),
            "access_key": self.l10n_ec_sri_access_key,
            "fecha_emision": date_order.strftime("%d/%m/%Y"),
            "partner": self.partner_id or self.config_id.l10n_ec_default_partner_id,
            "partner_id_code": self._l10n_ec_identifier_code(
                self.partner_id or self.config_id.l10n_ec_default_partner_id
            ),
            "total_sin_impuestos": sum(self.lines.mapped("price_subtotal")),
            "total_descuento": total_descuento,
            "importe_total": self.amount_total,
            "tax_groups": self._l10n_ec_prepare_tax_groups(),
            "payment_codes": self._l10n_ec_prepare_payment_codes(),
            "format_float": lambda x, p: ("%." + str(p) + "f") % x,
        }
        return self.env["ir.qweb"]._render(
            "l10n_ec_pos.l10n_ec_pos_factura_xml", values
        )

    # ==================================================================
    # Transmission (wires l10n_ec_edi signer + SRI SOAP client)
    # ==================================================================
    def _l10n_ec_check_transmission_window(self, force=False):
        """Raise if the mandatory transmission window has been exceeded."""
        self.ensure_one()
        config = self.config_id
        if not config.l10n_ec_transmission_window_hours or force:
            return True
        window_start = self.date_order or fields.Datetime.now()
        deadline = window_start + timedelta(
            hours=config.l10n_ec_transmission_window_hours
        )
        if fields.Datetime.now() > deadline and self.l10n_ec_sri_status in (
            "draft",
            "signed",
        ):
            raise UserError(
                _(
                    "SRI transmission window exceeded for ticket %s.\n"
                    "The voucher was emitted at %s and the mandatory window "
                    "is %s hours. Transmit immediately with 'force' "
                    "(contingency) — the delay must be reported in the "
                    "SRI contingency log."
                )
                % (self.pos_reference, window_start, config.l10n_ec_transmission_window_hours)
            )
        return True

    def action_l10n_ec_transmit(self):
        """Sign + transmit this ticket to the SRI reception web service."""
        for order in self:
            if not order.config_id.l10n_ec_sri_active:
                continue
            if order.l10n_ec_sri_status == "annulled":
                raise UserError(
                    _("Ticket %s is annulled and cannot be transmitted.")
                    % order.pos_reference
                )
            force = self.env.context.get("l10n_ec_force_transmission")
            order._l10n_ec_check_transmission_window(force=force)
            if not order.l10n_ec_sri_access_key:
                order._generate_pos_access_key()

            # 1. Build XML (integration hook)
            xml_content = order._l10n_ec_build_comprobante_xml()

            # 2. Sign with the company certificate (XAdES-BES)
            certificate = order.company_id.l10n_ec_certificate_id
            if not certificate or certificate.state != "active":
                raise UserError(
                    _("No active SRI signing certificate configured on the company.")
                )
            signed_xml = self.env["l10n_ec.sri.signer"].sign_xml(
                xml_content if isinstance(xml_content, bytes) else xml_content.encode("utf-8"),
                certificate.content,
                certificate.password,
            )
            order.l10n_ec_sri_status = "signed"

            # 3. Transmit — NETWORK CALL lives in l10n_ec.sri.service
            #    (zeep SOAP client against celcer/cel endpoints).
            env_code = (
                "1" if order.company_id.l10n_ec_sri_environment == "test" else "2"
            )
            response = self.env["l10n_ec.sri.service"].send_document(
                signed_xml if isinstance(signed_xml, bytes) else signed_xml.encode("utf-8"),
                env_code,
            )

            # 4. Process response
            order.l10n_ec_last_transmission_date = fields.Datetime.now()
            if response.get("status") == "RECIBIDA":
                order.l10n_ec_sri_status = "sent"
                order.l10n_ec_transmission_error = False
                # Flag contingency if emitted outside the window
                window = order.config_id.l10n_ec_transmission_window_hours or 0
                if window and order.date_order and fields.Datetime.now() > (
                    order.date_order + timedelta(hours=window)
                ):
                    order.l10n_ec_is_contingency = True
            else:
                order.l10n_ec_sri_status = "rejected"
                msgs = "\n".join(response.get("messages") or [])
                order.l10n_ec_transmission_error = "%s\n%s" % (
                    response.get("status"),
                    msgs,
                )
                _logger.warning(
                    "POS SRI transmission rejected for %s: %s",
                    order.pos_reference,
                    order.l10n_ec_transmission_error,
                )
        return True

    def action_l10n_ec_check_authorization(self):
        """Poll the SRI authorization web service for 'sent' tickets."""
        service = self.env["l10n_ec.sri.service"]
        for order in self:
            if order.l10n_ec_sri_status != "sent" or not order.l10n_ec_sri_access_key:
                continue
            response = service.check_authorization(order.l10n_ec_sri_access_key)
            status = response.get("status")
            if status == "AUTORIZADO":
                order.l10n_ec_sri_status = "authorized"
                order.l10n_ec_authorization_date = response.get("date") or fields.Datetime.now()
                order.l10n_ec_transmission_error = False
            elif status == "NO AUTORIZADO":
                order.l10n_ec_sri_status = "rejected"
                order.l10n_ec_transmission_error = "\n".join(
                    response.get("messages") or []
                )
            # 'PENDING' / 'ERROR' -> keep 'sent' (retry later)
        return True

    # ==================================================================
    # Annulment / cancellation rules
    # ==================================================================
    def action_l10n_ec_request_annulment(self):
        for order in self:
            if order.l10n_ec_sri_status == "annulled":
                continue
            annulable, reason = order._l10n_ec_is_annulable()
            if not annulable:
                raise UserError(reason)
            if not order.l10n_ec_annul_reason:
                raise UserError(
                    _("Provide the annulment reason before requesting it.")
                )
            order.l10n_ec_sri_status = "annul_requested"
        return True

    def action_l10n_ec_annul(self):
        for order in self:
            if order.l10n_ec_sri_status != "annul_requested":
                raise UserError(
                    _("Ticket %s has no pending annulment request.")
                    % order.pos_reference
                )
            order.write(
                {
                    "l10n_ec_sri_status": "annulled",
                    "l10n_ec_annul_date": fields.Datetime.now(),
                    "state": "cancel",
                }
            )
        return True

    def action_l10n_ec_cancel(self):
        """
        Cancel a POS ticket with SRI validation.

        A non-annulable ticket (transmitted Consumidor Final, or an
        authorized one past the day-7 deadline) CANNOT be cancelled.
        """
        for order in self:
            annulable, reason = order._l10n_ec_is_annulable()
            if not annulable:
                raise UserError(
                    _("SRI 2026: this ticket cannot be cancelled.\n%s") % reason
                )
            if order.l10n_ec_sri_status in ("sent", "authorized"):
                order.l10n_ec_sri_status = "annulled"
                order.l10n_ec_annul_date = fields.Datetime.now()
            order.state = "cancel"
        return True

    def unlink(self):
        """Transmitted vouchers must never be deleted (audit trail)."""
        for order in self:
            if order.l10n_ec_sri_status in ("sent", "authorized", "annulled"):
                raise UserError(
                    _(
                        "Ticket %s was transmitted to the SRI (status: %s) "
                        "and cannot be deleted; cancel/annul it instead."
                    )
                    % (order.pos_reference, order.l10n_ec_sri_status)
                )
        return super().unlink()

    # ==================================================================
    # Hooks + cron
    # ==================================================================
    def action_pos_order_paid(self):
        """Auto-transmit in 'online' mode right after payment."""
        res = super().action_pos_order_paid()
        for order in self:
            config = order.config_id
            if not config.l10n_ec_sri_active:
                continue
            if config.l10n_ec_transmission_mode == "online":
                try:
                    order.action_l10n_ec_transmit()
                except Exception as err:  # noqa: BLE001 - keep the POS usable
                    # Offline contingency: keep the ticket; the cron retries
                    # inside the mandatory window.
                    order.l10n_ec_is_contingency = True
                    order.l10n_ec_transmission_error = str(err)
                    _logger.warning(
                        "POS SRI auto-transmission failed for %s (%s); "
                        "kept as offline contingency.",
                        order.pos_reference,
                        err,
                    )
        return res

    @api.model
    def _l10n_ec_cron_transmit_pending(self):
        """
        Cron (hourly): transmit pending tickets and poll authorizations.

        * 'online' mode -> transmit everything not yet sent/annulled.
        * 'batch' mode  -> transmit once the session is closed/closing.
        * 'manual' mode -> skipped (operator action only), except tickets
          older than the transmission window which are always attempted
          (mandatory window; delay logged as contingency).
        """
        now = fields.Datetime.now()
        pending = self.search(
            [
                ("l10n_ec_sri_status", "in", ("draft", "signed", "rejected")),
                ("config_id.l10n_ec_sri_active", "=", True),
                ("state", "in", ("paid", "done", "invoiced")),
            ]
        )
        for order in pending:
            config = order.config_id
            overdue = config.l10n_ec_transmission_window_hours and order.date_order and (
                now > order.date_order + timedelta(hours=config.l10n_ec_transmission_window_hours)
            )
            if config.l10n_ec_transmission_mode == "manual" and not overdue:
                continue
            if config.l10n_ec_transmission_mode == "batch" and not overdue:
                if order.session_id.state not in ("closing_control", "closed", "done"):
                    continue
            try:
                order.action_l10n_ec_transmit()
            except Exception as err:  # noqa: BLE001 - keep the cron resilient
                _logger.warning(
                    "POS SRI cron: could not transmit %s: %s", order.pos_reference, err
                )

        # Poll authorizations for sent tickets (older than 5 minutes)
        sent_limit = now - timedelta(minutes=5)
        sent = self.search(
            [
                ("l10n_ec_sri_status", "=", "sent"),
                ("l10n_ec_last_transmission_date", "<=", sent_limit),
            ]
        )
        try:
            sent.action_l10n_ec_check_authorization()
        except Exception as err:  # noqa: BLE001
            _logger.warning("POS SRI cron: authorization check failed: %s", err)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if order.config_id.l10n_ec_sri_active and not order.l10n_ec_sri_access_key:
                order._generate_pos_access_key()
        return orders
