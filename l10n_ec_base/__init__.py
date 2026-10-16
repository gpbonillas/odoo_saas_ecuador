from . import models
# post_init_hook must be a direct attribute of the addon package:
# odoo/modules/loading.py does getattr(py_module, "post_init_hook")(env).
# hooks.py is new in this sprint; without this import every fresh install of
# l10n_ec_base crashed with:
#   AttributeError: module 'odoo.addons.l10n_ec_base' has no attribute
#   'post_init_hook'
from .hooks import post_init_hook  # noqa: F401
