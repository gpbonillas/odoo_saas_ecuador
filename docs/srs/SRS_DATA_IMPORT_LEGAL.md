# Data Import Options & Legal Implications

## Company Creation Wizard - Data Import Analysis

---

## 1. DATA IMPORT OPTIONS

### 1.1 CSV Import Capabilities

| Data Type | CSV Import | Template Provided | Validation |
|:----------|:-----------|:------------------|:-----------|
| 👥 Empleados | ✅ | ✅ | Cédula, IESS |
| 📦 Productos | ✅ | ✅ | Categoría, IVA |
| 🏢 Clientes | ✅ | ✅ | RUC/Cédula |
| 🏭 Proveedores | ✅ | ✅ | RUC, Retenciones |
| 📊 Plan Cuentas | ✅ | ✅ | Código, Tipo |
| 💰 Saldos Iniciales | ✅ | ✅ | Cuenta, Monto |

### 1.2 Employees CSV Template

```csv
cedula,nombres,apellidos,fecha_nacimiento,fecha_ingreso,cargo,salario,tipo_contrato,region,email,telefono
1712345678,Juan Carlos,Pérez López,1985-03-15,2024-01-15,Vendedor,500.00,indefinido,sierra,juan@empresa.com,0991234567
1798765432,María José,García Suárez,1990-07-22,2024-02-01,Cajera,482.00,indefinido,costa,maria@empresa.com,0987654321
```

**Validations:**
- Cédula válida (10 dígitos, algoritmo módulo 10)
- Fecha ingreso no futura
- Salario ≥ SBU ($482)
- Tipo contrato: indefinido, fijo, eventual, parcial
- Región: sierra, costa (para décimos)

### 1.3 Products CSV Template

```csv
codigo,nombre,categoria,precio_venta,costo,iva,tipo,unidad,codigo_barras
PROD001,Coca-Cola 500ml,Bebidas,0.75,0.50,15,producto,unidad,7890123456789
PROD002,Servicio Corte,Servicios,5.00,0,15,servicio,unidad,
```

### 1.4 Partners CSV Template (Clientes/Proveedores)

```csv
tipo,ruc_cedula,razon_social,nombre_comercial,email,telefono,direccion,tipo_contribuyente,es_cliente,es_proveedor
juridica,1793125212001,CANNACHAIN S.A.S.,CANNACHAIN,contacto@ejemplo.com,022345678,Av. Principal 123,general,1,0
natural,1713488185,CADENA PEÑA ADRIAN RAFAEL,,correo@ejemplo.com,0991234567,Calle 1 N1-23,natural,1,1
```

---

## 2. LEGAL IMPLICATIONS - COMPANY CREATION

### 2.1 SRI Requirements

| Requirement | Validation | System Action |
|:------------|:-----------|:--------------|
| RUC válido | API SRI | Auto-validate |
| Estado ACTIVO | API SRI | Block if PASIVO |
| Obligado Contabilidad | API SRI | Enable full accounting |
| Contribuyente Especial | API SRI | Special retention rules |
| RIMPE | API SRI | Simplified regime |

### 2.2 Labor Law (Código del Trabajo)

| Requirement | Validation | Legal Base |
|:------------|:-----------|:-----------|
| Salario ≥ SBU | $482 (2026) | CT Art. 117 |
| Contrato escrito | Obligatorio | CT Art. 19 |
| Registro IESS | 3 días desde ingreso | Ley IESS |
| Décimo Tercero | Provisión automática | CT Art. 111 |
| Décimo Cuarto | Sierra Ago/Costa Mar | CT Art. 113 |
| Vacaciones | 15 días/año | CT Art. 69 |
| Fondos Reserva | Después 13 meses | CT Art. 196 |

### 2.3 IESS Requirements

| Requirement | System Action |
|:------------|:--------------|
| Aviso de entrada | Generate form |
| Aporte personal 9.45% | Auto-calculate |
| Aporte patronal 12.15% | Auto-calculate |
| Techo $12,050/mes | Validate |

### 2.4 Fiscal Requirements

| Requirement | System Action | Legal Base |
|:------------|:--------------|:-----------|
| Factura electrónica | Configure | NAC-DGERCGC25-17 |
| Retenciones | Auto-calculate | LORTI |
| IVA 15% | Pre-configure | LORTI |
| ATS mensual | Generate | LORTI Art. 107 |

---

## 3. WIZARD FLOW WITH IMPORTS

### Step: Import Existing Data (Optional)

```
┌────────────────────────────────────────────────────────────────┐
│  📥 ¿TIENES DATOS EXISTENTES?                                  │
│                                                                │
│  Si ya tienes listas de empleados, productos o clientes,       │
│  puedes importarlos ahora:                                     │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ 👥 Empleados                                            │   │
│  │    [📎 Subir CSV]  [📄 Descargar Plantilla]            │   │
│  │    0 empleados cargados                                 │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ 📦 Productos (además de los del template)              │   │
│  │    [📎 Subir CSV]  [📄 Descargar Plantilla]            │   │
│  │    0 productos adicionales                              │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ 🏢 Clientes/Proveedores                                 │   │
│  │    [📎 Subir CSV]  [📄 Descargar Plantilla]            │   │
│  │    0 partners adicionales                               │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  [Saltar este paso →]        [Continuar con imports →]         │
└────────────────────────────────────────────────────────────────┘
```

### Import Validation Flow

```
CSV UPLOAD
    │
    ▼
┌─────────────────────┐
│ PARSE CSV           │
│ - Check format      │
│ - Check columns     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ VALIDATE EACH ROW   │
│ - Cédula/RUC valid  │
│ - Required fields   │
│ - Legal compliance  │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐   ┌────────┐
│ VALID  │   │ ERRORS │
│ ROWS   │   │ FOUND  │
└────┬───┘   └────┬───┘
     │            │
     ▼            ▼
┌─────────────────────┐
│ SHOW SUMMARY        │
│ ✅ 45 válidos       │
│ ❌ 3 con errores    │
│                     │
│ [Ver errores]       │
│ [Importar válidos]  │
└─────────────────────┘
```

---

## 4. LEGAL VALIDATIONS PER DATA TYPE

### 4.1 Employees

| Field | Validation | Error Message |
|:------|:-----------|:--------------|
| cedula | Módulo 10 | "Cédula inválida" |
| salario | ≥ $482 | "Salario menor al SBU 2026" |
| fecha_ingreso | ≤ today | "Fecha futura no permitida" |
| tipo_contrato | In list | "Tipo de contrato no válido" |
| region | sierra/costa | "Región no válida" |

### 4.2 Partners (Clientes/Proveedores)

| Field | Validation | Error Message |
|:------|:-----------|:--------------|
| ruc | 13 dígitos + módulo 11 | "RUC inválido" |
| cedula | 10 dígitos + módulo 10 | "Cédula inválida" |
| tipo | natural/juridica | "Tipo no válido" |
| tipo_contribuyente | In list | "Tipo contribuyente no válido" |

### 4.3 Products

| Field | Validation | Error Message |
|:------|:-----------|:--------------|
| precio | > 0 | "Precio debe ser mayor a 0" |
| iva | 0, 5, 15 | "Tarifa IVA no válida" |
| tipo | producto/servicio | "Tipo no válido" |

---

## 5. SIZE-BASED IMPORT OPTIONS

| Data Type | Simple | Medium | Enterprise |
|:----------|:-------|:-------|:-----------|
| Productos | ✅ | ✅ | ✅ |
| Clientes | ✅ | ✅ | ✅ |
| Proveedores | ❌ | ✅ | ✅ |
| Empleados | ❌ | ✅ | ✅ |
| Plan Cuentas | ❌ | ❌ | ✅ |
| Saldos Iniciales | ❌ | ❌ | ✅ |

---

## 6. POST-IMPORT ACTIONS

### For Employees (IESS)

```
AFTER IMPORT:
    │
    ▼
┌─────────────────────┐
│ GENERATE IESS FORMS │
│ - Aviso de entrada  │
│ - Por cada empleado │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ REMINDER:           │
│ "Debes registrar    │
│ estos empleados en  │
│ el IESS dentro de   │
│ 3 días hábiles"     │
└─────────────────────┘
```

### For Existing Business (Saldos)

```
IF MIGRATING FROM ANOTHER SYSTEM:
    │
    ▼
┌─────────────────────┐
│ SALDOS INICIALES    │
│ - Cuentas por cobrar│
│ - Cuentas por pagar │
│ - Inventario inicial│
│ - Bancos            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ASIENTO APERTURA    │
│ Fecha: [01/01/2026] │
│ Genera automático   │
└─────────────────────┘
```

---

**END OF DOCUMENT**
