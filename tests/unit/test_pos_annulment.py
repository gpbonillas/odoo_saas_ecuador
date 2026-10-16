# -*- coding: utf-8 -*-
"""
POS / SRI Annulment Rules — regression tests
============================================

Run with Odoo (needs l10n_ec_pos installed):

    odoo-bin -d <db> --test-enable -i l10n_ec_pos --stop-after-init

Background (Sprint-5 audit, Specialist Agent F)
------------------------------------------------
Bug found and fixed: `_l10n_ec_is_consumidor_final()` required a partner to
be set, but an ordinary Consumidor Final POS sale normally has NO partner at
all. Every CF ticket was therefore treated as non-CF and became annulable,
breaking the SRI 2026 rule that a transmitted CF comprobante can never be
annulled (and a nota de crédito for CF is also forbidden).
"""
from datetime import datetime, timedelta

from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install", "l10n_ec", "pos")
class TestPosAnnulment(TransactionCase):
    """SRI annulment rules for POS comprobantes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.PO = cls.env.get("pos.order")
        cls.now = datetime.now().date()

    def _order(self, status, auth_date, partner=None):
        order = self.PO.new({"l10n_ec_sri_status": status})
        order.l10n_ec_sri_access_key = "1" * 49
        if auth_date:
            order.l10n_ec_authorization_date = auth_date
        if partner is not None:
            order.partner_id = partner
        return order

    def test_status_field_has_full_state_machine(self):
        """[POS-R1] the SRI transmission state machine is complete."""
        if not self.PO:
            self.skipTest("l10n_ec_pos not installed")
        selection = dict(self.PO._fields["l10n_ec_sri_status"].selection)
        for key in (
            "draft",
            "signed",
            "sent",
            "authorized",
            "rejected",
            "annul_requested",
            "annulled",
        ):
            self.assertIn(key, selection, "missing SRI state %r" % key)

    def test_draft_order_is_annulable(self):
        """[POS-R2] a not-yet-transmitted order can be discarded."""
        if not self.PO:
            self.skipTest("l10n_ec_pos not installed")
        order = self.PO.new({})
        annulable, reason = order._l10n_ec_is_annulable()
        self.assertTrue(annulable, reason)

    def test_authorized_recent_non_cf_is_annulable(self):
        """[POS-R3] a recent authorized ticket (non-CF) is annulable."""
        if not self.PO:
            self.skipTest("l10n_ec_pos not installed")
        partner = self.env["res.partner"].create(
            {"name": "CLIENTE POS", "vat": "1793125212001"}
        )
        order = self._order("authorized", self.now - timedelta(days=2), partner)
        annulable, reason = order._l10n_ec_is_annulable()
        self.assertTrue(annulable, reason)

    def test_authorized_after_deadline_is_blocked(self):
        """[POS-R4] after day 7 of the following month, annulment is blocked."""
        if not self.PO:
            self.skipTest("l10n_ec_pos not installed")
        partner = self.env["res.partner"].create(
            {"name": "CLIENTE POS VIEJO", "vat": "1713488185001"}
        )
        old = self.now - timedelta(days=90)
        order = self._order("authorized", old, partner)
        order.date_order = datetime.combine(old, datetime.min.time())
        annulable, reason = order._l10n_ec_is_annulable()
        self.assertFalse(annulable, "an expired annulment window must block")
        self.assertIn("deadline", reason.lower())

    def test_transmitted_cf_without_partner_is_never_annulable(self):
        """
        [POS-R5] REGRESSION: a CF ticket with NO partner is still CF.

        This is the ordinary Consumidor Final sale. Before the fix,
        _l10n_ec_is_consumidor_final() required a partner, so every real CF
        ticket slipped through and could be annulled.
        """
        if not self.PO:
            self.skipTest("l10n_ec_pos not installed")
        order = self._order("authorized", self.now - timedelta(days=1))
        order.partner_id = False
        self.assertTrue(
            order._l10n_ec_is_consumidor_final(),
            "a ticket with no partner IS a Consumidor Final ticket",
        )
        annulable, reason = order._l10n_ec_is_annulable()
        self.assertFalse(
            annulable, "transmitted CF tickets can never be annulled (SRI 2026)"
        )
        self.assertIn("Consumidor Final", reason)

    def test_transmitted_cf_with_generic_ruc_is_never_annulable(self):
        """[POS-R6] a partner carrying the generic CF RUC is also CF."""
        if not self.PO:
            self.skipTest("l10n_ec_pos not installed")
        cf_ruc = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.consumidor_final_ruc", "9999999999999")
        )
        partner = self.env["res.partner"].create(
            {"name": "CONSUMIDOR FINAL", "vat": cf_ruc}
        )
        order = self._order("authorized", self.now - timedelta(days=1), partner)
        self.assertTrue(order._l10n_ec_is_consumidor_final())
        annulable, reason = order._l10n_ec_is_annulable()
        self.assertFalse(annulable, reason)

    def test_identifier_code_is_07_for_cf(self):
        """[POS-R7] SRI Table 07: CF = code 07, whether or not a partner."""
        if not self.PO:
            self.skipTest("l10n_ec_pos not installed")
        order = self._order("draft", None)
        self.assertEqual(order._l10n_ec_identifier_code(False), "07")
        self.assertEqual(order._l10n_ec_identifier_code(order.partner_id), "07")
