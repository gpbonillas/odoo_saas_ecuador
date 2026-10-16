# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FR-AG-12 / N-01 §241 — guardrails del wizard vertical.

Verificación: SRS-VERT §8 (guardrails agro) · N-01 líneas de validación ·
CHG-2026-011. El plan (dry-run) debe declarar:

* ``auto_enable``: caps obligatorias ausentes se activan con explicación
  (``agro`` sin ``cap.inv.stock`` ⇒ auto-enable + razón).
* ``warnings``: ``agro`` + ``size=simple`` ⇒ advertencia (recomendado medium).
* ``needs_data``: ``v.cultivos`` vacío ⇒ pregunta (nunca falla ni inventa
  datos — FR-BR-07 / WIZ-02).
"""
import unittest

from odoo.tests import common, tagged


def _spec(**over):
    base = {
        "code": "inline/test",
        "vertical": "agro",
        "size": "medium",
        "version": "9.9.9",
        "caps": {},
        "params": {},
        "data": {},
    }
    base.update(over)
    return base


@tagged("post_install", "-at_install")
class TestWizardGuardrails(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env["l10n_ec.vertical.template"]
        cls.Param = cls.env["l10n_ec.vertical.param"]

    def test_agro_auto_enables_stock_and_mrp_caps(self):
        plan = self.Template._plan_from_spec(_spec())
        enabled = {a["key"] for a in plan["auto_enable"]}
        self.assertEqual(enabled, {"cap.inv.stock", "cap.mrp"})
        self.assertTrue(plan["caps"]["cap.inv.stock"])
        self.assertTrue(all(a["reason"] for a in plan["auto_enable"]),
                       "auto-enable sin explicación (FR-AG-12)")

    def test_caps_already_present_no_auto_enable(self):
        plan = self.Template._plan_from_spec(
            _spec(caps={"cap.inv.stock": True, "cap.mrp": True}))
        self.assertEqual(plan["auto_enable"], [])

    def test_agro_simple_warns(self):
        plan = self.Template._plan_from_spec(_spec(size="simple"))
        self.assertTrue(plan["warnings"], "agro+simple debió advertir (SRS-VERT §8)")
        self.assertIn("medium", plan["warnings"][0])

    def test_agro_medium_no_warns(self):
        plan = self.Template._plan_from_spec(_spec())
        self.assertEqual(plan["warnings"], [])

    def test_agro_without_cultivos_asks_needs_data(self):
        plan = self.Template._plan_from_spec(_spec())
        self.assertEqual(len(plan["needs_data"]), 1)
        self.assertEqual(plan["needs_data"][0]["field"], "v.cultivos")
        self.assertIn("cultivo", plan["needs_data"][0]["question"].lower())

    def test_agro_with_cultivos_no_needs_data(self):
        self.Param.set_value("v.cultivos", "Cafe,Cacao", value_type="multi",
                             source="USER")
        plan = self.Template._plan_from_spec(_spec())
        self.assertEqual(plan["needs_data"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
