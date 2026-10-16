# -*- coding: utf-8 -*-
from odoo import models, fields, api

from . import l10n_ec_payroll_calc as calc


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # SRI 2026: Rebaja Tributaria Inputs
    l10n_ec_family_loads = fields.Integer(
        "Cargas Familiares (SRI)",
        default=0,
        help="Number of legal dependents for Tax Rebate (LORTI Art. 10).",
    )
    l10n_ec_catastrophic_disease = fields.Boolean(
        "Catastrophic/Rare Disease",
        default=False,
        help="Check if employee or dependent has a certified catastrophic disease (Max Rebate 20 Baskets).",
    )

    # MDT: Décimo cuarto payment region (KB_LABOR_SBU_DECIMOS §3):
    #   costa (Costa/Galápagos) -> deadline 15 March
    #   sierra (Sierra/Amazonía) -> deadline 15 August
    l10n_ec_decimo_cuarto_region = fields.Selection(
        [
            ("costa", "Costa / Galápagos (15 marzo)"),
            ("sierra", "Sierra / Amazonía (15 agosto)"),
        ],
        string="Décimo Cuarto Region",
        compute="_compute_decimo_cuarto_region",
        store=True,
        readonly=False,
        help="Region that determines the décimo cuarto period and payment "
        "deadline. Derived from the employee's address province/canton "
        "(l10n_ec.province.region); defaults to "
        "l10n_ec.decimo_cuarto_region_default when unknown.",
    )

    @api.depends(
        "private_state_id.name",
        "private_city",
        "private_country_id.code",
    )
    def _compute_decimo_cuarto_region(self):
        ICP = self.env["ir.config_parameter"].sudo()
        default = ICP.get_param("l10n_ec.decimo_cuarto_region_default") or "sierra"
        # Catalogs come from l10n_ec_base (optional dependency): degrade
        # gracefully to the configured default when they are not installed.
        Province = (
            self.env["l10n_ec.province"].sudo()
            if "l10n_ec.province" in self.env
            else None
        )
        Canton = self.env["l10n_ec.canton"] if "l10n_ec.canton" in self.env else None

        for employee in self:
            region = None
            # Odoo 18: hr.employee stores the home address as flat
            # private_* fields (address_home_id was removed).
            state = employee.private_state_id
            city = employee.private_city
            country = employee.private_country_id
            if state and Province:
                # 1) province directly from the state name
                state_name = state.name
                if state_name:
                    province = Province.search(
                        [("name", "=", state_name)], limit=1
                    )
                    if province:
                        region = province.region
                # 2) canton (city) -> province -> region
                if not region and city and Canton:
                    canton = Canton.search(
                        [("name", "=", city)], limit=1
                    )
                    if canton.province_id:
                        region = canton.province_id.region
            if not region and country and country.code not in (False, "EC"):
                region = default
            employee.l10n_ec_decimo_cuarto_region = (
                calc.normalize_decimo_cuarto_region(region, default=default)
            )
