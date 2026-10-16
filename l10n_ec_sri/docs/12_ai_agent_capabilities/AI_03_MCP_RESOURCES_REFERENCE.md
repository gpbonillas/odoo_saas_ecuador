# AI AGENT: MCP RESOURCES REFERENCE
## AI_03 - Django MCP Resources for Odoo Ecuador

**Document ID**: AI-003 | **Version**: 1.0 | **Date**: 2026-01-22
**Owner**: AI Architect (Expert Crew)

---

## 1. OVERVIEW

MCP Resources are read-only data endpoints that AI agents can query to provide context for operations.

---

## 2. RESOURCE DEFINITIONS

### 2.1 Partner Resources

```python
@mcp.resource("odoo://partners/{partner_id}")
def get_partner(partner_id: str) -> PartnerResource:
    """Get partner details including tax status."""
    return {
        "id": partner_id,
        "name": "Company Name",
        "vat": "1793125212001",
        "id_type": "ruc",  # ruc, cedula, pasaporte
        "address": {...},
        "is_withholding_agent": True,
        "credit_limit": 50000.00,
        "balance_due": 12500.00,
        "last_invoice_date": "2026-01-15",
    }

@mcp.resource("odoo://partners/search")
def search_partners(query: str) -> list[PartnerResource]:
    """Search partners by name or VAT."""
```

### 2.2 Product Resources

```python
@mcp.resource("odoo://products/{product_id}")
def get_product(product_id: str) -> ProductResource:
    """Get product details including tax configuration."""
    return {
        "id": product_id,
        "name": "Widget Pro",
        "sku": "WGT-001",
        "price": 150.00,
        "tax_ids": ["iva_15"],
        "stock_qty": 250,
        "category": "Electronics",
    }

@mcp.resource("odoo://products/stock_summary")
def get_stock_summary() -> StockSummary:
    """Get warehouse stock levels."""
```

### 2.3 Invoice Resources

```python
@mcp.resource("odoo://invoices/{invoice_id}")
def get_invoice(invoice_id: str) -> InvoiceResource:
    """Get invoice with SRI status."""
    return {
        "id": invoice_id,
        "number": "001-001-000012345",
        "partner": {...},
        "date": "2026-01-15",
        "amount_total": 1150.00,
        "sri_status": "authorized",  # draft, sent, authorized, rejected
        "sri_authorization": "15012026...",
        "payment_status": "partial",
        "balance_due": 500.00,
    }

@mcp.resource("odoo://invoices/pending")
def get_pending_invoices() -> list[InvoiceResource]:
    """Get invoices pending SRI authorization."""

@mcp.resource("odoo://invoices/overdue")
def get_overdue_invoices() -> list[InvoiceResource]:
    """Get overdue invoices for collection."""
```

### 2.4 Payroll Resources

```python
@mcp.resource("odoo://employees/{employee_id}")
def get_employee(employee_id: str) -> EmployeeResource:
    """Get employee with contract details."""
    return {
        "id": employee_id,
        "name": "Juan Pérez",
        "cedula": "1234567890",
        "contract": {
            "wage": 1200.00,
            "start_date": "2024-03-15",
            "months_worked": 22,
            "fondos_reserva_eligible": True,
        },
        "department": "Sales",
    }

@mcp.resource("odoo://payroll/period/{period}")
def get_payroll_period(period: str) -> PayrollPeriodResource:
    """Get payroll period summary."""

@mcp.resource("odoo://payroll/iess_pending")
def get_iess_pending() -> IESSPendingResource:
    """Get pending IESS submissions."""
```

### 2.5 Tax Resources

```python
@mcp.resource("odoo://taxes/withholding_codes")
def get_withholding_codes() -> list[WithholdingCode]:
    """Get all IR/IVA withholding codes."""
    return [
        {"code": "303", "name": "10% Honorarios", "rate": 10},
        {"code": "312", "name": "10% Servicios", "rate": 10},
        {"code": "343", "name": "2% Otras retenciones", "rate": 2},
        # ...
    ]

@mcp.resource("odoo://taxes/sri_calendar")
def get_sri_calendar() -> SRICalendar:
    """Get upcoming SRI deadlines."""
```

### 2.6 Report Resources

```python
@mcp.resource("odoo://reports/sales_summary")
def get_sales_summary(period: str) -> SalesSummary:
    """Get sales summary for AI analysis."""

@mcp.resource("odoo://reports/tax_summary")
def get_tax_summary(period: str) -> TaxSummary:
    """Get tax collected/paid summary."""

@mcp.resource("odoo://reports/cash_flow")
def get_cash_flow(days: int = 30) -> CashFlowReport:
    """Get cash flow projection."""
```

---

## 3. RESOURCE TEMPLATES

### 3.1 URI Patterns

| Pattern | Example | Description |
|:--------|:--------|:------------|
| `odoo://{model}/{id}` | `odoo://partners/42` | Single record |
| `odoo://{model}/search` | `odoo://products/search` | Search endpoint |
| `odoo://{model}/{filter}` | `odoo://invoices/pending` | Filtered list |
| `odoo://reports/{name}` | `odoo://reports/sales_summary` | Generated report |

---

## 4. CONTEXT BUILDING EXAMPLE

```python
# AI Agent builds context before executing action
async def handle_collection_request(partner_name: str):
    # Get partner context
    partner = await mcp.read_resource(f"odoo://partners/search?q={partner_name}")

    # Get overdue invoices
    invoices = await mcp.read_resource(
        f"odoo://invoices/overdue?partner_id={partner['id']}"
    )

    # Build context for LLM
    context = f"""
    Cliente: {partner['name']}
    RUC: {partner['vat']}
    Saldo Vencido: ${sum(inv['balance_due'] for inv in invoices)}
    Facturas Vencidas: {len(invoices)}
    """

    return context
```

---

## 5. CACHING STRATEGY

| Resource Type | TTL | Invalidation |
|:--------------|:----|:-------------|
| Partner details | 5 min | On update |
| Product stock | 1 min | On movement |
| Invoice status | 30 sec | On SRI response |
| Reports | 15 min | On demand |
| Tax codes | 24 hr | Manual |

---

**AI Resource Classification**: ISO 9001:2015 Controlled
