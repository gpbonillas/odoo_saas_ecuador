# Software Requirements Specification (SRS)
## Company Setup Wizard - Ecuador Localization

**Document ID:** SRS-WIZARD-EC-2026-001
**Version:** 1.1.0
**Date:** 2026-01-25 · **Última revisión:** 2026-10-16 (esquema SRI corregido contra payload real, CHG-2026-003)
**Module:** l10n_ec / l10n_ec_base
**Classification:** Internal

---

## 1. RESUMEN EJECUTIVO

### 1.1 Propósito
Documentar el flujo completo del Wizard de Configuración de Empresa Ecuador, incluyendo la integración automática con el API REST del SRI para auto-completar datos del contribuyente.

### 1.2 Alcance
- Consulta automática de RUC en base de datos SRI
- Auto-llenado de campos desde respuesta API
- Validación de estado del contribuyente
- Mapeo a modelo `res.company` de Odoo

---

## 2. API SRI - ESPECIFICACIÓN TÉCNICA

### 2.1 Endpoints Disponibles

| Endpoint | Método | Parámetro | Descripción |
|:---------|:-------|:----------|:------------|
| `/obtenerPorNumerosRuc` | GET | `ruc` | Consulta por RUC (13 dígitos) |
| `/obtenerPorNumeroCedula` | GET | `cedula` | Consulta por cédula (10 dígitos) |
| `/obtenerPorRazonSocial` | GET | `razonSocial` | Búsqueda por nombre |

### 2.2 URL Base
```
https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest/ConsolidadoContribuyente/
```

### 2.3 Headers Requeridos
```http
Accept: application/json
User-Agent: Odoo/18.0 SomatechEC/1.0
```

### 2.4 Ejemplo Request/Response

> **CORREGIDO 2026-10-16 (v1.1):** payload real verificado en vivo (2 llamadas, ambiente prod
> lectura). El ejemplo anterior (RUC inventado + campos inventados) era **falso** — ese RUC no
> existe en el SRI (respuesta vacía) y ya se eliminó. IDs de prueba exclusivos: D-04.

**Request:**
```
GET /obtenerPorNumerosRuc?ruc=1793125212001
```

**Response (200 OK) — payload real 2026-10-16 (16 claves exactas):**
```json
[{
  "numeroRuc": "1793125212001",
  "razonSocial": "CANNACHAIN S.A.S. ",
  "estadoContribuyenteRuc": "ACTIVO",
  "actividadEconomicaPrincipal": "CULTIVO DE LINO Y CÁÑAMO.",
  "tipoContribuyente": "SOCIEDAD",
  "regimen": "GENERAL",
  "categoria": null,
  "obligadoLlevarContabilidad": "SI",
  "agenteRetencion": "NO",
  "contribuyenteEspecial": "NO",
  "informacionFechasContribuyente": {
    "fechaInicioActividades": "2021-02-26 00:00:00.0",
    "fechaCese": "",
    "fechaReinicioActividades": "",
    "fechaActualizacion": "2025-01-15 11:12:14.0"
  },
  "representantesLegales": [
    { "identificacion": "1716341274", "nombre": "ENCALADA EGUEZ VICTOR AUGUSTO" }
  ],
  "motivoCancelacionSuspension": null,
  "contribuyenteFantasma": "NO",
  "transaccionesInexistente": "NO"
}]
```

Notas de ingestión:
* `razonSocial` trae **espacio final** → `trim`.
* **Persona natural** (`ruc=1713488185001`): `tipoContribuyente=PERSONA NATURAL`,
  `obligadoLlevarContabilidad=NO`, `representantesLegales=null` — mismas 16 claves.
* **NO devuelve** (pese a documentación anterior): `nombreComercial`, dirección/provincia/cantón,
  `telefono1`, `correo`, `codigoActividadEconomica` (CIIU), `regimenRimpe`, fecha de inicio
  plana → esos datos los **pregunta** el wizard paso ① (`USER`, WIZ-01).

---

## 3. FLUJO DE PANTALLAS

### 3.1 Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────────┐
│                    INICIO WIZARD                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 1: INGRESO RUC                                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ RUC: [________________] ← Usuario ingresa 13 dígitos        ││
│  │                         ↓                                    ││
│  │                    onchange()                                ││
│  │                         ↓                                    ││
│  │              ┌─────────────────────┐                        ││
│  │              │ API SRI consultar_ruc│                       ││
│  │              └──────────┬──────────┘                        ││
│  │                         ↓                                    ││
│  │              ┌─────────────────────┐                        ││
│  │              │ Auto-llenar campos  │                        ││
│  │              └─────────────────────┘                        ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 2: DATOS CARGADOS (Editable)                              │
│  ┌───────────────────┬─────────────────────────────────────────┐│
│  │ Razón Social:     │ [AUTO: razonSocial] (trim) ✅           ││
│  │ Estado SRI:       │ [AUTO: estadoContribuyenteRuc] ✅       ││
│  │ Tipo Contribuy:   │ [AUTO: tipoContribuyente]               ││
│  │ Régimen:          │ [AUTO: regimen]                         ││
│  │ Actividad Econ:   │ [AUTO: actividadEconomicaPrincipal]     ││
│  │ Obligado Contab:  │ [AUTO: obligadoLlevarContabilidad] ☑    ││
│  │ Contrib. Especial:│ [AUTO: contribuyenteEspecial]           ││
│  │ Agente Retención: │ [AUTO: agenteRetencion]                 ││
│  │ Inicio Activ.:    │ [AUTO: informacionFechasContribuyente]  ││
│  │ Rep. Legal:       │ [AUTO: representantesLegales[0]]        ││
│  │ (rojo fraude):    │ [AUTO: fantasma/transacciones/motivo]   ││
│  └───────────────────┴─────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 3: DATOS QUE EL SRI NO EXPONE (USER)                      │
│  ┌───────────────────┬─────────────────────────────────────────┐│
│  │ Nombre Comercial: │ [USER] (endpoint no lo devuelve)        ││
│  │ Dirección:        │ [USER]                                  ││
│  │ Ciudad:           │ [USER]                                  ││
│  │ Teléfono:         │ [USER]                                  ││
│  │ Email:            │ [USER]                                  ││
│  └───────────────────┴─────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 4: CONFIGURACIÓN SRI                                      │
│  ┌───────────────────┬─────────────────────────────────────────┐│
│  │ Ambiente SRI:     │ ○ Pruebas  ◉ Producción                 ││
│  └───────────────────┴─────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  [✅ Configurar Empresa] [Configurar Después]                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. MAPEO DE CAMPOS

### 4.1 API SRI → Wizard (esquema real, verificado 2026-10-16)

| Campo API SRI | Tipo | Campo Wizard | Auto-fill |
|:--------------|:-----|:-------------|:----------|
| `numeroRuc` | string(13) | `company_ruc` | ❌ Input |
| `razonSocial` | string | `company_name` | ✅ AUTO (**trim** — trae espacio final) |
| `estadoContribuyenteRuc` | string | `sri_estado` | ✅ AUTO (gate: `ACTIVO`; ≠ ⇒ ⛔) |
| `tipoContribuyente` | string | `sri_tipo_contribuyente` | ✅ AUTO |
| `regimen` | string | `sri_regimen` | ✅ AUTO |
| `actividadEconomicaPrincipal` | string | `sri_actividad` | ✅ AUTO (solo texto → mapeo local `texto→vertical`, N-01 §⑨) |
| `obligadoLlevarContabilidad` | "SI"/"NO" | `obligado_contabilidad` | ✅ AUTO |
| `contribuyenteEspecial` | "SI"/"NO" | `contribuyente_especial` | ✅ AUTO |
| `agenteRetencion` | "SI"/"NO" | `agente_retencion` | ✅ AUTO (valores posibles ≠ NO `[VERIFY]`) |
| `informacionFechasContribuyente.fechaInicioActividades` | datetime | `fecha_inicio` | ✅ AUTO (**anidado**) |
| `informacionFechasContribuyente.fechaActualizacion` | datetime | `fecha_actualizacion` | ✅ AUTO (**anidado**) |
| `representantesLegales[0].{nombre,identificacion}` | obj (lista) | `rep_legal_name` / `rep_legal_id` | ✅ AUTO (**lista** — null en natural; pre-filla usuarios paso ⑨) |
| `contribuyenteFantasma`, `transaccionesInexistente`, `motivoCancelacionSuspension` | flag | banderas de auditoría | ✅ AUTO (rojo si ≠ `NO`/`NO`/`null`) |
| `categoria` | ? | — | `[VERIFY]` (null en ambos IDs) |
| *(no expuestos)* `nombreComercial`, dirección, `telefono1`, `correo`, CIIU, `regimenRimpe` | — | paso ① | ❓ **USER** (WIZ-01: se pregunta lo que SRI no sabe) |

### 4.2 Wizard → res.company (Odoo)

| Campo Wizard | Campo res.company | Transformación |
|:-------------|:------------------|:---------------|
| `company_name` | `name` | Directo |
| `company_ruc` | `vat` | Directo |
| `commercial_name` | `company_registry` | Directo |
| `street` | `street` | Directo |
| `city` | `city` | Directo |
| `province` | `state_id` | Buscar en res.country.state |
| - | `country_id` | Fijo: Ecuador (base.ec) |
| `phone` | `phone` | Directo |
| `email` | `email` | Directo |
| `website` | `website` | Manual |

### 4.3 Wizard → ir.config_parameter

| Campo Wizard | Parámetro | Valor |
|:-------------|:----------|:------|
| `sri_environment` | `l10n_ec.sri_environment` | "test" / "production" |
| `obligado_contabilidad` | `l10n_ec.obligado_contabilidad` | "True" / "False" |
| `contribuyente_especial` | `l10n_ec.contribuyente_especial` | Número resolución |
| `agente_retencion` | `l10n_ec.agente_retencion` | Número resolución |

---

## 5. CAMPOS API SRI NO UTILIZADOS (Disponibles) — real, 2026-10-16

| Campo API | Uso Potencial | Prioridad |
|:----------|:--------------|:----------|
| `informacionFechasContribuyente.fechaCese` / `fechaReinicioActividades` | Bloqueo por cese / continuidad de actividades | Alta |
| `representantesLegales[]` (lista completa) | Alta: usuarios/firmantes paso ⑨ | Alta |
| `motivoCancelacionSuspension` | Auditoría (rojo si ≠ `null`) | Alta |
| `contribuyenteFantasma` / `transaccionesInexistente` | Señales de fraude (rojo si ≠ `NO`) | Alta |
| `categoria` | Clasificación (null observado) `[VERIFY]` | Baja |
| `actividadEconomicaPrincipal` (texto) | `vertical.suggested` vía mapeo local (no existe CIIU en el payload) | Alta |

**Campos que NO existen en la respuesta real** (corregido v1.1 — la v1.0 los inventó):
`codigoActividadEconomica`, `nombreComercial`, `direccionMatriz`, `nombreCalle`, `numeroCasa`,
`interseccion`, `nombreProvincia`, `nombreCanton`, `nombreParroquia`, `telefono1`, `correo`,
`fechaInicioActividades` (plana), `fechaActualizacion` (plana), `claseContribuyente`,
`regimenRimpe`, `estadoEstablecimiento`.

---

## 6. VALIDACIONES

### 6.1 Validación de Entrada (reglas stdnum — FR-LE-50, ISO-EC-10 §3.5)

| Campo | Regla | Mensaje Error |
|:------|:------|:--------------|
| RUC | 13 dígitos + despacho por 3er dígito (0–5 natural = cédula+001, 6 público, 9 jurídica, 7/8 inválidos) | "RUC inválido" |
| Cédula | 10 dígitos, provincia 01–24 (+30,50), 3er dígito 0–6, módulo 10 | "Cédula inválida" |
| Estado | `estadoContribuyenteRuc` ≠ "ACTIVO" | ⛔ "Contribuyente no activo — no puede facturar" (N-01) |
| Señales rojas | `contribuyenteFantasma`/`transaccionesInexistente` ≠ "NO" o `motivoCancelacionSuspension` ≠ null | ⛔ "Contribuyente con observaciones SRI — revisar" |

### 6.2 Validación API

| Código HTTP | Acción |
|:------------|:-------|
| 200 | Procesar respuesta |
| 404 | "RUC no existe en la base del SRI" |
| 500 | "Error de conexión con SRI" |
| Timeout (15s) | "Tiempo de espera agotado" |

---

## 7. CÓDIGO IMPLEMENTACIÓN

### 7.1 Servicio SRI (l10n_ec_sri_ruc_service.py)

```python
# Modelo: l10n_ec.sri.ruc.service

def consultar_ruc(self, ruc):
    url = f"{SRI_RUC_ENDPOINT}?ruc={ruc}"
    response = requests.get(url, headers=headers, timeout=15)

    if response.status_code == 200:
        data = response.json()[0]
        return {
            'success': True,
            'data': self._parse_sri_response(data)
        }
```

### 7.2 Wizard onchange (l10n_ec_company_setup_wizard.py)

```python
@api.onchange("company_ruc")
def _onchange_company_ruc(self):
    if len(self.company_ruc) == 13:
        result = self.env["l10n_ec.sri.ruc.service"].consultar_ruc(ruc)
        if result["success"]:
            data = result["data"]
            self.company_name = data.get("razon_social")
            self.commercial_name = data.get("nombre_comercial")
            # ... resto de campos
```

---

## 8. ARCHIVOS RELACIONADOS

| Archivo | Propósito |
|:--------|:----------|
| `l10n_ec_base/models/l10n_ec_sri_ruc_service.py` | Servicio API SRI |
| `l10n_ec/wizard/l10n_ec_company_setup_wizard.py` | Lógica wizard |
| `l10n_ec/wizard/l10n_ec_company_setup_wizard_views.xml` | Vista XML |
| `l10n_ec/hooks.py` | Auto-ejecutar wizard post-install |

---

## 9. APROBACIONES

| Rol | Nombre | Fecha |
|:----|:-------|:------|
| Desarrollador | __________ | ______ |
| QA | __________ | ______ |
| Product Owner | __________ | ______ |

---

**FIN DEL DOCUMENTO SRS-WIZARD-EC-2026-001**
