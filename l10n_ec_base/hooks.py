# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
Hooks de instalación de l10n_ec_base.

Migra los parámetros de configuración GLOBALES legados (ir.config_parameter),
que el antiguo asistente escribía para todo el servidor, a los nuevos campos
POR EMPRESA definidos en models/res_company.py. La migración se aplica a la
primera empresa (root) sólo si el campo correspondiente aún no tiene valor.
"""
import logging

_logger = logging.getLogger(__name__)

# Parámetro global legado → campo res.company
LEGACY_PARAM_TO_COMPANY_FIELD = {
    "l10n_ec.sri_environment": "l10n_ec_sri_environment",
    "l10n_ec.obligado_contabilidad": "l10n_ec_forced_accounting",
    "l10n_ec.contribuyente_especial": "l10n_ec_special_resolution",
    "l10n_ec.agente_retencion": "l10n_ec_withhold_resolution",
}


def _migrate_legacy_config_params(env):
    """Copia los ir.config_parameter legados al primer res.company.

    Idempotente: no pisa valores ya presentes en la empresa. Los campos
    l10n_ec_sri_environment / l10n_ec_forced_accounting /
    l10n_ec_special_resolution / l10n_ec_withhold_resolution los define
    l10n_ec_edi (dependencia); si no están instalados se omiten.
    """
    company = env.company
    ICP = env["ir.config_parameter"].sudo()
    company_fields = env["res.company"]._fields
    vals = {}
    for param, field_name in LEGACY_PARAM_TO_COMPANY_FIELD.items():
        if field_name not in company_fields:
            continue  # l10n_ec_edi aún no instalado en esta BD
        value = ICP.get_param(param, False)
        if not value or company[field_name]:
            continue
        if field_name == "l10n_ec_forced_accounting":
            vals[field_name] = str(value).lower() in ("true", "1", "yes")
        else:
            vals[field_name] = value
    if vals:
        company.sudo().write(vals)
        _logger.info(
            "l10n_ec_base: parámetros globales legados migrados a la empresa "
            "%s: %s", company.name, ", ".join(sorted(vals)),
        )


def post_init_hook(env):
    """Hook post-instalación (Odoo 18: recibe env)."""
    _migrate_legacy_config_params(env)
