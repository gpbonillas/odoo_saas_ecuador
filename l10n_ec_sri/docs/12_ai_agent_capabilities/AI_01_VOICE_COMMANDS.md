# AI AGENT CAPABILITIES: VOICE COMMANDS REFERENCE
## Natural Language Commands for Odoo via Django MCP

**Document ID**: AI-VOICE-001
**Version**: 1.0
**Last Updated**: 2026-01-22

---

## 1. OVERVIEW

The AI Agent accepts natural language commands in **Spanish** or **English** and executes them via Django MCP → Odoo.

```
┌─────────────────────────────────────────────────────────────┐
│              USER (Voice/Text/WhatsApp/SMS)                 │
│  "Crea una factura para SUPERMAXI por $500 de productos"   │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    AI AGENT (Claude/GPT)                     │
│  • Parses intent: CREATE_INVOICE                            │
│  • Extracts: customer=SUPERMAXI, amount=$500                │
│  • Calls MCP Tool: create_invoice()                         │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                     DJANGO MCP SERVER                        │
│  • Validates parameters                                      │
│  • Calls Odoo XML-RPC                                       │
│  • Returns structured response                               │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                        ODOO 18                               │
│  • Creates account.move record                              │
│  • Triggers e-invoicing workflow                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. COMMAND CATEGORIES

### 2.1 INVOICING COMMANDS

| Command (Spanish) | Command (English) | Action |
|:------------------|:------------------|:-------|
| "Crea una factura para [CLIENTE] por [MONTO]" | "Create invoice for [CLIENT] for [AMOUNT]" | Creates draft invoice |
| "Envía la factura [NÚMERO] al SRI" | "Send invoice [NUMBER] to SRI" | Posts and transmits |
| "¿Cuál es el estado de la factura [NÚMERO]?" | "What's the status of invoice [NUMBER]?" | Checks authorization |
| "Muéstrame las facturas pendientes de autorización" | "Show me pending invoices" | Lists pending |
| "Anula la factura [NÚMERO]" | "Cancel invoice [NUMBER]" | Creates credit note |
| "Envía el RIDE de [NÚMERO] por WhatsApp al cliente" | "Send RIDE of [NUMBER] via WhatsApp" | Sends PDF to customer |

### 2.2 PURCHASE ORDER COMMANDS

| Command (Spanish) | Action |
|:------------------|:-------|
| "Crea una orden de compra para [PROVEEDOR] con estos items [LISTA/FOTO]" | Creates draft PO with OCR from image |
| "Aprueba la orden de compra [NÚMERO]" | Confirms PO |
| "¿Cuáles son las órdenes pendientes de [PROVEEDOR]?" | Lists open POs |
| "Registra la recepción del pedido [NÚMERO]" | Creates stock picking |

### 2.3 WITHHOLDING COMMANDS

| Command (Spanish) | Action |
|:------------------|:-------|
| "Genera retención para la factura del proveedor [NOMBRE]" | Creates retention |
| "Envía la retención [NÚMERO] al SRI" | Signs and transmits |
| "¿Cuánto debemos retener a [PROVEEDOR]?" | Calculates applicable rates |

### 2.4 PAYROLL COMMANDS

| Command (Spanish) | Action |
|:------------------|:-------|
| "Calcula la nómina del mes" | Generates payslip batch |
| "¿Cuánto le corresponde de décimo tercero a [EMPLEADO]?" | Calculates D13 |
| "Calcula la liquidación de [EMPLEADO] por despido" | Full termination calc |
| "¿Cuál es el total de aportes IESS este mes?" | Sums IESS contributions |
| "Genera la planilla IESS del mes" | Creates IESS file |

### 2.5 COLLECTION COMMANDS

| Command (Spanish) | Action |
|:------------------|:-------|
| "¿Cuánto nos debe [CLIENTE]?" | Shows AR balance |
| "Envía recordatorio de pago a [CLIENTE]" | Sends SMS/WhatsApp |
| "Muéstrame la cartera vencida" | AR aging report |
| "Registra el pago de [CLIENTE] por [MONTO]" | Records payment |

### 2.6 REPORTING COMMANDS

| Command (Spanish) | Action |
|:------------------|:-------|
| "¿Cuáles son las ventas del mes?" | Sales summary |
| "Dame el estado de resultados" | P&L report |
| "¿Cuánto tenemos en cuentas por pagar?" | AP balance |
| "Genera el ATS del mes pasado" | Creates ATS XML |
| "¿Cuántos documentos electrónicos hemos emitido?" | Document count |

### 2.7 INVENTORY COMMANDS

| Command (Spanish) | Action |
|:------------------|:-------|
| "¿Cuánto stock tenemos de [PRODUCTO]?" | Stock quantity |
| "Crea una transferencia de [ORIGEN] a [DESTINO]" | Internal transfer |
| "¿Qué productos están por debajo del mínimo?" | Low stock alert |

---

## 3. WORKFLOW EXAMPLES

### 3.1 Complete Invoice Workflow
```
Usuario: "Factura a LA FAVORITA SAS por 100 unidades de arroz a $45 cada una"

AI: Buscando cliente LA FAVORITA SAS... ✓
    Buscando producto arroz... ✓ (Arroz Diana 50kg, código: ARROZ-001)

    Creando factura:
    • Cliente: LA FAVORITA SAS (RUC: 1793125212001)
    • Línea: Arroz Diana 50kg x 100 @ $45.00 = $4,500.00
    • Subtotal: $4,500.00
    • IVA 15%: $675.00
    • TOTAL: $5,175.00

    ¿Confirmo y envío al SRI?

Usuario: "Sí"

AI: Confirmando factura FAC-001-001-000000234...
    Generando clave de acceso...
    Firmando con XAdES-BES...
    Enviando al SRI...

    ✅ AUTORIZADO
    Número de autorización: 2201202601179312521200120010010000002341234567811

    ¿Envío el RIDE por WhatsApp a LA FAVORITA SAS?

Usuario: "Sí, envíalo"

AI: ✅ RIDE enviado a +593991234567
```

### 3.2 Purchase Order with Photo
```
Usuario: "Crea orden de compra para DIPOR con estos productos"
         [adjunta foto de lista de productos]

AI: Procesando imagen...

    Detectados 5 productos:
    1. Coca-Cola 3L x 24 packs @ $18.00 = $432.00
    2. Sprite 3L x 12 packs @ $17.50 = $210.00
    3. Fanta 3L x 12 packs @ $17.50 = $210.00
    4. Agua Dasani 500ml x 48 @ $4.00 = $192.00
    5. Jugos del Valle 1L x 24 @ $12.00 = $288.00

    Subtotal: $1,332.00
    IVA 15%: $199.80
    TOTAL: $1,531.80

    ¿Creo la orden de compra PO-2026-0045?

Usuario: "Confirma"

AI: ✅ Orden PO-2026-0045 creada y confirmada
    Proveedor notificado por correo
```

### 3.3 Termination Calculation
```
Usuario: "Calcula la liquidación de María López,
          trabajó 4 años ganando $1,200 y la despidieron ayer"

AI: Calculando liquidación para María López...

    Datos:
    • Fecha ingreso: 15/01/2022
    • Fecha salida: 21/01/2026
    • Antigüedad: 4 años, 6 días
    • Último sueldo: $1,200.00
    • Tipo: Despido Intempestivo

    ════════════════════════════════════════════
    CÁLCULO DE LIQUIDACIÓN
    ════════════════════════════════════════════

    A. Haberes pendientes:
    • Sueldo proporcional (21 días): $840.00
    • Décimo 13 proporcional (1.7 meses): $170.00
    • Décimo 14 proporcional (Sierra, 174 días): $232.87
    • Vacaciones no gozadas (12 días): $600.00
    • Fondos de reserva pendientes: $0.00

    B. Indemnización por despido:
    • Base: 3 meses + 1 mes por año adicional
    • Cálculo: (3 + 1) × $1,200 = $4,800.00

    ════════════════════════════════════════════
    TOTAL LIQUIDACIÓN: $6,642.87
    ════════════════════════════════════════════

    ¿Genero el borrador del Acta de Finiquito?
```

---

## 4. ERROR HANDLING

| Error | AI Response |
|:------|:------------|
| Cliente no encontrado | "No encontré a [NOMBRE]. ¿Querés que lo cree?" |
| Producto no encontrado | "No existe [PRODUCTO]. ¿Buscas otro similar?" |
| Monto CF > $50 | "Consumidor Final no puede exceder $50. Necesito identificación." |
| SRI no disponible | "SRI no responde. Lo reintento en 5 minutos automáticamente." |
| Retención vencida | "Han pasado más de 5 días. Esta retención no es válida." |

---

## 5. SUPPORTED CHANNELS

| Channel | Input | Output |
|:--------|:------|:-------|
| **Web Chat** | Text | Text + Images |
| **WhatsApp** | Text, Voice, Images | Text + PDFs |
| **SMS** | Text | Text |
| **Mobile App** | Voice, Text, Camera | Text + Push Notifications |
| **API** | JSON | JSON |

---

**Document Classification**: AI Agent Documentation
**Owner**: Product / AI Team
**Last Updated**: 2026-01-22
