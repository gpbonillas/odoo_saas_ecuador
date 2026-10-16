# Odoo shell script (sprint3_reports DB): e2e render checks for l10n_ec_reports.
# Renders the ATS XML template and PDF reports on wizard records created
# against whatever data exists in the scratch DB (may be empty rows - we
# validate the render pipeline, not the numbers, which unit tests cover).
import base64
from datetime import date

Company = env["res.company"].search([], limit=1)
print("E2E company:", Company.name, Company.vat)

# ---------- ATS wizard: generate + render XML ----------
ats = env["l10n_ec.ats.wizard"].create({
    "date_month": "09",
    "date_year": "2025",
    "company_id": Company.id,
})
ats.action_generate_ats()
xml = base64.b64decode(ats.xml_data).decode("utf-8")
print("ATS XML bytes:", len(xml))
print("ATS filename:", ats.xml_filename)
assert xml.startswith("<?xml"), "missing XML declaration"
assert "<iva>" in xml and "</iva>" in xml, "missing <iva> root"
import xml.etree.ElementTree as ET
root = ET.fromstring(xml.encode("utf-8"))
print("ATS root tag:", root.tag)
print("ATS children:", [c.tag for c in root])

# ---------- Libro PDF (ventas) ----------
libro = env["l10n_ec.libro.wizard"].create({
    "book_type": "ventas",
    "date_from": date(2025, 9, 1),
    "date_to": date(2025, 9, 30),
    "company_id": Company.id,
})
payload = libro.get_book_payload()
print("Libro payload keys:", sorted(payload.keys()))
pdf = env["ir.actions.report"]._render_qweb_pdf(
    "l10n_ec_reports.action_report_libro", res_ids=libro.ids)[0]
print("Libro PDF bytes:", len(pdf))
assert pdf[:4] == b"%PDF", "not a PDF"

# ---------- Form 104 PDF ----------
form = env["l10n_ec.form.wizard"].create({
    "form_code": "104",
    "date_from": date(2025, 9, 1),
    "date_to": date(2025, 9, 30),
    "company_id": Company.id,
})
data = form.get_form_data()
print("Form 104 title:", data.get("title"), "| sections:", len(data.get("sections") or []))
pdf = env["ir.actions.report"]._render_qweb_pdf(
    "l10n_ec_reports.action_report_form_104", res_ids=form.ids)[0]
print("Form 104 PDF bytes:", len(pdf))
assert pdf[:4] == b"%PDF", "not a PDF"

# ---------- Balance General PDF ----------
fin = env["l10n_ec.financials.wizard"].create({
    "statement_type": "balance",
    "date_from": date(2025, 1, 1),
    "date_to": date(2025, 9, 30),
    "company_id": Company.id,
})
sdata = fin.get_statement_data()
print("Balance sections:", len(sdata.get("sections") or []))
pdf = env["ir.actions.report"]._render_qweb_pdf(
    "l10n_ec_reports.action_report_estado_balance", res_ids=fin.ids)[0]
print("Balance PDF bytes:", len(pdf))
assert pdf[:4] == b"%PDF", "not a PDF"

# ---------- Books for every type render without error ----------
for bt in ("compras", "retenciones", "bancos", "caja", "diario", "mayor", "inventarios"):
    w = env["l10n_ec.libro.wizard"].create({
        "book_type": bt,
        "date_from": date(2025, 9, 1),
        "date_to": date(2025, 9, 30),
        "company_id": Company.id,
    })
    p = w.get_book_payload()
    print("book", bt, "-> rows:", len(p.get("rows") or []))

# ---------- All forms trial ----------
for fc in ("101", "102", "103", "107", "108", "gastos_personales"):
    w = env["l10n_ec.form.wizard"].create({
        "form_code": fc,
        "date_from": date(2025, 1, 1),
        "date_to": date(2025, 12, 31),
        "company_id": Company.id,
    })
    d = w.get_form_data()
    print("form", fc, "->", d.get("title"), "| rows/sections:",
          len(d.get("rows") or d.get("sections") or []))

print("E2E OK")
