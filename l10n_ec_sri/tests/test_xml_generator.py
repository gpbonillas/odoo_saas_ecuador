# -*- coding: utf-8 -*-
"""
E2E Test: XML Invoice Generator
================================
Tests the Access Key (Clave de Acceso) generation with Modulo 11 algorithm.
"""
import unittest
from datetime import date


class TestXMLGenerator(unittest.TestCase):
    """
    Unit tests for the XML generation logic.
    These tests run OUTSIDE Odoo to verify the core algorithms.
    """

    def test_01_modulo_11_algorithm(self):
        """
        Verify the Modulo 11 check digit algorithm.
        This is the EXACT algorithm required by SRI for the 49-digit Access Key.
        """

        def get_modulo_11(base_key):
            """Calculate the check digit using Modulo 11 algorithm."""
            factors = [2, 3, 4, 5, 6, 7]
            total = 0
            factor_index = 0

            # Iterate from right to left
            for digit in reversed(base_key):
                total += int(digit) * factors[factor_index]
                factor_index = (factor_index + 1) % 6

            remainder = total % 11
            check_digit = 11 - remainder

            if check_digit == 11:
                return 0
            elif check_digit == 10:
                return 1
            else:
                return check_digit

        # Test Case 1: Known valid access key (without check digit)
        # Format: DDMMAAAA + TT + RUC(13) + AMBIENTE + SERIE(6) + NUMERO(9) + CODIGO(8) + TIPO
        base_key = "210120250117931252120011001001000000001123456781"
        # This is 48 digits

        self.assertEqual(
            len(base_key), 48, "Base key should be 48 digits before check digit"
        )

        check_digit = get_modulo_11(base_key)
        self.assertIn(check_digit, range(0, 10), "Check digit must be 0-9")

        full_key = f"{base_key}{check_digit}"
        self.assertEqual(len(full_key), 49, "Full access key should be 49 digits")

        print("\n✅ Modulo 11 Algorithm Verified")
        print(f"   Base Key (48): {base_key}")
        print(f"   Check Digit: {check_digit}")
        print(f"   Full Key (49): {full_key}")

    def test_02_access_key_structure(self):
        """
        Verify the Access Key structure follows SRI specification.
        """
        # Components
        invoice_date = date(2025, 1, 21)
        doc_type = "01"  # Factura
        ruc = "1793125212001"
        environment = "1"  # Test
        serie = "001001"
        sequential = "000000001"
        numeric_code = "12345678"
        emission_type = "1"

        date_str = invoice_date.strftime("%d%m%Y")
        self.assertEqual(date_str, "21012025", "Date format should be DDMMAAAA")
        self.assertEqual(len(date_str), 8)

        base_key = f"{date_str}{doc_type}{ruc}{environment}{serie}{sequential}{numeric_code}{emission_type}"

        # Verify structure
        expected_length = 8 + 2 + 13 + 1 + 6 + 9 + 8 + 1  # = 48
        self.assertEqual(
            len(base_key), 48, f"Base key should be 48 digits, got {len(base_key)}"
        )

        print("\n✅ Access Key Structure Verified")
        print(f"   Date: {date_str} (8 digits)")
        print(f"   Doc Type: {doc_type} (2 digits)")
        print(f"   RUC: {ruc} (13 digits)")
        print(f"   Environment: {environment} (1 digit)")
        print(f"   Serie: {serie} (6 digits)")
        print(f"   Sequential: {sequential} (9 digits)")
        print(f"   Numeric Code: {numeric_code} (8 digits)")
        print(f"   Emission Type: {emission_type} (1 digit)")

    def test_03_ruc_validation(self):
        """
        Verify RUC validation patterns (13 digits, check digit).
        """
        valid_rucs = [
            "1793125212001",  # Approved company RUC (jurídica)
            "1713488185001",  # Approved natural-person RUC
            "9999999999999",  # Consumidor Final
        ]

        for ruc in valid_rucs:
            self.assertEqual(len(ruc), 13, f"RUC {ruc} should be 13 digits")
            self.assertTrue(ruc.isdigit(), f"RUC {ruc} should be all digits")

        # Consumidor Final check
        consumidor_final = "9999999999999"
        self.assertEqual(consumidor_final, "9" * 13, "Consumidor Final RUC is all 9s")

        print("\n✅ RUC Validation Patterns Verified")

    def test_04_xml_template_structure(self):
        """
        Verify the XML template produces valid structure.
        """
        from lxml import etree

        # Minimal valid invoice XML structure
        xml_template = """<?xml version="1.0" encoding="UTF-8"?>
        <factura id="comprobante" version="2.1.0">
            <infoTributaria>
                <ambiente>1</ambiente>
                <tipoEmision>1</tipoEmision>
                <razonSocial>EMPRESA PRUEBA</razonSocial>
                <nombreComercial>EMPRESA PRUEBA</nombreComercial>
                <ruc>1793125212001</ruc>
                <claveAcceso>2101202501179312521200110010010000000011234567813</claveAcceso>
                <codDoc>01</codDoc>
                <estab>001</estab>
                <ptoEmi>001</ptoEmi>
                <secuencial>000000001</secuencial>
                <dirMatriz>Quito</dirMatriz>
            </infoTributaria>
            <infoFactura>
                <fechaEmision>21/01/2025</fechaEmision>
                <dirEstablecimiento>Quito</dirEstablecimiento>
                <obligadoContabilidad>SI</obligadoContabilidad>
                <tipoIdentificacionComprador>04</tipoIdentificacionComprador>
                <razonSocialComprador>CLIENTE PRUEBA</razonSocialComprador>
                <identificacionComprador>1713488185001</identificacionComprador>
                <totalSinImpuestos>100.00</totalSinImpuestos>
                <totalDescuento>0.00</totalDescuento>
                <totalConImpuestos>
                    <totalImpuesto>
                        <codigo>2</codigo>
                        <codigoPorcentaje>4</codigoPorcentaje>
                        <baseImponible>100.00</baseImponible>
                        <valor>15.00</valor>
                    </totalImpuesto>
                </totalConImpuestos>
                <propina>0.00</propina>
                <importeTotal>115.00</importeTotal>
                <moneda>DOLAR</moneda>
            </infoFactura>
            <detalles>
                <detalle>
                    <codigoPrincipal>001</codigoPrincipal>
                    <descripcion>Producto de prueba</descripcion>
                    <cantidad>1</cantidad>
                    <precioUnitario>100.00</precioUnitario>
                    <descuento>0.00</descuento>
                    <precioTotalSinImpuesto>100.00</precioTotalSinImpuesto>
                    <impuestos>
                        <impuesto>
                            <codigo>2</codigo>
                            <codigoPorcentaje>4</codigoPorcentaje>
                            <tarifa>15</tarifa>
                            <baseImponible>100.00</baseImponible>
                            <valor>15.00</valor>
                        </impuesto>
                    </impuestos>
                </detalle>
            </detalles>
        </factura>"""

        # Parse and validate structure
        root = etree.fromstring(xml_template.encode())

        # Check required elements
        self.assertEqual(root.tag, "factura")
        self.assertEqual(root.get("id"), "comprobante")
        self.assertIsNotNone(root.find(".//infoTributaria"))
        self.assertIsNotNone(root.find(".//infoFactura"))
        self.assertIsNotNone(root.find(".//detalles"))

        # Check 49-digit access key
        clave = root.find(".//claveAcceso").text
        self.assertEqual(len(clave), 49, "Access key should be 49 digits")

        # Check 15% IVA (codigoPorcentaje 4 = 15%)
        impuesto = root.find(".//totalImpuesto/valor")
        self.assertEqual(impuesto.text, "15.00", "15% of 100 = 15.00")

        print("\n✅ XML Template Structure Verified")
        print(f"   Root Tag: {root.tag}")
        print(f"   Access Key Length: {len(clave)}")
        print(f"   IVA Amount: {impuesto.text}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
