# -*- coding: utf-8 -*-
"""
Guía de Remisión Electrónica (SRI codDoc 06) on stock pickings.

FIXES (audit of this module):
  * Template used non-existent field `identifier_type` (driver model has
    `identification_type`) and mapped `rucTransportista` to the driver's
    LICENSE NUMBER — SRI requires the transportista's RUC/Cédula.
  * Sequential of the access key was not zero-padded to 9 digits.
  * Added optional transport COMPANY (razón social + RUC) so a picking
    can be transported by a legal entity, not only an individual driver.
  * `motivoTraslado` now maps to SRI free-text (VENTA, TRASLADO
    INTERNO, ...) instead of internal selection keys.
  * Pre-validated data (destinatario, dirección, fechas, líneas) before
    touching the network.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)

# SRI Table 07 (identificación) codes.
SRI_ID_CODES = {"ruc": "04", "cedula": "05", "pasaporte": "06"}

# Free-text 'motivoTraslado' per selection value. SRI accepts a free
# description; these are the conventional literals.
GUIA_MOTIVOS = {
    "ventas": "VENTA",
    "traslado": "TRASLADO INTERNO",
    "devolucion": "DEVOLUCION",
    "consignacion": "CONSIGNACION",
    "exportacion": "EXPORTACION",
    "otros": "OTROS",
}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Transport Info
    l10n_ec_transport_reason = fields.Selection(
        [
            ("ventas", "Venta"),
            ("traslado", "Traslado entre establecimientos"),
            ("devolucion", "Devolución"),
            ("consignacion", "Consignación"),
            ("exportacion", "Exportación"),
            ("otros", "Otros"),
        ],
        string="Reason for Transport",
        default="ventas",
        copy=False,
    )

    l10n_ec_start_date = fields.Date(
        string="Start Date", default=fields.Date.context_today
    )
    l10n_ec_end_date = fields.Date(string="End Date", default=fields.Date.context_today)

    # Driver & Vehicle
    l10n_ec_carrier_id = fields.Many2one(
        "res.partner",
        string="Transportista (empresa)",
        help="Transport company (razón social + RUC). If set, it takes "
        "priority over the individual driver for the guía's "
        "razonSocialTransportista/rucTransportista fields.",
    )
    l10n_ec_driver_id = fields.Many2one("l10n_ec.driver", string="Driver")
    l10n_ec_vehicle_id = fields.Many2one("l10n_ec.vehicle", string="Vehicle")

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

    # ------------------------------------------------------------------
    # Computed helpers consumed by the QWeb XML template
    # ------------------------------------------------------------------
    l10n_ec_guia_transport_name = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Transport Name"
    )
    l10n_ec_guia_transport_ident = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Transport ID"
    )
    l10n_ec_guia_transport_ident_code = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Transport ID Type"
    )
    l10n_ec_guia_placa = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Plate"
    )
    l10n_ec_guia_motivo = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Motivo"
    )
    l10n_ec_guia_fecha_ini = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Fecha Ini"
    )
    l10n_ec_guia_fecha_fin = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Fecha Fin"
    )
    l10n_ec_destinatario_ident_code = fields.Char(
        compute="_l10n_ec_compute_guia_helpers", string="Tmp Dest ID Type"
    )

    @api.depends(
        "l10n_ec_carrier_id",
        "l10n_ec_driver_id",
        "l10n_ec_vehicle_id",
        "l10n_ec_transport_reason",
        "l10n_ec_start_date",
        "l10n_ec_end_date",
        "partner_id",
    )
    def _l10n_ec_compute_guia_helpers(self):
        for rec in self:
            # Transportista: company (carrier) wins over individual driver
            if rec.l10n_ec_carrier_id:
                name = rec.l10n_ec_carrier_id.name
                ident = rec.l10n_ec_carrier_id.vat or ""
                ident_code = SRI_ID_CODES.get(
                    rec.l10n_ec_carrier_id.l10n_ec_identifier_type
                    or ("ruc" if len(ident) == 13 else "cedula"),
                    "04",
                )
            elif rec.l10n_ec_driver_id:
                name = rec.l10n_ec_driver_id.name
                ident = rec.l10n_ec_driver_id.identification_number or ""
                ident_code = SRI_ID_CODES.get(
                    rec.l10n_ec_driver_id.identification_type, "05"
                )
            else:
                name = ident = ident_code = ""

            rec.l10n_ec_guia_transport_name = name
            rec.l10n_ec_guia_transport_ident = ident
            rec.l10n_ec_guia_transport_ident_code = ident_code
            rec.l10n_ec_guia_placa = rec.l10n_ec_vehicle_id.license_plate or ""
            rec.l10n_ec_guia_motivo = GUIA_MOTIVOS.get(
                rec.l10n_ec_transport_reason, "OTROS"
            )
            rec.l10n_ec_guia_fecha_ini = (
                rec.l10n_ec_start_date.strftime("%d/%m/%Y")
                if rec.l10n_ec_start_date
                else fields.Date.today().strftime("%d/%m/%Y")
            )
            rec.l10n_ec_guia_fecha_fin = (
                rec.l10n_ec_end_date.strftime("%d/%m/%Y")
                if rec.l10n_ec_end_date
                else rec.l10n_ec_guia_fecha_ini
            )
            partner = rec.partner_id
            rec.l10n_ec_destinatario_ident_code = SRI_ID_CODES.get(
                partner.l10n_ec_identifier_type or ("ruc" if partner.vat and len(partner.vat) == 13 else "cedula"),
                "05",
            ) if partner else "05"

    # ------------------------------------------------------------------
    # Validation & access key
    # ------------------------------------------------------------------
    def _l10n_ec_validate_guia_data(self):
        """Precise pre-flight validation before SRI transmission."""
        for record in self:
            problems = []
            if not record.company_id.vat:
                problems.append(_("Company has no RUC."))
            if not record.partner_id:
                problems.append(_("Destinatario (customer) is required."))
            elif not record.partner_id.vat:
                problems.append(
                    _("Destinatario %s has no identification (RUC/Cédula).")
                    % record.partner_id.name
                )
            elif not record.partner_id.street:
                problems.append(
                    _("Destinatario %s has no address (dirDestinatario).")
                    % record.partner_id.name
                )
            if not record.l10n_ec_carrier_id and not record.l10n_ec_driver_id:
                problems.append(
                    _("Transportista (company or driver) is required.")
                )
            if not record.l10n_ec_vehicle_id:
                problems.append(_("Vehicle (placa) is required."))
            if record.l10n_ec_start_date and record.l10n_ec_end_date:
                if record.l10n_ec_end_date < record.l10n_ec_start_date:
                    problems.append(_("End date cannot be before start date."))
            moves = record.move_ids.filtered(lambda m: m.quantity > 0)
            if not moves:
                problems.append(_("The picking has no product lines to declare."))
            if problems:
                raise UserError(
                    _("Guía de Remisión incomplete:\n\n• %s")
                    % "\n• ".join(problems)
                )
        return True

    def _generate_access_key(self):
        """49-digit access key (codDoc 06) using the shared EDI utility."""
        for record in self:
            if record.l10n_ec_sri_access_key:
                continue
            if not record.company_id.vat:
                raise UserError(_("Company has no RUC configured."))
            from odoo.addons.l10n_ec_edi.models.access_key import AccessKey

            env = (
                "2"
                if record.company_id.l10n_ec_sri_environment == "production"
                else "1"
            )
            # Picking name 'WH/OUT/00001' -> 9-digit zero-padded sequential
            seq_num = "".join(
                filter(str.isdigit, record.name.split("/")[-1] if record.name else "")
            ).zfill(9)[-9:]

            key = AccessKey.generate(
                invoice_date=(
                    record.scheduled_date.date()
                    if record.scheduled_date
                    else fields.Date.today()
                ),
                doc_type="06",
                ruc=record.company_id.vat,
                environment=env,
                establishment=getattr(
                    record.picking_type_id.warehouse_id,
                    "l10n_ec_establishment",
                    "001",
                )
                or "001",
                emission_point="001",
                sequential=seq_num,
            )
            record.l10n_ec_sri_access_key = key

    # ------------------------------------------------------------------
    # Transmission (reuses l10n_ec_edi signer + SOAP client)
    # ------------------------------------------------------------------
    def action_send_guia_sri(self):
        """
        Generates XML, signs it and sends it to the SRI reception service.
        """
        signer = self.env["l10n_ec.sri.signer"]
        service = self.env["l10n_ec.sri.service"]
        for record in self:
            record._l10n_ec_validate_guia_data()

            if not record.l10n_ec_sri_access_key:
                record._generate_access_key()

            # 1. Render XML
            values = {
                "picking": record,
                "company": record.company_id,
                "environment": (
                    "1" if record.company_id.l10n_ec_sri_environment == "test" else "2"
                ),
                "access_key": record.l10n_ec_sri_access_key,
                "format_float": lambda x, p: ("%." + str(p) + "f") % x,
            }
            xml_content = self.env["ir.qweb"]._render(
                "l10n_ec_stock.l10n_ec_guia_xml", values
            )
            if isinstance(xml_content, str):
                xml_content = xml_content.encode("utf-8")

            # 2. Sign
            certificate = record.company_id.l10n_ec_certificate_id
            if not certificate or certificate.state != "active":
                raise UserError(
                    _("SRI Error: No active Signing Certificate configured.")
                )

            signed_xml_bytes = signer.sign_xml(
                xml_content,
                certificate.content,
                certificate.password,
            )
            if isinstance(signed_xml_bytes, str):
                signed_xml_bytes = signed_xml_bytes.encode("utf-8")

            # 3. Transmit (NETWORK: SOAP call lives in l10n_ec.sri.service)
            env_code = (
                "1" if record.company_id.l10n_ec_sri_environment == "test" else "2"
            )
            response_data = service.send_document(signed_xml_bytes, env_code)

            # 4. Process
            if response_data.get("status") == "RECIBIDA":
                record.l10n_ec_sri_status = "sent"
                record.l10n_ec_sri_response = "RECIBIDA. Waiting for Authorization..."
            else:
                record.l10n_ec_sri_status = "rejected"
                msgs = "\n".join(response_data.get("messages", []))
                record.l10n_ec_sri_response = "%s: %s" % (
                    response_data.get("status"),
                    msgs,
                )

            record.l10n_ec_xml_data = base64.b64encode(signed_xml_bytes)
        return True

    def action_check_guia_authorization(self):
        """Poll the SRI authorization service for sent guías."""
        service = self.env["l10n_ec.sri.service"]
        for record in self:
            if record.l10n_ec_sri_status != "sent" or not record.l10n_ec_sri_access_key:
                continue
            response = service.check_authorization(record.l10n_ec_sri_access_key)
            status = response.get("status")
            if status == "AUTORIZADO":
                record.l10n_ec_sri_status = "authorized"
                record.l10n_ec_sri_response = "AUTORIZADO %s" % response.get("date")
            elif status == "NO AUTORIZADO":
                record.l10n_ec_sri_status = "rejected"
                record.l10n_ec_sri_response = "\n".join(response.get("messages") or [])
        return True
