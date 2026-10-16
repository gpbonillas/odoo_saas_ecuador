# mcp_server — Gateway MCP para Odoo Ecuador (pure Python, cero dependencias)

Servidor **MCP (Model Context Protocol)** sobre transporte `stdio` implementado
directamente con la librería estándar de Python 3 (JSON-RPC 2.0 sobre JSON
delimitado por newlines en stdin/stdout). Traduce llamadas MCP del agente a
**JSON-RPC 2.0 sobre HTTP** contra Odoo, aplicando en el camino el motor de
reglas ecuatoriano (`rules.py`): RUC/cédula mod-11/mod-10, tipo de persona
jurídica/natural, Consumidor Final ≤ $50, anulación día 7, retención 5 días
hábiles con feriados, tablas IR/IVA, IESS con techo 25×SBU.

> **stdout es exclusivamente el canal MCP.** Todo el logging va a stderr.

## Archivos

| Archivo | Rol |
|---|---|
| `server.py` | Entrada: loop stdio JSON-RPC (`initialize`, `tools/*`, `resources/*`, `ping`) |
| `odoo_client.py` | Cliente JSON-RPC 2.0 de Odoo (`service/db|common|object`, auth por `session_id`) |
| `tools.py` | 18 herramientas MCP + handlers; todo error vuelve estructurado |
| `rules.py` | Motor de reglas ecuatoriano, **sin imports de Odoo** (unit-testeable offline) |
| `test_server.py` | `unittest` stdlib: handshake real por subprocess + reglas |

## Requisitos

- Python ≥ 3.9 (probado con 3.12). **Sin pip, sin npm, sin `requests`.**
- Un Odoo 18 con los módulos `l10n_ec*` instalados (opcional para arrancar:
  si Odoo está caído el servidor arranca igual y las herramientas devuelven
  `{"status":"error", "hint": ...}` o degradan con `sri.available=false`).

## Registro en OpenCode

Agregue este bloque en `~/.config/opencode/opencode.json` (o `opencode.json`
del proyecto), ajustando la ruta absoluta:

```json
{
  "mcp": {
    "odoo": {
      "type": "local",
      "command": ["python3", "/Users/macbookpro201916i964gb1tb/Documents/GitHub/odoo_saas_ecuador/mcp_server/server.py"],
      "environment": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "odooec",
        "ODOO_USER": "admin",
        "ODOO_PASSWORD": "admin",
        "ODOO_TIMEOUT": "30"
      }
    }
  }
}
```

Dentro del clúster Docker el `docker-compose.yml` ya define el servicio `mcp`
(`python:3.12-slim`, monta este directorio en `/app/mcp_server`). Para probar
a mano el transporte:

```bash
docker compose run --rm mcp
# y luego escribir líneas JSON, p.ej.:
# {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}
```

## Variables de entorno

| Var | Default | Descripción |
|---|---|---|
| `ODOO_URL` | `http://odoo:8069` | URL base de Odoo (Docker); use `http://localhost:8069` en local |
| `ODOO_DB` | `odooec` | Base de datos |
| `ODOO_USER` | `admin` | Usuario |
| `ODOO_PASSWORD` | `admin` | Contraseña |
| `ODOO_TIMEOUT` | `30` | Timeout HTTP (s) |

## Herramientas

| Tool | Qué hace (reglas aplicadas) |
|---|---|
| `detect_taxpayer` | CI/RUC, natural/jurídica (3er dígito), obligado contabilidad, contribuyente especial, agente de retención, RIMPE, checksum + estado SRI (degrada si el SRI no responde) |
| `validate_ruc` | módulo-11/módulo-10 + consulta SRI |
| `get_client_data` | Set legal completo de la factura + `missing_for_invoice` |
| `create_partner` | Prefill vía `l10n_ec.sri.ruc.service.consultar_ruc`; devuelve `missing_from_sri` |
| `create_invoice` | Detección de contribuyente, CF ≤ $50, `needs_data` + `question` si falta dato legal, codDoc 01/03 |
| `post_invoice` | `action_post` + `action_send_sri` (l10n_ec_edi); devuelve clave 49 díg. + estado SRI |
| `create_credit_note` | codDoc 04; CF no anulable; anulación solo hasta día 7 del mes siguiente |
| `calculate_withholding` | IR Tabla 19 / IVA 30-70; avisa vencimiento de 5 días hábiles (sin escribir) |
| `create_withholding` | `account.retention` (codDoc 07) con `l10n_ec.withholding.tax`; plazo 5 días hábiles |
| `generate_payslips` | `l10n_ec.payslip` para contratos activos + `action_confirm` |
| `generate_iess_planilla` | Agrega aportes personal/patronal de payslips confirmados |
| `calculate_liquidation` | Décimo 13/14, fondos 8.33%, IESS techo 25×SBU, renta progresiva opcional |
| `generate_ats` | `l10n_ec.ats.wizard.action_generate_ats` → XML ATS |
| `get_sales_summary` | Ventas + NC por periodo, top clientes, estados SRI |
| `get_ar_aging` | Buckets 0-30/31-60/61-90/90+ |
| `record_payment` | `account.payment` + `action_post` contra factura |
| `send_ride` | Reporte/URL si existe, clave de acceso, estado SRI, XML |
| `get_stock_level` | Existencias por producto |

## Ejemplos de prompts (en español, para el agente)

- *«Detecta el contribuyente del RUC 1792368647001 y dime si es agente de
  retención.»* → `detect_taxpayer`
- *«Hazme una factura para este cliente»* → el agente debe primero
  `get_client_data` (o `detect_taxpayer` con el RUC que le dio el usuario) y
  luego `create_invoice`; si el sistema responde
  `{"status":"needs_data","question":"..."}`, el agente repite la pregunta al
  usuario y vuelve a llamar con los datos faltantes.
- *«Ponle IVA 15% y factura 3 unidades del producto X a $20»* →
  `create_invoice` con `lines:[{...,"tax_rate":15}]`.
- *«Envíala al SRI y pásame la clave»* → `post_invoice`.
- *«Anula la factura 5 con nota de crédito por producto dañado»* →
  `create_credit_note` (el motor responde con la regla del día 7 o CF si aplica).
- *«¿Cuánto le retenemos a esta factura de servicios?»* →
  `calculate_withholding` (muestra base, %, monto y vencimiento del plazo).

## Verificación

```bash
python3 mcp_server/test_server.py     # 46 tests, sin Odoo
```

El test de handshake arranca `server.py` como subprocess, habla MCP real por
stdio (initialize → initialized → tools/list → ping → resources/read →
tools/call con Odoo caído) y verifica que stdout contenga **solo** JSON válido.
