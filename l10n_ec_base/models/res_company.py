# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
Campos de configuración ecuatoriana POR EMPRESA (res.company).

Históricamente el asistente guardaba sri_environment / obligado_contabilidad /
contribuyente_especial / agente_retencion como ``ir.config_parameter`` GLOBALES
del servidor — incorrecto en bases multiempresa. Esos valores ahora viven aquí
(como los campos l10n_ec_*, que l10n_ec_edi define para facturación
electrónica). El hook post_init_hook de este módulo migra los parámetros
legados a la primera empresa al instalar.
"""
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # =========================================================================
    # TIPO DE CONTRIBUYENTE / RÉGIMEN (por empresa)
    # =========================================================================
    l10n_ec_taxpayer_type = fields.Selection(
        [
            ("general", "Régimen General"),
            ("special", "Contribuyente Especial"),
            ("rimpe_e", "RIMPE Emprendedor"),
            ("rimpe_p", "RIMPE Negocio Popular"),
            ("exporter", "Exportador Habitual"),
            ("nonprofit", "Sin Fines de Lucro"),
            ("zede", "ZEDE"),
            ("public_sector", "Sector Público"),
        ],
        string="Tipo de Contribuyente (EC)",
        default="general",
        help="Régimen tributario de la empresa para efectos SRI (retenciones, "
             "facturación electrónica). Misma selección que res.partner."
    )

    l10n_ec_regimen = fields.Selection(
        [
            ("general", "Régimen General"),
            ("rimpe_empresario", "RIMPE - Empresario"),
            ("rimpe_negocio_popular", "RIMPE - Negocio Popular"),
            ("contribuyente_especial", "Contribuyente Especial"),
            ("regimen_especial", "Régimen Especial (entidades sin fines de lucro)"),
            ("zede", "ZEDE"),
            ("public_sector", "Sector Público"),
        ],
        string="Régimen Tributario (EC)",
        default="general",
        help="Régimen aplicado por el SRI. Se autocompleta desde el RUC en el "
             "asistente de configuración."
    )

    l10n_ec_person_type = fields.Selection(
        [
            ("natural", "Persona Natural"),
            ("juridica", "Persona Jurídica"),
        ],
        string="Tipo de Persona (EC)",
        compute="_compute_l10n_ec_person_type",
        store=True,
        readonly=False,
        help="Derivado del 3er dígito del RUC (0-5 natural, 6-9 jurídica).",
    )

    l10n_ec_contribuyente_especial = fields.Char(
        string="Nº Resolución Contribuyente Especial",
        help="Número de resolución de contribuyente especial (SRI). "
             "Equivalente al antiguo parámetro global "
             "l10n_ec.contribuyente_especial.",
    )

    # =========================================================================
    # MÉTODO DE CONTABILIZACIÓN (por empresa)
    # =========================================================================
    l10n_ec_accounting_method = fields.Selection(
        [
            ("accrual", "Devengado"),
            ("cash", "Caja (lo percibido)"),
        ],
        string="Método de Contabilización (EC)",
        default="accrual",
        help="Elección del contribuyente: contabilizar por lo devengado o por "
             "lo percibido (método de caja, Art. 12 LORI). Los impuestos "
             "electrónicos pueden exigir lo percibido.",
    )

    # =========================================================================
    # ESTÁNDAR DEL PLAN DE CUENTAS (elección del asistente, item auditoría)
    # =========================================================================
    l10n_ec_chart_standard = fields.Selection(
        [
            ("ecuador_niif", "Ecuador — NIIF PYMES (NEC)"),
            ("ecuador_nif", "Ecuador — NIF (NEC)"),
        ],
        string="Estándar de Presentación (EC)",
        default="ecuador_niif",
        help="Estándar elegido en el asistente de configuración. Hoy existe un "
             "único plan de cuentas NEC implementado (l10n_ec_base); el campo "
             "persiste la elección y servirá para distinguir futuras variantes."
    )

    @api.depends("vat")
    def _compute_l10n_ec_person_type(self):
        for company in self:
            vat = (company.vat or "").strip()
            if len(vat) == 13 and vat.isdigit() and vat[2] in "012345":
                company.l10n_ec_person_type = "natural"
            else:
                # RUC jurídica (3er dígito 6-9) o aún sin RUC cargado.
                company.l10n_ec_person_type = "juridica"

    # =========================================================================
    # HOOK CONTABLE — método caja vs devengado (item 5, sólo gancho documentado)
    # =========================================================================
    def _l10n_ec_accounting_criterion(self):
        """Devuelve 'cash' o 'accrual' según la elección de la empresa.

        GANCHO DOCUMENTADO: los módulos de impuestos electrónicos (SRI 2026,
        Res. NAC-DGERCGC-2025-00000017) deben llamar a este método para decidir
        el reconocimiento de ingresos/deducibilidad de gastos. Este módulo base
        NO altera la contabilización por sí mismo; sólo expone la elección.
        """
        self.ensure_one()
        return self.l10n_ec_accounting_method or "accrual"
