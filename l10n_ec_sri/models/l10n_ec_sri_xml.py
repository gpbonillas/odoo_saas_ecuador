# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import ValidationError
import random
import logging

_logger = logging.getLogger(__name__)


class L10nEcSriXml(models.AbstractModel):
    _name = "l10n_ec.sri.xml"
    _description = "SRI XML Generator"

    @api.model
    def generate_access_key(self, record):
        """
        Generate 49-digit Access Key.
        Format:
        [0:8]   Date (DDMMYYYY)
        [8:10]  Doc Type (01)
        [10:23] RUC (1793125212001)
        [23:24] Environment (1 or 2)
        [24:27] Establishment (001)
        [27:30] Emission Point (001)
        [30:39] Sequential (000000001)
        [39:47] Random Number (8 digits)
        [47:48] Emission Type (1)
        [48:49] Verifier Digit (Mod 11)
        """
        # 1. Extraction
        date_inv = record.invoice_date.strftime("%d%m%Y")
        doc_type = record.l10n_latam_document_type_id.code
        if not doc_type:
            doc_type = "04" if record.move_type in ("out_refund", "in_refund") else "01"

        ruc = "".join(c for c in (record.company_id.vat or "") if c.isdigit())
        if len(ruc) != 13:
            raise ValidationError(
                "Company %s has no valid 13-digit RUC configured; "
                "cannot generate the SRI access key." % record.company_id.name
            )

        # Environment: the access key digit is 1 (test) or 2 (production),
        # NOT the company selection value ("test"/"production").
        env = "2" if record.company_id.l10n_ec_sri_environment == "production" else "1"

        # Split Journal code: 001-001 (establecimiento-punto de emisión)
        entity = emission = ""
        journal_code = record.journal_id.code or ""
        if "-" in journal_code:
            entity, emission = [p.strip() for p in journal_code.split("-")[:2]]
        else:
            # Optional account.journal extension fields (not always present)
            entity = str(getattr(record.journal_id, "l10n_ec_entity", "") or "")
            emission = str(getattr(record.journal_id, "l10n_ec_emission", "") or "")

        entity = "".join(c for c in entity if c.isdigit()).zfill(3)[-3:]
        emission = "".join(c for c in emission if c.isdigit()).zfill(3)[-3:]
        if entity == "000" and emission == "000":
            # Fallback: default establishment/emission point 001-001
            entity, emission = "001", "001"
        serie = f"{entity}{emission}"

        # Sequential: digits only, last 9
        sequential = "".join(c for c in (record.name or "") if c.isdigit())[-9:]
        sequential = sequential.zfill(9)

        # Random 8 digits
        code_numeric = f"{random.randint(1, 99999999):08d}"
        emission_type = "1"  # Normal

        # 2. Construction (Pre-Verifier)
        base_key = f"{date_inv}{doc_type}{ruc}{env}{serie}{sequential}{code_numeric}{emission_type}"

        # 3. Check Digit (Modulo 11)
        verifier = self._get_modulo_11(base_key)

        access_key = f"{base_key}{verifier}"

        if len(access_key) != 49 or not access_key.isdigit():
            raise ValidationError(
                f"Generated Access Key is invalid (got {access_key!r}, "
                "expected 49 digits)."
            )

        return access_key

    def _get_modulo_11(self, key):
        """
        Standard SRI Modulo 11 Algorithm
        """
        key = key[::-1]
        total = 0
        factor = 2

        for char in key:
            total += int(char) * factor
            factor += 1
            if factor > 7:
                factor = 2

        remainder = total % 11
        check_digit = 11 - remainder

        if check_digit == 11:
            check_digit = 0
        elif check_digit == 10:
            check_digit = 1

        return str(check_digit)

    @api.model
    def render_xml(self, record):
        """
        Render the SRI XML for *record*.

        Delegates to the l10n_ec_edi template engine (factura 01 /
        liquidación de compra 03 / nota de crédito 04 / nota de débito 05)
        so both emission paths share one XSD-compliant implementation.
        The previously referenced 'l10n_ec_sri.xml_invoice' template never
        existed under that id.
        """
        return self.env["account.edi.format"]._export_l10n_ec_edi(record)
