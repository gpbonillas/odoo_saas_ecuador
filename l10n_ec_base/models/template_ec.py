# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""
Plan de Cuentas Ecuatoriano — NEC 2026 (Normas Ecuatorianas de Contabilidad).

Este módulo es la ÚNICA fuente del plan de cuentas. Los antiguos CSV muertos
(``data/account.account.template.csv`` y ``data/account.tax.template.csv``)
fueron eliminados: nunca se cargaban porque su ruta/ubicación no coincidía con
lo que ``account.chart.template._parse_csv`` espera
(``data/template/<modelo>-<template>.csv``).

Mecánica de carga (Odoo 18 ``account/models/chart_template.py``):

* Las llaves de cada diccionario SIN punto se tratan como xmlids parciales y se
  prefijan con ``account.<empresa_id>_``. Por eso las llaves de este archivo son
  el código NEC **sin puntos** (invariante: ``llave == code.replace('.', '')``).
* El código NEC visible con puntos va en el campo explícito ``"code"``.
* Los valores SIN punto se resuelven vía ``account.<empresa_id>_<llave>`` contra
  los registros ya creados (p. ej. ``"tax_group_iva"`` → grupo de impuestos
  definido en ``_get_ec_account_tax_group``); un valor que CONTIENE punto se
  trata como xmlid completo.
* Los grupos de impuestos se definen DENTRO del template (no en XML data):
  ``_load`` borra los registros contables de la empresa (incluidos
  ``account.tax.group`` con ``company_id``) antes de recrearlos; grupos en XML
  quedarían eliminados y sus xmlids rotos.

Códigos reservados (NO crear — otros módulos del repo resuelven cuentas por
código y aceptan el primer match, a veces sin validar el nombre):

* ``2.01.03.02`` / ``2.01.03.03`` → candidatos de l10n_ec_withholding para
  retención IR/IVA por pagar (resolvemos por NOMBRE: "…Fuente… por Pagar" /
  "Retención IVA por Pagar" en 2.01.05.04/.05).
* ``2.01.04.01``..``2.01.04.03`` → candidatos de retención/payroll (el IVA por
  pagar vive a nivel de grupo 2.01.04, sin hijos).
* ``2.01.05.01``..``2.01.05.03`` → candidatos de payroll para sueldos/décimos
  (aceptación silenciosa de cuenta única equivocada); por eso los hijos de
  retenciones son 2.01.05.04/.05.
"""
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    # =====================================================================
    # TEMPLATE DATA + PROPIEDADES POR EMPRESA
    # =====================================================================
    @template("ec")
    def _get_ec_template_data(self):
        return {
            "name": "Ecuador - NEC 2026",
            "code_digits": 6,
            # Cuentas por defecto de partners/productos (llaves = códigos sin puntos)
            "property_account_receivable_id": "1010202",
            "property_account_payable_id": "2010102",
            "property_account_income_categ_id": "40101",
            "property_account_expense_categ_id": "6010101",
            # Prefijos punteados (longitud >= code_digits para que Odoo los use
            # verbatim al crear las cuentas utilitarias: suspense, outstanding
            # receipts/payments, liquidity transfer → 1.01.01.3 .. 1.01.01.6).
            "cash_account_code_prefix": "1.01.01.1",
            "bank_account_code_prefix": "1.01.01.2",
            "transfer_account_code_prefix": "1.01.01.3",
        }

    @template("ec", "res.company")
    def _get_ec_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ec",
                "account_default_pos_receivable_account_id": "1010202",
                "income_currency_exchange_account_id": "4020102",
                "expense_currency_exchange_account_id": "50402",
            }
        }

    # =====================================================================
    # CUENTAS — CLASE 1: ACTIVO (35)
    # =====================================================================
    @template("ec", "account.account")
    def _get_ec_account_account(self):
        def acc(code, name, account_type, reconcile=False):
            return (code, {
                "code": code,
                "name": name,
                "account_type": account_type,
                "reconcile": reconcile,
            })

        entries = [
            # --- 1.01.01 Efectivo y Equivalentes (6) -----------------------
            acc("1.01.01.01", "Caja", "asset_cash", True),
            acc("1.01.01.02", "Bancos", "asset_cash", True),
            acc("1.01.01.03", "Cuentas de Ahorro", "asset_cash", True),
            acc("1.01.01.04", "Caja Chica", "asset_cash", True),
            acc("1.01.01.05", "Bancos del Exterior", "asset_cash", True),
            acc("1.01.01.06", "Inversiones Temporales", "asset_current"),
            # --- 1.01.02 Cuentas por Cobrar (4) ---------------------------
            acc("1.01.02.01", "Clientes Nacionales", "asset_receivable", True),
            acc("1.01.02.02", "Clientes No Relacionados", "asset_receivable", True),
            acc("1.01.02.03", "Otras Cuentas por Cobrar", "asset_receivable", True),
            acc("1.01.02.04", "Provisión de Cuentas Incobrables", "asset_current"),
            # --- 1.01.03 Inventarios (5) ----------------------------------
            acc("1.01.03.01", "Inventario de Mercaderías", "asset_current"),
            acc("1.01.03.02", "Inventario de Materia Prima", "asset_current"),
            acc("1.01.03.03", "Inventario de Productos en Proceso", "asset_current"),
            acc("1.01.03.04", "Inventario de Productos Terminados", "asset_current"),
            acc("1.01.03.05", "Inventario de Suministros y Materiales", "asset_current"),
            # --- 1.01.04 Activos por Impuestos (5) ------------------------
            acc("1.01.04.01", "IVA en Compras", "asset_current"),
            acc("1.01.04.02", "Retenciones IVA Recibidas", "asset_current"),
            acc("1.01.04.03", "Retenciones IR Recibidas", "asset_current"),
            acc("1.01.04.04", "ISD Pagado", "asset_current"),
            acc("1.01.04.05", "Anticipo de Impuesto a la Renta", "asset_current"),
            # --- 1.01.05 Activos Prepagados (2) ---------------------------
            acc("1.01.05.01", "Seguros Pagados por Anticipado", "asset_prepayments"),
            acc("1.01.05.02", "Alquileres Pagados por Anticipado", "asset_prepayments"),
            # --- 1.02.01 Propiedades, Planta y Equipo (11) ----------------
            acc("1.02.01.01", "Terrenos", "asset_fixed"),
            acc("1.02.01.02", "Edificios", "asset_fixed"),
            acc("1.02.01.03", "Mobiliario y Enseres", "asset_fixed"),
            acc("1.02.01.04", "Equipos de Computación", "asset_fixed"),
            acc("1.02.01.05", "Vehículos", "asset_fixed"),
            acc("1.02.01.06", "Maquinaria y Equipo", "asset_fixed"),
            acc("1.02.01.07", "Herramientas", "asset_fixed"),
            acc("1.02.01.08", "Equipos de Transporte Interno", "asset_fixed"),
            acc("1.02.01.09", "Animales y Plantas", "asset_fixed"),
            acc("1.02.01.10", "Desarrollo de Software", "asset_fixed"),
            acc("1.02.01.11", "Diversas Propiedades, Planta y Equipo", "asset_fixed"),
            # --- 1.02.02 Intangibles (2) ----------------------------------
            acc("1.02.02.01", "Marcas y Patentes", "asset_fixed"),
            acc("1.02.02.02", "Programas Informáticos", "asset_fixed"),
            # === CLASE 2: PASIVO (19) =====================================
            # --- 2.01.01 Cuentas por Pagar Comerciales (2) -----------------
            acc("2.01.01.01", "Proveedores Nacionales", "liability_payable", True),
            acc("2.01.01.02", "Proveedores del Exterior", "liability_payable", True),
            # --- 2.01.02 Obligaciones Financieras Corrientes (1) -----------
            acc("2.01.02.01", "Documentos por Pagar Bancarios", "liability_current"),
            # --- 2.01.03 Obligaciones Laborales y Tributarias (3) ----------
            # (.02/.03 reservados: candidatos de retención; ver cabecera)
            acc("2.01.03.01", "Sueldos y Salarios por Pagar", "liability_current"),
            acc("2.01.03.04", "Impuesto a la Renta por Pagar", "liability_current"),
            acc("2.01.03.05", "Préstamos IESS por Pagar", "liability_current"),
            # --- 2.01.04 IVA por Pagar (nivel grupo, sin hijos) ------------
            acc("2.01.04", "IVA por Pagar", "liability_current"),
            # --- 2.01.05 Retenciones por Pagar (.01-.03 reservados) --------
            acc("2.01.05", "Retenciones por Pagar", "liability_current"),
            acc("2.01.05.04", "Retención IR (Fuente) por Pagar", "liability_current"),
            acc("2.01.05.05", "Retención IVA por Pagar", "liability_current"),
            # --- 2.01.06 Obligaciones con el IESS (3) ----------------------
            acc("2.01.06.01", "IESS Aporte Personal por Pagar", "liability_current"),
            acc("2.01.06.02", "IESS Aporte Patronal por Pagar", "liability_current"),
            acc("2.01.06.03", "Fondos de Reserva por Pagar", "liability_current"),
            # --- 2.01.07 Beneficios Sociales (3) --------------------------
            acc("2.01.07.01", "Décimo Tercero por Pagar", "liability_current"),
            acc("2.01.07.02", "Décimo Cuarto por Pagar", "liability_current"),
            acc("2.01.07.03", "Vacaciones por Pagar", "liability_current"),
            # --- 2.01.08 Participación de los Trabajadores (1) -------------
            acc("2.01.08", "Participación de los Trabajadores 15% por Pagar",
                "liability_current"),
            # --- 2.02 Pasivo No Corriente (2) ------------------------------
            acc("2.02.01.01", "Préstamos Bancarios Largo Plazo", "liability_non_current"),
            acc("2.02.02.01", "Jubilación Patronal", "liability_non_current"),
            # === CLASE 3: PATRIMONIO (7) ==================================
            acc("3.01.01.01", "Capital Social", "equity"),
            acc("3.01.02.01", "Reserva Legal", "equity"),
            acc("3.01.02.02", "Reserva de Capitalización", "equity"),
            # 3.01.03.01 es la ÚNICA cuenta "equity_unaffected" (Current Year
            # Earnings) del plan: Odoo 18 solo permite una por compañía
            # (_check_account_type_unique_current_year_earning).
            acc("3.01.03.01", "Utilidad de Ejercicios Anteriores", "equity_unaffected"),
            acc("3.01.03.02", "Pérdida de Ejercicios Anteriores", "equity"),
            acc("3.01.04.01", "Utilidad del Ejercicio", "equity"),
            acc("3.01.04.02", "Pérdida del Ejercicio", "equity"),
            # === CLASE 4: INGRESOS (10) ===================================
            acc("4.01.01", "Ventas 15%", "income"),
            acc("4.01.02", "Ventas 0%", "income"),
            acc("4.01.03", "Ventas Exentas", "income"),
            acc("4.01.04", "Exportaciones", "income"),
            acc("4.01.05", "Ventas 5%", "income"),
            acc("4.01.06", "Prestación de Servicios 15%", "income"),
            acc("4.02.01.01", "Intereses Ganados", "income_other"),
            acc("4.02.01.02", "Otros Ingresos Operacionales", "income_other"),
            acc("4.03.01.01", "Descuentos Obtenidos en Ventas", "income"),
            acc("4.03.01.02", "Devoluciones en Ventas", "income"),
            # === CLASE 5: GASTOS (30) =====================================
            # --- 5.01 Gastos de Administración (16) -----------------------
            acc("5.01.01.01", "Alquileres", "expense"),
            acc("5.01.01.02", "Servicios Básicos", "expense"),
            acc("5.01.01.03", "Útiles y Papelería", "expense"),
            acc("5.01.01.04", "Papeles y Formularios", "expense"),
            acc("5.01.01.05", "Avisos y Publicaciones", "expense"),
            acc("5.01.01.06", "Gastos de Aseo y Limpieza", "expense"),
            acc("5.01.01.07", "Tributarios y Tasas", "expense"),
            acc("5.01.01.08", "Licencias de Software", "expense"),
            acc("5.01.01.09", "Seguros y Pólizas", "expense"),
            acc("5.01.01.10", "Gastos de Representación", "expense"),
            acc("5.01.01.11", "Suscripciones y Membresías", "expense"),
            acc("5.01.01.12", "Mantenimiento y Reparaciones", "expense"),
            acc("5.01.01.13", "Asesorías y Consultorías", "expense"),
            acc("5.01.01.14", "Depreciación de Propiedad, Planta y Equipo",
                "expense_depreciation"),
            acc("5.01.01.15", "Amortización de Intangibles", "expense_depreciation"),
            acc("5.01.01.16", "Cuentas Incobrables", "expense"),
            # --- 5.02 Gastos de Personal (8) ------------------------------
            # (códigos 5.02.0x = candidatos de l10n_ec_hr_payroll gasto_*)
            acc("5.02.01", "Sueldos y Salarios", "expense"),
            acc("5.02.02", "Aporte Patronal IESS", "expense"),
            acc("5.02.03", "Décimo Tercer Sueldo", "expense"),
            acc("5.02.04", "Décimo Cuarto Sueldo", "expense"),
            acc("5.02.05", "Horas Extras y Bonificaciones", "expense"),
            acc("5.02.06", "Fondos de Reserva", "expense"),
            acc("5.02.07", "Vacaciones", "expense"),
            acc("5.02.08", "Alimentación y Transporte del Personal", "expense"),
            # --- 5.03 Gastos de Ventas (3) --------------------------------
            acc("5.03.01", "Publicidad y Propaganda", "expense"),
            acc("5.03.02", "Comisiones y Corretajes", "expense"),
            acc("5.03.03", "Transporte y Fletes", "expense"),
            # --- 5.04 Gastos Financieros (3) ------------------------------
            acc("5.04.01", "Intereses Pagados", "expense"),
            acc("5.04.02", "Diferencias de Cambio", "expense"),
            acc("5.04.03", "Comisiones Bancarias", "expense"),
            # === CLASE 6: COSTOS (2) ======================================
            acc("6.01.01.01", "Costo de Ventas", "expense_direct_cost"),
            acc("6.01.01.02", "Costo de Producción", "expense_direct_cost"),
        ]
        return {code.replace(".", ""): vals for code, vals in entries}

    # =====================================================================
    # GRUPOS DE CUENTAS (jerarquía NEC, prefijos punteados)
    # =====================================================================
    # Las llaves llevan prefijo "nec_" porque comparten el namespace de
    # xmlids account.<empresa_id>_<llave> con las cuentas: sin él, las
    # llaves "20104"/"20105"/"20108" (grupos 2.01.04/.05/.08) chocarían con
    # las cuentas 2.01.04/2.01.05/2.01.08.
    @template("ec", "account.group")
    def _get_ec_account_group(self):
        return {
            # CLASE 1
            "nec_1": {"name": "ACTIVO", "code_prefix_start": "1"},
            "nec_101": {"name": "Activo Corriente", "code_prefix_start": "1.01",
                        "parent_id": "nec_1"},
            "nec_10101": {"name": "Efectivo y Equivalentes de Efectivo",
                          "code_prefix_start": "1.01.01", "parent_id": "nec_101"},
            "nec_10102": {"name": "Cuentas por Cobrar Comerciales",
                          "code_prefix_start": "1.01.02", "parent_id": "nec_101"},
            "nec_10103": {"name": "Inventarios", "code_prefix_start": "1.01.03",
                          "parent_id": "nec_101"},
            "nec_10104": {"name": "Activos por Impuestos",
                          "code_prefix_start": "1.01.04", "parent_id": "nec_101"},
            "nec_10105": {"name": "Activos Prepagados", "code_prefix_start": "1.01.05",
                          "parent_id": "nec_101"},
            "nec_102": {"name": "Activo No Corriente", "code_prefix_start": "1.02",
                        "parent_id": "nec_1"},
            "nec_10201": {"name": "Propiedades, Planta y Equipo",
                          "code_prefix_start": "1.02.01", "parent_id": "nec_102"},
            "nec_10202": {"name": "Intangibles", "code_prefix_start": "1.02.02",
                          "parent_id": "nec_102"},
            # CLASE 2
            "nec_2": {"name": "PASIVO", "code_prefix_start": "2"},
            "nec_201": {"name": "Pasivo Corriente", "code_prefix_start": "2.01",
                        "parent_id": "nec_2"},
            "nec_20101": {"name": "Cuentas por Pagar Comerciales",
                          "code_prefix_start": "2.01.01", "parent_id": "nec_201"},
            "nec_20102": {"name": "Obligaciones Financieras Corrientes",
                          "code_prefix_start": "2.01.02", "parent_id": "nec_201"},
            "nec_20103": {"name": "Obligaciones Laborales y Tributarias Corrientes",
                          "code_prefix_start": "2.01.03", "parent_id": "nec_201"},
            "nec_20104": {"name": "IVA por Pagar", "code_prefix_start": "2.01.04",
                          "parent_id": "nec_201"},
            "nec_20105": {"name": "Retenciones por Pagar", "code_prefix_start": "2.01.05",
                          "parent_id": "nec_201"},
            "nec_20106": {"name": "Obligaciones con el IESS",
                          "code_prefix_start": "2.01.06", "parent_id": "nec_201"},
            "nec_20107": {"name": "Beneficios Sociales por Pagar",
                          "code_prefix_start": "2.01.07", "parent_id": "nec_201"},
            "nec_20108": {"name": "Participación de los Trabajadores",
                          "code_prefix_start": "2.01.08", "parent_id": "nec_201"},
            "nec_202": {"name": "Pasivo No Corriente", "code_prefix_start": "2.02",
                        "parent_id": "nec_2"},
            "nec_20201": {"name": "Obligaciones Financieras Largo Plazo",
                          "code_prefix_start": "2.02.01", "parent_id": "nec_202"},
            "nec_20202": {"name": "Provisiones Largo Plazo",
                          "code_prefix_start": "2.02.02", "parent_id": "nec_202"},
            # CLASE 3
            "nec_3": {"name": "PATRIMONIO", "code_prefix_start": "3"},
            "nec_301": {"name": "Patrimonio", "code_prefix_start": "3.01",
                        "parent_id": "nec_3"},
            "nec_30101": {"name": "Capital Social", "code_prefix_start": "3.01.01",
                          "parent_id": "nec_301"},
            "nec_30102": {"name": "Reservas", "code_prefix_start": "3.01.02",
                          "parent_id": "nec_301"},
            "nec_30103": {"name": "Utilidades Retenidas", "code_prefix_start": "3.01.03",
                          "parent_id": "nec_301"},
            "nec_30104": {"name": "Resultado del Ejercicio",
                          "code_prefix_start": "3.01.04", "parent_id": "nec_301"},
            # CLASE 4
            "nec_4": {"name": "INGRESOS", "code_prefix_start": "4"},
            "nec_401": {"name": "Ingresos Operacionales", "code_prefix_start": "4.01",
                        "parent_id": "nec_4"},
            "nec_402": {"name": "Ingresos No Operacionales", "code_prefix_start": "4.02",
                        "parent_id": "nec_4"},
            "nec_403": {"name": "Descuentos y Devoluciones sobre Ingresos",
                        "code_prefix_start": "4.03", "parent_id": "nec_4"},
            # CLASE 5
            "nec_5": {"name": "GASTOS", "code_prefix_start": "5"},
            "nec_501": {"name": "Gastos de Administración", "code_prefix_start": "5.01",
                        "parent_id": "nec_5"},
            "nec_502": {"name": "Gastos de Personal", "code_prefix_start": "5.02",
                        "parent_id": "nec_5"},
            "nec_503": {"name": "Gastos de Ventas", "code_prefix_start": "5.03",
                        "parent_id": "nec_5"},
            "nec_504": {"name": "Gastos Financieros", "code_prefix_start": "5.04",
                        "parent_id": "nec_5"},
            # CLASE 6
            "nec_6": {"name": "COSTOS", "code_prefix_start": "6"},
            "nec_601": {"name": "Costos de Ventas y Producción",
                        "code_prefix_start": "6.01", "parent_id": "nec_6"},
        }

    # =====================================================================
    # GRUPOS DE IMPUESTOS
    # =====================================================================
    # Definen DENTRO del template (no en XML): al cargar el chart, Odoo 18
    # borra los registros contables existentes de la empresa (incluidos
    # account.tax.group con company_id) antes de recrearlos desde el
    # template; grupos definidos en XML data se eliminan y los xmlids
    # l10n_ec_base.tax_group_* dejan de existir (ref → tax_group_id NULL).
    @template("ec", "account.tax.group")
    def _get_ec_account_tax_group(self):
        def tax_group(name, sequence):
            return {"name": name, "country_id": "base.ec", "sequence": sequence}

        return {
            "tax_group_iva": tax_group("IVA 15%", 10),
            "tax_group_iva_0": tax_group("IVA 0%", 11),
            "tax_group_iva_exempt": tax_group("Exento de IVA", 12),
            "tax_group_iva_5": tax_group("IVA 5% (Construcción)", 13),
            "tax_group_no_iva": tax_group("No Objeto de IVA", 14),
            "tax_group_ret_ir": tax_group("Retención Fuente IR", 20),
            "tax_group_ret_iva": tax_group("Retención IVA", 21),
            "tax_group_ice": tax_group("ICE", 30),
        }

    # =====================================================================
    # IMPUESTOS (IVA 15/5/0/exento/exportación/no-objeto + retenciones + ICE)
    # =====================================================================
    @template("ec", "account.tax")
    def _get_ec_account_tax(self):
        def repartition(account_key, tax_account_key=None):
            """Líneas base + impuesto 100%, para factura y notas de crédito.

            Odoo 18: repartition_type es 'base'/'tax' y document_type
            separa 'invoice' de 'refund' (ambos obligatorios).
            La línea 'base' (ingreso/gasto) va a ``account_key``; la línea
            'tax' (el impuesto propiamente) a ``tax_account_key`` — por
            defecto la misma cuenta.
            """
            tax_account_key = tax_account_key or account_key
            lines = []
            for document_type in ("invoice", "refund"):
                lines += [
                    (0, 0, {"document_type": document_type,
                            "repartition_type": "base", "factor_percent": 100.0,
                            "account_id": account_key}),
                    (0, 0, {"document_type": document_type,
                            "repartition_type": "tax", "factor_percent": 100.0,
                            "account_id": tax_account_key}),
                ]
            return lines

        def retention_repartition(account_key):
            """Retenciones: la base va 0% y el importe (negativo) 100% a la
            cuenta destino, en factura y notas de crédito."""
            lines = []
            for document_type in ("invoice", "refund"):
                lines += [
                    (0, 0, {"document_type": document_type,
                            "repartition_type": "base", "factor_percent": 0.0,
                            "account_id": account_key}),
                    (0, 0, {"document_type": document_type,
                            "repartition_type": "tax", "factor_percent": 100.0,
                            "account_id": account_key}),
                ]
            return lines

        taxes = {
            # ---------------- IVA VENTAS ----------------
            "vat_sales_15": {
                "name": "IVA 15% (Ventas)", "amount": 15.0, "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_iva",
                "repartition_line_ids": repartition("40101", "20104"),
            },
            "vat_sales_5": {
                "name": "IVA 5% (Ventas)", "amount": 5.0, "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_iva_5",
                "repartition_line_ids": repartition("40105", "20104"),
            },
            "vat_sales_0": {
                "name": "IVA 0% (Ventas)", "amount": 0.0, "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_iva_0",
                "repartition_line_ids": repartition("40102", "20104"),
            },
            "vat_sales_exempt": {
                "name": "IVA Exento (Ventas)", "amount": 0.0, "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_iva_exempt",
                "repartition_line_ids": repartition("40103", "20104"),
            },
            "export_sales": {
                "name": "Exportaciones (IVA 0%)", "amount": 0.0,
                "amount_type": "percent", "type_tax_use": "sale",
                "tax_group_id": "tax_group_iva_0",
                "repartition_line_ids": repartition("40104", "20104"),
            },
            "no_iva_sales": {
                "name": "No Objeto de IVA (Ventas)", "amount": 0.0,
                "amount_type": "percent", "type_tax_use": "sale",
                "tax_group_id": "tax_group_no_iva",
                "repartition_line_ids": repartition("40101", "20104"),
            },
            # ---------------- IVA COMPRAS ----------------
            "vat_purchase_15": {
                "name": "IVA 15% (Compras)", "amount": 15.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_iva",
                "repartition_line_ids": repartition("1010401"),
            },
            "vat_purchase_5": {
                "name": "IVA 5% (Compras)", "amount": 5.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_iva_5",
                "repartition_line_ids": repartition("1010401"),
            },
            "vat_purchase_0": {
                "name": "IVA 0% (Compras)", "amount": 0.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_iva_0",
                "repartition_line_ids": repartition("1010401"),
            },
            "vat_purchase_exempt": {
                "name": "IVA Exento (Compras)", "amount": 0.0,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_iva_exempt",
                "repartition_line_ids": repartition("1010401"),
            },
            "no_iva_purchase": {
                "name": "No Objeto de IVA (Compras)", "amount": 0.0,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_no_iva",
                "repartition_line_ids": repartition("1010401"),
            },
            # ---------------- RETENCIÓN EN LA FUENTE ----------------
            # Destino: 2.01.05.04 "Retención IR (Fuente) por Pagar".
            "ir_withholding_1": {
                "name": "Retención IR 1%", "amount": -1.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "ir_withholding_2": {
                "name": "Retención IR 2%", "amount": -2.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "ir_withholding_5": {
                "name": "Retención IR 5%", "amount": -5.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "ir_withholding_10": {
                "name": "Retención IR 10%", "amount": -10.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "ir_withholding_20": {
                "name": "Retención IR 20%", "amount": -20.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "ir_withholding_35": {
                "name": "Retención IR 35%", "amount": -35.0, "amount_type": "percent",
                "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "ir_withholding_100": {
                "name": "Retención IR 100%", "amount": -100.0,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "islr_withholding_1": {
                "name": "Retención ISLR 1% (Bienes Muebles)", "amount": -1.0,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            "islr_withholding_1_75": {
                "name": "Retención ISLR 1.75% (Bienes Muebles)", "amount": -1.75,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_ir",
                "repartition_line_ids": retention_repartition("2010504"),
            },
            # ---------------- RETENCIÓN IVA ----------------
            # Destino: 2.01.05.05 "Retención IVA por Pagar". El 100% del
            # retenido se declara al SRI (F104, casillas 721-731); no existe
            # split SENAE/IESS (ver docs/legal_audit_2026.md).
            # Los porcentajes 30/70 de estos impuestos son tasas de retención
            # válidas (casillas 725 y 729), NO un reparto SRI/IESS.
            "iva_withholding_30": {
                "name": "Retención IVA 30%", "amount": -30.0,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_iva",
                "repartition_line_ids": retention_repartition("2010505"),
            },
            "iva_withholding_70": {
                "name": "Retención IVA 70%", "amount": -70.0,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_iva",
                "repartition_line_ids": retention_repartition("2010505"),
            },
            "iva_withholding_100": {
                "name": "Retención IVA 100%", "amount": -100.0,
                "amount_type": "percent", "type_tax_use": "purchase",
                "tax_group_id": "tax_group_ret_iva",
                "repartition_line_ids": retention_repartition("2010505"),
            },
            # ---------------- ICE ----------------
            "ice_generic": {
                "name": "ICE (Genérico)", "amount": 0.0, "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": "tax_group_ice",
            },
        }
        return taxes
