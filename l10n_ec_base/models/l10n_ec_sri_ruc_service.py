# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Servicio de Consulta RUC - SRI Ecuador

Este módulo consulta el RUC/Cédula en la base de datos del SRI
y retorna la información del contribuyente.

Endpoint SRI:
https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc
"""

import logging
import requests
from odoo import api, models

_logger = logging.getLogger(__name__)

# SRI REST API Endpoints
SRI_RUC_ENDPOINT = "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumerosRuc"
SRI_CEDULA_ENDPOINT = "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorNumeroCedula"
SRI_NOMBRE_ENDPOINT = "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/obtenerPorRazonSocial"

# Timeout for requests
REQUEST_TIMEOUT = 15


class L10nEcSriRucService(models.AbstractModel):
    """
    Servicio para consultar RUC/Cédula en la base de datos del SRI.
    """

    _name = "l10n_ec.sri.ruc.service"
    _description = "Servicio de Consulta RUC SRI Ecuador"

    @api.model
    def consultar_ruc(self, ruc):
        """
        Consulta un RUC en la base de datos del SRI.

        Args:
            ruc (str): Número de RUC (13 dígitos)

        Returns:
            dict: Datos del contribuyente o error
            {
                'success': bool,
                'data': {
                    'ruc': str,
                    'razon_social': str,
                    'nombre_comercial': str,
                    'estado': str,
                    'clase_contribuyente': str,
                    'tipo_contribuyente': str,
                    'obligado_contabilidad': bool,
                    'actividad_economica': str,
                    'direccion': str,
                    'provincia': str,
                    'canton': str,
                },
                'error': str (if success=False)
            }
        """
        if not ruc:
            return {"success": False, "error": "RUC no proporcionado"}

        ruc = str(ruc).strip()

        # Validar formato básico
        if len(ruc) != 13 or not ruc.isdigit():
            return {"success": False, "error": "El RUC debe tener 13 dígitos numéricos"}

        try:
            _logger.info(f"Consultando RUC {ruc} en SRI...")

            # Llamar al API del SRI
            url = f"{SRI_RUC_ENDPOINT}?ruc={ruc}"
            headers = {
                "Accept": "application/json",
                "User-Agent": "Odoo/18.0 SomatechEC/1.0",
            }

            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()

                if data and isinstance(data, list) and len(data) > 0:
                    contribuyente = data[0]

                    # Mapear respuesta del SRI
                    result = {
                        "success": True,
                        "data": self._parse_sri_response(contribuyente),
                    }

                    _logger.info(
                        f"RUC {ruc} encontrado: {result['data'].get('razon_social')}"
                    )
                    return result
                else:
                    return {
                        "success": False,
                        "error": f"RUC {ruc} no encontrado en la base del SRI",
                    }

            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": f"RUC {ruc} no existe en la base del SRI",
                }
            else:
                _logger.warning(f"SRI retornó código {response.status_code}")
                return {
                    "success": False,
                    "error": f"Error de conexión con SRI (código {response.status_code})",
                }

        except requests.Timeout:
            _logger.error("Timeout al consultar SRI")
            return {
                "success": False,
                "error": "Tiempo de espera agotado al consultar el SRI. Intente nuevamente.",
            }
        except requests.ConnectionError:
            _logger.error("Error de conexión con SRI")
            return {
                "success": False,
                "error": "No se pudo conectar con el SRI. Verifique su conexión a internet.",
            }
        except Exception as e:
            _logger.exception(f"Error consultando RUC: {e}")
            return {"success": False, "error": f"Error inesperado: {str(e)}"}

    @api.model
    def consultar_cedula(self, cedula):
        """
        Consulta una cédula en la base de datos del SRI.

        Args:
            cedula (str): Número de cédula (10 dígitos)

        Returns:
            dict: Datos del contribuyente o error
        """
        if not cedula:
            return {"success": False, "error": "Cédula no proporcionada"}

        cedula = str(cedula).strip()

        # Validar formato básico
        if len(cedula) != 10 or not cedula.isdigit():
            return {
                "success": False,
                "error": "La cédula debe tener 10 dígitos numéricos",
            }

        try:
            _logger.info(f"Consultando Cédula {cedula} en SRI...")

            url = f"{SRI_CEDULA_ENDPOINT}?cedula={cedula}"
            headers = {
                "Accept": "application/json",
                "User-Agent": "Odoo/18.0 SomatechEC/1.0",
            }

            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()

                if data and isinstance(data, list) and len(data) > 0:
                    contribuyente = data[0]
                    return {
                        "success": True,
                        "data": self._parse_sri_response(contribuyente),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Cédula {cedula} no encontrada en el SRI",
                    }
            else:
                return {
                    "success": False,
                    "error": f"Error al consultar cédula (código {response.status_code})",
                }

        except Exception as e:
            _logger.exception(f"Error consultando cédula: {e}")
            return {"success": False, "error": str(e)}

    def _parse_sri_response(self, data):
        """
        Parsea la respuesta del SRI a formato estandarizado.

        CHG-2026-003: el ConsolidadoContribuyente cambió de esquema (verificado
        en vivo 2026-10-16, payload real en docs/srs/SRS_WIZARD_COMPANY_EC.md
        §2.4). Llaves nuevas primero, las viejas como fallback por si el SRI
        revierte. Mismo mapeo que mcp_server/sri_client.py::_parse:
          * estadoContribuyente       -> estadoContribuyenteRuc
          * obligadoContabilidad      -> obligadoLlevarContabilidad
          * regimenRimpe              -> regimen
          * fechas planas             -> informacionFechasContribuyente{}
          * agrega: categoria, representantesLegales[], banderas rojas
            (contribuyenteFantasma / transaccionesInexistente) y motivo de
            cancelación/suspensión.
        El consolidado NO trae dirección/teléfono/correo/CIIU: esos campos
        quedan "" y los pregunta el wizard (WIZ-01, datos USER).
        """
        fechas = data.get("informacionFechasContribuyente") or {}

        def pick(*keys, default=""):
            for key in keys:
                if data.get(key) not in (None, ""):
                    return data.get(key)
            return default

        return {
            "ruc": pick("numeroRuc", "ruc"),
            # razonSocial trae espacio final -> trim
            "razon_social": str(pick("razonSocial", "razon_social")).strip(),
            "nombre_comercial": str(
                pick("nombreComercial", "nombre_comercial")).strip(),
            "estado": pick("estadoContribuyenteRuc", "estadoContribuyente"),
            "estado_establecimiento": pick("estadoEstablecimiento"),
            "clase_contribuyente": pick("claseContribuyente"),
            "tipo_contribuyente": pick("tipoContribuyente"),
            "regimen": pick("regimen", "regimenRimpe"),
            "categoria": pick("categoria"),
            "obligado_contabilidad": str(
                pick("obligadoLlevarContabilidad", "obligadoContabilidad",
                     default="NO")).upper() == "SI",
            "actividad_economica": pick("actividadEconomicaPrincipal"),
            "codigo_actividad": pick("codigoActividadEconomica"),
            # Dirección (NO viene en el consolidado: se queda vacío)
            "direccion": pick("direccionMatriz", "direccion"),
            "calle": pick("nombreCalle"),
            "numero": pick("numeroCasa"),
            "interseccion": pick("interseccion"),
            "provincia": pick("nombreProvincia"),
            "canton": pick("nombreCanton"),
            "parroquia": pick("nombreParroquia"),
            # Contacto (NO viene en el consolidado)
            "telefono": pick("telefono1"),
            "email": pick("correo"),
            "direccion_disponible_en_sri": bool(
                pick("direccionMatriz", "nombreProvincia", "nombreCanton")),
            # Fechas (ahora anidadas; planas como fallback)
            "fecha_inicio_actividades": fechas.get(
                "fechaInicioActividades", pick("fechaInicioActividades")),
            "fecha_actualizacion": fechas.get(
                "fechaActualizacion", pick("fechaActualizacion")),
            "fecha_cese": fechas.get("fechaCese", ""),
            "fecha_reinicio_actividades": fechas.get(
                "fechaReinicioActividades", ""),
            # Especiales y banderas rojas
            "contribuyente_especial": pick("contribuyenteEspecial"),
            "agente_retencion": pick("agenteRetencion"),
            "regimen_rimpe": pick("regimenRimpe", "regimen"),
            "contribuyente_fantasma": pick("contribuyenteFantasma"),
            "transacciones_inexistentes": pick("transaccionesInexistente"),
            "motivo_cancelacion_suspension": pick(
                "motivoCancelacionSuspension"),
            "representantes_legales": data.get("representantesLegales") or [],
            "schema_version": "consolidado-2026",
        }

    @api.model
    def validar_y_cargar_ruc(self, ruc):
        """
        Valida un RUC y retorna los datos para auto-completar formularios.

        Este método es llamado desde la UI cuando el usuario ingresa un RUC.
        """
        result = self.consultar_ruc(ruc)

        if not result["success"]:
            return result

        data = result["data"]

        # Verificar estado del contribuyente
        if data.get("estado", "").upper() != "ACTIVO":
            return {
                "success": False,
                "warning": True,
                "error": f"El contribuyente {data.get('razon_social')} tiene estado: {data.get('estado')}",
                "data": data,  # Retornar datos de todas formas
            }

        return result

    @api.model
    def consultar_por_nombre(self, nombre):
        """
        Busca contribuyentes por nombre/razón social en el SRI.

        Args:
            nombre (str): Nombre o razón social a buscar (mínimo 3 caracteres)

        Returns:
            dict: Lista de contribuyentes encontrados o error
            {
                'success': bool,
                'data': [
                    {
                        'ruc': str,
                        'razon_social': str,
                        'estado': str,
                        ...
                    }
                ],
                'error': str (if success=False)
            }
        """
        if not nombre:
            return {"success": False, "error": "Nombre no proporcionado"}

        nombre = str(nombre).strip()

        if len(nombre) < 3:
            return {
                "success": False,
                "error": "Ingrese al menos 3 caracteres para buscar",
            }

        try:
            _logger.info(f"Buscando '{nombre}' en SRI...")

            # URL encode the name
            import urllib.parse

            nombre_encoded = urllib.parse.quote(nombre.upper())

            url = f"{SRI_NOMBRE_ENDPOINT}?razonSocial={nombre_encoded}"
            headers = {
                "Accept": "application/json",
                "User-Agent": "Odoo/18.0 SomatechEC/1.0",
            }

            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()

                if data and isinstance(data, list) and len(data) > 0:
                    # Parsear todos los resultados
                    resultados = [
                        self._parse_sri_response(c) for c in data[:20]
                    ]  # Limitar a 20

                    _logger.info(
                        f"Encontrados {len(resultados)} contribuyentes para '{nombre}'"
                    )
                    return {
                        "success": True,
                        "count": len(resultados),
                        "data": resultados,
                    }
                else:
                    return {
                        "success": False,
                        "error": f'No se encontraron contribuyentes con nombre "{nombre}"',
                    }
            else:
                return {
                    "success": False,
                    "error": f"Error en búsqueda (código {response.status_code})",
                }

        except requests.Timeout:
            return {
                "success": False,
                "error": "Tiempo de espera agotado. Intente nuevamente.",
            }
        except Exception as e:
            _logger.exception(f"Error buscando por nombre: {e}")
            return {"success": False, "error": str(e)}
