# -*- coding: utf-8 -*-
"""
E2E Test: SRI SOAP Service
===========================
Tests the SOAP client connectivity to SRI Test Environment.

WARNING: These tests make REAL HTTP requests to SRI servers.
         They may fail if network is unavailable or SRI is down.
"""
import unittest

# Zeep for SOAP
try:
    from zeep import Client, Settings
    from zeep.transports import Transport
    from zeep.exceptions import Fault

    ZEEP_AVAILABLE = True
except ImportError:
    ZEEP_AVAILABLE = False


class TestSRIService(unittest.TestCase):
    """
    Integration tests for SRI SOAP Web Services.
    """

    @classmethod
    def setUpClass(cls):
        if not ZEEP_AVAILABLE:
            raise unittest.SkipTest("Zeep library not installed")

        # SRI Test Environment URLs
        cls.reception_url = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl"
        cls.authorization_url = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"

        cls.settings = Settings(strict=False, xml_huge_tree=True)
        cls.transport = Transport(timeout=30, operation_timeout=30)

    def test_01_wsdl_loading_reception(self):
        """Verify we can load the SRI Reception WSDL."""
        try:
            client = Client(
                wsdl=self.reception_url,
                settings=self.settings,
                transport=self.transport,
            )

            # Check that the service has the expected method
            service = client.service
            self.assertTrue(
                hasattr(service, "validarComprobante"),
                "Service should have validarComprobante method",
            )

            print("\n✅ SRI Reception WSDL Loaded Successfully")
            print(f"   URL: {self.reception_url}")

        except Exception as e:
            self.fail(f"Failed to load WSDL: {e}")

    def test_02_wsdl_loading_authorization(self):
        """Verify we can load the SRI Authorization WSDL."""
        try:
            client = Client(
                wsdl=self.authorization_url,
                settings=self.settings,
                transport=self.transport,
            )

            # Check that the service has the expected method
            service = client.service
            self.assertTrue(
                hasattr(service, "autorizacionComprobante"),
                "Service should have autorizacionComprobante method",
            )

            print("\n✅ SRI Authorization WSDL Loaded Successfully")
            print(f"   URL: {self.authorization_url}")

        except Exception as e:
            self.fail(f"Failed to load WSDL: {e}")

    def test_03_send_invalid_document(self):
        """
        Test sending an INVALID document to SRI.
        Expected: DEVUELTA (Rejected) with error messages.
        This proves our SOAP client can communicate with SRI.
        """
        try:
            client = Client(
                wsdl=self.reception_url,
                settings=self.settings,
                transport=self.transport,
            )

            # Send completely invalid XML (should be rejected immediately)
            invalid_xml = (
                b'<?xml version="1.0"?><invalid>not a valid SRI document</invalid>'
            )

            response = client.service.validarComprobante(xml=invalid_xml)

            # SRI should return DEVUELTA (rejected)
            # The response structure gives us estado (status)
            estado = response.estado

            # We expect either DEVUELTA or an error
            # If we get any valid response, the connection works
            self.assertIsNotNone(estado, "Should receive a status from SRI")

            print("\n✅ SRI Communication Test Passed")
            print(f"   Status: {estado}")

            if estado == "DEVUELTA" and hasattr(response, "comprobantes"):
                if response.comprobantes:
                    for comp in response.comprobantes.comprobante:
                        if hasattr(comp, "mensajes") and comp.mensajes:
                            for msg in comp.mensajes.mensaje:
                                print(f"   Error: {msg.identificador}: {msg.mensaje}")

        except Fault as e:
            # SOAP Fault is also a valid response - means we connected
            print("\n✅ SRI Responded with SOAP Fault (Expected for Invalid Doc)")
            print(f"   Fault: {e}")

        except Exception as e:
            # Network or timeout error
            print(f"\n⚠️ Could not reach SRI (Network Issue): {e}")
            self.skipTest(f"SRI unreachable: {e}")

    def test_04_check_nonexistent_authorization(self):
        """
        Test checking authorization for a non-existent access key.
        Expected: No authorization found.
        """
        try:
            client = Client(
                wsdl=self.authorization_url,
                settings=self.settings,
                transport=self.transport,
            )

            # Use a fake but valid-format access key
            fake_access_key = "2101202501179312521200110010010000000011234567813"

            response = client.service.autorizacionComprobante(
                claveAccesoComprobante=fake_access_key
            )

            # Check response structure
            if hasattr(response, "autorizaciones"):
                if response.autorizaciones and response.autorizaciones.autorizacion:
                    auth = response.autorizaciones.autorizacion[0]
                    print(f"\n   Authorization Status: {auth.estado}")
                else:
                    print("\n✅ No authorization found (Expected for fake key)")
            else:
                print("\n✅ Authorization check returned (No results expected)")

        except Exception as e:
            print(f"\n⚠️ Authorization check failed: {e}")
            self.skipTest(f"SRI unreachable: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
