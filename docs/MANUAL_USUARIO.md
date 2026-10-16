# Manual de Usuario

## 🇪🇨 Localización Ecuador para Odoo 18

**Por [Somatech.dev](https://somatech.dev)**

---

## 📑 Contenido

1. [Introducción](#1-introducción)
2. [Configuración Inicial](#2-configuración-inicial)
3. [Facturación Electrónica](#3-facturación-electrónica)
4. [Retenciones](#4-retenciones)
5. [Guía de Remisión](#5-guía-de-remisión)
6. [Nómina](#6-nómina)
7. [Reportes](#7-reportes)
8. [Preguntas Frecuentes](#8-preguntas-frecuentes)

---

## 1. Introducción

Esta guía explica cómo usar los módulos de localización ecuatoriana para Odoo 18, cumpliendo con todas las regulaciones del SRI 2026.

### Módulos Incluidos

| Módulo | Función |
|--------|---------|
| Facturación Electrónica | Facturas, NC, ND |
| Retenciones | IR + IVA |
| Guía de Remisión | Transporte |
| Nómina | IESS, Décimos |
| Reportes | ATS, Form 104 |

---

## 2. Configuración Inicial

### 2.1 Datos de la Empresa

**Ruta**: Configuración > Empresas > Su Empresa

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| RUC | 13 dígitos | 1793125212001 |
| Razón Social | Nombre legal | Mi Empresa S.A. |
| Dirección | Dirección fiscal | Av. Principal, Quito |

### 2.2 Certificado Digital SRI

**Ruta**: Contabilidad > Configuración > Ecuador SRI > Certificados

**Pasos:**
1. Clic en **Crear**
2. Subir archivo `.p12`
3. Ingresar contraseña del certificado
4. Configurar fecha de vencimiento
5. Clic en **Activar**

> ⚠️ **Importante**: El certificado debe ser de un proveedor autorizado:
> - Security Data
> - ANF AC Ecuador
> - Banco Central del Ecuador

### 2.3 Ambiente SRI

**Ruta**: Configuración > Empresas > Ecuador SRI

| Ambiente | Uso |
|----------|-----|
| **Pruebas** | Desarrollo y testing |
| **Producción** | Facturas reales al SRI |

---

## 3. Facturación Electrónica

### 3.1 Crear Factura

**Ruta**: Contabilidad > Clientes > Facturas

1. Clic en **Crear**
2. Seleccionar cliente
3. Agregar líneas de productos
4. Clic en **Confirmar**

### 3.2 Enviar al SRI

1. Abrir factura confirmada
2. Clic en botón **Enviar a SRI**
3. Esperar respuesta:

| Estado | Significado |
|--------|-------------|
| ✅ AUTORIZADO | Factura válida |
| ❌ RECHAZADO | Revisar errores |

### 3.3 Reimprimir RIDE

1. Abrir factura autorizada
2. Clic en **Imprimir > RIDE**
3. Se genera PDF con código de barras

### 3.4 Consumidor Final

| Regla | Valor |
|-------|-------|
| Límite máximo | **$50.00 USD** |
| RUC automático | 9999999999999 |
| ¿Se puede anular? | **NO** (regla SRI 2026) |

---

## 4. Retenciones

### 4.1 Crear Retención

**Ruta**: Contabilidad > Proveedores > Retenciones

1. Clic en **Crear**
2. Seleccionar factura del proveedor
3. Agregar líneas de retención:
   - Retención IR (ej: 303 = 10%)
   - Retención IVA (ej: 721 = 10%)
4. Clic en **Validar**

### 4.2 Regla de 5 Días

> ⚠️ **Obligatorio**: La retención debe emitirse dentro de **5 días hábiles** desde la fecha de la factura.

El sistema bloqueará automáticamente retenciones fuera de plazo.

### 4.3 Códigos de Retención IR

| Código | Porcentaje | Concepto |
|--------|------------|----------|
| 303 | 10% | Honorarios Profesionales |
| 304 | 8% | Servicios Predomina Intelecto |
| 307 | 2% | Servicios Mano de Obra |
| 308 | 2% | Servicios Entre Sociedades |
| 312 | 1% | Bienes Muebles |
| 320 | 1.75% | Arrendamiento Inmuebles |

### 4.4 Códigos de Retención IVA

| Código | Porcentaje | Aplicación |
|--------|------------|------------|
| 721 | 10% | Bienes |
| 723 | 20% | Servicios |
| 725 | 30% | Bienes (Contribuyente Especial) |
| 727 | 70% | Servicios (CE) |
| 729 | 100% | Liquidación de Compra |
| 731 | 100% | Profesionales |

---

## 5. Guía de Remisión

### 5.1 Crear Guía

**Ruta**: Inventario > Entregas

1. Abrir entrega confirmada
2. Clic en **Generar Guía de Remisión**
3. Completar datos:
   - Placa del vehículo
   - RUC/Cédula del transportista
   - Motivo de traslado
4. Clic en **Enviar a SRI**

### 5.2 Motivos de Traslado

| Código | Motivo |
|--------|--------|
| 01 | Venta |
| 02 | Compra |
| 03 | Devolución |
| 04 | Traslado entre establecimientos |
| 05 | Consignación |
| 06 | Exportación |

---

## 6. Nómina

### 6.1 Rol de Pagos

**Ruta**: Recursos Humanos > Nómina > Roles

El sistema calcula automáticamente:

| Concepto | Cálculo |
|----------|---------|
| Sueldo base | Según contrato |
| IESS Personal | 9.45% |
| IESS Patronal | 12.15% |
| Horas extras 50% | Hora × 1.5 |
| Horas extras 100% | Hora × 2.0 |

### 6.2 Décimo Tercero

| Atributo | Valor |
|----------|-------|
| Cálculo | Ingresos totales ÷ 12 |
| Período | 1 Dic - 30 Nov |
| Pago | Antes del **24 de diciembre** |

### 6.3 Décimo Cuarto

| Atributo | Valor |
|----------|-------|
| Monto | 1 SBU = **$482** (2026) |
| Mensualizado | $40.17/mes |
| Costa/Galápagos | Antes del **15 de marzo** |
| Sierra/Amazonía | Antes del **15 de agosto** |

### 6.4 Fondos de Reserva

| Atributo | Valor |
|----------|-------|
| Porcentaje | 8.33% |
| Elegibilidad | Después de 13 meses continuos |
| Pago | Mensual vía IESS o acumulado |

### 6.5 Utilidades

| Componente | Porcentaje | Distribución |
|------------|------------|--------------|
| Individual | 10% | Por días trabajados |
| Familiar | 5% | Por cargas familiares |
| **Total** | **15%** | Utilidad neta |
| Fecha límite | **15 de abril** | |
| Máximo por empleado | 24 × SBU = $11,568 | |

---

## 7. Reportes

### 7.1 ATS (Anexo Transaccional Simplificado)

**Ruta**: Contabilidad > Reportes > Ecuador > ATS

1. Seleccionar mes
2. Clic en **Generar ATS**
3. Descargar archivo XML
4. Subir a portal SRI

**Contenido del ATS:**
- Ventas del período
- Compras del período
- Retenciones emitidas
- Documentos anulados

### 7.2 Formulario 104

**Ruta**: Contabilidad > Reportes > Ecuador > Form 104

Declaración mensual de IVA.

---

## 8. Preguntas Frecuentes

### ¿Qué hago si el SRI rechaza mi factura?

1. Revisar el mensaje de error detallado
2. Corregir el problema identificado
3. Intentar enviar nuevamente

### ¿Puedo anular una factura autorizada?

| Tipo de Factura | ¿Se puede anular? |
|-----------------|-------------------|
| Facturas normales | ✅ Sí, dentro de **7 días** |
| Consumidor Final | ❌ **No permitido** |

### ¿Cómo renuevo mi certificado?

1. Obtener nuevo certificado del proveedor
2. Subir nuevo .p12 en Odoo
3. Activar nuevo certificado
4. Desactivar el anterior

### ¿Qué errores son más comunes?

| Error | Causa | Solución |
|-------|-------|----------|
| CLAVE DUPLICADA | Ya existe la factura | Usar clave existente |
| RUC NO INSCRITO | Cliente no registrado | Verificar RUC |
| FIRMA INVALIDA | Problema con certificado | Revisar .p12 |

---

## 📞 Soporte

| Canal | Contacto |
|-------|----------|
| Email | soporte@somatech.dev |
| Web | [somatech.dev](https://somatech.dev) |
| GitHub | [Issues](https://github.com/somatechlat/odoo_saas_ecuador/issues) |

---

**Licencia**: LGPL-3.0 | **Versión**: 18.0.1.0.0
