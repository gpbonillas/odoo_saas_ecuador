# -*- coding: utf-8 -*-
"""
CHG-2026-003 — Parser del servicio SRI contra el payload REAL.

El endpoint ConsolidadoContribuyente cambió de esquema (verificado en vivo
2026-10-16, ver docs/srs/SRS_WIZARD_COMPANY_EC.md §2.4):

  * estadoContribuyente        -> estadoContribuyenteRuc
  * obligadoContabilidad       -> obligadoLlevarContabilidad
  * regimenRimpe               -> regimen
  * fechas planas              -> informacionFechasContribuyente{} (anidado)
  * NO trae dirección/teléfono/correo/CIIU; trae representantesLegales[]
    y banderas rojas (contribuyenteFantasma / transaccionesInexistente).

Antes de este cambio el parser leía las llaves viejas => estado siempre "",
obligado_contabilidad siempre False y fechas siempre vacías, lo que rompía
el guard WIZ-07 (estado ACTIVO) en validar_y_cargar_ruc.

IDs de prueba exclusivos (D-04): 1793125212001 (CANNACHAIN S.A.S.) y
1713488185001 (RUC natural de la cédula aprobada 1713488185).
"""
from unittest import mock

from odoo.tests import common, tagged

# Payload RAW real, 16 claves exactas, capturado en vivo 2026-10-16
# (misma captura documentada en SRS_WIZARD_COMPANY_EC.md §2.4).
RAW_CANNACHAIN = {
    "numeroRuc": "1793125212001",
    "razonSocial": "CANNACHAIN S.A.S. ",
    "estadoContribuyenteRuc": "ACTIVO",
    "actividadEconomicaPrincipal": "CULTIVO DE LINO Y CÁÑAMO.",
    "tipoContribuyente": "SOCIEDAD",
    "regimen": "GENERAL",
    "categoria": None,
    "obligadoLlevarContabilidad": "SI",
    "agenteRetencion": "NO",
    "contribuyenteEspecial": "NO",
    "informacionFechasContribuyente": {
        "fechaInicioActividades": "2021-02-26 00:00:00.0",
        "fechaCese": "",
        "fechaReinicioActividades": "",
        "fechaActualizacion": "2025-01-15 11:12:14.0",
    },
    "representantesLegales": [
        {"identificacion": "1716341274",
         "nombre": "ENCALADA EGUEZ VICTOR AUGUSTO"},
    ],
    "motivoCancelacionSuspension": None,
    "contribuyenteFantasma": "NO",
    "transaccionesInexistente": "NO",
}

# Esquema VIEJO del SRI (por si revierte): llaves planas y otros nombres.
RAW_LEGACY = {
    "numeroRuc": "1713488185001",
    "razonSocial": "CADENA PEÑA ADRIAN RAFAEL",
    "estadoContribuyente": "ACTIVO",
    "tipoContribuyente": "PERSONA NATURAL",
    "obligadoContabilidad": "NO",
    "regimenRimpe": "GENERAL",
    "fechaInicioActividades": "1999-03-09 00:00:00.0",
    "fechaActualizacion": "2021-07-26 10:00:11.0",
    "contribuyenteEspecial": "NO",
    "agenteRetencion": "NO",
}


@tagged("post_install", "-at_install")
class TestSriRucParser(common.TransactionCase):
    """_parse_sri_response debe mapear el esquema real y el legado."""

    def _parse(self, raw):
        return self.env["l10n_ec.sri.ruc.service"]._parse_sri_response(raw)

    # ------------------------------------------------------------------ esquema real
    def test_real_schema_core(self):
        data = self._parse(RAW_CANNACHAIN)
        self.assertEqual(data["ruc"], "1793125212001")
        # trim: razonSocial viene con espacio final
        self.assertEqual(data["razon_social"], "CANNACHAIN S.A.S.")
        self.assertEqual(data["estado"], "ACTIVO")          # llave nueva
        self.assertEqual(data["tipo_contribuyente"], "SOCIEDAD")
        self.assertEqual(data["regimen"], "GENERAL")
        self.assertTrue(data["obligado_contabilidad"])      # llave nueva
        self.assertEqual(data["actividad_economica"],
                         "CULTIVO DE LINO Y CÁÑAMO.")

    def test_real_schema_nested_dates(self):
        data = self._parse(RAW_CANNACHAIN)
        self.assertEqual(data["fecha_inicio_actividades"],
                         "2021-02-26 00:00:00.0")           # anidado
        self.assertEqual(data["fecha_actualizacion"],
                         "2025-01-15 11:12:14.0")           # anidado
        self.assertEqual(data["fecha_cese"], "")
        self.assertEqual(data["fecha_reinicio_actividades"], "")

    def test_real_schema_flags_and_reps(self):
        data = self._parse(RAW_CANNACHAIN)
        self.assertEqual(data["contribuyente_especial"], "NO")
        self.assertEqual(data["agente_retencion"], "NO")
        self.assertEqual(data["contribuyente_fantasma"], "NO")
        self.assertEqual(data["transacciones_inexistentes"], "NO")
        # None -> "" (nunca None)
        self.assertEqual(data["motivo_cancelacion_suspension"], "")
        self.assertEqual(data["categoria"], "")
        self.assertEqual(len(data["representantes_legales"]), 1)
        self.assertEqual(data["representantes_legales"][0]["identificacion"],
                         "1716341274")

    def test_real_schema_missing_fields_default_empty(self):
        # El consolidado NO devuelve dirección/teléfono/CIIU: contrato estable
        data = self._parse(RAW_CANNACHAIN)
        for key in ("nombre_comercial", "direccion", "calle", "telefono",
                    "email", "provincia", "canton", "codigo_actividad",
                    "estado_establecimiento", "clase_contribuyente"):
            self.assertEqual(data[key], "", key)
        self.assertEqual(data["schema_version"], "consolidado-2026")

    # ------------------------------------------------------------------ esquema legado
    def test_legacy_schema_fallback(self):
        data = self._parse(RAW_LEGACY)
        self.assertEqual(data["estado"], "ACTIVO")       # llave vieja
        self.assertFalse(data["obligado_contabilidad"])
        self.assertEqual(data["fecha_inicio_actividades"],
                         "1999-03-09 00:00:00.0")        # llave plana
        self.assertEqual(data["fecha_actualizacion"],
                         "2021-07-26 10:00:11.0")
        self.assertEqual(data["regimen_rimpe"], "GENERAL")
        self.assertEqual(data["representantes_legales"], [])

    # ------------------------------------------------------------------ guard WIZ-07
    def test_validar_y_cargar_ruc_gate_activo(self):
        """Con estado ACTIVO real el gate deja pasar (antes siempre fallaba)."""
        service = self.env["l10n_ec.sri.ruc.service"]
        with mock.patch.object(
            type(service), "consultar_ruc", autospec=True,
            return_value={"success": True,
                          "data": self._parse(RAW_CANNACHAIN)},
        ):
            result = service.validar_y_cargar_ruc("1793125212001")
        self.assertTrue(result.get("success"))
        self.assertNotIn("warning", result)

    def test_validar_y_cargar_ruc_gate_no_activo(self):
        raw = dict(RAW_CANNACHAIN, estadoContribuyenteRuc="SUSPENDIDO")
        service = self.env["l10n_ec.sri.ruc.service"]
        with mock.patch.object(
            type(service), "consultar_ruc", autospec=True,
            return_value={"success": True, "data": self._parse(raw)},
        ):
            result = service.validar_y_cargar_ruc("1793125212001")
        self.assertFalse(result.get("success"))
        self.assertTrue(result.get("warning"))
        self.assertIn("SUSPENDIDO", result.get("error", ""))
