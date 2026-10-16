# -*- coding: utf-8 -*-
from odoo import models, _
from collections import defaultdict
import base64
import logging

_logger = logging.getLogger(__name__)

# SRI Table 17 (codigoPorcentaje) fallback keyed by IVA rate. Used only when
# the l10n_ec.tax.code catalog (l10n_ec_base) cannot resolve the tax.
# NOTE: the codigoPorcentaje does NOT match the Odoo tax amount:
# IVA 15% -> "4", IVA 5% -> "5", IVA 12% -> "2", IVA 14% -> "3", IVA 0% -> "0".
L10N_EC_SRI_CODIGO_PORCENTAJE_BY_RATE = {
    0.0: "0",
    5.0: "5",
    12.0: "2",
    14.0: "3",
    15.0: "4",
}


class AccountEdiFormat(models.Model):
    _inherit = "account.edi.format"

    def _get_l10n_ec_identifier_code(self, partner):
        """
        Maps Partner Identifier type to SRI Table 07:
        RUC = 04, Cedula = 05, Pasaporte = 06, Consumidor Final = 07, Exterior = 08
        """
        # Get CF RUC from config (not hardcoded)
        cf_ruc = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.consumidor_final_ruc", "9999999999999")
        )

        if partner.vat == cf_ruc:
            return "07"

        id_type = partner.l10n_ec_identifier_type
        if not id_type and partner.vat and str(partner.vat).strip().isdigit():
            # Fallback: infer from the identifier length when the type is not set
            vat = str(partner.vat).strip()
            id_type = "ruc" if len(vat) == 13 else ("cedula" if len(vat) == 10 else False)

        type_map = {"ruc": "04", "cedula": "05", "pasaporte": "06"}
        return type_map.get(id_type, "08")

    def _get_sri_tax_codes(self, tax):
        """
        Resolve (codigo, codigoPorcentaje) for an account.tax record.

        * codigo         -> SRI Table 16 (2 = IVA, 3 = ICE)
        * codigoPorcentaje -> SRI Table 17 (4 = 15%, 5 = 5%, 6 = No Objeto,
                            7 = Exento, 0 = 0%, ...). These codes do NOT match
                            the Odoo tax amount, so they must be resolved from
                            the l10n_ec.tax.code catalog or a rate fallback.

        ICE keeps its legacy per-product catalog code (3023).
        """
        name = (tax.name or "").upper()

        # ICE keeps the legacy catalog code (SRI Table for ICE products).
        if "ICE" in name:
            return "3", "3023"

        TaxCode = self.env["l10n_ec.tax.code"].sudo()

        # 1. Explicit link tax -> catalog (manually maintained mapping).
        catalog = TaxCode.search([("tax_id", "=", tax.id), ("active", "=", True)], limit=1)

        if not catalog:
            # 2. Catalog search by type + rate. The 0% rate is ambiguous:
            #    "0" (0%), "6" (No Objeto) and "7" (Exento) all share rate 0.
            rate = round(float(tax.amount or 0.0), 2)
            domain = [
                ("tax_type", "=", "iva"),
                ("active", "=", True),
                ("rate", "=", rate),
            ]
            if not rate:
                # 0% is ambiguous: "0" (0%), "6" (No Objeto) and "7" (Exento)
                # all share rate 0.0 in the catalog, so pin the code.
                if "NO OBJETO" in name:
                    domain.append(("code", "=", "6"))
                elif "EXENT" in name:
                    domain.append(("code", "=", "7"))
                else:
                    domain.append(("code", "=", "0"))
            catalog = TaxCode.search(domain, limit=1)

        if catalog:
            codigo = "3" if catalog.tax_type == "ice" else "2"
            return codigo, str(catalog.code)

        # 3. Rate-based fallback when the catalog is empty/unavailable.
        codigo_porcentaje = L10N_EC_SRI_CODIGO_PORCENTAJE_BY_RATE.get(
            round(float(tax.amount or 0.0), 2)
        )
        if codigo_porcentaje is None:
            _logger.warning(
                "l10n_ec_edi: no SRI codigoPorcentaje found for tax %r "
                "(amount=%s); falling back to 0%%.",
                tax.name,
                tax.amount,
            )
            codigo_porcentaje = "0"
        return "2", codigo_porcentaje

    def _get_l10n_ec_line_taxes(self, invoice):
        """
        SRI <impuesto> entries for each invoice line (detalle level).

        Returns {invoice_line_id: [ {codigo, codigo_porcentaje, tarifa,
        base, valor}, ... ]}. Untaxed lines get a single IVA 0% entry because
        SRI XSDs require at least one <impuesto> per <detalle>
        (LiquidacionCompra 1.1.0).
        """
        line_taxes = {}
        for line in invoice.invoice_line_ids.filtered(lambda l: not l.display_type):
            entries = []

            price_reduce = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes_res = line.tax_ids.compute_all(
                price_reduce,
                quantity=line.quantity,
                product=line.product_id,
                partner=invoice.partner_id,
            )

            for tax_val in taxes_res["taxes"]:
                tax = self.env["account.tax"].browse(tax_val["id"])
                codigo, codigo_porcentaje = self._get_sri_tax_codes(tax)
                entries.append(
                    {
                        "codigo": codigo,
                        "codigo_porcentaje": codigo_porcentaje,
                        "tarifa": tax.amount,
                        "base": tax_val["base"],
                        "valor": tax_val["amount"],
                    }
                )

            if not entries:
                entries.append(
                    {
                        "codigo": "2",
                        "codigo_porcentaje": "0",
                        "tarifa": 0.0,
                        "base": line.price_subtotal,
                        "valor": 0.0,
                    }
                )

            line_taxes[line.id] = entries
        return line_taxes

    def _compute_tax_aggregates(self, invoice):
        """
        Groups taxes by SRI Table 16 (Codigo) and Table 17 (Porcentaje).
        Returns list of dicts for <totalImpuesto>. Untaxed documents still
        produce one IVA 0% aggregate because the SRI XSDs require
        at least one <totalImpuesto>.
        """
        tax_grouped = defaultdict(lambda: {"base": 0.0, "amount": 0.0, "tarifa": 0.0})

        for entries in self._get_l10n_ec_line_taxes(invoice).values():
            for entry in entries:
                key = (entry["codigo"], entry["codigo_porcentaje"])
                tax_grouped[key]["base"] += entry["base"]
                tax_grouped[key]["amount"] += entry["valor"]
                tax_grouped[key]["tarifa"] = entry["tarifa"]

        results = []
        for (code, perc), vals in tax_grouped.items():
            results.append(
                {
                    "codigo": code,
                    "codigo_porcentaje": perc,
                    "tarifa": vals["tarifa"],
                    "base": vals["base"],
                    "amount": vals["amount"],
                }
            )
        return results

    def _get_l10n_ec_modified_doc(self, invoice):
        """
        Values of the document modified by a Nota de Crédito (04) or
        Nota de Débito (05): codDocModificado, numDocModificado and
        fechaEmisionDocSustento per the SRI XSDs.
        """
        original = invoice.reversed_entry_id or invoice.debit_origin_id

        cod_doc = "01"
        num_doc = "001-001-000000000"
        fecha = invoice.invoice_date

        if original:
            cod_doc = original.l10n_latam_document_type_id.code or "01"
            key = original.l10n_ec_sri_access_key or ""
            if len(key) == 49 and key.isdigit():
                num_doc = "%s-%s-%s" % (key[24:27], key[27:30], key[30:39])
            else:
                seq = "".join(c for c in (original.name or "") if c.isdigit())[-9:]
                num_doc = "001-001-%s" % seq.zfill(9)
            fecha = original.invoice_date or fecha

        motivo = (invoice.narration or "").strip() or _("Documento afectado")

        return {
            "cod_doc_modificado": cod_doc,
            "num_doc_modificado": num_doc,
            "fecha_emision_doc_sustento": fecha.strftime("%d/%m/%Y") if fecha else "",
            "motivo": motivo[:300],
        }

    def _get_l10n_ec_edi_values(self, invoice):
        """
        Prepares the dictionary of values for the QWeb template.
        """
        total_discount = 0.0
        for line in invoice.invoice_line_ids:
            if line.discount:
                untaxed = line.price_unit * line.quantity
                discount_amt = untaxed * (line.discount / 100.0)
                total_discount += discount_amt

        taxes = self._compute_tax_aggregates(invoice)
        if not taxes:
            # The SRI XSDs require >= 1 <totalImpuesto>: untaxed documents are
            # declared as IVA 0% over the full untaxed base.
            taxes = [
                {
                    "codigo": "2",
                    "codigo_porcentaje": "0",
                    "tarifa": 0.0,
                    "base": invoice.amount_untaxed,
                    "amount": 0.0,
                }
            ]

        # codigoPorcentaje per Odoo tax id (used by legacy template callers).
        tax_map = {}
        for line in invoice.invoice_line_ids:
            for tax in line.tax_ids:
                tax_map[tax.id] = self._get_sri_tax_codes(tax)[1]

        vals = {
            "move": invoice,
            "company": invoice.company_id,
            "partner": invoice.partner_id,
            "environment": (
                "1" if invoice.company_id.l10n_ec_sri_environment == "test" else "2"
            ),
            "access_key": invoice.l10n_ec_sri_access_key,
            "format_monetary": lambda x: "%.2f" % x,
            "format_float": lambda x, p: ("%." + str(p) + "f") % x,
            "l10n_ec_identifier_code": self._get_l10n_ec_identifier_code(
                invoice.partner_id
            ),
            "vals": {
                "total_sin_impuestos": invoice.amount_untaxed,
                "total_descuento": total_discount,
                "taxes": taxes,
                "pagos": [{"code": "20", "amount": invoice.amount_total}],
                "modificado": self._get_l10n_ec_modified_doc(invoice),
            },
            "tax_map": tax_map,
            "line_taxes": self._get_l10n_ec_line_taxes(invoice),
        }
        return vals

    def _get_l10n_ec_edi_template(self, invoice):
        """
        Map the latam document type (codDoc) to the matching SRI template:
        01 Factura, 03 Liquidación de Compra, 04 Nota de Crédito,
        05 Nota de Débito.
        """
        doc_code = invoice.l10n_latam_document_type_id.code
        if not doc_code:
            doc_code = "04" if invoice.move_type in ("out_refund", "in_refund") else "01"
        return {
            "01": "l10n_ec_edi.l10n_ec_edi_factura",
            "03": "l10n_ec_edi.l10n_ec_edi_liquidacion_compra",
            "04": "l10n_ec_edi.l10n_ec_edi_nota_credito",
            "05": "l10n_ec_edi.l10n_ec_edi_nota_debito",
        }.get(doc_code, "l10n_ec_edi.l10n_ec_edi_factura")

    def _export_l10n_ec_edi(self, invoice):
        """
        Generates the XML content using the template for the document type.
        """
        values = self._get_l10n_ec_edi_values(invoice)
        xml_content = self.env["ir.qweb"]._render(
            self._get_l10n_ec_edi_template(invoice), values
        )
        return xml_content

    def _post_invoice_edi(self, invoices):
        """
        Main entry point for EDI transmission.
        """
        ec_invoices = invoices.filtered(lambda i: i.company_id.country_id.code == "EC")
        if not ec_invoices:
            return super()._post_invoice_edi(invoices)

        res = {}
        for invoice in ec_invoices:
            if not invoice.l10n_ec_sri_access_key:
                invoice._generate_access_key()

            xml_content = self._export_l10n_ec_edi(invoice)

            # Check Active Certificate (New Model Link)
            certificate = invoice.company_id.l10n_ec_certificate_id
            if not certificate or certificate.state != "active":
                res[invoice] = {
                    "error": _("SRI Error: No active Signing Certificate configured.")
                }
                continue

            try:
                # Use AbstractModels from l10n_ec_edi
                signer = self.env["l10n_ec.sri.signer"]
                service = self.env["l10n_ec.sri.service"]

                # Sign
                # The signer expect bytes, xml_content is str
                signed_xml_bytes = signer.sign_xml(
                    xml_content.encode("utf-8"),
                    certificate.content,  # This is binary (base64)
                    certificate.password,
                )

                # Transmit
                env_code = (
                    "1" if invoice.company_id.l10n_ec_sri_environment == "test" else "2"
                )
                response_data = service.send_document(signed_xml_bytes, env_code)

                # Process Response
                if response_data.get("status") == "RECIBIDA":
                    invoice.l10n_ec_sri_status = "sent"
                    invoice.l10n_ec_sri_response = (
                        "RECIBIDA. Waiting for Authorization..."
                    )
                else:
                    invoice.l10n_ec_sri_status = "rejected"
                    msgs = "\n".join(response_data.get("messages", []))
                    invoice.l10n_ec_sri_response = (
                        f"{response_data.get('status')}: {msgs}"
                    )

                invoice.l10n_ec_xml_data = base64.b64encode(signed_xml_bytes)
                res[invoice] = {"success": True, "attachment": invoice.l10n_ec_xml_data}

            except Exception as e:
                _logger.error("EDI Logic Error: %s", str(e), exc_info=True)
                res[invoice] = {"error": _("SRI Transmission Error: %s") % str(e)}

        return res
