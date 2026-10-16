# -*- coding: utf-8 -*-
"""
Tests del asistente de configuración (auditoría items 2-5):

* el asistente escribe configuración POR EMPRESA (res.company), nunca
  ir.config_parameter globales;
* persiste estándar del plan de cuentas, tipo de persona, régimen y método
  de contabilización;
* el hook de migración copia parámetros globales legados a la empresa.
"""
from odoo.tests import common, tagged

from odoo.addons.l10n_ec_base.hooks import _migrate_legacy_config_params


@tagged("post_install", "-at_install")
class TestCompanySetupWizard(common.TransactionCase):

    def _make_wizard(self, **overrides):
        vals = {
            "company_ruc": "1793125212001",
            "company_name": "PRUEBA SRI S.A.",
            "sri_environment": "test",
            "obligado_contabilidad": True,
            "chart_template": "ecuador_niif",
            "accounting_method": "cash",
            "person_type": "juridica",
            "regimen": "general",
        }
        vals.update(overrides)
        return self.env["l10n_ec.company.setup.wizard"].create(vals)

    def test_configure_writes_company_not_config_params(self):
        wizard = self._make_wizard()
        wizard.action_configure_company()
        company = self.env.company

        # --- por empresa -------------------------------------------------
        self.assertEqual(company.l10n_ec_sri_environment, "test")
        self.assertTrue(company.l10n_ec_forced_accounting)
        self.assertEqual(company.l10n_ec_chart_standard, "ecuador_niif")
        self.assertEqual(company.l10n_ec_accounting_method, "cash")
        self.assertEqual(company.l10n_ec_person_type, "juridica")
        self.assertEqual(company.l10n_ec_regimen, "general")

        # --- NO globales -------------------------------------------------
        ICP = self.env["ir.config_parameter"].sudo()
        self.assertFalse(
            ICP.get_param("l10n_ec.sri_environment"),
            "El asistente aún escribe el ambiente SRI como parámetro global",
        )
        self.assertFalse(ICP.get_param("l10n_ec.obligado_contabilidad"))

    def test_configure_installs_chart_when_missing(self):
        company = self.env.company
        if company.chart_template == "ec":
            self.skipTest("La empresa ya tiene el plan de cuentas NEC")
        wizard = self._make_wizard()
        wizard.action_configure_company()
        self.assertEqual(company.chart_template, "ec")

    def test_contribuyente_especial_writes_resolution(self):
        wizard = self._make_wizard(
            contribuyente_especial="CAR-12345",
            agente_retencion="AG-000123",
        )
        wizard.action_configure_company()
        company = self.env.company
        self.assertEqual(company.l10n_ec_special_resolution, "CAR-12345")
        self.assertEqual(company.l10n_ec_withhold_resolution, "AG-000123")
        self.assertTrue(company.l10n_ec_withhold_agent)
        self.assertEqual(company.l10n_ec_taxpayer_type, "special")

    def test_guess_regimen_rimpe(self):
        wizard = self._make_wizard(regimen_rimpe="RIMPE NEGOCIO POPULAR")
        self.assertEqual(wizard._guess_regimen(), "rimpe_negocio_popular")
        wizard.regimen_rimpe = "RIMPE"
        self.assertEqual(wizard._guess_regimen(), "rimpe_empresario")
        wizard.regimen_rimpe = ""
        wizard.contribuyente_especial = "CAR-1"
        self.assertEqual(wizard._guess_regimen(), "contribuyente_especial")

    def test_person_type_from_ruc(self):
        wizard = self._make_wizard(company_ruc="1713488185001")
        wizard._onchange_company_ruc()  # sin red: sólo deduce tipo de persona
        # 3er dígito '1' → persona natural
        self.assertEqual(wizard.person_type, "natural")


@tagged("post_install", "-at_install")
class TestLegacyParamMigration(common.TransactionCase):

    def test_migration_copies_params_to_company(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("l10n_ec.sri_environment", "production")
        ICP.set_param("l10n_ec.obligado_contabilidad", "True")
        ICP.set_param("l10n_ec.contribuyente_especial", "CAR-777")
        ICP.set_param("l10n_ec.agente_retencion", "AG-999")

        company = self.env.company
        company.l10n_ec_sri_environment = False
        company.l10n_ec_forced_accounting = False
        company.l10n_ec_special_resolution = False
        company.l10n_ec_withhold_resolution = False

        _migrate_legacy_config_params(self.env)

        self.assertEqual(company.l10n_ec_sri_environment, "production")
        self.assertTrue(company.l10n_ec_forced_accounting)
        self.assertEqual(company.l10n_ec_special_resolution, "CAR-777")
        self.assertEqual(company.l10n_ec_withhold_resolution, "AG-999")

    def test_migration_does_not_override_company_values(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("l10n_ec.sri_environment", "production")

        company = self.env.company
        company.l10n_ec_sri_environment = "test"

        _migrate_legacy_config_params(self.env)
        self.assertEqual(
            company.l10n_ec_sri_environment, "test",
            "La migración pisó un valor ya configurado en la empresa",
        )
