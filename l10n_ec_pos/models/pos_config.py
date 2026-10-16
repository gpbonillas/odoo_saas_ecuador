# -*- coding: utf-8 -*-
from odoo import models, fields


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_ec_sri_active = fields.Boolean(
        string="Active SRI Electronic Invoicing", default=True
    )
    l10n_ec_entity = fields.Char(
        string="Establishment", default="001", help="SRI Establishment Code (e.g. 001)"
    )
    l10n_ec_emission_point = fields.Char(
        string="Emission Point",
        default="001",
        help="SRI Emission Point for this POS (e.g. 002)",
    )
    l10n_ec_default_partner_id = fields.Many2one(
        "res.partner", string="Default Customer (Consumidor Final)"
    )

    # --- SRI transmission policy (facturación en línea) -----------------
    l10n_ec_transmission_mode = fields.Selection(
        [
            ("online", "En línea (transmitir cada ticket)"),
            ("batch", "Agregado (transmitir al cerrar la sesión)"),
            ("manual", "Manual (botón / cron)"),
        ],
        string="Transmission Mode",
        default="online",
        required=True,
        help="SRI 'facturación en línea': every electronic voucher must be "
        "transmitted. 'online' sends each ticket right after payment; "
        "'batch' sends them when the session closes; 'manual' relies on the "
        "cron/back-office button (contingency mode).",
    )
    l10n_ec_offline_contingency = fields.Boolean(
        string="Allow Offline Contingency",
        default=True,
        help="Permits tickets to be created without reaching SRI "
        "(offline contingency). Contingency vouchers MUST still be "
        "transmitted within the mandatory window below.",
    )
    l10n_ec_transmission_window_hours = fields.Integer(
        string="Transmission Window (hours)",
        default=24,
        help="Mandatory maximum time (hours) between ticket emission and "
        "SRI transmission. Tickets older than this are flagged by the cron "
        "as overdue (SRI requires same-day/next-day transmission; 24h is "
        "the conservative default).",
    )


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    l10n_ec_payment_code = fields.Selection(
        [
            ("01", "01 - Transferencia"),
            ("02", "02 - Cheque"),
            ("03", "03 - Tarjeta de Crédito"),
            ("04", "04 - Tarjeta de Débito"),
            ("05", "05 - Dinero electrónico"),
            ("06", "06 - Ventas a crédito"),
            ("20", "20 - Efectivo"),
        ],
        string="SRI Payment Code",
        default="20",
        help="SRI Table 01 (forma de pago) code written into the electronic "
        "voucher <formaPago> for payments made with this method.",
    )
