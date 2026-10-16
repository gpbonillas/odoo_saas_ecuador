# -*- coding: utf-8 -*-
from . import test_invoice_emission
from . import test_consumidor_final
from . import test_sri_validation
from . import test_bank_transfer  # pure-python (no Odoo runtime needed)
from . import test_access_key  # pure-python (no Odoo runtime needed)
from . import test_sri_endpoints  # pure-python (no Odoo runtime needed)
from . import test_manifest_data  # pure-python (no Odoo runtime needed)
from . import test_sri_tax_codes  # requires the Odoo test runtime
from . import test_liquidacion_compra  # requires the Odoo test runtime
from . import test_withholding
from . import test_payroll_calc_standalone  # pure-python (no Odoo runtime)
from . import test_reports_ats  # pure-python (books, forms, ATS, estados)
from . import test_nec_chart_static  # pure-python (NEC chart AST check)
from . import test_customs  # requires the Odoo test runtime (l10n_ec_customs)
from . import test_pos_annulment  # requires the Odoo test runtime (l10n_ec_pos)
