# -*- coding: utf-8 -*-
"""
Unit Tests: module manifests vs. data files on disk (pure python)
==================================================================

Run directly:
    python3 tests/unit/test_manifest_data.py

Background: Sprint 1 audit found data files present on disk but missing
from the manifests (they silently never load), e.g. l10n_ec_edi's
edi_templates.xml and l10n_ec_sri's account_move_xml_template.xml.

Covers:
* every data/security/views file on disk is listed in its manifest
* the previously-missing entries are now required manifest members
* known-unloadable legacy files are excluded ON PURPOSE (documented)
* every XML data/view file is well-formed
* the SRI QWeb templates exist with the right root element, version and
  codDoc (static check that does not need an Odoo runtime)
"""
import ast
import os
import unittest
import xml.dom.minidom

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODULES = ("l10n_ec_edi", "l10n_ec_sri")
DATA_DIRS = ("data", "security", "views")

# Files that exist on disk but must NOT be loaded: they target Odoo < 18
# models removed in Odoo 18 (account.account.template, account.tax.template,
# and chart-template records with property_* fields on the now-AbstractModel
# account.chart.template). Loading them breaks module installation.
# Migration/deletion is tracked as a remaining blocker (S1.4).
EXCLUDED_UNLOADABLE = {
    "l10n_ec_sri/data/l10n_ec_chart_data.xml",
    "l10n_ec_sri/data/account.account.template.csv",
    "l10n_ec_sri/data/account.tax.template.csv",
}

# Entries that must be present after the Sprint 1 fixes.
REQUIRED_MANIFEST_ENTRIES = {
    "l10n_ec_edi": {"data/edi_templates.xml"},
    "l10n_ec_sri": {
        "views/account_move_xml_template.xml",
        "data/account.tax.group.csv",
    },
}

# template id -> (root element, version, codDoc)
EXPECTED_TEMPLATES = {
    "l10n_ec_edi_factura": ("factura", "2.1.0", "01"),
    "l10n_ec_edi_liquidacion_compra": ("liquidacionCompra", "1.1.0", "03"),
    "l10n_ec_edi_nota_credito": ("notaCredito", "1.1.0", "04"),
    "l10n_ec_edi_nota_debito": ("notaDebito", "1.0.0", "05"),
}


def _manifest(module):
    path = os.path.join(_REPO_ROOT, module, "__manifest__.py")
    with open(path, encoding="utf-8") as handle:
        return ast.literal_eval(handle.read())


def _files_on_disk(module):
    found = set()
    for data_dir in DATA_DIRS:
        abs_dir = os.path.join(_REPO_ROOT, module, data_dir)
        if not os.path.isdir(abs_dir):
            continue
        for root, _dirs, names in os.walk(abs_dir):
            for name in names:
                full = os.path.join(root, name)
                relpath = os.path.relpath(full, os.path.join(_REPO_ROOT, module))
                found.add("%s/%s" % (module, relpath))
    return found


def _find_template_nodes(template_id):
    """Yield (template element, document) for the given QWeb template id."""
    path = os.path.join(_REPO_ROOT, "l10n_ec_edi", "data", "edi_templates.xml")
    dom = xml.dom.minidom.parse(path)
    for node in dom.getElementsByTagName("template"):
        if node.getAttribute("id") == template_id:
            yield node, dom


def _child_text_by_tag(element, tag):
    for child in element.getElementsByTagName(tag):
        return "".join(
            n.data for n in child.childNodes if n.nodeType in (n.TEXT_NODE, n.CDATA_SECTION_NODE)
        ).strip()
    return None


class TestManifestCoverage(unittest.TestCase):
    def test_every_data_file_is_listed_in_manifest(self):
        for module in MODULES:
            listed = {"%s/%s" % (module, entry) for entry in _manifest(module)["data"]}
            on_disk = _files_on_disk(module) - EXCLUDED_UNLOADABLE
            missing = on_disk - listed
            self.assertFalse(
                missing,
                "%s: files on disk missing from __manifest__.py data: %s"
                % (module, sorted(missing)),
            )

    def test_manifest_entries_exist_on_disk(self):
        for module in MODULES:
            listed = {"%s/%s" % (module, entry) for entry in _manifest(module)["data"]}
            on_disk = _files_on_disk(module)
            ghosts = listed - on_disk
            self.assertFalse(
                ghosts,
                "%s: manifest lists files that do not exist: %s"
                % (module, sorted(ghosts)),
            )

    def test_previously_missing_entries_are_required(self):
        for module, entries in REQUIRED_MANIFEST_ENTRIES.items():
            listed = set(_manifest(module)["data"])
            for entry in entries:
                self.assertIn(
                    entry, listed, "%s must load %s" % (module, entry)
                )

    def test_excluded_files_still_documented_on_disk(self):
        # If someone deletes/migrates them, the EXCLUDED set can be pruned.
        for relpath in EXCLUDED_UNLOADABLE:
            self.assertTrue(
                os.path.isfile(os.path.join(_REPO_ROOT, relpath)),
                "documented dead file disappeared; prune EXCLUDED: %s" % relpath,
            )

    def test_xml_data_files_are_well_formed(self):
        for module in MODULES:
            for relpath in _files_on_disk(module):
                if not relpath.endswith(".xml"):
                    continue
                try:
                    xml.dom.minidom.parse(os.path.join(_REPO_ROOT, relpath))
                except Exception as exc:  # pragma: no cover - failure path
                    self.fail("%s/%s is not well-formed XML: %s" % (module, relpath, exc))


class TestSriTemplates(unittest.TestCase):
    def test_all_document_templates_exist(self):
        for template_id in EXPECTED_TEMPLATES:
            self.assertTrue(
                list(_find_template_nodes(template_id)),
                "missing QWeb template %s" % template_id,
            )

    def test_template_root_version_and_coddoc(self):
        for template_id, (root_tag, version, cod_doc) in EXPECTED_TEMPLATES.items():
            nodes = list(_find_template_nodes(template_id))
            self.assertEqual(len(nodes), 1, template_id)
            template_node, _dom = nodes[0]
            roots = [
                child
                for child in template_node.childNodes
                if child.nodeType == child.ELEMENT_NODE
            ]
            self.assertEqual(len(roots), 1, "%s must have one root element" % template_id)
            root = roots[0]
            self.assertEqual(root.tagName, root_tag, template_id)
            self.assertEqual(root.getAttribute("version"), version, template_id)

            cod_doc_nodes = root.getElementsByTagName("codDoc")
            self.assertTrue(cod_doc_nodes, "%s has no codDoc" % template_id)
            cod_doc_text = "".join(
                n.data
                for n in cod_doc_nodes[0].childNodes
                if n.nodeType in (n.TEXT_NODE, n.CDATA_SECTION_NODE)
            ).strip()
            self.assertEqual(cod_doc_text, cod_doc, template_id)

    def test_templates_do_not_hardcode_percentage_codes(self):
        # Regression: codigoPorcentaje must come from the resolved SRI code
        # (tax['codigo_porcentaje'] / imp['codigo_porcentaje']), never from
        # the raw Odoo tax amount (which wrongly emitted 15 for IVA 15%).
        path = os.path.join(_REPO_ROOT, "l10n_ec_edi", "data", "edi_templates.xml")
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        self.assertNotIn("tax_map.get(tax_line.id, '0')", content)
        self.assertIn("imp['codigo_porcentaje']", content)
        self.assertIn("tax['codigo_porcentaje']", content)

    def test_liquidacion_compra_uses_proveedor_fields(self):
        # LC 1.1.0 declares PROVEEDOR (vendor) fields, not COMPRADOR.
        nodes = list(_find_template_nodes("l10n_ec_edi_liquidacion_compra"))
        root = nodes[0][0].getElementsByTagName("liquidacionCompra")[0]
        for tag in (
            "tipoIdentificacionProveedor",
            "razonSocialProveedor",
            "identificacionProveedor",
            "totalDescuento",
            "importeTotal",
        ):
            self.assertTrue(root.getElementsByTagName(tag), "LC missing %s" % tag)
        self.assertFalse(root.getElementsByTagName("infoFactura"))

    def test_nota_debito_uses_motivos_and_no_detalles(self):
        # ND 1.0.0 has no <detalles>; it requires <motivos> and declares
        # <impuestos> inside <infoNotaDebito>.
        nodes = list(_find_template_nodes("l10n_ec_edi_nota_debito"))
        root = nodes[0][0].getElementsByTagName("notaDebito")[0]
        self.assertTrue(root.getElementsByTagName("motivos"))
        self.assertTrue(root.getElementsByTagName("razon"))
        self.assertFalse(root.getElementsByTagName("detalles"))
        info = root.getElementsByTagName("infoNotaDebito")[0]
        self.assertTrue(info.getElementsByTagName("impuestos"))
        self.assertTrue(info.getElementsByTagName("valorTotal"))


if __name__ == "__main__":
    unittest.main()
