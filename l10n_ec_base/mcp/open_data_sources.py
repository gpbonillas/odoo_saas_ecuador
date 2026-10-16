# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Ecuador Open Data Sources - Fuentes de Datos Abiertos

Este módulo centraliza todas las fuentes de datos abiertos
de Ecuador requeridas para la localización completa.

Incluye datasets descargables para precargar datos esenciales:
- Catastro SRI
- Arancel Nacional SENAE
- IPC/Canasta Básica INEC
- División territorial
- Códigos tributarios
"""

import logging
from typing import Dict, List, Optional

_logger = logging.getLogger(__name__)


# =============================================================================
# FUENTES DE DATOS ABIERTOS OFICIALES
# =============================================================================

ECUADOR_OPEN_DATA_SOURCES = {
    # -------------------------------------------------------------------------
    # SRI - SERVICIO DE RENTAS INTERNAS
    # -------------------------------------------------------------------------
    'sri': {
        'entity': 'Servicio de Rentas Internas',
        'base_url': 'https://www.sri.gob.ec',
        'datasets': {
            'catastro_contribuyentes': {
                'name': 'Catastro de Contribuyentes',
                'description': 'RUC, razón social, estado, tipo contribuyente',
                'format': 'CSV',
                'delimiter': '|',
                'url': 'https://www.sri.gob.ec/datos-abiertos',
                'update_frequency': 'mensual',
                'use_case': 'Precargar partners con datos oficiales',
            },
            'recaudacion_tributaria': {
                'name': 'Recaudación Tributaria',
                'description': 'Recaudación por tipo de impuesto y período',
                'format': 'CSV',
                'url': 'https://www.sri.gob.ec/datos-abiertos',
                'update_frequency': 'mensual',
            },
            'base_imponible': {
                'name': 'Base Imponible',
                'description': 'Bases imponibles por sector',
                'format': 'CSV',
                'url': 'https://www.sri.gob.ec/datos-abiertos',
            },
            'codigos_retenciones': {
                'name': 'Códigos de Retenciones',
                'description': 'Catálogo oficial de códigos IR e IVA',
                'format': 'PDF/Manual',
                'url': 'https://www.sri.gob.ec/web/intersri/retenciones',
                'preloaded': True,
                'data': {
                    # IR - Retenciones (Tabla 19, Res. NAC-DGERCGC26-00000009)
                    '303': {'rate': 10.0, 'name': 'Honorarios Profesionales'},
                    '304': {'rate': 10.0, 'name': 'Servicios Predomina Intelecto'},
                    '307': {'rate': 3.0, 'name': 'Servicios Mano de Obra'},
                    '308': {'rate': 10.0, 'name': 'Imagen o Renombre'},
                    '309': {'rate': 3.0, 'name': 'Publicidad y Comunicación'},
                    '310': {'rate': 1.0, 'name': 'Transporte'},
                    '312': {'rate': 2.0, 'name': 'Bienes Muebles'},
                    '319': {'rate': 2.0, 'name': 'Arrendamiento Mercantil'},
                    '320': {'rate': 10.0, 'name': 'Arrendamiento Inmuebles'},
                    '322': {'rate': 2.0, 'name': 'Seguros y Reaseguros'},
                    '323': {'rate': 3.0, 'name': 'Rendimientos Financieros'},
                    '325': {'rate': 25.0, 'name': 'Anticipo de Utilidades'},
                    '340': {'rate': 3.0, 'name': 'Impuesto Único Exportación Banano'},
                    '500': {'rate': 25.0, 'name': 'No Residentes - Rentas Inmobiliarias'},
                    # IVA - Retenciones (casilleros F.104, Res. NAC-DGERCGC20-00000061)
                    '721': {'rate': 10.0, 'name': 'Bienes IVA 10%'},
                    '723': {'rate': 20.0, 'name': 'Servicios IVA 20%'},
                    '725': {'rate': 30.0, 'name': 'Contrib. Especial 30%'},
                    '727': {'rate': 50.0, 'name': 'Contrib. Especial 50%'},
                    '729': {'rate': 70.0, 'name': 'Contrib. Especial 70%'},
                    '731': {'rate': 100.0, 'name': 'Liquidación de Compra / Importación Servicios 100%'},
                },
            },
            'tipos_impuestos': {
                'name': 'Tipos de Impuestos 2026',
                'description': 'IVA, IR, ICE vigentes',
                'preloaded': True,
                'data': {
                    'iva_15': {'code': '4', 'rate': 15.0, 'name': 'IVA 15%'},
                    'iva_5': {'code': '5', 'rate': 5.0, 'name': 'IVA 5% Construcción'},
                    'iva_0': {'code': '0', 'rate': 0.0, 'name': 'IVA 0%'},
                    'iva_exento': {'code': '7', 'rate': 0.0, 'name': 'IVA Exento'},
                    'iva_no_objeto': {'code': '6', 'rate': 0.0, 'name': 'No Objeto IVA'},
                },
            },
            'tipos_comprobantes': {
                'name': 'Tipos de Comprobantes Electrónicos',
                'preloaded': True,
                'data': {
                    '01': 'Factura',
                    '03': 'Liquidación de Compra',
                    '04': 'Nota de Crédito',
                    '05': 'Nota de Débito',
                    '06': 'Guía de Remisión',
                    '07': 'Comprobante de Retención',
                },
            },
        },
    },

    # -------------------------------------------------------------------------
    # SENAE - SERVICIO NACIONAL DE ADUANA
    # -------------------------------------------------------------------------
    'senae': {
        'entity': 'Servicio Nacional de Aduana del Ecuador',
        'base_url': 'https://www.aduana.gob.ec',
        'datasets': {
            'arancel_nacional': {
                'name': 'Arancel Nacional de Importaciones',
                'description': 'Partidas arancelarias, descripciones, tasas',
                'format': 'EXCEL/PDF',
                'url': 'https://mesadeservicios.aduana.gob.ec/arancel/',
                'use_case': 'Clasificación de productos importados',
            },
            'incoterms': {
                'name': 'INCOTERMS 2020',
                'preloaded': True,
                'data': {
                    'EXW': 'Ex Works (En Fábrica)',
                    'FCA': 'Free Carrier (Franco Porteador)',
                    'CPT': 'Carriage Paid To (Transporte Pagado Hasta)',
                    'CIP': 'Carriage and Insurance Paid To',
                    'DAP': 'Delivered at Place (Entregado en Lugar)',
                    'DPU': 'Delivered at Place Unloaded',
                    'DDP': 'Delivered Duty Paid (Entregado con Derechos Pagados)',
                    'FAS': 'Free Alongside Ship',
                    'FOB': 'Free on Board (Franco a Bordo)',
                    'CFR': 'Cost and Freight',
                    'CIF': 'Cost, Insurance and Freight',
                },
            },
            'impuestos_importacion': {
                'name': 'Impuestos de Importación',
                'preloaded': True,
                'data': {
                    'ad_valorem': {'variable': True, 'description': 'Según partida arancelaria'},
                    'fodinfa': {'rate': 0.5, 'description': 'FODINFA 0.5%'},
                    'iva_importacion': {'rate': 15.0, 'description': 'IVA 15% sobre CIF + aranceles'},
                    'ice': {'variable': True, 'description': 'ICE según producto'},
                    'isd': {'rate': 5.0, 'description': 'ISD 5% salida divisas'},
                },
            },
        },
    },

    # -------------------------------------------------------------------------
    # INEC - INSTITUTO NACIONAL DE ESTADÍSTICA Y CENSOS
    # -------------------------------------------------------------------------
    'inec': {
        'entity': 'Instituto Nacional de Estadística y Censos',
        'base_url': 'https://www.ecuadorencifras.gob.ec',
        'api': {
            'type': 'RESTful',
            'base_url': 'https://www.ecuadorencifras.gob.ec/api/',
            'formats': ['JSON', 'CSV', 'XLSX'],
        },
        'datasets': {
            'canasta_basica': {
                'name': 'Canasta Familiar Básica',
                'description': 'Costo canasta básica por ciudad',
                'format': 'CSV/XLSX',
                'url': 'https://www.ecuadorencifras.gob.ec/canasta/',
                'update_frequency': 'mensual',
                'use_case': 'Cálculo beneficios sociales, referencia SBU',
                'current_value_2026': 808.95,  # Canasta Básica Enero 2026
            },
            'canasta_vital': {
                'name': 'Canasta Familiar Vital',
                'description': 'Costo canasta vital por ciudad',
                'format': 'CSV/XLSX',
                'url': 'https://www.ecuadorencifras.gob.ec/canasta/',
                'current_value_2026': 576.12,  # Canasta Vital Enero 2026
            },
            'ipc': {
                'name': 'Índice de Precios al Consumidor',
                'description': 'IPC nacional y por ciudad',
                'format': 'CSV/XLSX',
                'url': 'https://www.ecuadorencifras.gob.ec/indice-de-precios-al-consumidor/',
                'update_frequency': 'mensual',
                'use_case': 'Ajustes por inflación, indexación',
            },
            'inflacion': {
                'name': 'Tasa de Inflación',
                'description': 'Inflación mensual y anual',
                'format': 'CSV',
                'url': 'https://www.ecuadorencifras.gob.ec/indice-de-precios-al-consumidor/',
            },
            'division_territorial': {
                'name': 'División Político-Administrativa',
                'description': 'Provincias, cantones, parroquias',
                'format': 'CSV/XLSX',
                'url': 'https://www.ecuadorencifras.gob.ec/division-politico-administrativa/',
                'use_case': 'Direcciones, formularios SRI',
            },
            'poblacion': {
                'name': 'Población por Provincia',
                'description': 'Datos demográficos',
                'format': 'CSV',
                'url': 'https://www.ecuadorencifras.gob.ec/estadisticas/',
            },
        },
    },

    # -------------------------------------------------------------------------
    # MDT - MINISTERIO DEL TRABAJO
    # -------------------------------------------------------------------------
    'mdt': {
        'entity': 'Ministerio del Trabajo',
        'base_url': 'https://www.trabajo.gob.ec',
        'datasets': {
            'tabla_sectorial': {
                'name': 'Tabla de Salarios Mínimos Sectoriales',
                'description': 'Salarios por sector y cargo',
                'format': 'PDF/XLSX',
                'url': 'https://www.trabajo.gob.ec/tabla-de-salarios-minimos-sectoriales/',
                'update_frequency': 'anual',
                'use_case': 'Validación salarios mínimos por cargo',
            },
            'sbu': {
                'name': 'Salario Básico Unificado',
                'preloaded': True,
                'data': {
                    '2024': 460.00,
                    '2025': 470.00,
                    '2026': 482.00,
                },
            },
            'beneficios_sociales': {
                'name': 'Beneficios Sociales',
                'preloaded': True,
                'data': {
                    'decimo_tercero': {'calculation': 'Total ingresos / 12', 'deadline': 'Dic 24'},
                    'decimo_cuarto': {'amount': 'SBU', 'deadline_costa': 'Mar 15', 'deadline_sierra': 'Ago 15'},
                    'utilidades': {'rate': 15.0, 'deadline': 'Abr 15'},
                    'fondos_reserva': {'rate': 8.33, 'after_months': 13},
                    'vacaciones': {'days': 15, 'calculation': 'Salario / 24'},
                },
            },
            'contratos_registrados': {
                'name': 'Contratos Registrados SUT',
                'format': 'CSV',
                'url': 'https://www.trabajo.gob.ec/datos-abiertos/',
            },
        },
    },

    # -------------------------------------------------------------------------
    # IESS - INSTITUTO ECUATORIANO DE SEGURIDAD SOCIAL
    # -------------------------------------------------------------------------
    'iess': {
        'entity': 'Instituto Ecuatoriano de Seguridad Social',
        'base_url': 'https://www.iess.gob.ec',
        'datasets': {
            'tasas_aportacion': {
                'name': 'Tasas de Aportación 2026',
                'preloaded': True,
                'data': {
                    'personal': {
                        'rate': 9.45,
                        'description': 'Aporte personal empleado',
                    },
                    'patronal': {
                        'rate': 11.15,
                        'description': 'Aporte patronal base',
                    },
                    'secap': {
                        'rate': 0.50,
                        'description': 'SECAP (Capacitación)',
                    },
                    'iece': {
                        'rate': 0.50,
                        'description': 'IECE (Educación)',
                    },
                    'total_empleador': {
                        'rate': 12.15,
                        'description': 'Total empleador (patronal + SECAP + IECE)',
                    },
                    'techo_aportacion': {
                        'value': 12050.00,
                        'description': '25 SBU máximo',
                        'calculation': '482 * 25',
                    },
                },
            },
            'prestamos': {
                'name': 'Tipos de Préstamos IESS',
                'preloaded': True,
                'data': {
                    'quirografario': {
                        'max_amount': 'Según aportes',
                        'max_term_months': 60,
                        'interest_range': '8-10%',
                    },
                    'hipotecario': {
                        'max_amount': 150000,
                        'max_term_months': 300,
                        'interest_range': '5-7%',
                    },
                },
            },
            'subsidios': {
                'name': 'Subsidios IESS',
                'preloaded': True,
                'data': {
                    'enfermedad': {'rate': 75, 'description': '75% del sueldo'},
                    'maternidad': {'weeks': 12, 'rate': 100},
                    'paternidad': {'days': 10, 'rate': 100},
                },
            },
        },
    },

    # -------------------------------------------------------------------------
    # BCE - BANCO CENTRAL DEL ECUADOR
    # -------------------------------------------------------------------------
    'bce': {
        'entity': 'Banco Central del Ecuador',
        'base_url': 'https://www.bce.fin.ec',
        'datasets': {
            'indicadores_economicos': {
                'name': 'Indicadores Económicos',
                'format': 'PDF/Web',
                'url': 'https://www.bce.fin.ec/estadisticas-economicas/',
            },
            'tasas_interes': {
                'name': 'Tasas de Interés',
                'preloaded': True,
                'data': {
                    'activa_referencial': 9.76,
                    'pasiva_referencial': 5.12,
                    'maxima_convencional': 16.85,
                    'mora': 10.26,
                },
            },
        },
    },

    # -------------------------------------------------------------------------
    # SUPERCIAS - SUPERINTENDENCIA DE COMPAÑÍAS
    # -------------------------------------------------------------------------
    'supercias': {
        'entity': 'Superintendencia de Compañías',
        'base_url': 'https://www.supercias.gob.ec',
        'datasets': {
            'tipos_compania': {
                'name': 'Tipos de Compañías',
                'preloaded': True,
                'data': {
                    'SA': 'Sociedad Anónima',
                    'CIA_LTDA': 'Compañía de Responsabilidad Limitada',
                    'SAS': 'Sociedad por Acciones Simplificada',
                    'EP': 'Empresa Pública',
                    'CEM': 'Compañía de Economía Mixta',
                },
            },
            'capital_minimo': {
                'name': 'Capital Mínimo Requerido',
                'preloaded': True,
                'data': {
                    'SA': 800.00,
                    'CIA_LTDA': 400.00,
                    'SAS': 0.00,  # Sin mínimo
                },
            },
        },
    },

    # -------------------------------------------------------------------------
    # DATOS GEOGRÁFICOS
    # -------------------------------------------------------------------------
    'geografia': {
        'entity': 'División Territorial Ecuador',
        'datasets': {
            'provincias': {
                'name': 'Provincias del Ecuador',
                'preloaded': True,
                'count': 24,
                'data': [
                    {'code': '01', 'name': 'Azuay', 'capital': 'Cuenca', 'region': 'Sierra'},
                    {'code': '02', 'name': 'Bolívar', 'capital': 'Guaranda', 'region': 'Sierra'},
                    {'code': '03', 'name': 'Cañar', 'capital': 'Azogues', 'region': 'Sierra'},
                    {'code': '04', 'name': 'Carchi', 'capital': 'Tulcán', 'region': 'Sierra'},
                    {'code': '05', 'name': 'Cotopaxi', 'capital': 'Latacunga', 'region': 'Sierra'},
                    {'code': '06', 'name': 'Chimborazo', 'capital': 'Riobamba', 'region': 'Sierra'},
                    {'code': '07', 'name': 'El Oro', 'capital': 'Machala', 'region': 'Costa'},
                    {'code': '08', 'name': 'Esmeraldas', 'capital': 'Esmeraldas', 'region': 'Costa'},
                    {'code': '09', 'name': 'Guayas', 'capital': 'Guayaquil', 'region': 'Costa'},
                    {'code': '10', 'name': 'Imbabura', 'capital': 'Ibarra', 'region': 'Sierra'},
                    {'code': '11', 'name': 'Loja', 'capital': 'Loja', 'region': 'Sierra'},
                    {'code': '12', 'name': 'Los Ríos', 'capital': 'Babahoyo', 'region': 'Costa'},
                    {'code': '13', 'name': 'Manabí', 'capital': 'Portoviejo', 'region': 'Costa'},
                    {'code': '14', 'name': 'Morona Santiago', 'capital': 'Macas', 'region': 'Oriente'},
                    {'code': '15', 'name': 'Napo', 'capital': 'Tena', 'region': 'Oriente'},
                    {'code': '16', 'name': 'Pastaza', 'capital': 'Puyo', 'region': 'Oriente'},
                    {'code': '17', 'name': 'Pichincha', 'capital': 'Quito', 'region': 'Sierra'},
                    {'code': '18', 'name': 'Tungurahua', 'capital': 'Ambato', 'region': 'Sierra'},
                    {'code': '19', 'name': 'Zamora Chinchipe', 'capital': 'Zamora', 'region': 'Oriente'},
                    {'code': '20', 'name': 'Galápagos', 'capital': 'Puerto Baquerizo Moreno', 'region': 'Insular'},
                    {'code': '21', 'name': 'Sucumbíos', 'capital': 'Nueva Loja', 'region': 'Oriente'},
                    {'code': '22', 'name': 'Orellana', 'capital': 'Puerto Francisco de Orellana', 'region': 'Oriente'},
                    {'code': '23', 'name': 'Santo Domingo de los Tsáchilas', 'capital': 'Santo Domingo', 'region': 'Costa'},
                    {'code': '24', 'name': 'Santa Elena', 'capital': 'Santa Elena', 'region': 'Costa'},
                ],
            },
            'regiones': {
                'name': 'Regiones',
                'preloaded': True,
                'data': {
                    'Costa': {'decimo_cuarto': 'Marzo 15', 'vacaciones': 'Febrero-Marzo'},
                    'Sierra': {'decimo_cuarto': 'Agosto 15', 'vacaciones': 'Julio-Agosto'},
                    'Oriente': {'decimo_cuarto': 'Agosto 15', 'vacaciones': 'Julio-Agosto'},
                    'Insular': {'decimo_cuarto': 'Marzo 15', 'vacaciones': 'Febrero-Marzo'},
                },
            },
        },
    },
}


class EcuadorOpenDataRegistry:
    """
    Registro de fuentes de datos abiertos de Ecuador.

    Proporciona acceso a datasets oficiales para precarga
    de datos en la localización.
    """

    def __init__(self, env=None):
        self.env = env
        self.sources = ECUADOR_OPEN_DATA_SOURCES

    def list_entities(self) -> List[Dict]:
        """Lista todas las entidades con datos disponibles."""
        return [
            {
                'code': code,
                'entity': data.get('entity', code),
                'datasets_count': len(data.get('datasets', {})),
            }
            for code, data in self.sources.items()
        ]

    def list_datasets(self, entity: str) -> List[Dict]:
        """Lista todos los datasets de una entidad."""
        entity_data = self.sources.get(entity.lower())
        if not entity_data:
            return []

        return [
            {
                'name': name,
                'title': data.get('name', name),
                'format': data.get('format', 'N/A'),
                'preloaded': data.get('preloaded', False),
                'url': data.get('url'),
            }
            for name, data in entity_data.get('datasets', {}).items()
        ]

    def get_preloaded_data(self, entity: str, dataset: str) -> Optional[Dict]:
        """Obtiene datos precargados de un dataset."""
        entity_data = self.sources.get(entity.lower(), {})
        dataset_data = entity_data.get('datasets', {}).get(dataset, {})

        if dataset_data.get('preloaded'):
            return dataset_data.get('data')
        return None

    def get_sbu(self, year: int = 2026) -> float:
        """Obtiene el Salario Básico Unificado de un año."""
        sbu_data = self.get_preloaded_data('mdt', 'sbu')
        return sbu_data.get(str(year), 482.00)

    def get_iess_rates(self) -> Dict:
        """Obtiene tasas IESS vigentes."""
        return self.get_preloaded_data('iess', 'tasas_aportacion')

    def get_tipo_impuesto(self, codigo: str) -> Dict:
        """Obtiene información de un tipo de impuesto."""
        impuestos = self.get_preloaded_data('sri', 'tipos_impuestos')
        return impuestos.get(codigo, {})

    def get_provincias(self) -> List[Dict]:
        """Obtiene lista de provincias de Ecuador."""
        provincias_data = self.get_preloaded_data('geografia', 'provincias')
        return provincias_data if isinstance(provincias_data, list) else []

    def get_retention_codes(self) -> Dict:
        """Obtiene códigos de retención."""
        return self.get_preloaded_data('sri', 'codigos_retenciones')


def get_open_data_registry(env=None) -> EcuadorOpenDataRegistry:
    """Factory function para obtener instancia del registro."""
    return EcuadorOpenDataRegistry(env)
