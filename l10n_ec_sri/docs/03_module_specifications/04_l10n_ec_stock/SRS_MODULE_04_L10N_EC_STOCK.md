# SOFTWARE REQUIREMENTS SPECIFICATION
## Module: l10n_ec_stock (Ecuador Logistics - Guía de Remisión)

**Document Identifier**: SRS-L10N-EC-STOCK-001
**Version**: 1.0
**Date**: 2026-01-22
**Status**: APPROVED
**Standard**: ISO/IEC/IEEE 29148:2018

---

## 1. INTRODUCTION

### 1.1 Purpose
This SRS describes the requirements for the `l10n_ec_stock` module, which implements electronic "Guía de Remisión" (Waybill/Delivery Note) generation, signing, and transmission to SRI.

### 1.2 Scope
The module SHALL:
1. Extend `stock.picking` with transport fields.
2. Define a Driver/Vehicle registry.
3. Generate XML compliant with `guiaRemision_v1.1.0.xsd`.
4. Integrate with `l10n_ec_edi` for signing.

### 1.3 Definitions
| Term | Definition |
|:---|:---|
| **Guía de Remisión** | Waybill required to transport goods in Ecuador |
| **Destinatario** | Recipient of goods at a destination point |
| **Transportista** | Licensed carrier/driver |
| **Motivo Traslado** | Reason for transport (Sale, Transfer, etc.) |

### 1.4 References
- SRI Ficha Técnica - Guía de Remisión v1.1.0
- Ley de Régimen Tributario Interno Art. 36
- Odoo 18.0 Stock Module Documentation

---

## 2. OVERALL DESCRIPTION

### 2.1 Product Perspective
This module extends the Odoo Inventory module. When goods leave a warehouse, a legally required Guía de Remisión must accompany the shipment.

### 2.2 Product Functions
1. **F-GR-001**: Driver/Vehicle Registry
2. **F-GR-002**: Picking Extensions
3. **F-GR-003**: XML Generation
4. **F-GR-004**: Print RIDE (Waybill PDF)

### 2.3 User Classes
| User | Role |
|:---|:---|
| **Warehouse Manager** | Validates pickings with Guía |
| **Driver** | Receives printed Guía |

### 2.4 Constraints
- Guía MUST be authorized BEFORE goods leave premises.
- Driver/Plate information is MANDATORY.
- Transport dates MUST be realistic (start <= end).

---

## 3. EXTERNAL INTERFACE REQUIREMENTS

### 3.1 User Interfaces
| Screen | Description |
|:---|:---|
| **Driver Registry** | CRUD for drivers (Menu: Inventory > Configuration > Drivers) |
| **Vehicle Registry** | CRUD for vehicles (Plates) |
| **Picking Form** | Extended with "Transport" tab |

### 3.2 Software Interfaces
| Interface | Module |
|:---|:---|
| `stock.picking` | Extended model |
| `l10n_ec_edi` | Signing engine |
| `sale.order` | Optional link to sales |

---

## 4. SPECIFIC REQUIREMENTS

### 4.1 Functional Requirements

#### 4.1.1 Driver Registry (F-GR-001)
**REQ-F-001.1**: Model `l10n_ec.driver`:
| Field | Type | Constraints |
|:---|:---|:---|
| `name` | Char | Required |
| `partner_id` | Many2one | Optional (link to Driver as Partner) |
| `license_number` | Char | Required |
| `license_type` | Selection | A, B, C, D, E |
| `license_expiry` | Date | Warn if expired |
| `vat` | Char | RUC/Cédula |

**REQ-F-001.2**: Model `l10n_ec.vehicle`:
| Field | Type | Constraints |
|:---|:---|:---|
| `name` | Char | Description (e.g., "Camión Hino") |
| `plate` | Char | Required, Unique |
| `carrier_id` | Many2one | Link to Carrier Partner |

#### 4.1.2 Picking Extensions (F-GR-002)
**REQ-F-002.1**: Extend `stock.picking` with:
| Field | Type | XML Tag |
|:---|:---|:---|
| `l10n_ec_is_guia` | Boolean | - |
| `l10n_ec_access_key` | Char(49) | `claveAcceso` |
| `l10n_ec_driver_id` | Many2one | - |
| `l10n_ec_vehicle_id` | Many2one | `placa` |
| `l10n_ec_carrier_id` | Many2one | `rucTransportista` |
| `l10n_ec_transport_reason` | Selection | `motivoTraslado` |
| `l10n_ec_route` | Text | `ruta` |
| `l10n_ec_start_date` | Date | `fechaIniTransporte` |
| `l10n_ec_end_date` | Date | `fechaFinTransporte` |
| `l10n_ec_start_address` | Char | `dirPartida` |
| `l10n_ec_edi_state` | Selection | Authorization state |

**REQ-F-002.2**: Transport Reason Selection:
| Code | Name |
|:---|:---|
| 01 | Venta |
| 02 | Compra |
| 03 | Transformación |
| 04 | Consignación |
| 05 | Devolución |
| 06 | Traslado entre establecimientos |
| 07 | Traslado por emisor itinerante |
| 08 | Exportación |
| 99 | Otros |

#### 4.1.3 XML Generation (F-GR-003)
**REQ-F-003.1**: XML Structure:
```xml
<guiaRemision id="comprobante" version="1.1.0">
    <infoTributaria>
        <ambiente>2</ambiente>
        <tipoEmision>1</tipoEmision>
        <razonSocial>Mi Empresa S.A.</razonSocial>
        <ruc>1793125212001</ruc>
        <claveAcceso>2201202606179312521200110010010000000011234567811</claveAcceso>
        <codDoc>06</codDoc>
        <estab>001</estab>
        <ptoEmi>001</ptoEmi>
        <secuencial>000000001</secuencial>
        <dirMatriz>Av. Principal 123</dirMatriz>
    </infoTributaria>
    <infoGuiaRemision>
        <dirEstablecimiento>Av. Principal 123</dirEstablecimiento>
        <dirPartida>Bodega Central, Quito</dirPartida>
        <razonSocialTransportista>Transportes ABC S.A.</razonSocialTransportista>
        <tipoIdentificacionTransportista>04</tipoIdentificacionTransportista>
        <rucTransportista>1793125212001</rucTransportista>
        <rise>NO</rise>
        <obligadoContabilidad>SI</obligadoContabilidad>
        <contribuyenteEspecial>No</contribuyenteEspecial>
        <fechaIniTransporte>22/01/2026</fechaIniTransporte>
        <fechaFinTransporte>22/01/2026</fechaFinTransporte>
        <placa>ABC-1234</placa>
    </infoGuiaRemision>
    <destinatarios>
        <destinatario>
            <identificacionDestinatario>1793125212001</identificacionDestinatario>
            <razonSocialDestinatario>Cliente XYZ S.A.</razonSocialDestinatario>
            <dirDestinatario>Calle Secundaria 456, Guayaquil</dirDestinatario>
            <motivoTraslado>Venta</motivoTraslado>
            <docAduaneroUnico/>
            <codEstabDestino>001</codEstabDestino>
            <ruta>Quito - Guayaquil</ruta>
            <codDocSustento>01</codDocSustento>
            <numDocSustento>001-001-000000123</numDocSustento>
            <numAutDocSustento>22012026011793125212001...</numAutDocSustento>
            <fechaEmisionDocSustento>22/01/2026</fechaEmisionDocSustento>
            <detalles>
                <detalle>
                    <codigoInterno>PROD001</codigoInterno>
                    <codigoAdicional>SKU123</codigoAdicional>
                    <descripcion>Producto ABC</descripcion>
                    <cantidad>10</cantidad>
                </detalle>
            </detalles>
        </destinatario>
    </destinatarios>
    <infoAdicional>
        <campoAdicional nombre="Conductor">Juan Pérez</campoAdicional>
        <campoAdicional nombre="CedulaConductor">1713488185</campoAdicional>
    </infoAdicional>
</guiaRemision>
```

#### 4.1.4 Validation Rules (F-GR-004)
**REQ-F-004.1**: On `button_validate`:
```python
if picking.picking_type_code == 'outgoing' and picking.l10n_ec_is_guia:
    if not picking.l10n_ec_driver_id:
        raise UserError("Debe seleccionar un conductor.")
    if not picking.l10n_ec_vehicle_id:
        raise UserError("Debe seleccionar un vehículo.")
    if picking.l10n_ec_start_date > picking.l10n_ec_end_date:
        raise UserError("Fecha inicio no puede ser mayor a fecha fin.")
```

---

## 5. USE CASES

### 5.1 UC-001: Generate Guía for Outgoing Shipment
**Actor**: Warehouse Manager
**Flow**:
1. User confirms Sale Order -> Delivery Order created.
2. User opens Delivery Order.
3. User enables "Generate Guía de Remisión".
4. User selects Driver, Vehicle, Route, Dates.
5. User validates picking.
6. System generates XML, signs, transmits to SRI.
7. System receives authorization.
8. User prints Guía (PDF with Access Key barcode).
**Postcondition**: Goods can legally leave warehouse.

---

## 6. VALIDATION CRITERIA

| Test ID | Description | Expected |
|:---|:---|:---|
| **T-GR-001** | Create driver with valid license | Success |
| **T-GR-002** | Validate picking without driver | UserError |
| **T-GR-003** | Generate XML for multi-product picking | Valid XML |
| **T-GR-004** | Authorize Guía in SRI Test | state = authorized |

---

**Document Control**:
| Version | Date | Author |
|:---|:---|:---|
| 1.0 | 2026-01-22 | Antigravity (World's #1 Odoo Expert + Logistics Specialist) |
