# AI AGENT: MCP TOOLS REFERENCE
## Complete Django MCP Tool Definitions for Odoo Operations

**Document ID**: AI-MCP-002
**Version**: 1.0
**Last Updated**: 2026-01-22

---

## 1. MCP TOOLS OVERVIEW

MCP Tools are **action functions** that modify Odoo data. The AI agent calls these tools to perform operations.

```python
# Tool structure
@mcp_tool("tool_name")
async def tool_name(
    param1: type,
    param2: type = default
) -> dict:
    """Tool description for AI agent"""
    pass
```

---

## 2. INVOICING TOOLS

### 2.1 create_invoice
```python
@mcp_tool("create_invoice")
async def create_invoice(
    customer_name: str,          # Customer name or RUC
    items: list[dict],           # [{product, qty, price}]
    invoice_date: str = None,    # DD/MM/YYYY, defaults today
    payment_term: str = None     # Immediate, 30 days, etc.
) -> dict:
    """
    Creates a draft customer invoice in Odoo.
    Returns invoice ID, number, and totals.
    """
    return {
        "invoice_id": 123,
        "number": "FAC-001-001-000000123",
        "subtotal": 1000.00,
        "iva": 150.00,
        "total": 1150.00,
        "status": "draft"
    }
```

### 2.2 post_invoice
```python
@mcp_tool("post_invoice")
async def post_invoice(
    invoice_id: int,
    send_to_sri: bool = True
) -> dict:
    """
    Posts invoice and optionally sends to SRI.
    Returns access key and authorization status.
    """
    return {
        "status": "posted",
        "clave_acceso": "22012026011793125212001...",
        "sri_status": "AUTORIZADO",
        "numero_autorizacion": "22012026011793125212001..."
    }
```

### 2.3 send_ride_whatsapp
```python
@mcp_tool("send_ride_whatsapp")
async def send_ride_whatsapp(
    invoice_id: int,
    phone: str = None  # If not provided, uses customer's
) -> dict:
    """Sends RIDE PDF via WhatsApp to customer"""
    return {"sent": True, "phone": "+593991234567"}
```

### 2.4 create_credit_note
```python
@mcp_tool("create_credit_note")
async def create_credit_note(
    original_invoice_id: int,
    reason: str,
    lines: list[dict] = None  # Partial CN, or full if None
) -> dict:
    """Creates credit note referencing original invoice"""
    return {
        "credit_note_id": 456,
        "number": "NC-001-001-000000001",
        "total": -500.00
    }
```

---

## 3. WITHHOLDING TOOLS

### 3.1 create_withholding
```python
@mcp_tool("create_withholding")
async def create_withholding(
    vendor_bill_id: int,
    ir_taxes: list[dict],    # [{code, base, rate}]
    iva_taxes: list[dict]    # [{rate, base}]
) -> dict:
    """Creates withholding certificate for vendor bill"""
    return {
        "withholding_id": 789,
        "number": "RET-001-001-000000001",
        "total_ir": 20.00,
        "total_iva": 45.00
    }
```

### 3.2 calculate_withholding
```python
@mcp_tool("calculate_withholding")
async def calculate_withholding(
    vendor_name: str,
    base_amount: float,
    transaction_type: str  # goods, services, professional
) -> dict:
    """Calculates applicable withholding rates"""
    return {
        "ir_rate": "1.75%",
        "ir_amount": 17.50,
        "iva_rate": "30%",
        "iva_base": 150.00,
        "iva_amount": 45.00,
        "is_within_5_days": True
    }
```

---

## 4. PURCHASE TOOLS

### 4.1 create_purchase_order
```python
@mcp_tool("create_purchase_order")
async def create_purchase_order(
    vendor_name: str,
    items: list[dict],        # [{product, qty, price}]
    images: list[str] = None  # Base64 images for OCR
) -> dict:
    """
    Creates draft PO. If images provided, extracts items via OCR.
    """
    return {
        "po_id": 111,
        "name": "PO-2026-0001",
        "lines": [...],
        "total": 1531.80,
        "status": "draft"
    }
```

### 4.2 confirm_purchase_order
```python
@mcp_tool("confirm_purchase_order")
async def confirm_purchase_order(po_id: int) -> dict:
    """Confirms purchase order"""
    return {"status": "confirmed", "name": "PO-2026-0001"}
```

### 4.3 receive_products
```python
@mcp_tool("receive_products")
async def receive_products(
    po_id: int,
    received_lines: list[dict] = None  # Partial reception
) -> dict:
    """Records product reception in warehouse"""
    return {
        "picking_id": 222,
        "status": "done",
        "received_qty": 100
    }
```

---

## 5. PAYROLL TOOLS

### 5.1 generate_payslips
```python
@mcp_tool("generate_payslips")
async def generate_payslips(
    period: str,          # "2026-01" format
    employee_ids: list[int] = None  # All if None
) -> dict:
    """Generates payslip batch for period"""
    return {
        "batch_id": 55,
        "count": 45,
        "total_gross": 125000.00,
        "total_net": 98000.00
    }
```

### 5.2 calculate_liquidation
```python
@mcp_tool("calculate_liquidation")
async def calculate_liquidation(
    employee_name: str,
    termination_type: str,  # despido, renuncia, desahucio
    termination_date: str
) -> dict:
    """Calculates full termination liquidation"""
    return {
        "pending_salary": 840.00,
        "decimo_13": 170.00,
        "decimo_14": 232.87,
        "vacations": 600.00,
        "indemnification": 4800.00,
        "total": 6642.87
    }
```

### 5.3 generate_iess_planilla
```python
@mcp_tool("generate_iess_planilla")
async def generate_iess_planilla(period: str) -> dict:
    """Generates IESS monthly contribution file"""
    return {
        "file_path": "/path/to/planilla.csv",
        "total_personal": 11812.50,
        "total_patronal": 15187.50,
        "employee_count": 45
    }
```

---

## 6. COLLECTION TOOLS

### 6.1 get_customer_balance
```python
@mcp_tool("get_customer_balance")
async def get_customer_balance(customer_name: str) -> dict:
    """Gets AR balance for customer"""
    return {
        "customer": "LA FAVORITA SAS",
        "total_due": 5000.00,
        "current": 2000.00,
        "overdue_30": 1500.00,
        "overdue_60": 1000.00,
        "overdue_90": 500.00
    }
```

### 6.2 send_payment_reminder
```python
@mcp_tool("send_payment_reminder")
async def send_payment_reminder(
    customer_name: str,
    channel: str = "whatsapp",  # whatsapp, sms, email
    invoices: list[int] = None  # Specific or all overdue
) -> dict:
    """Sends payment reminder via specified channel"""
    return {"sent": True, "channel": "whatsapp", "invoices": [123, 456]}
```

### 6.3 record_payment
```python
@mcp_tool("record_payment")
async def record_payment(
    customer_name: str,
    amount: float,
    payment_method: str,
    invoices: list[int] = None  # Auto-allocate if None
) -> dict:
    """Records customer payment"""
    return {
        "payment_id": 333,
        "amount": 1500.00,
        "invoices_paid": [123],
        "remaining_balance": 3500.00
    }
```

---

## 7. REPORTING TOOLS

### 7.1 get_sales_summary
```python
@mcp_tool("get_sales_summary")
async def get_sales_summary(
    period: str,  # "2026-01" or "2026"
    group_by: str = "product"  # product, customer, salesperson
) -> dict:
    """Gets sales summary for period"""
    return {
        "total": 125000.00,
        "count": 234,
        "top_items": [...]
    }
```

### 7.2 generate_ats
```python
@mcp_tool("generate_ats")
async def generate_ats(period: str) -> dict:
    """Generates ATS XML file for SRI"""
    return {
        "file_path": "/path/to/ats_202601.xml",
        "sales_count": 234,
        "purchases_count": 89,
        "withholdings_count": 45
    }
```

### 7.3 get_ar_aging
```python
@mcp_tool("get_ar_aging")
async def get_ar_aging() -> dict:
    """Gets AR aging report"""
    return {
        "total": 50000.00,
        "current": 20000.00,
        "1_30": 15000.00,
        "31_60": 8000.00,
        "61_90": 5000.00,
        "over_90": 2000.00
    }
```

---

## 8. INVENTORY TOOLS

### 8.1 get_stock_level
```python
@mcp_tool("get_stock_level")
async def get_stock_level(
    product_name: str,
    location: str = None  # All if None
) -> dict:
    """Gets current stock level for product"""
    return {
        "product": "Arroz Diana 50kg",
        "qty_available": 150,
        "qty_reserved": 20,
        "qty_free": 130,
        "locations": [...]
    }
```

### 8.2 create_transfer
```python
@mcp_tool("create_transfer")
async def create_transfer(
    source_location: str,
    dest_location: str,
    products: list[dict]  # [{product, qty}]
) -> dict:
    """Creates internal stock transfer"""
    return {
        "picking_id": 444,
        "name": "INT/2026/0001",
        "status": "draft"
    }
```

---

## 9. ERROR CODES

| Code | Description | AI Response |
|:-----|:------------|:------------|
| E001 | Customer not found | "No encontré ese cliente" |
| E002 | Product not found | "Producto no existe" |
| E003 | Insufficient stock | "Stock insuficiente" |
| E004 | SRI timeout | "SRI no responde, reintentando..." |
| E005 | 5-day rule violation | "Retención fuera del plazo de 5 días" |
| E006 | CF limit exceeded | "Monto excede $50 para CF" |

---

**Document Classification**: MCP Technical Reference
**Owner**: Development Team
**Last Updated**: 2026-01-22
