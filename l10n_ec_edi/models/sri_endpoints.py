# -*- coding: utf-8 -*-
"""
SRI web-service endpoint resolution by environment.

Pure-python helper (NO Odoo imports) so it can be unit-tested standalone.
The environment must always drive the endpoint: the test ambiente lives on
celcer.sri.gob.ec and production on cel.sri.gob.ec. Configuration keys are
seeded by l10n_ec_base/data/l10n_ec_sri_config.xml.
"""

# Values accepted for "environment" anywhere in the codebase:
# l10n_ec_edi passes "1"/"2", l10n_ec_sri passes the company selection
# value ("test"/"production").
PRODUCTION_ENVIRONMENTS = ("2", "prod", "production")

SERVICE_PATHS = {
    "reception": "RecepcionComprobantesOffline",
    "authorization": "AutorizacionComprobantesOffline",
}

CONFIG_KEYS = {
    ("reception", "test"): "l10n_ec.sri_reception_url_test",
    ("reception", "prod"): "l10n_ec.sri_reception_url_prod",
    ("authorization", "test"): "l10n_ec.sri_authorization_url_test",
    ("authorization", "prod"): "l10n_ec.sri_authorization_url_prod",
}

HOSTS = {
    "test": "celcer.sri.gob.ec",
    "prod": "cel.sri.gob.ec",
}


def sri_environment_key(environment):
    """Normalize any environment value to 'test' or 'prod'."""
    if environment in (None, False, "", "1"):
        return "test"
    if str(environment).strip().lower() in PRODUCTION_ENVIRONMENTS:
        return "prod"
    return "test"


def sri_config_key(service, ambiente):
    """ir.config_parameter key holding the WSDL URL for service/ambiente."""
    return CONFIG_KEYS[(service, ambiente)]


def sri_fallback_url(service, ambiente):
    """Official SRI WSDL URL used when the config parameter is not set."""
    return "https://%s/comprobantes-electronicos-ws/%s?wsdl" % (
        HOSTS[ambiente],
        SERVICE_PATHS[service],
    )
