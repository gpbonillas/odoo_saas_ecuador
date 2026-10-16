# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ec_identifier_type = fields.Selection(
        [
            ("ruc", "RUC"),
            ("cedula", "Cédula"),
            ("pasaporte", "Pasaporte"),
        ],
        string="Identifier Type",
        help="Type of Ecuadorian Identification",
    )

    l10n_ec_taxpayer_type = fields.Selection(
        [
            ("special", "Contribuyente Especial"),
            ("rimpe_e", "RIMPE Emprendedor"),
            ("rimpe_p", "RIMPE Negocio Popular"),
            ("general", "Régimen General"),
            ("exporter", "Exportador Habitual"),
            ("nonprofit", "Sin Fines de Lucro"),
            ("zede", "ZEDE"),
            ("public_sector", "Sector Público"),
        ],
        string="Taxpayer Type",
    )

    l10n_ec_related_party = fields.Boolean("Related Party (ATS)", default=False)

    # =========================================================================
    # Birth Date and Age - Auto-compute Tercera Edad
    # =========================================================================
    l10n_ec_fecha_nacimiento = fields.Date(
        string="Fecha de Nacimiento",
        help="Fecha de nacimiento para calcular edad automáticamente",
    )
    l10n_ec_edad = fields.Integer(
        string="Edad",
        compute="_compute_edad",
        store=True,
        help="Edad calculada automáticamente desde fecha de nacimiento",
    )
    l10n_ec_tercera_edad = fields.Boolean(
        string="Tercera Edad",
        compute="_compute_tercera_edad",
        store=True,
        help="LORTI Art. 74: Se activa automáticamente si edad ≥ 65 años",
    )

    @api.depends("l10n_ec_fecha_nacimiento")
    def _compute_edad(self):
        """Computes age from birthdate."""
        from datetime import date
        today = date.today()
        for partner in self:
            if partner.l10n_ec_fecha_nacimiento:
                born = partner.l10n_ec_fecha_nacimiento
                age = today.year - born.year - (
                    (today.month, today.day) < (born.month, born.day)
                )
                partner.l10n_ec_edad = age
            else:
                partner.l10n_ec_edad = 0

    @api.depends("l10n_ec_edad", "company_type")
    def _compute_tercera_edad(self):
        """Auto-compute Tercera Edad: person with age >= 65."""
        for partner in self:
            # Only persons can be Tercera Edad, not companies
            if partner.company_type == "person" and partner.l10n_ec_edad >= 65:
                partner.l10n_ec_tercera_edad = True
            else:
                partner.l10n_ec_tercera_edad = False

    # =========================================================================
    # Ley Orgánica de Discapacidades Art. 78: IVA Refund
    # =========================================================================
    l10n_ec_discapacidad = fields.Boolean(
        string="Persona con Discapacidad",
        default=False,
        help="Persona con discapacidad calificada por CONADIS. "
             "Derecho a devolución de IVA según Ley de Discapacidades Art. 78.",
    )
    l10n_ec_discapacidad_porcentaje = fields.Integer(
        string="Porcentaje Discapacidad",
        help="Porcentaje de discapacidad según carnet CONADIS (30% mínimo para beneficios)",
    )
    l10n_ec_discapacidad_carnet = fields.Char(
        string="Nº Carnet CONADIS",
        help="Número de carnet del CONADIS",
    )

    # =========================================================================
    # Entity Type and Special Regimes
    # =========================================================================
    l10n_ec_entity_type = fields.Selection(
        [
            ("sa", "Sociedad Anónima (S.A.)"),
            ("cia_ltda", "Compañía Limitada (Cía. Ltda.)"),
            ("sas", "Sociedad por Acciones Simplificada (S.A.S.)"),
            ("ep", "Empresa Pública (E.P.)"),
            ("fundacion", "Fundación sin Fines de Lucro"),
            ("ong", "ONG / Organismo Internacional"),
            ("cooperativa", "Cooperativa"),
            ("zede", "ZEDE - Zona Especial"),
            ("persona", "Persona Natural"),
        ],
        string="Tipo de Entidad",
        help="Tipo de entidad jurídica para tratamiento tributario",
    )
    l10n_ec_nueva_empresa = fields.Boolean(
        string="Nueva Empresa",
        help="LORTI Art. 9.1 bis: Exoneración de IR por 3 años para nuevas empresas",
    )
    l10n_ec_fecha_constitucion = fields.Date(
        string="Fecha de Constitución",
        help="Fecha de constitución de la empresa",
    )
    l10n_ec_artesano_calificado = fields.Boolean(
        string="Artesano Calificado",
        help="LORTI Art. 56: IVA 0% en servicios de artesanos calificados por JNDA",
    )

    @api.constrains("l10n_ec_discapacidad", "l10n_ec_discapacidad_porcentaje")
    def _check_discapacidad(self):
        """Validates disability percentage if disability is marked."""
        for partner in self:
            if partner.l10n_ec_discapacidad:
                if not partner.l10n_ec_discapacidad_porcentaje:
                    raise ValidationError(
                        _("Debe ingresar el porcentaje de discapacidad (30-100%).")
                    )
                if partner.l10n_ec_discapacidad_porcentaje < 30:
                    raise ValidationError(
                        _("El porcentaje mínimo para beneficios tributarios es 30%.")
                    )

    # =========================================================================
    # DE 045-2025: UAF Certificate for Government Contractors
    # =========================================================================
    l10n_ec_uaf_certificate = fields.Binary(
        string="Certificado UAF",
        attachment=True,
        help="Certificado de la Unidad de Análisis Financiero (UAF). "
        "Requerido por DE 045-2025 para contratistas del Estado.",
    )
    l10n_ec_uaf_certificate_filename = fields.Char(string="UAF Filename")
    l10n_ec_uaf_certificate_date = fields.Date(
        string="Fecha Emisión UAF", help="Fecha de emisión del certificado UAF"
    )
    l10n_ec_uaf_certificate_expiry = fields.Date(
        string="Fecha Vencimiento UAF", help="Fecha de vencimiento del certificado UAF"
    )
    l10n_ec_uaf_valid = fields.Boolean(
        string="UAF Válido",
        compute="_compute_uaf_valid",
        store=True,
        help="Indica si el certificado UAF está vigente",
    )
    l10n_ec_government_contractor = fields.Boolean(
        string="Contratista del Estado",
        default=False,
        help="Marcar si es proveedor de entidades gubernamentales",
    )

    @api.depends("l10n_ec_uaf_certificate", "l10n_ec_uaf_certificate_expiry")
    def _compute_uaf_valid(self):
        """Computes if UAF certificate is valid (exists and not expired)."""
        from datetime import date

        today = date.today()
        for partner in self:
            partner.l10n_ec_uaf_valid = False
            if partner.l10n_ec_uaf_certificate:
                if partner.l10n_ec_uaf_certificate_expiry:
                    partner.l10n_ec_uaf_valid = (
                        partner.l10n_ec_uaf_certificate_expiry >= today
                    )
                else:
                    # Has certificate but no expiry = assume valid
                    partner.l10n_ec_uaf_valid = True

    @api.constrains("l10n_ec_government_contractor", "l10n_ec_uaf_certificate")
    def _check_uaf_required(self):
        """
        DE 045-2025: Government contractors MUST have valid UAF certificate.
        """
        for partner in self:
            if (
                partner.l10n_ec_government_contractor
                and not partner.l10n_ec_uaf_certificate
            ):
                raise ValidationError(
                    _(
                        "DE 045-2025: Contratistas del Estado deben tener un "
                        "Certificado UAF válido.\\n\\n"
                        "Proveedor: %s\\n"
                        "Por favor, adjunte el certificado UAF antes de continuar."
                    )
                    % partner.name
                )

    @api.constrains("vat", "l10n_ec_identifier_type", "country_id")
    def _check_l10n_ec_vat(self):
        """
        Validates the Tax ID (vat) based on the Identifier Type for Ecuador.
        Algorithms: Modulo 10 (Cedula/RUC Natural) and Modulo 11 (RUC Private/Public).
        """
        for partner in self:
            if partner.country_id.code != "EC" or not partner.l10n_ec_identifier_type:
                continue

            vat = partner.vat or ""
            if not vat:
                continue

            if partner.l10n_ec_identifier_type == "pasaporte":
                if len(vat) < 5:
                    raise ValidationError(
                        _("Passport number must be at least 5 characters.")
                    )
                continue

            if not vat.isdigit():
                raise ValidationError(
                    _("Ecuadorian RUC/Cédula must contain only digits.")
                )

            is_ruc = partner.l10n_ec_identifier_type == "ruc"
            expected_len = 13 if is_ruc else 10

            if len(vat) != expected_len:
                raise ValidationError(
                    _("Invalid length for %s. Expected %s digits, got %s.")
                    % (partner.l10n_ec_identifier_type.upper(), expected_len, len(vat))
                )

            if is_ruc and not vat.endswith("001"):
                # Note: SRI allows other suffixes, but 001 is standard. Warning for now?
                # Strict check per requirement: RUC usually ends in 001, but branches exist.
                # We will enforce the Modulo check which is the critical part.
                pass

            if not self._validate_ec_document(vat):
                raise ValidationError(
                    _(
                        "Invalid Ecuadorian Identity Number (%s): Check Digit Verification Failed."
                    )
                    % vat
                )

    def _validate_ec_document(self, document_number):
        """
        Validates Ecuadorian RUC or Cédula.

        CHG-2026-004: port fiel de mcp_server/rules.py (`_ci_ok` /
        `ruc_check_digit_ok`), implementación equivalente a stdnum.ec.ci +
        stdnum.ec.ruc, cross-checkeada contra stdnum con 20.195 casos y 0
        diferencias (ISO-EC-11 §3.1). Correcciones vs. la versión anterior:
        provincias especiales 30/50, 3er dígito de cédula hasta 6 (no solo
        0-5), fallback natural del sector público (stdnum) y dispatch por
        largo exacto (10 / 13).

          - Cédula (10 dígitos): provincia 01-24 + 30/50, 3er dígito <= 6,
            mod-10 == 0.
          - RUC (13 dígitos):
              3er 0-5 natural : establecimiento != 000 + cédula de los 10
              3er 6   público : mod-11 (3,2,7,6,5,4,3,2,1) sobre 9 dígitos;
                                si no, fallback natural de stdnum
              3er 9   jurídica: mod-11 (4,3,2,7,6,5,4,3,2,1) sobre 10 dígitos
              3er 7 u 8       : inválido
        """
        if not isinstance(document_number, str) or not document_number.isdigit():
            return False
        if len(document_number) == 10:
            return self._ec_ci_ok(document_number)
        if len(document_number) == 13:
            return self._ec_ruc_ok(document_number)
        return False

    def _ec_province_ok(self, first2):
        """Provincia 01..24 + códigos especiales 30/50 (stdnum)."""
        return "01" <= first2 <= "24" or first2 in ("30", "50")

    def _ec_ci_ok(self, number):
        """stdnum.ec.ci: 10 dígitos, provincia válida, 3er dígito <= 6,
        mod-10 == 0."""
        if len(number) != 10:
            return False
        if not self._ec_province_ok(number[:2]):
            return False
        if number[2] > "6":
            return False
        total = 0
        for i, n in enumerate(number):
            p = (2, 1)[i % 2] * int(n)   # pesos alternados 2,1,2,1,...
            total += p - 9 if p > 9 else p
        return total % 10 == 0

    def _ec_mod11_sum(self, number, weights):
        """stdnum.ec.ruc._checksum: suma ponderada módulo 11 (válida == 0)."""
        return sum(w * int(n) for w, n in zip(weights, number)) % 11

    def _ec_ruc_ok(self, number):
        """stdnum.ec.ruc: dispatch por 3er dígito (ver docstring madre)."""
        if not self._ec_province_ok(number[:2]):
            return False
        third = number[2]
        if third < "6":                                   # persona natural
            return number[-3:] != "000" and self._ec_ci_ok(number[:10])
        if third == "6":                                  # sector público
            if (number[-4:] != "0000"
                    and self._ec_mod11_sum(
                        number[:9], (3, 2, 7, 6, 5, 4, 3, 2, 1)) == 0):
                return True
            return number[-3:] != "000" and self._ec_ci_ok(number[:10])
        if third == "9":                                  # persona jurídica
            return (number[-3:] != "000"
                    and self._ec_mod11_sum(
                        number[:10], (4, 3, 2, 7, 6, 5, 4, 3, 2, 1)) == 0)
        return False                                      # 3er dígito 7 u 8

    # =========================================================================
    # SRI AUTO-LOAD: Carga automática de datos del SRI al ingresar RUC
    # =========================================================================

    @api.onchange("vat")
    def _onchange_vat_load_sri(self):
        """
        Carga automáticamente los datos del contribuyente desde el SRI
        cuando se ingresa un RUC válido de Ecuador.
        """
        if not self.vat:
            return

        # Solo para Ecuador o si no hay país definido
        if self.country_id and self.country_id.code != "EC":
            return

        vat = str(self.vat).strip()

        # Solo consultar si parece un RUC ecuatoriano (13 dígitos)
        if len(vat) != 13 or not vat.isdigit():
            return

        # Evitar consultas repetidas
        if hasattr(self, "_sri_loaded_ruc") and self._sri_loaded_ruc == vat:
            return

        try:
            service = self.env["l10n_ec.sri.ruc.service"]
            result = service.consultar_ruc(vat)

            if result.get("success"):
                data = result["data"]

                # Auto-completar campos
                if not self.name or self.name == "/":
                    self.name = data.get("razon_social", "")

                if data.get("nombre_comercial"):
                    self.company_registry = data.get("nombre_comercial")

                # Dirección
                if not self.street:
                    self.street = data.get("direccion", "")
                if not self.city:
                    self.city = data.get("canton", "")

                # Contacto
                if not self.phone and data.get("telefono"):
                    self.phone = data.get("telefono")
                if not self.email and data.get("email"):
                    self.email = data.get("email")

                # País Ecuador
                if not self.country_id:
                    self.country_id = self.env.ref("base.ec")

                # Tipo de identificación
                self.l10n_ec_identifier_type = "ruc"

                # Tipo de contribuyente según SRI (CHG-2026-003: los valores
                # SRI son "SI"/"NO" — un "NO" no puede caer en "special" por
                # ser truthy, y régimen GENERAL debe terminar en general).
                regimen = (data.get("regimen_rimpe")
                           or data.get("regimen") or "").upper()
                if "EMPRENDEDOR" in regimen:
                    self.l10n_ec_taxpayer_type = "rimpe_e"
                elif "POPULAR" in regimen:
                    self.l10n_ec_taxpayer_type = "rimpe_p"
                elif str(data.get("contribuyente_especial") or "").upper() == "SI":
                    self.l10n_ec_taxpayer_type = "special"
                else:
                    self.l10n_ec_taxpayer_type = "general"

                # Marcar como cargado
                self._sri_loaded_ruc = vat

                # Advertir si no está ACTIVO
                estado = data.get("estado", "").upper()
                if estado and estado != "ACTIVO":
                    return {
                        "warning": {
                            "title": "⚠️ Contribuyente No Activo",
                            "message": f"El contribuyente '{data.get('razon_social')}' tiene estado: {estado}. "
                            f"Verifique en el SRI antes de continuar.",
                        }
                    }

        except Exception as e:
            # Silenciamos errores para no interrumpir el flujo
            import logging

            _logger = logging.getLogger(__name__)
            _logger.warning(f"Error al consultar SRI para RUC {vat}: {e}")

    def action_load_from_sri(self):
        """
        Acción para cargar/actualizar datos desde el SRI manualmente.
        Puede ser invocado desde un botón en la vista.
        """
        self.ensure_one()

        if not self.vat:
            raise ValidationError(_("Ingrese un RUC para consultar en el SRI"))

        service = self.env["l10n_ec.sri.ruc.service"]
        result = service.consultar_ruc(self.vat)

        if not result.get("success"):
            raise ValidationError(_(result.get("error", "Error al consultar SRI")))

        data = result["data"]

        # Actualizar todos los campos
        vals = {
            "name": data.get("razon_social", self.name),
            "street": data.get("direccion", self.street),
            "city": data.get("canton", self.city),
            "phone": data.get("telefono", self.phone),
            "email": data.get("email", self.email),
            "country_id": self.env.ref("base.ec").id,
            "l10n_ec_identifier_type": "ruc",
        }

        if data.get("nombre_comercial"):
            vals["company_registry"] = data.get("nombre_comercial")

        self.write(vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "✅ Datos Cargados del SRI",
                "message": f"Contribuyente: {data.get('razon_social')}\n"
                f"Estado: {data.get('estado')}\n"
                f"Tipo: {data.get('tipo_contribuyente')}",
                "type": "success",
                "sticky": False,
            },
        }
