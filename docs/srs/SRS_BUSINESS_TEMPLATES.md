# SRS - Business Template System
## AI-Assisted Company Setup + Operations

**Document ID:** SRS-L10N-EC-BUSINESS-TEMPLATES
**Version:** 1.0.0
**Date:** 2026-01-25
**Status:** PLANNING

---

## 1. EXECUTIVE SUMMARY

### 1.1 Vision

**5 MINUTES from install to INVOICING**

Any business owner (tendero, panadero, dentista) can:
1. Select their business type
2. Enter RUC (or login SRI)
3. Start selling immediately

The AI Agent handles everything else.

### 1.2 Two-Dimensional Selection

**BUSINESS TYPE** = What products to load
**BUSINESS SIZE** = How complex the system

```
SELECT:
┌────────────────────────────────────────────────────────────┐
│  1. ¿Qué tipo de negocio?                                  │
│     🍞 Panadería                                           │
│                                                            │
│  2. ¿Qué tamaño?                                          │
│     ○ Pequeño (POS simple)        ← Panadería de Barrio   │
│     ○ Mediano (+ Inventario)      ← Panaderías Guaraní    │
│     ○ Grande (ERP completo)       ← SUPAN                 │
└────────────────────────────────────────────────────────────┘
```

### 1.3 Size Determines Features

| Feature | Simple | Medium | Enterprise |
|:--------|:-------|:-------|:-----------|
| POS | ✅ | ✅ | ✅ |
| Products | Pre-loaded | Pre-loaded | Pre-loaded |
| Invoicing | Auto | Auto | Auto |
| Inventory | ❌ | ✅ | ✅ |
| Stock Alerts | ❌ | ✅ | ✅ |
| Production/BOM | ❌ | Basic | Full MRP |
| Multi-Warehouse | ❌ | ❌ | ✅ |
| Advanced Reports | ❌ | Basic | Full |
| Accounting | Auto | Basic | Full |
| HR/Payroll | ❌ | ❌ | ✅ |

### 1.3.1 Size Metrics (What Defines Implementation)

| Metric | Simple | Medium | Enterprise |
|:-------|:-------|:-------|:-----------|
| **Employees** | 1-3 | 4-15 | 16+ |
| **Annual Revenue** | <$50K | $50K-$500K | >$500K |
| **Locations** | 1 | 1-3 | Multiple |
| **Users** | 1 | 2-5 | 6+ |
| **Obligado Contab.** | No | Maybe | Yes |
| **Contrib. Especial** | No | No | Maybe |

### 1.3.2 System Auto-Detection

System can suggest size based on:
- RUC type (natural vs juridica)
- SRI data (obligado contabilidad)
- User answers (¿cuántos empleados?)

### 1.4 Same Products, Different Complexity

| Business | Simple | Medium | Enterprise |
|:---------|:-------|:-------|:-----------|
| Panadería | Barrio | Guaraní | SUPAN |
| Ferretería | Pequeña | Regional | Kywi |
| Farmacia | Barrio | Cadena | Fybeca |
| Restaurante | Pequeño | Cadena | Franquicia |

### 1.5 Target Users

| Persona | Skill Level | Needs |
|:--------|:------------|:------|
| 🏪 Tendero | Basic | Scan → Sell → Collect |
| 🍞 Panadero | Basic | Sell → Invoice → End of day |
| 🔧 Ferretero | Medium | Inventory + Sales |
| 🦷 Dentista | Medium | Appointments + Invoice |
| 🏢 PYME | Advanced | Full accounting |
| 🏭 Enterprise | Expert | Complete ERP |

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Components

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  AI Agent   │  │   Wizard    │  │    POS      │         │
│  │   (Chat)    │  │  (Steps)    │  │   (Scan)    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
└─────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                     MCP LAYER                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Agent Tools: query_erp, create_invoice, get_stock  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    ODOO BACKEND                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │Products│ │Partners│ │ Stock  │ │Invoices│ │  POS   │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                 EXTERNAL SERVICES                            │
│  ┌────────┐ ┌────────┐ ┌────────┐                          │
│  │  SRI   │ │  IESS  │ │  BCE   │                          │
│  └────────┘ └────────┘ └────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. BUSINESS TEMPLATES

### 3.1 Template Definition

```python
class BusinessTemplate:
    name: str           # "Tienda de Barrio"
    code: str           # "tienda_barrio"
    icon: str           # "🏪"
    tier: str           # "pymes" | "enterprise"

    products: List[Product]
    suppliers: List[Partner]
    categories: List[Category]
    pos_config: POSConfig
    bom_recipes: List[BOM]  # For production businesses
```

### 3.2 Available Templates

| Template | Products | Suppliers | BOM | POS |
|:---------|:---------|:----------|:----|:----|
| 🏪 Tienda de Barrio | 80+ | 5 | ❌ | ✅ |
| 🍞 Panadería | 30 | 4 | ✅ | ✅ |
| 🍽️ Restaurante | 40 | 6 | ✅ | ✅ |
| 🔧 Ferretería | 50 | 5 | ❌ | ✅ |
| 💇 Peluquería | 25 | 3 | ❌ | ✅ |
| 🦷 Consultorio Dental | 20 | 3 | ❌ | ❌ |
| 🏥 Consultorio Médico | 15 | 2 | ❌ | ❌ |
| 📚 Papelería | 40 | 4 | ❌ | ✅ |
| 🚗 Taller Mecánico | 30 | 5 | ❌ | ✅ |
| 🏥 Farmacia | 50 | 4 | ❌ | ✅ |

---

## 4. USER FLOWS

### 4.1 FLOW: Initial Setup (5 minutes)

```
┌──────────────────────────────────────────────────────────────┐
│                    SETUP FLOW                                 │
└──────────────────────────────────────────────────────────────┘

START
  │
  ▼
┌─────────────────────┐
│ SELECT BUSINESS     │
│ TYPE                │
│ [Grid of icons]     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ENTER RUC           │
│ [1793125212001]     │
│                     │
│ ☐ Login SRI         │◄─── OPTIONAL
│   (user/pass)       │
└──────────┬──────────┘
           │
           ├──────────────────────┐
           │                      │
           ▼                      ▼
┌─────────────────────┐  ┌─────────────────────┐
│ AUTO-FILL FROM      │  │ DOWNLOAD FIRMA      │
│ RUC API             │  │ FROM SRI PORTAL     │
│ - Razón Social      │  │ - Certificate .p12  │
│ - Dirección         │  │ - Puntos Emisión    │
│ - Estado            │  └──────────┬──────────┘
└──────────┬──────────┘             │
           │                        │
           ▼                        │
┌─────────────────────┐             │
│ OR: UPLOAD .p12     │◄────────────┘
│ MANUALLY            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ CONFIRM             │
│                     │
│ "Tu tienda tendrá:  │
│  • 80+ productos    │
│  • 5 proveedores    │
│  • POS listo"       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ LOAD TEMPLATE       │
│ - Create products   │
│ - Create suppliers  │
│ - Configure POS     │
│ - Setup sequences   │
└──────────┬──────────┘
           │
           ▼
         DONE
   ✅ READY TO SELL
```

---

### 4.2 FLOW: Tendero Daily Operation

```
┌──────────────────────────────────────────────────────────────┐
│                TENDERO FLOW (SIMPLEST)                        │
└──────────────────────────────────────────────────────────────┘

MORNING: Open POS
  │
  ▼
┌─────────────────────┐
│ SCAN PRODUCT        │
│ [Beep - Coca-Cola]  │
│                     │
│ + $0.75             │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ SCAN MORE OR        │
│ [COBRAR]            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌─────────────────────┐
│ TOTAL < $50?        │─YES─▶│ NOTA DE VENTA       │
│                     │      │ (No RUC needed)     │
└──────────┬──────────┘      └─────────────────────┘
           │ NO
           ▼
┌─────────────────────┐
│ ASK: ¿RUC o Cédula? │
│ [9999999999999]     │◄── Consumidor Final
│ OR [Cliente RUC]    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ AUTO: FACTURA       │
│ ELECTRÓNICA         │
│ - Send to SRI       │
│ - Print RIDE        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ COLLECT PAYMENT     │
│ - Cash              │
│ - Card              │
│ - Transfer          │
└──────────┬──────────┘
           │
           ▼
      NEXT CUSTOMER

EVENING: Close POS
  │
  ▼
┌─────────────────────┐
│ AUTO CASH COUNT     │
│ "Vendiste $250 hoy" │
│ "Efectivo: $180"    │
│ "Tarjeta: $70"      │
└─────────────────────┘
```

---

### 4.3 FLOW: AI Agent Queries

```
┌──────────────────────────────────────────────────────────────┐
│                AI AGENT WITH MCP                              │
└──────────────────────────────────────────────────────────────┘

USER: "¿Cuándo fue el último pago a Coca-Cola?"

AGENT:
  │
  ▼
┌─────────────────────┐
│ MCP: query_erp()    │
│                     │
│ SELECT MAX(date)    │
│ FROM account_payment│
│ WHERE partner =     │
│ 'Coca-Cola'         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RESPONSE:           │
│ "El último pago a   │
│ Coca-Cola fue el    │
│ 15 de enero por     │
│ $450.00"            │
└─────────────────────┘

---

USER: "¿Cuántas Coca-Colas tengo en stock?"

AGENT:
  │
  ▼
┌─────────────────────┐
│ MCP: get_stock()    │
│                     │
│ product: Coca-Cola  │
│ location: WH/Stock  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RESPONSE:           │
│ "Tienes 48 unidades │
│ de Coca-Cola 500ml" │
└─────────────────────┘

---

USER: "Crea una factura para Juan Pérez"

AGENT:
  │
  ▼
┌─────────────────────┐
│ MCP: create_invoice │
│                     │
│ Partner: Juan Pérez │
│ Products: [from POS]│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ FACTURA FAC-001-001 │
│ Created & sent SRI  │
└─────────────────────┘
```

---

### 4.4 FLOW: Purchase from Supplier

```
┌──────────────────────────────────────────────────────────────┐
│              PURCHASE FLOW (TENDERO)                          │
└──────────────────────────────────────────────────────────────┘

SUPPLIER DELIVERS
  │
  ▼
┌─────────────────────┐
│ SCAN SUPPLIER       │
│ INVOICE BARCODE     │
│ OR: Enter # manual  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ SYSTEM AUTO:        │
│ - Validate SRI      │
│ - Match products    │
│ - Update stock      │
│ - Calculate ret.    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ AUTO: RETENTION     │
│ (If applicable)     │
│ - IR 1% goods       │
│ - IVA 30% Cont.Esp. │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ SCHEDULE PAYMENT    │
│ OR: Pay now         │
└─────────────────────┘
```

---

## 5. LEGAL COMPLIANCE (AUTO)

### 5.1 Automatic Rules

| Rule | Condition | System Action |
|:-----|:----------|:--------------|
| Nota Venta vs Factura | Amount ≤ $50 | Issue Nota de Venta |
| Consumidor Final | RUC = 9999999999999 | Auto-apply |
| Retención Required | Purchase > $50 | Auto-calculate |
| IVA 15% | Standard sale | Auto-apply |
| RIDE Print | Always | Auto-generate |

### 5.2 Configuration Parameters

```python
# System auto-configures based on law

PARAMS = {
    'nota_venta_limit': 50.00,          # LORTI
    'consumidor_final_ruc': '9999999999999',
    'iva_rate': 0.15,                   # 2026
    'retention_threshold': 50.00,
    'sri_transmission': 'immediate',    # NAC-2025-17
}
```

---

## 6. MCP AGENT TOOLS

### 6.1 Available Tools

| Tool | Description | Example |
|:-----|:------------|:--------|
| `query_erp` | SQL-like queries | "Last payment to X" |
| `get_stock` | Stock levels | "How many X in stock" |
| `create_invoice` | Create document | "Invoice for X" |
| `create_payment` | Register payment | "Pay supplier X" |
| `get_report` | Generate report | "Sales today" |
| `search_partner` | Find partner | "Find Juan Pérez" |

### 6.2 Tool Implementation

```python
@mcp_tool
def query_erp(model: str, domain: list, fields: list):
    """Query any Odoo model."""
    return request.env[model].search_read(domain, fields)

@mcp_tool
def get_stock(product_name: str):
    """Get stock qty for product."""
    product = env['product.product'].search([
        ('name', 'ilike', product_name)
    ], limit=1)
    return product.qty_available

@mcp_tool
def create_invoice(partner_name: str, lines: list):
    """Create and validate invoice."""
    invoice = env['account.move'].create({...})
    invoice.action_post()
    invoice.action_send_sri()
    return invoice.name
```

---

## 7. IMPLEMENTATION PHASES

### Phase 1: Template System (3 days)
- [ ] Business template model
- [ ] Tienda de Barrio template (80+ products)
- [ ] Panadería template (30 products + BOM)
- [ ] Restaurante template (40 products + BOM)

### Phase 2: Wizard Integration (2 days)
- [ ] Business type selection step
- [ ] Template loading on confirm
- [ ] POS auto-configuration

### Phase 3: MCP Agent Tools (3 days)
- [ ] query_erp tool
- [ ] get_stock tool
- [ ] create_invoice tool
- [ ] Payment tools

### Phase 4: Remaining Templates (Ongoing)
- [ ] Ferretería
- [ ] Peluquería
- [ ] Dental
- [ ] Others

---

## 8. SUCCESS CRITERIA

| Metric | Target |
|:-------|:-------|
| Setup Time | ≤ 5 minutes |
| First Sale | < 10 minutes |
| Training Required | 0 (AI guides) |
| Support Calls | Minimal |

---

**END OF DOCUMENT**
