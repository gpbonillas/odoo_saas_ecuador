# -*- coding: utf-8 -*-
"""
Verificación ESTÁTICA del plan de cuentas NEC (pure-python, sin runtime Odoo).

Analiza ``l10n_ec_base/models/template_ec.py`` por AST y valida:
  * los seis grupos NEC (1..6) existen como account.group;
  * existen las cuentas del plan oficial con sus nombres;
  * invariante llave == code sin puntos, sin duplicados;
  * todas las referencias internas (properties, repartitions, parents,
    tax groups) resuelven;
  * los códigos "envenenados" por la resolución de cuentas de otros módulos
    (payroll/withholding) NO se crean;
  * compatibilidad payroll (gasto_* 5.02.0x + iess 2.01.06.0x) y fallbacks
    por nombre de retenciones.
"""
import ast
import os
import re
import unicodedata
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE_PATH = os.path.join(REPO, "l10n_ec_base", "models", "template_ec.py")


def _norm(text):
    """minúsculas sin acentos, para comparar nombres NEC."""
    stripped = unicodedata.normalize("NFKD", text or "")
    return "".join(
        char for char in stripped if not unicodedata.combining(char)
    ).lower()


def _parse_template():
    """Devuelve (accounts, groups, template_data, company_data, taxes)."""
    with open(TEMPLATE_PATH, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    klass = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AccountChartTemplate"
    )
    methods = {
        node.name: node for node in klass.body if isinstance(node, ast.FunctionDef)
    }

    # ---- cuentas: lista de llamadas acc("1.01.01.01", "Caja", "asset_cash") ---
    accounts = {}
    for node in ast.walk(methods["_get_ec_account_account"]):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "acc":
            code = ast.literal_eval(node.args[0])
            name = ast.literal_eval(node.args[1])
            account_type = ast.literal_eval(node.args[2])
            accounts[code] = {"name": name, "account_type": account_type}

    # ---- grupos: return {...} literal --------------------------------------
    groups = ast.literal_eval(
        next(node for node in ast.walk(methods["_get_ec_account_group"])
             if isinstance(node, ast.Return)).value
    )

    # ---- template_data / res.company --------------------------------------
    template_data = ast.literal_eval(
        next(node for node in ast.walk(methods["_get_ec_template_data"])
             if isinstance(node, ast.Return)).value
    )
    # res.company: dict literal anidado como llave {self.env.company.id: {...}}
    ret = next(node for node in ast.walk(methods["_get_ec_res_company"])
               if isinstance(node, ast.Return))
    company_data = ast.literal_eval(ret.value.values[0])

    # ---- taxes: asignación local `taxes = {...}` con llamadas a helpers ----
    taxes_assign = next(
        node for node in ast.walk(methods["_get_ec_account_tax"])
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "taxes"
    )
    taxes = {}
    for key_node, value_node in zip(taxes_assign.value.keys,
                                    taxes_assign.value.values):
        xmlid = ast.literal_eval(key_node)
        tax = {}
        for fname_node, fvalue_node in zip(value_node.keys, value_node.values):
            fname = ast.literal_eval(fname_node)
            if fname == "repartition_line_ids":
                # repartition("40101") / retention_repartition("2010504")
                account_key = ast.literal_eval(fvalue_node.args[0])
                tax[fname] = [{"account_id": account_key}]
            else:
                tax[fname] = ast.literal_eval(fvalue_node)
        taxes[xmlid] = tax

    return accounts, groups, template_data, company_data, taxes


def _parse_tax_group_keys():
    """Llaves de account.tax.group definidas dentro del template (dict literal)."""
    tree = ast.parse(open(TEMPLATE_PATH, encoding="utf-8").read())
    klass = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AccountChartTemplate"
    )
    method = next(
        node for node in klass.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_get_ec_account_tax_group"
    )
    ret = next(node for node in ast.walk(method) if isinstance(node, ast.Return))
    return {ast.literal_eval(key) for key in ret.value.keys}


ACCOUNTS, GROUPS, TEMPLATE_DATA, COMPANY_DATA, TAXES = _parse_template()
CODES = set(ACCOUNTS)
KEYS = {code.replace(".", "") for code in CODES}


class TestNecChartStatic(unittest.TestCase):

    # =====================================================================
    # ESTRUCTURA BASE
    # =====================================================================
    def test_six_nec_groups_exist(self):
        prefixes = {g.get("code_prefix_start") for g in GROUPS.values()}
        for digit in "123456":
            self.assertIn(
                digit, prefixes, f"Falta el grupo NEC clase {digit}"
            )
            self.assertTrue(
                any(code.startswith(digit + ".") or code == digit for code in CODES),
                f"La clase {digit} no tiene ninguna cuenta",
            )

    def test_group_counts_by_class(self):
        counts = {
            digit: sum(1 for code in CODES if code.startswith(digit + ".") or code == digit)
            for digit in "123456"
        }
        print("ACCOUNT COUNTS BY NEC GROUP (static):", counts)
        self.assertEqual(sum(counts.values()), len(CODES))

    def test_key_invariant_and_uniqueness(self):
        # llave esperada == code sin puntos; el diccionario se construye con
        # code.replace('.',''), validamos el invariante sobre los códigos.
        self.assertEqual(len(KEYS), len(CODES), "Colisión de llaves sin puntos")
        for code in CODES:
            self.assertRegex(code, r"^\d{1,2}(\.\d{2,4})*$",
                             f"Código NEC mal formado: {code}")

    def test_group_keys_do_not_collide_with_account_keys(self):
        # Regresión: las llaves comparten el namespace xmlid
        # account.<empresa_id>_<llave>; un grupo "20104" y una cuenta "20104"
        # producían "found record of different model" al cargar.
        clash = set(GROUPS) & KEYS
        self.assertEqual(clash, set(),
                         f"Llaves de grupo colisionando con cuentas: {sorted(clash)}")
        for key in GROUPS:
            self.assertTrue(key.startswith("nec_"),
                            f"Llave de grupo sin prefijo nec_: {key}")

    # =====================================================================
    # CUENTAS OFICIALES EXIGIDAS (con etiqueta verbatim, sin acentos)
    # =====================================================================
    REQUIRED = {
        "1.01.01.01": "caja",
        "1.01.01.02": "bancos",
        "1.01.04.01": "iva en compras",
        "1.01.04.02": "retenciones iva recibidas",
        "1.01.04.03": "retenciones ir recibidas",
        "2.01.04": "iva por pagar",
        "2.01.05": "retenciones por pagar",
        "2.01.06.01": "aporte personal",
        "2.01.06.02": "aporte patronal",
        "2.01.06.03": "fondos de reserva",
        "2.01.07.01": "decimo tercer",
        "2.01.07.02": "decimo cuarto",
        "2.01.07.03": "vacaciones",
        "2.01.08": "participacion de los trabajadores 15",
        "4.01.01": "ventas 15",
        "4.01.02": "ventas 0",
        "4.01.03": "ventas exentas",
        "4.01.04": "exportaciones",
        "6.01.01.01": "costo de ventas",
    }

    def test_required_accounts_present_with_labels(self):
        missing = []
        for code, label in self.REQUIRED.items():
            self.assertIn(code, CODES, f"Falta la cuenta oficial {code}")
            name = _norm(ACCOUNTS[code]["name"])
            if label not in name:
                missing.append((code, ACCOUNTS[code]["name"], label))
        self.assertEqual(missing, [], f"Nombres sin la etiqueta del plan: {missing}")

    # =====================================================================
    # REFERENCIAS INTERNAS
    # =====================================================================
    def test_template_property_refs_resolve(self):
        for key, value in TEMPLATE_DATA.items():
            if key.startswith("property_"):
                self.assertIn(value, KEYS,
                              f"Property {key} referencia llave inexistente {value}")

    def test_company_refs_resolve(self):
        for fname, value in COMPANY_DATA.items():
            if fname == "account_fiscal_country_id":
                self.assertEqual(value, "base.ec")
            else:
                self.assertIn(value, KEYS,
                              f"res.company {fname} referencia llave inexistente")

    def test_group_parents_resolve_and_prefixes(self):
        for key, group in GROUPS.items():
            self.assertIn("name", group)
            self.assertRegex(group["code_prefix_start"], r"^\d{1,2}(\.\d{2,4})*$")
            parent = group.get("parent_id")
            if parent:
                self.assertIn(parent, GROUPS, f"parent_id {parent} inexistente")
                # el prefijo del padre debe ser prefijo del hijo
                self.assertTrue(
                    group["code_prefix_start"].startswith(
                        GROUPS[parent]["code_prefix_start"] + "."
                    ),
                    f"Jerarquía inválida: {key} bajo {parent}",
                )

    def test_tax_refs_resolve(self):
        tax_groups = _parse_tax_group_keys()
        # Sin punto: se resuelven vía account.<empresa_id>_<llave> al cargar
        self.assertIn("tax_group_iva", tax_groups)
        self.assertIn("tax_group_ice", tax_groups)
        self.assertNotIn("l10n_ec_base.tax_group_iva", tax_groups,
                         "Los grupos deben ir SIN prefijo de módulo (llaves del template)")
        for xmlid, tax in TAXES.items():
            group = tax.get("tax_group_id")
            self.assertIn(group, tax_groups,
                          f"Impuesto {xmlid}: grupo {group} no existe en el template")
            self.assertNotIn(".", group,
                              f"Impuesto {xmlid}: grupo {group} no debe llevar punto/xmlid")
            for line in tax.get("repartition_line_ids", []):
                account_key = line["account_id"]
                self.assertIn(account_key, KEYS,
                              f"Impuesto {xmlid}: cuenta {account_key} inexistente")

    # =====================================================================
    # CÓDIGOS RESERVADOS (poisoning cross-module) + COMPAT
    # =====================================================================
    POISONED = {
        # withholding: candidates por código SIN validación de nombre
        "2.01.03.02", "2.01.03.03",
        # payroll: candidates únicos que aceptaría en silencio
        "2.01.04.01", "2.01.04.02", "2.01.04.03",
        "2.01.05.01", "2.01.05.02", "2.01.05.03",
    }

    def test_poisoned_codes_absent(self):
        clash = self.POISONED & CODES
        self.assertEqual(clash, set(),
                         f"Códigos reservados creados: {sorted(clash)}")

    def test_single_equity_unaffected_account(self):
        # Odoo 18: solo una cuenta "Current Year Earnings" por compañía
        unaffected = [
            code for code, vals in ACCOUNTS.items()
            if vals.get("account_type") == "equity_unaffected"
        ]
        self.assertEqual(len(unaffected), 1,
                         f"Debe haber exactamente 1 equity_unaffected: {unaffected}")
        self.assertEqual(unaffected[0], "3.01.03.01")

    def test_payroll_candidate_codes_resolve_correctly(self):
        # gasto_* de l10n_ec_hr_payroll (candidate dotted + patrón de nombre)
        expected = {
            "5.02.01": r"sueldos\s+y\s+salarios",
            "5.02.02": r"aporte\s+patronal",
            "5.02.03": r"decimo\s+tercer",
            "5.02.04": r"decimo\s+cuarto",
            "5.02.06": r"fondos?\s+de\s+reserva",
            "2.01.06.01": r"aporte\s+personal",
            "2.01.06.02": r"aporte\s+patronal",
            "2.01.06.03": r"fondos?\s+de\s+reserva",
        }
        for code, pattern in expected.items():
            self.assertIn(code, CODES, f"Payroll necesita la cuenta {code}")
            name = _norm(ACCOUNTS[code]["name"]).replace("é", "e").replace("ó", "o")
            self.assertRegex(name, pattern,
                             f"{code} ({ACCOUNTS[code]['name']}) no cumple {pattern}")

    def test_withholding_name_fallbacks(self):
        def any_match(pattern):
            return any(
                re.search(pattern, _norm(acc["name"]), re.IGNORECASE)
                for acc in ACCOUNTS.values()
            )

        self.assertTrue(any_match(r"fuente.*por pagar"),
                        "Retención IR por pagar sin nombre localizable")
        self.assertTrue(any_match(r"retenc.*iva.*por pagar"),
                        "Retención IVA por pagar sin nombre localizable")
        self.assertTrue(any_match(r"aporte personal"),
                        "Aporte personal sin nombre localizable")

    # =====================================================================
    # MANIFEST / LIMPIEZA DE CSVs MUERTOS (items 1 y 6)
    # =====================================================================
    def test_manifest_category_is_account_chart(self):
        manifest_path = os.path.join(REPO, "l10n_ec_base", "__manifest__.py")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = ast.literal_eval(handle.read())
        self.assertEqual(
            manifest["category"], "Accounting/Localizations/Account Charts",
            "Sin category 'Account Charts' el loader OMITE el template (raíz del bug)",
        )
        self.assertIn("post_init_hook", manifest)

    def test_dead_csvs_removed(self):
        for csv_name in ("account.account.template.csv", "account.tax.template.csv"):
            path = os.path.join(REPO, "l10n_ec_base", "data", csv_name)
            self.assertFalse(os.path.exists(path),
                             f"CSV muerto aún presente: {csv_name}")

    def test_l10n_ec_manifest_declares_functional_modules(self):
        manifest_path = os.path.join(REPO, "l10n_ec", "__manifest__.py")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = ast.literal_eval(handle.read())
        for module in ("l10n_ec_income_tax", "l10n_ec_loans", "l10n_ec_vacation",
                       "l10n_ec_sut", "l10n_ec_bank_transfer", "l10n_ec_portal"):
            self.assertIn(module, manifest["depends"],
                          f"{module} no declarado en depends de l10n_ec")


if __name__ == "__main__":
    unittest.main()
