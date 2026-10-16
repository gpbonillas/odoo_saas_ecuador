# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nEcTariffHeading(models.Model):
    _name = "l10n_ec.tariff.heading"
    _description = "Tariff Headings (Partida Arancelaria)"

    name = fields.Char("Tariff Code", required=True, index=True)  # e.g. 8471.30.00.00
    description = fields.Char("Description")

    ad_valorem = fields.Float(
        "Ad Valorem (%)",
        default=0.0,
        help="SENAE Ad Valorem duty, 0-40% depending on the tariff "
        "heading (Arancel de Gravámenes).",
    )
    specific_duty = fields.Float("Specific Duty ($/Unit)", default=0.0)
    fodinfa = fields.Float(
        "FODINFA (%)",
        default=0.5,
        help="Fondo de Desarrollo e Infraestructura, 0.5% on CIF "
        "(per-heading override; global default via l10n_ec.fodinfa param).",
    )

    active = fields.Boolean(default=True)

    @api.constrains("ad_valorem")
    def _check_ad_valorem_range(self):
        """SENAE Ad Valorem duty ranges 0-40% by tariff heading."""
        for rec in self:
            if rec.ad_valorem < 0.0 or rec.ad_valorem > 40.0:
                raise ValidationError(
                    _(
                        "Ad Valorem must be between 0%% and 40%% per the "
                        "SENAE tariff schedule (got %.2f%% on %s)."
                    )
                    % (rec.ad_valorem, rec.name)
                )

    @api.constrains("fodinfa")
    def _check_fodinfa_range(self):
        for rec in self:
            if rec.fodinfa < 0.0 or rec.fodinfa > 5.0:
                raise ValidationError(
                    _(
                        "FODINFA must be between 0%% and 5%% (standard 0.5%%); "
                        "got %.2f%% on %s."
                    )
                    % (rec.fodinfa, rec.name)
                )
