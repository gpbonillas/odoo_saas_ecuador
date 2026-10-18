# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-10 / DES-02/03/04 — catálogo + loader idempotente de plantillas.

Verificación: SRS-VERT §6.2 FR-AG-10 · ISO-EC-09 DES-02/03/04 · CHG-2026-011.

* catálogo: sync descubre ``<mod>/templates/*.json`` de módulos instalados;
  checksum = sha256 del archivo (valor golden en el test = validación CI,
  ISO-EC-09 §10 "Plantillas con checksum validado en CI").
* dry-run (DES-04): preview NO crea nada.
* idempotencia (DES-03/FR-AG-10): aplicar 2ª vez ⇒ 0 creates, todo skip,
  sin duplicados.
* actualización: si un registro diverge (alguien lo editó a mano), re-aplicar
  lo restaura (update).
* params: TEMPLATE rellena; USER nunca se pisa (FR-AG-12).
"""
import hashlib
import os
import unittest

from odoo import modules as odoo_modules
from odoo.tests import common, tagged

# sha256 de l10n_ec_agro/templates/agro_medium.json (v1.0.0).
# Si edita la plantilla, este test FALLA a propósito: recalcule y actualice
# conscientemente (validación de integridad DES-03 + ISO-EC-09 §10).
GOLDEN_AGRO_MEDIUM_SHA256 = (
    "a7330fd633eb644d0f644db933e22da1c7542428989cfe34657c9a1c42e844ce"
)

CAT_NAMES = [
    "Insumos & Fertilizantes", "Semillas & Plantines", "Cultivos Frescos",
    "Cultivos Procesados", "Envasados & Alimentarios", "Cosméticos & Sanitarios",
]


def _agro_spec_path():
    base = odoo_modules.module.get_module_path("l10n_ec_agro")
    return os.path.join(base, "templates", "agro_medium.json")


@tagged("post_install", "-at_install")
class TestVerticalTemplateCatalog(common.TransactionCase):

    def test_catalog_sync_discovers_agro_template(self):
        Template = self.env["l10n_ec.vertical.template"]
        rows = Template.sync_catalog()
        agro = rows.filtered(lambda r: r.code == "agro/medium")
        self.assertTrue(agro, "agro/medium no está en el catálogo")
        self.assertEqual(agro.vertical, "agro")
        self.assertEqual(agro.size, "medium")
        self.assertEqual(agro.version, "1.0.0")
        self.assertTrue(agro.changelog)

    def test_checksum_matches_file_and_golden(self):
        Template = self.env["l10n_ec.vertical.template"]
        Template.sync_catalog()
        row = Template.search([("code", "=", "agro/medium")], limit=1)
        with open(_agro_spec_path(), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(row.checksum, digest, "checksum del catálogo ≠ sha256 del archivo")
        self.assertEqual(digest, GOLDEN_AGRO_MEDIUM_SHA256,
                         "agro_medium.json cambió sin actualización consciente del golden (DES-03)")

    def test_sync_is_idempotent(self):
        Template = self.env["l10n_ec.vertical.template"]
        n1 = len(Template.sync_catalog())
        n2 = len(Template.sync_catalog())
        self.assertEqual(n1, n2, "sync_catalog duplicó filas")


@tagged("post_install", "-at_install")
class TestVerticalTemplateLoader(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env["l10n_ec.vertical.template"]
        cls.Param = cls.env["l10n_ec.vertical.param"]
        cls.Category = cls.env["product.category"]
        # Estado "primera aplicación": los tests son deterministas aunque el
        # wizard ya se haya usado en esta BD (p.ej. smoke live del bridge);
        # todo se revierte al final del test (TransactionCase).
        cls.env["ir.model.data"].search([
            ("module", "=", "l10n_ec_vertical"),
            ("model", "=", "product.category"),
        ]).unlink()
        cls.Category.search([("name", "in", CAT_NAMES)]).unlink()
        cls.Param.search([]).unlink()
        cls.Template.search([]).unlink()

    def _categories(self):
        return self.Category.search([("name", "in", CAT_NAMES)])

    # -- DES-04: dry-run --------------------------------------------------
    def test_preview_creates_nothing(self):
        plan = self.Template.preview("agro", "medium")
        self.assertTrue(plan["dry_run"])
        self.assertTrue(plan["template"]["checksum_ok"])
        self.assertEqual(plan["summary"]["create"], 6 + 4 + 6)  # cats+params+caps
        self.assertEqual(len(self._categories()), 0, "preview creó datos (violó DES-04)")

    def test_preview_actions_are_all_create_first_time(self):
        plan = self.Template.preview("agro", "medium")
        self.assertTrue(all(r["action"] == "create" for r in plan["records"]))
        self.assertEqual(len(plan["records"]), 6)

    # -- FR-AG-10: aplicar + re-aplicar ----------------------------------
    def test_apply_then_reapply_no_duplicates(self):
        plan1 = self.Template.apply("agro", "medium")
        self.assertTrue(plan1["applied"])
        self.assertEqual(plan1["summary"]["create"], 16)
        self.assertEqual(len(self._categories()), 6)
        row = self.Template.search([("code", "=", "agro/medium")], limit=1)
        self.assertEqual(row.applied_version, "1.0.0")

        plan2 = self.Template.apply("agro", "medium")
        self.assertEqual(plan2["summary"]["create"], 0, "re-aplicar creó registros (FR-AG-10)")
        self.assertTrue(all(r["action"] == "skip" for r in plan2["records"]))
        self.assertEqual(len(self._categories()), 6, "duplicados tras re-aplicar")

    def test_dry_run_apply_creates_nothing(self):
        self.Template.apply("agro", "medium", dry_run=True)
        self.assertEqual(len(self._categories()), 0)

    # -- DEFECT-2026-014: sobrevivir al reload del módulo ----------------
    def test_applied_records_survive_module_reload(self):
        """Los registros aplicados NO deben borrarse al recargar el módulo.

        Odoo borra al final de cada load los registros con xmlid del módulo
        ausentes de sus data files (``ir.model.data._process_end``). Los
        xmlids que ``apply()`` registra dinámicamente deben ir con
        ``noupdate=True`` o una recarga del módulo (p.ej. ``-u`` con tests,
        CHG-2026-014) se lleva puestas las categorías aplicadas.
        """
        self.Template.apply("agro", "medium")
        self.assertEqual(len(self._categories()), 6)
        self.env["ir.model.data"]._process_end({"l10n_ec_vertical"})
        self.assertEqual(
            len(self._categories()), 6,
            "recargar el módulo borró las categorías aplicadas "
            "(xmlids dinámicos sin noupdate=True)")

    # -- DES-03: update de divergencias ----------------------------------
    def test_reapply_repairs_edited_record(self):
        self.Template.apply("agro", "medium")
        cat = self.Category.search([("name", "=", "Cultivos Frescos")], limit=1)
        cat.write({"name": "EDITADO A MANO"})
        plan = self.Template.apply("agro", "medium")
        actions = {r["key"]: r["action"] for r in plan["records"]}
        self.assertEqual(actions["cat_frescos"], "update")
        self.assertTrue(
            self.Category.search([("name", "=", "Cultivos Frescos")], limit=1),
            "re-aplicar no restauró la categoría editada")

    # -- FR-AG-12: params -------------------------------------------------
    def test_apply_sets_template_params(self):
        self.Template.apply("agro", "medium")
        self.assertEqual(self.Param.get_value("v.lotes"), True)
        self.assertEqual(self.Param.get_value("v.analisis_lab"), True)
        self.assertEqual(self.Param.get_value("v.genealogia"), "seed_to_sale")
        self.assertEqual(self.Param.get_value("v.recall"), True)
        # caps del §8 activadas como params
        self.assertEqual(self.Param.get_value("cap.inv.stock"), True)
        self.assertEqual(self.Param.get_value("cap.mrp"), True)

    def test_user_param_never_overwritten(self):
        self.Param.set_value("v.genealogia", "lote_simple", value_type="select",
                             source="USER")
        plan = self.Template.apply("agro", "medium")
        actions = {p["key"]: p["action"] for p in plan["params"]}
        self.assertEqual(actions["v.genealogia"], "skip", "plan debió saltar param USER")
        self.assertEqual(self.Param.get_value("v.genealogia"), "lote_simple")
        self.assertEqual(self.Param.get_value("v.lotes"), True)  # el resto sí aplica


if __name__ == "__main__":
    unittest.main(verbosity=2)
