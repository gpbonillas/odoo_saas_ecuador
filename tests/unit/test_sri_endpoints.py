# -*- coding: utf-8 -*-
"""
Unit Tests: SRI endpoint resolution by environment (pure python)
=================================================================

Run directly:
    python3 tests/unit/test_sri_endpoints.py

Background: sri_service.py previously ALWAYS used the company URL fields,
whose defaults point to the TEST host (celcer), even when the company was
in production. Endpoints must be selected by environment.

Covers:
* environment normalization ("1"/"2"/"test"/"production"/"prod"/empty)
* official fallback WSDL URLs for both services and both ambientes
* config-parameter keys/values cross-checked against
  l10n_ec_base/data/l10n_ec_sri_config.xml
"""
import importlib.util
import os
import unittest
import xml.dom.minidom

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MODULE_PATH = os.path.join(_REPO_ROOT, "l10n_ec_edi", "models", "sri_endpoints.py")
_SRI_CONFIG_XML = os.path.join(
    _REPO_ROOT, "l10n_ec_base", "data", "l10n_ec_sri_config.xml"
)

_spec = importlib.util.spec_from_file_location("l10n_ec_edi_sri_endpoints", _MODULE_PATH)
endpoints = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(endpoints)


def _config_parameters():
    """Parse the ir.config_parameter records seeded by l10n_ec_base."""
    dom = xml.dom.minidom.parse(_SRI_CONFIG_XML)
    params = {}
    for record in dom.getElementsByTagName("record"):
        if record.getAttribute("model") != "ir.config_parameter":
            continue
        key = value = None
        for field in record.getElementsByTagName("field"):
            if field.getAttribute("name") == "key":
                key = "".join(n.data for n in field.childNodes if n.nodeType == n.TEXT_NODE)
            elif field.getAttribute("name") == "value":
                value = "".join(n.data for n in field.childNodes if n.nodeType == n.TEXT_NODE)
        if key:
            params[key] = value
    return params


class TestSriEnvironmentKey(unittest.TestCase):
    def test_numeric_environment_codes(self):
        self.assertEqual(endpoints.sri_environment_key("1"), "test")
        self.assertEqual(endpoints.sri_environment_key("2"), "prod")

    def test_word_environment_values(self):
        self.assertEqual(endpoints.sri_environment_key("test"), "test")
        self.assertEqual(endpoints.sri_environment_key("production"), "prod")
        self.assertEqual(endpoints.sri_environment_key("prod"), "prod")
        self.assertEqual(endpoints.sri_environment_key("Production"), "prod")

    def test_empty_values_default_to_test(self):
        for value in (None, False, "", "  "):
            self.assertEqual(endpoints.sri_environment_key(value), "test")


class TestSriFallbackUrls(unittest.TestCase):
    def test_reception_urls(self):
        self.assertEqual(
            endpoints.sri_fallback_url("reception", "test"),
            "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/"
            "RecepcionComprobantesOffline?wsdl",
        )
        self.assertEqual(
            endpoints.sri_fallback_url("reception", "prod"),
            "https://cel.sri.gob.ec/comprobantes-electronicos-ws/"
            "RecepcionComprobantesOffline?wsdl",
        )

    def test_authorization_urls(self):
        self.assertEqual(
            endpoints.sri_fallback_url("authorization", "test"),
            "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/"
            "AutorizacionComprobantesOffline?wsdl",
        )
        self.assertEqual(
            endpoints.sri_fallback_url("authorization", "prod"),
            "https://cel.sri.gob.ec/comprobantes-electronicos-ws/"
            "AutorizacionComprobantesOffline?wsdl",
        )

    def test_production_never_points_to_celcer(self):
        for service in ("reception", "authorization"):
            self.assertNotIn(
                "celcer", endpoints.sri_fallback_url(service, "prod")
            )


class TestSriConfigKeys(unittest.TestCase):
    def test_config_keys_exist_in_l10n_ec_base(self):
        params = _config_parameters()
        for service in ("reception", "authorization"):
            for ambiente in ("test", "prod"):
                key = endpoints.sri_config_key(service, ambiente)
                self.assertIn(key, params, "missing ir.config_parameter %s" % key)
                expected_host = (
                    "celcer.sri.gob.ec" if ambiente == "test" else "cel.sri.gob.ec"
                )
                self.assertIn(expected_host, params[key], key)
                wsdl = endpoints.SERVICE_PATHS[service]
                self.assertIn(wsdl, params[key], key)


if __name__ == "__main__":
    unittest.main()
