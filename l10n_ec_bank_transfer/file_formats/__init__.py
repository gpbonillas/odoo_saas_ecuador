# -*- coding: utf-8 -*-
"""
Bank file-format registry.

PURE PYTHON (stdlib only) — safe to import from standalone unit tests
and from Odoo code alike.

Every supported bank is one class in its own module; the wizard (and
any report/code) resolves a `bank_code` string to a generator through
`get_generator()`. Adding a bank = add a module + add the class to
LAYOUTS. None of the layouts are certified by the banks — see the
per-bank docstrings and their `# TODO: validate against bank spec`
markers.
"""
from .base import (  # noqa: F401
    ACCOUNT_TYPE_CURRENT,
    ACCOUNT_TYPE_SAVINGS,
    VALID_ACCOUNT_TYPES,
    BankFileError,
    BatchHeader,
    BaseLayoutGenerator,
    PaymentLine,
)
from .pichincha import PichinchaCashManagementLayout
from .guayaquil import GuayaquilMulticashLayout
from .produbanco import ProdubancoLayout
from .pacifico import PacificoLayout
from .austro import AustroLayout
from .bolivariano import BolivarianoLayout
from .loja import LojaLayout
from .internacional import InternacionalLayout
from .ib_cenpe import IbCenpeLayout
from .generic import GenericLayout

LAYOUTS = {
    cls.bank_code: cls
    for cls in (
        PichinchaCashManagementLayout,
        GuayaquilMulticashLayout,
        ProdubancoLayout,
        PacificoLayout,
        AustroLayout,
        BolivarianoLayout,
        LojaLayout,
        InternacionalLayout,
        IbCenpeLayout,
        GenericLayout,
    )
}

DEFAULT_BANK_CODE = "generic"


def get_generator(bank_code):
    """Return a generator *instance* for `bank_code` or raise BankFileError."""
    cls = LAYOUTS.get(bank_code)
    if cls is None:
        raise BankFileError(
            "Banco no soportado: %r. Bancos disponibles: %s"
            % (bank_code, ", ".join(sorted(LAYOUTS)))
        )
    return cls()


def available_bank_codes():
    return sorted(LAYOUTS)
