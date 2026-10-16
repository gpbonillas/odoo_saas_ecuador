from odoo import models, fields


class HrContract(models.Model):
    _inherit = "hr.contract"

    l10n_ec_regime = fields.Selection(
        [
            ("general", "General"),
            ("construction", "Construction"),
            ("agriculture", "Agriculture"),
            ("part_time", "Part Time"),
        ],
        string="IESS Regime",
        default="general",
        required=True,
    )

    l10n_ec_accumulate_13 = fields.Boolean("Accumulate 13th Salary", default=False)
    l10n_ec_accumulate_14 = fields.Boolean("Accumulate 14th Salary", default=False)
    l10n_ec_accumulate_reserve = fields.Boolean(
        "Retain Reserve Funds (Acumulado)",
        default=False,
        help="Acumulado: the employer retains the 8.33% fondos de reserva and "
        "pays them at termination (liquidación). Unchecked (default): the "
        "fondos de reserva are deposited monthly through the IESS planilla — "
        "they are never paid as cash in the rol de pagos "
        "(KB_IESS_2026 §3.2, CUMPLIMIENTO §5.4).",
    )

    # SRI Projections
    l10n_ec_projected_expenses = fields.Float(
        "Projected Personal Expenses (SRI Encuesta)"
    )

    # Jubilación Patronal (Employer Retirement)
    l10n_ec_jubilacion_patronal = fields.Boolean(
        "Apply Jubilación Patronal",
        default=False,
        help="Check if this employee is eligible for Employer Retirement provision (usually >10 years).",
    )
    l10n_ec_jubilacion_accumulated = fields.Float(
        "Accumulated Jubilación Liability",
        help="Total actuarial calculation of liability to date.",
    )
