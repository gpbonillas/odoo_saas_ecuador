# -*- coding: utf-8 -*-
"""
MCP tool definitions + handlers for operating Odoo with Ecuadorian rules.

Every handler receives (client: OdooClient|None, args: dict) and returns a
JSON-serializable dict.  Errors are always structured:
    {"status": "error", "error": "...", "hint": "..."}
Never a raw traceback.  Mutating tools run mcp_server.rules first; if legally
required data is missing they return {"status": "needs_data", "missing": [...],
"question": "..."} instead of failing.

Odoo APIs used here were read from the actual module sources:
  * l10n_ec.sri.ruc.service.consultar_ruc / consultar_cedula   (l10n_ec_base)
  * account.move.action_post / action_send_sri (l10n_ec_edi)
  * account.retention + l10n_ec.withholding.tax (l10n_ec_withholding)
  * l10n_ec.payslip.action_confirm (l10n_ec_hr_payroll)
  * l10n_ec.ats.wizard.action_generate_ats (l10n_ec_reports)
  * l10n_ec.tax.table / l10n_ec.family.basket (l10n_ec_income_tax)
"""
import datetime
import logging

import rules

_log = logging.getLogger("mcp.tools")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
class ToolError(Exception):
    def __init__(self, message, hint=None, **extra):
        super().__init__(message)
        self.hint = hint
        self.extra = extra


def _err(message, hint=None, **extra):
    out = {"status": "error", "error": str(message)}
    if hint:
        out["hint"] = hint
    out.update(extra)
    return out


def _needs_data(missing, **extra):
    out = {"status": "needs_data", "missing": missing,
           "question": rules.build_question(missing)}
    out.update(extra)
    return out


def _to_date(value):
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _iso(value):
    return value.isoformat() if isinstance(value, (datetime.date,)) else value


def _require(client):
    if client is None:
        raise ToolError("el cliente Odoo no está inicializado")
    return client


def _odoo_call(client, *a, **kw):
    try:
        return client.execute(*a, **kw)
    except Exception as exc:  # noqa: BLE001 - normalized to structured error
        from odoo_client import OdooConnectionError, OdooRPCError
        if isinstance(exc, OdooConnectionError):
            raise ToolError(str(exc), hint=exc.hint,
                            kind="odoo_unreachable")
        if isinstance(exc, OdooRPCError):
            raise ToolError("Odoo rechazó la operación: %s" % exc,
                            hint="Revise permisos del usuario y configuración "
                                 "del módulo implicado.")
        raise ToolError("error inesperado llamando a Odoo: %s" % exc)


# ---------------------------------------------------------------------------
# Odoo data access helpers
# ---------------------------------------------------------------------------
def _company_info(client, company_id=None):
    """Read company EC config, tolerating fields that may not exist."""
    cid = company_id
    core_fields = ["id", "name", "vat", "l10n_ec_sri_environment",
                   "l10n_ec_certificate_id", "l10n_ec_withhold_agent",
                   "l10n_ec_forced_accounting", "l10n_ec_special_resolution",
                   "l10n_ec_commercial_name"]
    if not cid:
        me = _odoo_call(client, "res.users", "read", [[client.uid], ["company_id"]])
        cid = me[0]["company_id"][0] if me and me[0].get("company_id") else None
        if not cid:
            row = client.search_read("res.company", [], ["id"], limit=1)
            cid = row[0]["id"] if row else None
    company = {}
    if cid:
        company = _odoo_call(client, "res.company", "read", [[cid], core_fields])[0]
        # Probe optional establishment/emission-point fields defensively.
        try:
            extra = _odoo_call(client, "res.company", "fields_get", [],
                               {"attributes": ["string"]})
            for fname in ("l10n_ec_establishment", "l10n_ec_emission_point"):
                if fname in extra:
                    val = _odoo_call(client, "res.company", "read", [[cid], [fname]])
                    company[fname] = val[0].get(fname)
        except Exception:  # noqa: BLE001
            pass
    cert = company.get("l10n_ec_certificate_id")
    return {
        "id": company.get("id"),
        "name": company.get("name"),
        "vat": company.get("vat"),
        "ambiente": company.get("l10n_ec_sri_environment"),
        "establishment": company.get("l10n_ec_establishment") or None,
        "emission_point": company.get("l10n_ec_emission_point") or None,
        "certificate_active": bool(cert) if cert is not None else None,
        "certificate_id": cert[0] if isinstance(cert, (list, tuple)) else cert,
        "agente_retencion": company.get("l10n_ec_withhold_agent"),
        "obligado_contabilidad": company.get("l10n_ec_forced_accounting"),
        "resolucion_contribuyente_especial": company.get("l10n_ec_special_resolution"),
        "nombre_comercial": company.get("l10n_ec_commercial_name"),
    }


PARTNER_FIELDS = ["id", "name", "vat", "street", "street2", "city",
                  "country_id", "email", "phone", "is_company", "company_type",
                  "l10n_ec_identifier_type", "l10n_ec_taxpayer_type"]


def _partner_dict(row):
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "vat": row.get("vat"),
        "street": row.get("street"),
        "city": row.get("city"),
        "email": row.get("email"),
        "phone": row.get("phone"),
        "company_type": row.get("company_type"),
        "id_type": row.get("l10n_ec_identifier_type"),
        "taxpayer_type": row.get("l10n_ec_taxpayer_type"),
    }


def _sri_consult(client, vat):
    """Consult SRI via l10n_ec.sri.ruc.service; degrade gracefully."""
    if not vat:
        return None, {"available": False, "error": "sin identificación"}
    if client is None:
        return None, {"available": False,
                      "error": "cliente Odoo no inicializado",
                      "hint": "configure ODOO_URL y reinicie el gateway"}
    try:
        digits = str(vat).strip()
        if len(digits) == 13:
            res = _odoo_call(client, "l10n_ec.sri.ruc.service", "consultar_ruc",
                             [digits])
        elif len(digits) == 10:
            res = _odoo_call(client, "l10n_ec.sri.ruc.service", "consultar_cedula",
                             [digits])
        else:
            return None, {"available": False,
                          "error": "la consulta SRI solo acepta cédula (10) o "
                                   "RUC (13) digitos"}
    except ToolError as exc:
        return None, {"available": False, "error": str(exc),
                      "hint": exc.hint}
    if isinstance(res, dict) and res.get("success"):
        return res.get("data"), {"available": True, "error": None}
    msg = res.get("error") if isinstance(res, dict) else "respuesta inválida"
    return None, {"available": False, "error": msg}


def _resolve_partner(client, args, required=True):
    """
    Resolve a partner from partner_id | vat | search.
    Returns (partner_dict|None, note).  Raises ToolError on ambiguity handled
    as needs_data by the caller via note['candidates'].
    """
    partner_id = args.get("partner_id")
    if partner_id:
        rows = client.search_read("res.partner", [("id", "=", int(partner_id))],
                                  PARTNER_FIELDS, limit=1)
        if not rows:
            raise ToolError("partner_id %s no existe" % partner_id)
        return _partner_dict(rows[0]), None
    vat = (args.get("vat") or "").strip()
    if vat:
        rows = client.search_read("res.partner", [("vat", "=", vat)],
                                  PARTNER_FIELDS, limit=2)
        if len(rows) == 1:
            return _partner_dict(rows[0]), None
        if len(rows) > 1:
            return None, {"candidates": [_partner_dict(r) for r in rows]}
    term = (args.get("search") or args.get("client") or "").strip()
    if term:
        rows = client.search_read(
            "res.partner",
            ["&", ("active", "=", True), "|", ("name", "ilike", term),
             ("vat", "ilike", term)],
            PARTNER_FIELDS, limit=5)
        if len(rows) == 1:
            return _partner_dict(rows[0]), None
        if len(rows) > 1:
            return None, {"candidates": [_partner_dict(r) for r in rows]}
    if required:
        return None, None
    return None, None


def _document_type_id(client, code):
    """Find l10n_latam.document.type for Ecuador with the given SRI code."""
    try:
        rows = client.search_read(
            "l10n_latam.document.type",
            [("code", "=", code), ("country_id.code", "=", "EC")],
            ["id", "code", "name"], limit=1)
        if not rows:
            rows = client.search_read("l10n_latam.document.type",
                                      [("code", "=", code)],
                                      ["id", "code", "name"], limit=1)
        return rows[0] if rows else None
    except Exception:  # noqa: BLE001
        return None


def _tax_ids_for_rate(client, rate, company_id):
    try:
        rows = client.search_read(
            "account.tax",
            [("amount", "=", float(rate)), ("type_tax_use", "=", "sale"),
             ("company_id", "=", company_id or False), ("active", "=", True)],
            ["id", "name", "amount"], limit=1)
        return rows, None
    except Exception as exc:  # noqa: BLE001
        return None, "no se pudo buscar impuestos: %s" % exc


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
def tool_detect_taxpayer(client, args):
    vat = (args.get("vat") or args.get("ruc") or args.get("cedula") or "").strip()
    if not vat:
        raise ToolError("indique el RUC o cédula a detectar")
    profile = rules.taxpayer_profile(vat)
    sri_meta = {"available": False, "error": None}
    if args.get("consult_sri", True) and profile["id_type"] in ("ruc", "cedula"):
        data, sri_meta = _sri_consult(client, vat)
        profile = rules.taxpayer_profile(vat, data)
    return {"status": "ok", "profile": profile, "sri": sri_meta,
            "es_consumidor_final": rules.is_consumidor_final(vat)}


def tool_validate_ruc(client, args):
    vat = (args.get("vat") or args.get("ruc") or args.get("cedula") or "").strip()
    if not vat:
        raise ToolError("indique el RUC o cédula a validar")
    v = rules.validate_vat(vat)
    out = {"status": "ok" if v["valid"] else "error", "validation": v}
    if not v["valid"]:
        out["error"] = "; ".join(v["errors"]) or "identificación inválida"
        out["hint"] = "Verifique el número con el emisor del documento."
        return out
    if args.get("consult_sri", True) and v["id_type"] in ("ruc", "cedula"):
        data, sri_meta = _sri_consult(client, vat)
        out["sri"] = sri_meta
        if data:
            out["sri_data"] = data
            if (data.get("estado") or "").upper() not in ("ACTIVO", ""):
                out["warning"] = "contribuyente en estado %s" % data.get("estado")
    return out


def tool_get_client_data(client, args):
    client = _require(client)
    partner, note = _resolve_partner(client, args)
    if partner is None:
        if note and note.get("candidates"):
            return _needs_data(
                [{"field": "partner_id", "label": "Cliente ambiguo",
                  "question": "Encontré varios clientes; ¿cuál de estos es? "
                              + ", ".join("%s (%s)" % (c["name"], c["vat"] or "sin RUC")
                                          for c in note["candidates"]),
                  "severity": "blocker"}],
                candidates=note["candidates"])
        return _needs_data([{
            "field": "partner", "label": "Cliente",
            "question": "No encontré ese cliente en Odoo. ¿Me da el nombre o "
                        "el RUC/cédula, o lo creo con create_partner?",
            "severity": "blocker"}])
    profile = rules.taxpayer_profile(partner.get("vat") or "")
    sri_meta = {"available": False, "error": None}
    sri_data = None
    if args.get("consult_sri", True) and profile["id_type"] in ("ruc", "cedula"):
        sri_data, sri_meta = _sri_consult(client, partner.get("vat"))
        profile = rules.taxpayer_profile(partner.get("vat"), sri_data)
    company = _company_info(client)
    missing = rules.missing_invoice_data(
        dict(partner, razon_social=profile.get("razon_social"),
             direccion=partner.get("street") or profile.get("direccion")),
        company)
    cf = rules.is_consumidor_final(partner.get("vat"))
    return {
        "status": "ok",
        "partner": partner,
        "taxpayer": profile,
        "sri": sri_meta,
        "sri_data": sri_data,
        "legally_required": {
            "nombre_razon_social": partner.get("name"),
            "identificacion": partner.get("vat"),
            "direccion": partner.get("street"),
            "email": partner.get("email"),
            "telefono": partner.get("phone"),
            "regimen": profile.get("regimen_rimpe") or profile.get("sri_estado"),
            "contribuyente_especial": profile.get("contribuyente_especial"),
            "agente_retencion": profile.get("agente_retencion"),
            "obligado_contabilidad": profile.get("obligado_contabilidad"),
        },
        "retention_applies": bool(profile.get("agente_retencion")),
        "cf_limit_applies": cf,
        "cf_limit": rules.CF_LIMIT_DEFAULT if cf else None,
        "missing_for_invoice": missing,
    }


def tool_create_partner(client, args):
    client = _require(client)
    name = (args.get("name") or "").strip()
    vat = (args.get("vat") or "").strip()
    if not vat:
        return _needs_data([{
            "field": "vat", "label": "Identificación",
            "question": "¿Cuál es el RUC o cédula del nuevo cliente?",
            "severity": "blocker"}])
    v = rules.validate_vat(vat)
    if not v["valid"]:
        return _err("identificación inválida: %s" % "; ".join(v["errors"]),
                    hint="La cédula usa verificación mod-10 y el RUC mod-11.")
    existing = client.search_read("res.partner", [("vat", "=", v["input"])],
                                  PARTNER_FIELDS, limit=1)
    if existing:
        return {"status": "ok", "already_exists": True,
                "partner": _partner_dict(existing[0])}
    sri_data, sri_meta = _sri_consult(client, v["input"])
    vals = {
        "name": name or (sri_data or {}).get("razon_social")
                or (sri_data or {}).get("nombre_comercial") or "",
        "vat": v["input"],
        "l10n_ec_identifier_type": v["id_type"],
        "company_type": "company" if (rules.classify_ruc(v["input"])["person_type"]
                                      == "juridica") else "person",
        "is_company": rules.classify_ruc(v["input"])["person_type"] == "juridica",
    }
    if not vals["name"]:
        return _needs_data([{
            "field": "name", "label": "Nombre / Razón social",
            "question": "El SRI no devolvió razón social para %s; ¿cuál es el "
                        "nombre del cliente?" % v["input"],
            "severity": "blocker"}], sri=sri_meta)
    if sri_data:
        direccion = " ".join(filter(None, [sri_data.get("direccion"),
                                           sri_data.get("canton"),
                                           sri_data.get("provincia")]))
        if direccion:
            vals["street"] = direccion
        if sri_data.get("telefono"):
            vals["phone"] = sri_data["telefono"]
        if sri_data.get("email"):
            vals["email"] = sri_data["email"]
    for opt in ("email", "phone", "street"):
        if args.get(opt):
            vals[opt] = args[opt]
    missing_from_sri = []
    for field, label in (("street", "dirección"), ("email", "email"),
                         ("phone", "teléfono")):
        if not vals.get(field):
            missing_from_sri.append({
                "field": field, "label": label,
                "question": "El SRI no tiene %s para este contribuyente; ¿me "
                            "lo proporciona?" % label,
                "severity": "warning"})
    new_id = client.create("res.partner", vals)
    created = client.search_read("res.partner", [("id", "=", new_id)],
                                 PARTNER_FIELDS, limit=1)[0]
    return {"status": "ok", "created": True,
            "partner": _partner_dict(created),
            "sri": sri_meta,
            "missing_from_sri": missing_from_sri,
            "taxpayer": rules.taxpayer_profile(v["input"], sri_data)}


def tool_create_invoice(client, args):
    # 1) Identify the counterpart ------------------------------------------------
    # Fast ask-path: nothing identifying was given -> ask the user first,
    # without touching Odoo at all.
    if not (args.get("partner_id") or args.get("vat") or args.get("search")
            or args.get("client")):
        return _needs_data([{
            "field": "partner", "label": "Cliente",
            "question": "No tengo el cliente. Deme nombre o RUC/cédula y, si "
                        "no existe, lo creo primero con create_partner.",
            "severity": "blocker"}])
    # Consumidor Final pre-check with zero Odoo round-trips: if the caller
    # passed the CF RUC directly we can already enforce the $50 cap.
    vat_arg = (args.get("vat") or "").strip()
    if rules.is_consumidor_final(vat_arg):
        lines0 = args.get("lines") or []
        if not lines0 and args.get("amount") is not None:
            lines0 = [{"quantity": 1, "unit_price": float(args["amount"])}]
        chk = rules.cf_limit_check(rules.estimate_lines_total(lines0))
        if lines0 and not chk["ok"]:
            return _err(chk["error"],
                        hint="Facture a un cliente identificado (RUC/cédula) "
                             "o divida la venta.",
                        rule="cf_limit_50")
    client = _require(client)
    partner, note = _resolve_partner(client, args)
    if partner is None:
        if note and note.get("candidates"):
            return _needs_data(
                [{"field": "partner_id", "label": "Cliente ambiguo",
                  "question": "Hay varios clientes con ese nombre: "
                              + ", ".join("%s (id %s, %s)" %
                                          (c["name"], c["id"], c["vat"] or "sin RUC")
                                          for c in note["candidates"])
                              + ". ¿Cuál uso?",
                  "severity": "blocker"}],
                candidates=note["candidates"])
        return _needs_data([{
            "field": "partner", "label": "Cliente",
            "question": "No tengo el cliente. Deme nombre o RUC/cédula y, si "
                        "no existe, lo creo primero con create_partner.",
            "severity": "blocker"}])

    lines = args.get("lines") or []
    if not lines and args.get("amount") is not None:
        lines = [{"description": args.get("description") or "Venta",
                  "quantity": 1, "unit_price": float(args["amount"])}]
    if not lines:
        return _needs_data([{
            "field": "lines", "label": "Detalle de la factura",
            "question": "¿Qué productos o servicios facturo y a qué precio "
                        "(cantidad y valor unitario)?",
            "severity": "blocker"}], partner=partner)

    # 2) Taxpayer detection ------------------------------------------------------
    profile = rules.taxpayer_profile(partner.get("vat") or "")
    sri_meta = {"available": False, "error": None}
    if profile["id_type"] in ("ruc", "cedula"):
        sri_data, sri_meta = _sri_consult(client, partner.get("vat"))
        profile = rules.taxpayer_profile(partner.get("vat"), sri_data)
    if profile["id_type"] == "ruc" and not profile["valid_checksum"]:
        return _err("el RUC %s no pasa la validación mod-11 del SRI; no se "
                    "puede facturar" % partner.get("vat"),
                    hint="Corrija el RUC del cliente antes de facturar.")

    # 3) Consumidor Final pre-flight -------------------------------------------
    estimated = rules.estimate_lines_total(lines)
    cf = rules.is_consumidor_final(partner.get("vat"))
    warnings = []
    if cf:
        cfchk = rules.cf_limit_check(estimated)
        if not cfchk["ok"]:
            return _err(cfchk["error"],
                        hint="Facture a un cliente identificado (RUC/cédula) "
                             "o divida la venta.",
                        rule="cf_limit_50")
    elif sri_meta.get("available") is False and sri_meta.get("error"):
        warnings.append("SRI no consultable: %s" % sri_meta["error"])

    # 4) Missing legally-required data -----------------------------------------
    company = _company_info(client)
    if not company.get("id"):
        return _err("no hay empresa configurada en Odoo",
                    hint="Instance/active una compañía antes de facturar.")
    missing = rules.missing_invoice_data(
        dict(partner, razon_social=partner.get("name"),
             direccion=partner.get("street")), company)
    blockers = [m for m in missing if m["severity"] == "blocker"]
    if blockers:
        return _needs_data(blockers, partner=partner, company=company,
                           estimated_total=estimated)
    warnings.extend(m["question"] for m in missing if m["severity"] == "warning")

    # 5) Build the move ----------------------------------------------------------
    doc_code = str(args.get("document_type") or "01")
    if doc_code not in ("01", "03"):
        return _err("tipo de comprobante no soportado para venta: %s" % doc_code,
                    hint="Use 01 (factura) o 03 (liquidación de compra).")
    vals = {
        "move_type": "out_invoice",
        "partner_id": partner["id"],
        "invoice_date": str(args.get("invoice_date")
                            or datetime.date.today().isoformat()),
        "company_id": company["id"],
    }
    if args.get("ref") or args.get("description"):
        vals["narration"] = args.get("ref") or args.get("description")
    dtype = _document_type_id(client, doc_code)
    if dtype:
        vals["l10n_latam_document_type_id"] = dtype["id"]
    if args.get("journal_id"):
        vals["journal_id"] = int(args["journal_id"])

    line_cmds = []
    for line in lines:
        qty = float(line.get("quantity", 1) or 1)
        price = float(line.get("unit_price", 0) or 0)
        if price < 0:
            return _err("precio unitario negativo en '%s'"
                        % line.get("description"),
                        hint="Para devoluciones use create_credit_note.")
        vals_line = {
            "name": line.get("description") or "Producto/Servicio",
            "quantity": qty,
            "price_unit": price,
            "product_id": int(line["product_id"]) if line.get("product_id") else None,
        }
        if vals_line["product_id"] is None:
            del vals_line["product_id"]
        if line.get("tax_ids"):
            vals_line["tax_ids"] = [(6, 0, [int(t) for t in line["tax_ids"]])]
        elif line.get("tax_rate") is not None or args.get("tax_rate") is not None:
            rate = line.get("tax_rate", args.get("tax_rate"))
            taxrows, note_tax = _tax_ids_for_rate(client, rate, company["id"])
            if taxrows:
                vals_line["tax_ids"] = [(6, 0, [taxrows[0]["id"]])]
            else:
                warnings.append("no encontré impuesto de venta con tasa %s%%; "
                                "la línea queda sin impuesto (%s)"
                                % (rate, note_tax or "verifique el plan de "
                                                     "cuentas/tax tags"))
        line_cmds.append((0, 0, vals_line))
    vals["invoice_line_ids"] = line_cmds

    move_id = client.create("account.move", vals)
    move = client.search_read("account.move", [("id", "=", move_id)],
                              ["id", "name", "amount_total", "amount_untaxed",
                               "l10n_latam_document_number",
                               "l10n_latam_document_type_id",
                               "l10n_ec_sri_access_key", "l10n_ec_sri_status",
                               "state"], limit=1)[0]
    if cf and move.get("amount_total", 0) > rules.CF_LIMIT_DEFAULT + 1e-9:
        # Odoo-side constraint should have fired; belt and suspenders.
        _odoo_call(client, "account.move", "button_cancel", [[move_id]])
        return _err("factura a Consumidor Final excede $%.2f y fue revertida"
                    % rules.CF_LIMIT_DEFAULT, rule="cf_limit_50")
    return {
        "status": "ok",
        "invoice_id": move["id"],
        "name": move.get("name"),
        "state": move.get("state"),
        "document_type": dtype or {"code": doc_code,
                                   "name": rules.DOC_TYPES.get(doc_code)},
        "amount_total": move.get("amount_total"),
        "amount_untaxed": move.get("amount_untaxed"),
        "partner": {"id": partner["id"], "name": partner["name"],
                    "vat": partner["vat"]},
        "taxpayer_type": profile.get("person_type"),
        "consumidor_final": cf,
        "ambiente": company.get("ambiente"),
        "warnings": warnings,
        "next": "post_invoice con invoice_id=%s para firmar y enviar al SRI"
                % move["id"],
    }


def tool_post_invoice(client, args):
    client = _require(client)
    invoice_id = int(args.get("invoice_id") or 0)
    if not invoice_id:
        raise ToolError("falta invoice_id")
    fields = ["id", "name", "state", "move_type", "partner_id",
              "l10n_ec_sri_access_key", "l10n_ec_sri_status",
              "l10n_ec_sri_response", "company_id", "invoice_date"]
    move = client.search_read("account.move", [("id", "=", invoice_id)],
                              fields, limit=1)
    if not move:
        raise ToolError("factura %s no existe" % invoice_id)
    move = move[0]
    out = {"invoice_id": move["id"], "name": move.get("name")}
    if move.get("state") != "posted":
        _odoo_call(client, "account.move", "action_post", [[move["id"]]])
        out["posted"] = True
    else:
        out["posted"] = False
        out["note"] = "la factura ya estaba posted"
    send = args.get("send_to_sri", True)
    if send:
        company = _company_info(client, (move.get("company_id") or [None])[0])
        if not company.get("certificate_active"):
            out["sri_sent"] = False
            out["warning"] = ("sin certificado P12 activo: la factura quedó "
                              "posteada pero NO firmada/enviada al SRI")
        else:
            try:
                _odoo_call(client, "account.move", "action_send_sri",
                           [[move["id"]]])
                out["sri_sent"] = True
            except ToolError as exc:
                out["sri_sent"] = False
                out["sri_error"] = str(exc)
    after = client.search_read("account.move", [("id", "=", move["id"])],
                               ["l10n_ec_sri_access_key", "l10n_ec_sri_status",
                                "l10n_ec_sri_response", "state"], limit=1)
    after = after[0] if after else {}
    clave = after.get("l10n_ec_sri_access_key")
    out.update({
        "state": after.get("state"),
        "clave_acceso": clave,
        "clave_valida": rules.validate_access_key(clave) if clave else None,
        "sri_status": after.get("l10n_ec_sri_status"),
        "sri_response": after.get("l10n_ec_sri_response"),
        "status": "ok",
    })
    return out


def tool_create_credit_note(client, args):
    client = _require(client)
    invoice_id = int(args.get("invoice_id") or 0)
    reason = (args.get("reason") or "").strip()
    if not invoice_id:
        raise ToolError("falta invoice_id de la factura a anular/devolver")
    if not reason:
        return _needs_data([{
            "field": "reason", "label": "Motivo",
            "question": "¿Cuál es el motivo de la nota de crédito? Es "
                        "obligatorio para el comprobante y el ATS.",
            "severity": "blocker"}])
    inv = client.search_read(
        "account.move", [("id", "=", invoice_id)],
        ["id", "name", "state", "move_type", "partner_id", "invoice_date",
         "l10n_ec_sri_status", "company_id"], limit=1)
    if not inv:
        raise ToolError("factura %s no existe" % invoice_id)
    inv = inv[0]
    if inv.get("move_type") != "out_invoice":
        return _err("la factura %s no es una venta (move_type=%s)"
                    % (invoice_id, inv.get("move_type")))
    partner_vat = None
    if inv.get("partner_id"):
        prow = client.search_read("res.partner",
                                  [("id", "=", inv["partner_id"][0])],
                                  ["vat"], limit=1)
        partner_vat = prow[0].get("vat") if prow else None
    cf = rules.is_consumidor_final(partner_vat)
    inv_date = _to_date(inv.get("invoice_date"))
    annul = rules.check_annul_allowed(inv_date, is_cf=cf)
    if not annul["allowed"]:
        return _err(annul["error"],
                    hint="Solo se puede corregir dentro del plazo fiscal; "
                         "consulte con el contador.",
                    rule="anulacion_dia_7" if not cf else "cf_no_anulable")
    # Copy product lines into the refund
    src_lines = client.search_read(
        "account.move.line",
        [("move_id", "=", invoice_id), ("display_type", "=", "product")],
        ["name", "quantity", "price_unit", "product_id", "tax_ids"], limit=500)
    line_cmds = []
    for line in src_lines:
        vals_line = {"name": line.get("name") or "Nota de crédito",
                     "quantity": line.get("quantity") or 1,
                     "price_unit": line.get("price_unit") or 0}
        if line.get("product_id"):
            vals_line["product_id"] = line["product_id"][0]
        if line.get("tax_ids"):
            vals_line["tax_ids"] = [(6, 0, line["tax_ids"])]
        line_cmds.append((0, 0, vals_line))
    vals = {
        "move_type": "out_refund",
        "partner_id": inv["partner_id"][0] if inv.get("partner_id") else None,
        "invoice_date": str(args.get("credit_note_date")
                            or datetime.date.today().isoformat()),
        "narration": "Nota de crédito a %s. Motivo: %s" % (inv.get("name"), reason),
        "invoice_line_ids": line_cmds,
        "company_id": (inv.get("company_id") or [None])[0],
    }
    dtype = _document_type_id(client, "04")
    if dtype:
        vals["l10n_latam_document_type_id"] = dtype["id"]
    refund_id = client.create("account.move", vals)
    out = {"status": "ok", "credit_note_id": refund_id,
           "original_invoice_id": invoice_id, "reason": reason,
           "cod_doc": "04",
           "annulment_deadline": annul.get("deadline"),
           "warnings": [w for w in (annul.get("warning"),) if w]}
    if args.get("post", True):
        _odoo_call(client, "account.move", "action_post", [[refund_id]])
        out["posted"] = True
    row = client.search_read("account.move", [("id", "=", refund_id)],
                             ["name", "amount_total", "l10n_ec_sri_access_key",
                              "l10n_ec_sri_status"], limit=1)
    if row:
        out["name"] = row[0].get("name")
        out["amount_total"] = row[0].get("amount_total")
        out["clave_acceso"] = row[0].get("l10n_ec_sri_access_key")
        out["sri_status"] = row[0].get("l10n_ec_sri_status")
    return out


def _retention_pct_table(client, tax_type):
    try:
        rows = client.search_read("l10n_ec.withholding.tax",
                                  [("type", "=", tax_type), ("active", "=", True)],
                                  ["id", "code", "name", "percentage"])
        return rows or []
    except Exception:  # noqa: BLE001
        return []


def tool_calculate_withholding(client, args):
    client = _require(client)
    invoice_id = int(args.get("invoice_id") or 0)
    if not invoice_id:
        raise ToolError("falta invoice_id")
    inv = client.search_read(
        "account.move", [("id", "=", invoice_id)],
        ["id", "name", "move_type", "partner_id", "invoice_date", "state",
         "amount_untaxed", "amount_tax", "amount_total", "company_id"], limit=1)
    if not inv:
        raise ToolError("factura %s no existe" % invoice_id)
    inv = inv[0]
    kind = (args.get("tax_type") or "renta").lower()
    if kind not in ("renta", "iva", "isd"):
        return _err("tax_type debe ser renta, iva o isd")
    pct_arg = args.get("percentage")
    if kind == "renta":
        category = args.get("category") or "servicios"
        computed = rules.ir_retention_pct(inv["amount_untaxed"], category,
                                          override=pct_arg)
        base = inv["amount_untaxed"]
        if not computed["valid"]:
            return _err("porcentaje IR inválido: %s" % computed["warning"],
                        hint="Use uno de los valores de la Tabla 19 o consulte "
                             "la resolución de retención del cliente.")
        pct = computed["percentage"]
        warnings = [w for w in (computed.get("warning"),) if w]
    else:
        iva = abs(inv.get("amount_tax") or 0.0)
        split = rules.iva_retention_amount(iva, pct_arg or 30.0)
        base = split["base_iva"]
        pct = split["percentage"]
        warnings = ["retención IVA se aplica sobre el valor del IVA "
                    "(%.2f); el porcentaje corresponde al casillero del "
                    "Formulario 104 (721=10%%, 723=20%%, 725=30%%, 727=50%%, "
                    "729=70%%, 731=100%%)" % iva]
        if split.get("warning"):
            warnings.append(split["warning"])
    due = rules.retention_deadline(_to_date(inv.get("invoice_date")))
    if due.get("warning"):
        warnings.append(due["warning"])
    amount = round(base * pct / 100.0, 2)
    table = _retention_pct_table(client, "renta" if kind == "renta" else
                                 ("iva" if kind == "iva" else "isd"))
    suggestion = None
    for row in table:
        if abs(float(row.get("percentage") or 0) - pct) < 0.01:
            suggestion = row
            break
    return {
        "status": "ok",
        "invoice_id": invoice_id,
        "invoice": {"name": inv.get("name"), "date": inv.get("invoice_date"),
                    "untaxed": inv.get("amount_untaxed"),
                    "iva": inv.get("amount_tax"),
                    "total": inv.get("amount_total")},
        "tax_type": kind,
        "base": round(base, 2),
        "percentage": pct,
        "amount": amount,
        "suggested_tax_code": suggestion,
        "due_date": due.get("due_date"),
        "overdue": due.get("overdue"),
        "warnings": warnings,
        "note": "use create_withholding para registrar el comprobante (07)",
    }


def tool_create_withholding(client, args):
    client = _require(client)
    invoice_id = int(args.get("invoice_id") or 0)
    if not invoice_id:
        raise ToolError("falta invoice_id")
    calc_args = dict(args)
    calc_args["invoice_id"] = invoice_id
    calc = tool_calculate_withholding(client, calc_args)
    if calc.get("status") != "ok":
        return calc
    inv = client.search_read("account.move", [("id", "=", invoice_id)],
                             ["partner_id", "company_id", "move_type"], limit=1)[0]
    if not inv.get("partner_id"):
        return _err("la factura no tiene proveedor/cliente; imposible retener")
    tax_id = args.get("tax_id")
    if not tax_id:
        table = _retention_pct_table(client, "renta" if calc["tax_type"] == "renta"
                                     else ("iva" if calc["tax_type"] == "iva" else "isd"))
        for row in table:
            if abs(float(row.get("percentage") or 0) - calc["percentage"]) < 0.01:
                tax_id = row["id"]
                break
    if not tax_id:
        return _needs_data([{
            "field": "tax_id", "label": "Código de retención",
            "question": "No hay código de retención %.2f%% para %s en la tabla "
                        "l10n_ec.withholding.tax. ¿Cuál uso (o lo creo en "
                        "Odoo)?" % (calc["percentage"], calc["tax_type"]),
            "severity": "blocker"}], available_codes=table)
    line = {"tax_type": {"renta": "1", "iva": "2", "isd": "6"}[calc["tax_type"]],
            "tax_id": int(tax_id), "base": calc["base"]}
    vals = {
        "partner_id": inv["partner_id"][0],
        "date": str(args.get("date") or datetime.date.today().isoformat()),
        "company_id": (inv.get("company_id") or [None])[0],
        "invoice_id": invoice_id,
        "retention_line_ids": [(0, 0, line)],
        "l10n_ec_sri_status": "draft",
    }
    if inv.get("move_type") == "out_invoice":
        # We are withholding on our own sales (agente de retención): the
        # voucher we emit is codDoc 07 by US. account.retention supports the
        # data model; note the domain is purchase-oriented in the UI.
        pass
    ret_id = client.create("account.retention", vals)
    out = {"status": "ok", "retention_id": ret_id,
           "invoice_id": invoice_id,
           "amount": calc["amount"], "base": calc["base"],
           "percentage": calc["percentage"], "tax_type": calc["tax_type"],
           "due_date": calc.get("due_date"), "overdue": calc.get("overdue"),
           "cod_doc": "07",
           "warnings": calc.get("warnings", [])}
    if args.get("post", False):
        _odoo_call(client, "account.retention", "action_post", [[ret_id]])
        out["posted"] = True
        if args.get("send_to_sri", False):
            try:
                _odoo_call(client, "account.retention", "action_send_sri",
                           [[ret_id]])
                out["sri_sent"] = True
            except ToolError as exc:
                out["sri_sent"] = False
                out["sri_error"] = str(exc)
    row = client.search_read("account.retention", [("id", "=", ret_id)],
                             ["name", "state", "l10n_ec_sri_access_key",
                              "l10n_ec_sri_status"], limit=1)
    if row:
        out["name"] = row[0].get("name")
        out["state"] = row[0].get("state")
        out["clave_acceso"] = row[0].get("l10n_ec_sri_access_key")
        out["sri_status"] = row[0].get("l10n_ec_sri_status")
    return out


def tool_generate_payslips(client, args):
    client = _require(client)
    date_start = str(args.get("date_start") or "")
    date_end = str(args.get("date_end") or "")
    if not date_start or not date_end:
        raise ToolError("falta date_start / date_end (YYYY-MM-DD)")
    domain = [("state", "in", ["open", "in_progress"])]
    contracts = client.search_read(
        "hr.contract", domain,
        ["id", "name", "employee_id", "wage", "state"], limit=500)
    if args.get("employee_ids"):
        wanted = {int(i) for i in args["employee_ids"]}
        contracts = [c for c in contracts
                     if c.get("employee_id") and c["employee_id"][0] in wanted]
    if not contracts:
        return _err("no hay contratos activos para generar planilla",
                    hint="Cargue empleados y contratos (hr) o amplíe el rango.")
    created, errors = [], []
    for contract in contracts:
        existing = client.search_read(
            "l10n_ec.payslip",
            [("contract_id", "=", contract["id"]),
             ("date_start", "=", date_start), ("date_end", "=", date_end)],
            ["id", "name"], limit=1)
        if existing:
            created.append({"contract_id": contract["id"],
                            "payslip_id": existing[0]["id"],
                            "name": existing[0].get("name"),
                            "skipped": "ya existe"})
            continue
        try:
            pid = client.create("l10n_ec.payslip", {
                "employee_id": contract["employee_id"][0],
                "contract_id": contract["id"],
                "date_start": date_start,
                "date_end": date_end,
            })
            row = client.search_read("l10n_ec.payslip", [("id", "=", pid)],
                                     ["id", "name", "total_income", "net_wage"],
                                     limit=1)[0]
            if args.get("confirm", True):
                _odoo_call(client, "l10n_ec.payslip", "action_confirm", [[pid]])
            created.append({"contract_id": contract["id"], "payslip_id": pid,
                            "name": row.get("name"),
                            "total_income": row.get("total_income"),
                            "net_wage": row.get("net_wage")})
        except ToolError as exc:
            errors.append({"contract_id": contract["id"], "error": str(exc)})
    return {"status": "ok" if not errors else "ok_with_errors",
            "period": {"date_start": date_start, "date_end": date_end},
            "payslips": created, "errors": errors,
            "count": len(created)}


def tool_generate_iess_planilla(client, args):
    client = _require(client)
    date_start = str(args.get("date_start") or "")
    date_end = str(args.get("date_end") or "")
    if not date_start or not date_end:
        raise ToolError("falta date_start / date_end (YYYY-MM-DD)")
    slips = client.search_read(
        "l10n_ec.payslip",
        [("date_start", ">=", date_start), ("date_end", "<=", date_end),
         ("state", "=", "done")],
        ["id", "name", "employee_id", "total_income", "iess_personal",
         "iess_employer", "net_wage", "wage", "days_worked"], limit=2000)
    if not slips:
        return _err("no hay payslips confirmados en el periodo",
                    hint="Ejecute generate_payslips con confirm=true primero.")
    total_p = round(sum(s.get("iess_personal") or 0 for s in slips), 2)
    total_e = round(sum(s.get("iess_employer") or 0 for s in slips), 2)
    return {
        "status": "ok",
        "period": {"date_start": date_start, "date_end": date_end},
        "employees": len(slips),
        "total_aporte_personal": total_p,
        "total_aporte_patronal": total_e,
        "total_aportes": round(total_p + total_e, 2),
        "detail": [{"payslip_id": s["id"], "employee": s.get("employee_id"),
                    "total_income": s.get("total_income"),
                    "iess_personal": s.get("iess_personal"),
                    "iess_patronal": s.get("iess_employer"),
                    "net_wage": s.get("net_wage")} for s in slips],
        "note": "Agregación lista para la planilla IESS del período; el "
                "modelo oficial de planilla electrónica aún no existe en "
                "l10n_ec_hr_payroll (ver ODOO-SIDE HELPERS NEEDED).",
    }


def tool_calculate_liquidation(client, args):
    client = _require(client)
    employee_id = args.get("employee_id")
    wage = args.get("wage")
    if not employee_id and wage is None:
        raise ToolError("indique employee_id o wage")
    if employee_id and wage is None:
        contracts = client.search_read(
            "hr.contract", [("employee_id", "=", int(employee_id)),
                            ("state", "in", ["open", "in_progress"])],
            ["wage", "name"], limit=1)
        if not contracts:
            return _err("el empleado %s no tiene contrato activo"
                        % employee_id)
        wage = contracts[0]["wage"]
    sbu = client.config_param("l10n_ec.sbu", str(rules.SBU_2026))
    pers = float(client.config_param("l10n_ec.iess_aporte_personal",
                                     str(rules.IESS_PERSONAL_RATE)))
    patr = float(client.config_param("l10n_ec.iess_aporte_patronal",
                                     str(rules.IESS_PATRONAL_RATE)))
    warnings = []
    if args.get("include_tax", False):
        year = _to_date(args.get("period_end") or datetime.date.today()
                        .isoformat()).year
        rows = client.search_read("l10n_ec.tax.table", [("year", "=", year)],
                                  ["basic_fraction", "excess_until", "basic_tax",
                                   "marginal_rate"])
        if rows:
            taxable_annual = (float(wage) - float(wage) * pers / 100.0) * 12
            annual = rules.progressive_tax(taxable_annual, rows)
            income_tax = round(annual / 12.0, 2)
        else:
            income_tax = 0.0
            warnings.append("no hay tabla de impuesto a la renta %s en Odoo; "
                            "impuesto calculado en 0" % year)
    else:
        income_tax = float(args.get("income_tax") or 0)
    liq = rules.calculate_liquidation(
        float(wage), days_worked=float(args.get("days_worked") or 30),
        sbu=float(sbu), personal_rate=pers, patronal_rate=patr,
        extra_income=float(args.get("extra_income") or 0),
        advances=float(args.get("advances") or 0),
        income_tax=income_tax)
    liq.update({"status": "ok", "employee_id": employee_id,
                "sbu": float(sbu),
                "warnings": warnings + liq.get("warnings", [])})
    return liq


def tool_generate_ats(client, args):
    client = _require(client)
    today = datetime.date.today()
    month = str(args.get("month") or today.month).zfill(2)
    year = str(args.get("year") or today.year)
    if month not in ["%02d" % m for m in range(1, 13)]:
        return _err("month inválido: %s" % month)
    company = _company_info(client)
    vals = {"date_month": month, "date_year": year}
    if company.get("id"):
        vals["company_id"] = company["id"]
    wizard_id = client.create("l10n_ec.ats.wizard", vals)
    _odoo_call(client, "l10n_ec.ats.wizard", "action_generate_ats", [[wizard_id]])
    row = client.search_read("l10n_ec.ats.wizard", [("id", "=", wizard_id)],
                             ["xml_data", "xml_filename"], limit=1)[0]
    import base64
    xml_text = None
    truncated = False
    if row.get("xml_data"):
        raw = base64.b64decode(row["xml_data"])
        xml_text = raw.decode("utf-8", errors="replace")
        if len(xml_text) > 200_000:
            xml_text = xml_text[:200_000]
            truncated = True
    return {"status": "ok", "period": "%s/%s" % (month, year),
            "filename": row.get("xml_filename"),
            "wizard_id": wizard_id,
            "xml": xml_text, "truncated": truncated,
            "size_bytes": len(xml_text or "")}


def tool_get_sales_summary(client, args):
    client = _require(client)
    date_from = str(args.get("date_from") or
                    (datetime.date.today().replace(day=1)).isoformat())
    date_to = str(args.get("date_to") or datetime.date.today().isoformat())
    domain = [("invoice_date", ">=", date_from), ("invoice_date", "<=", date_to),
              ("state", "=", "posted"),
              ("move_type", "in", ["out_invoice", "out_refund"])]
    rows = client.search_read(
        "account.move", domain,
        ["move_type", "amount_untaxed", "amount_tax", "amount_total",
         "amount_total_signed", "partner_id", "l10n_ec_sri_status"], limit=5000)
    tot_untaxed = sum(r.get("amount_untaxed") or 0 for r in rows
                      if r["move_type"] == "out_invoice")
    tot_refunds = sum(abs(r.get("amount_total_signed") or 0) for r in rows
                      if r["move_type"] == "out_refund")
    tot_iva = sum(r.get("amount_tax") or 0 for r in rows
                  if r["move_type"] == "out_invoice")
    by_partner = {}
    for r in rows:
        if r.get("partner_id"):
            p = by_partner.setdefault(r["partner_id"][0],
                                      {"name": r["partner_id"][1],
                                       "count": 0, "total": 0.0})
            p["count"] += 1
            p["total"] += (r.get("amount_total_signed") or 0)
    top = sorted(by_partner.values(), key=lambda x: -abs(x["total"]))[:10]
    for p in top:
        p["total"] = round(p["total"], 2)
    sri_states = {}
    for r in rows:
        st = r.get("l10n_ec_sri_status") or "sin_estado"
        sri_states[st] = sri_states.get(st, 0) + 1
    return {"status": "ok", "period": {"from": date_from, "to": date_to},
            "documents": len(rows),
            "sales_untaxed": round(tot_untaxed, 2),
            "sales_iva": round(tot_iva, 2),
            "credit_notes_total": round(tot_refunds, 2),
            "net_sales": round(tot_untaxed - sum(
                r.get("amount_untaxed") or 0 for r in rows
                if r["move_type"] == "out_refund"), 2),
            "sri_status_counts": sri_states,
            "top_partners": top}


def tool_get_ar_aging(client, args):
    client = _require(client)
    today = _to_date(args.get("as_of")) or datetime.date.today()
    rows = client.search_read(
        "account.move",
        [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
         ("residual", ">", 0)],
        ["name", "partner_id", "invoice_date", "date_due", "residual",
         "amount_total"], limit=5000)
    buckets = {"not_due": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0,
               "90+": 0.0}
    detail = []
    for r in rows:
        due = _to_date(r.get("date_due")) or _to_date(r.get("invoice_date")) \
            or today
        overdue = (today - due).days
        residual = float(r.get("residual") or 0)
        if overdue <= 0:
            buckets["not_due"] += residual
        elif overdue <= 30:
            buckets["1-30"] += residual
        elif overdue <= 60:
            buckets["31-60"] += residual
        elif overdue <= 90:
            buckets["61-90"] += residual
        else:
            buckets["90+"] += residual
        detail.append({"name": r.get("name"),
                       "partner": r.get("partner_id") and r["partner_id"][1],
                       "invoice_date": r.get("invoice_date"),
                       "due_date": r.get("date_due"),
                       "days_overdue": max(overdue, 0),
                       "residual": residual})
    total = sum(buckets.values())
    return {"status": "ok", "as_of": today.isoformat(),
            "total_ar": round(total, 2),
            "buckets": {k: round(v, 2) for k, v in buckets.items()},
            "invoices": detail}


def tool_record_payment(client, args):
    client = _require(client)
    invoice_id = int(args.get("invoice_id") or 0)
    if not invoice_id:
        raise ToolError("falta invoice_id")
    inv = client.search_read(
        "account.move", [("id", "=", invoice_id)],
        ["id", "name", "state", "move_type", "partner_id", "residual",
         "currency_id"], limit=1)
    if not inv:
        raise ToolError("factura %s no existe" % invoice_id)
    inv = inv[0]
    if inv.get("state") != "posted":
        return _err("la factura %s está en %s; postee antes de registrar pago"
                    % (invoice_id, inv.get("state")),
                    hint="Use post_invoice primero.")
    amount = float(args.get("amount") or inv.get("residual") or 0)
    if amount <= 0:
        return _err("monto de pago inválido: %s" % amount)
    journal_id = args.get("journal_id")
    if not journal_id:
        journals = client.search_read(
            "account.journal",
            [("type", "in", ["bank", "cash"]), ("active", "=", True)],
            ["id", "name", "type"], limit=1)
        if not journals:
            return _err("no hay diarios de banco/caja configurados",
                        hint="Cree un diario de pago en Configuración > "
                             "Diarios.")
        journal_id = journals[0]["id"]
    inbound = inv["move_type"] in ("out_invoice", "out_refund")
    vals = {
        "payment_type": "inbound" if inbound else "outbound",
        "partner_type": "customer" if inbound else "supplier",
        "partner_id": inv["partner_id"][0],
        "amount": amount,
        "date": str(args.get("date") or datetime.date.today().isoformat()),
        "journal_id": int(journal_id),
        "invoice_ids": [(6, 0, [invoice_id])],
    }
    # payment_method_line is required in Odoo 18 on most configurations
    try:
        jrow = client.search_read("account.journal", [("id", "=", vals["journal_id"])],
                                  ["inbound_payment_method_line_ids",
                                   "outbound_payment_method_line_ids"], limit=1)[0]
        method_lines = jrow.get("inbound_payment_method_line_ids" if inbound
                                else "outbound_payment_method_line_ids") or []
        if method_lines:
            vals["payment_method_line_id"] = method_lines[0]
    except Exception:  # noqa: BLE001
        pass
    payment_id = client.create("account.payment", vals)
    _odoo_call(client, "account.payment", "action_post", [[payment_id]])
    row = client.search_read("account.payment", [("id", "=", payment_id)],
                             ["name", "state", "amount", "date"], limit=1)[0]
    after = client.search_read("account.move", [("id", "=", invoice_id)],
                               ["residual", "payment_state"], limit=1)[0]
    return {"status": "ok", "payment_id": payment_id,
            "name": row.get("name"), "state": row.get("state"),
            "amount": row.get("amount"), "date": row.get("date"),
            "invoice_id": invoice_id,
            "invoice_residual": after.get("residual"),
            "invoice_payment_state": after.get("payment_state")}


def tool_send_ride(client, args):
    client = _require(client)
    invoice_id = int(args.get("invoice_id") or 0)
    if not invoice_id:
        raise ToolError("falta invoice_id")
    inv = client.search_read(
        "account.move", [("id", "=", invoice_id)],
        ["id", "name", "state", "partner_id", "l10n_ec_sri_access_key",
         "l10n_ec_sri_status", "l10n_ec_xml_data"], limit=1)[0]
    out = {"status": "ok", "invoice_id": invoice_id, "name": inv.get("name"),
           "clave_acceso": inv.get("l10n_ec_sri_access_key"),
           "sri_status": inv.get("l10n_ec_sri_status"),
           "xml_available": bool(inv.get("l10n_ec_xml_data")),
           "warnings": []}
    reports = []
    try:
        reports = client.search_read(
            "ir.actions.report", [("model", "=", "account.move")],
            ["id", "name", "report_name"], limit=10)
    except Exception:  # noqa: BLE001
        reports = []
    if reports:
        out["report_action_id"] = reports[0]["id"]
        out["report_name"] = reports[0].get("report_name")
        out["url"] = "/web#id=%s&model=account.move&view_type=form" % invoice_id
    else:
        out["warnings"].append(
            "no existe un reporte RIDE (PDF) para account.move en estas "
            "versiones de los módulos; solo puedo darle la clave y el XML. "
            "Ver ODOO-SIDE HELPERS NEEDED.")
    email = args.get("email")
    if email:
        try:
            _odoo_call(client, "account.move", "message_post",
                       [[invoice_id]],
                       {"body": ("Factura %s — Clave de acceso: %s (estado "
                                 "SRI: %s)" % (inv.get("name"),
                                               out["clave_acceso"],
                                               out["sri_status"])),
                        "subject": "Comprobante electrónico %s"
                                   % inv.get("name")})
            out["messaged"] = True
        except ToolError as exc:
            out["messaged"] = False
            out["warnings"].append("no se pudo registrar el mensaje: %s" % exc)
    return out


def tool_get_stock_level(client, args):
    client = _require(client)
    domain = [("sale_ok", "=", True)]
    product_id = args.get("product_id")
    search = (args.get("search") or args.get("product") or "").strip()
    if product_id:
        domain = [("id", "=", int(product_id))]
    elif search:
        domain = ["&", ("sale_ok", "=", True), "|",
                  ("name", "ilike", search), ("default_code", "ilike", search)]
    rows = client.search_read(
        "product.product", domain,
        ["id", "name", "default_code", "qty_available", "virtual_available",
         "incoming_qty", "outgoing_qty", "uom_id"], limit=int(args.get("limit") or 20))
    items = [{
        "product_id": r["id"],
        "name": r.get("name"),
        "default_code": r.get("default_code"),
        "qty_available": r.get("qty_available"),
        "virtual_available": r.get("virtual_available"),
        "incoming_qty": r.get("incoming_qty"),
        "outgoing_qty": r.get("outgoing_qty"),
        "uom": r.get("uom_id") and r["uom_id"][1],
    } for r in rows]
    if product_id and not items:
        return _err("producto %s no encontrado" % product_id)
    return {"status": "ok", "count": len(items), "products": items}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "detect_taxpayer",
        "description": (
            "Detecta el tipo de contribuyente ecuatoriano a partir del RUC o "
            "cédula: persona natural vs jurídica (3er dígito RUC), obligado a "
            "contabilidad, contribuyente especial, agente de retención, "
            "régimen RIMPE, validez del dígito verificador y estado en el SRI."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vat": {"type": "string", "description": "RUC (13) o cédula (10)"},
                "consult_sri": {"type": "boolean",
                                "description": "Consultar el SRI vía Odoo (default true)"},
            },
            "required": ["vat"],
        },
        "handler": tool_detect_taxpayer,
    },
    {
        "name": "validate_ruc",
        "description": "Valida RUC/cédula (módulo 11 / módulo 10) y opcionalmente consulta el SRI.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "vat": {"type": "string"},
                "consult_sri": {"type": "boolean"},
            },
            "required": ["vat"],
        },
        "handler": tool_validate_ruc,
    },
    {
        "name": "get_client_data",
        "description": (
            "Devuelve el set legal completo de un cliente para factura "
            "electrónica: nombre/razón social, RUC/CI, dirección, email/tel, "
            "régimen, si aplica retención y si aplica límite de Consumidor "
            "Final, más los campos faltantes."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "partner_id": {"type": "integer"},
                "vat": {"type": "string"},
                "search": {"type": "string", "description": "nombre a buscar"},
                "consult_sri": {"type": "boolean"},
            },
        },
        "handler": tool_get_client_data,
    },
    {
        "name": "create_partner",
        "description": (
            "Crea un cliente pre-llenando los datos del SRI (consultar_ruc). "
            "Si el SRI no tiene algún dato obligatorio lo devuelve en "
            "missing_from_sri con la pregunta para el usuario."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "vat": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "street": {"type": "string"},
            },
            "required": ["vat"],
        },
        "handler": tool_create_partner,
    },
    {
        "name": "create_invoice",
        "description": (
            "Crea una factura de venta (codDoc 01) aplicando las reglas "
            "ecuatorianas: detecta el tipo de contribuyente, valida el RUC, "
            "respeta Consumidor Final ≤ $50 y, si faltan datos legalmente "
            "obligatorios, responde status=needs_data con la pregunta a "
            "hacerse al usuario en vez de fallar."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "partner_id": {"type": "integer"},
                "vat": {"type": "string"},
                "search": {"type": "string"},
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                            "product_id": {"type": "integer"},
                            "tax_rate": {"type": "number"},
                            "tax_ids": {"type": "array", "items": {"type": "integer"}},
                        },
                        "required": ["description", "unit_price"],
                    },
                },
                "amount": {"type": "number",
                           "description": "atajo: factura única por monto"},
                "description": {"type": "string"},
                "invoice_date": {"type": "string", "description": "YYYY-MM-DD"},
                "document_type": {"type": "string", "description": "01 factura | 03 liquidación compra"},
                "journal_id": {"type": "integer"},
                "ref": {"type": "string"},
            },
        },
        "handler": tool_create_invoice,
    },
    {
        "name": "post_invoice",
        "description": (
            "Postea la factura y la envía al SRI (firma + recepción) usando "
            "l10n_ec_edi (action_post + action_send_sri). Devuelve la clave "
            "de acceso de 49 dígitos y el estado SRI."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer"},
                "send_to_sri": {"type": "boolean"},
            },
            "required": ["invoice_id"],
        },
        "handler": tool_post_invoice,
    },
    {
        "name": "create_credit_note",
        "description": (
            "Nota de crédito (codDoc 04) contra una factura de venta. "
            "Respeta: CF no anulable y anulación solo hasta el día 7 del mes "
            "siguiente (Res. NAC-DGERCGC25-00000017)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer"},
                "reason": {"type": "string"},
                "credit_note_date": {"type": "string"},
                "post": {"type": "boolean"},
            },
            "required": ["invoice_id", "reason"],
        },
        "handler": tool_create_credit_note,
    },
    {
        "name": "calculate_withholding",
        "description": (
            "Calcula la retención IR (Tabla 19) o IVA (casilleros F.104 "
            "721-731: 10/20/30/50/70/100%) sobre una factura y avisa si el "
            "plazo de 5 días hábiles (LRTI art. 50; feriados ecuatorianos "
            "incluidos) ya venció. No escribe nada."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer"},
                "tax_type": {"type": "string", "description": "renta | iva | isd"},
                "percentage": {"type": "number"},
                "category": {"type": "string", "description": "servicios | bienes"},
            },
            "required": ["invoice_id"],
        },
        "handler": tool_calculate_withholding,
    },
    {
        "name": "create_withholding",
        "description": (
            "Crea el comprobante de retención (account.retention, codDoc 07) "
            "ligado a la factura, con código de retención de "
            "l10n_ec.withholding.tax y control del plazo de 5 días hábiles."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer"},
                "tax_type": {"type": "string", "description": "renta | iva | isd"},
                "percentage": {"type": "number"},
                "category": {"type": "string"},
                "tax_id": {"type": "integer"},
                "date": {"type": "string"},
                "post": {"type": "boolean"},
                "send_to_sri": {"type": "boolean"},
            },
            "required": ["invoice_id"],
        },
        "handler": tool_create_withholding,
    },
    {
        "name": "generate_payslips",
        "description": (
            "Genera payslips ecuatorianos (l10n_ec.payslip) para todos los "
            "contratos activos en un periodo y los confirma."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_start": {"type": "string"},
                "date_end": {"type": "string"},
                "employee_ids": {"type": "array", "items": {"type": "integer"}},
                "confirm": {"type": "boolean"},
            },
            "required": ["date_start", "date_end"],
        },
        "handler": tool_generate_payslips,
    },
    {
        "name": "generate_iess_planilla",
        "description": (
            "Agrega los aportes IESS personal/patronal de los payslips "
            "confirmados de un periodo, listo para la planilla IESS."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_start": {"type": "string"},
                "date_end": {"type": "string"},
            },
            "required": ["date_start", "date_end"],
        },
        "handler": tool_generate_iess_planilla,
    },
    {
        "name": "calculate_liquidation",
        "description": (
            "Calcula liquidación de beneficios sociales (décimo tercero, "
            "décimo cuarto, fondos de reserva 8.33%, IESS con techo 25×SBU, "
            "opcional impuesto a la renta progresivo con la tabla de Odoo)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "integer"},
                "wage": {"type": "number"},
                "days_worked": {"type": "number"},
                "extra_income": {"type": "number"},
                "advances": {"type": "number"},
                "income_tax": {"type": "number"},
                "include_tax": {"type": "boolean",
                                "description": "calcular renta con l10n_ec.tax.table"},
                "period_end": {"type": "string"},
            },
        },
        "handler": tool_calculate_liquidation,
    },
    {
        "name": "generate_ats",
        "description": (
            "Genera el Anexo Transaccional Simplificado (ATS) mensual vía "
            "l10n_ec.ats.wizard y devuelve el XML."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "01..12"},
                "year": {"type": "string"},
            },
        },
        "handler": tool_generate_ats,
    },
    {
        "name": "get_sales_summary",
        "description": "Resumen de ventas (facturas y NC) por periodo con top de clientes y estados SRI.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
        },
        "handler": tool_get_sales_summary,
    },
    {
        "name": "get_ar_aging",
        "description": "Antigüedad de saldos por cobrar con buckets 0-30/31-60/61-90/90+.",
        "inputSchema": {
            "type": "object",
            "properties": {"as_of": {"type": "string"}},
        },
        "handler": tool_get_ar_aging,
    },
    {
        "name": "record_payment",
        "description": "Registra un cobro/pago (account.payment) contra una factura posteada.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer"},
                "amount": {"type": "number"},
                "date": {"type": "string"},
                "journal_id": {"type": "integer"},
            },
            "required": ["invoice_id"],
        },
        "handler": tool_record_payment,
    },
    {
        "name": "send_ride",
        "description": (
            "Entrega el RIDE de una factura: reporte/URL si existe, clave de "
            "acceso, estado SRI y disponibilidad del XML firmado."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["invoice_id"],
        },
        "handler": tool_send_ride,
    },
    {
        "name": "get_stock_level",
        "description": "Existencias de productos (disponible, virtual, entradas/salidas).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "product_id": {"type": "integer"},
                "limit": {"type": "integer"},
            },
        },
        "handler": tool_get_stock_level,
    },
]

_HANDLERS = {t["name"]: t["handler"] for t in TOOLS}


def list_tools():
    return [{k: t[k] for k in ("name", "description", "inputSchema")} for t in TOOLS]


def call_tool(client, name, arguments):
    """Dispatch a tool call; never raises — always a dict."""
    handler = _HANDLERS.get(name)
    if handler is None:
        return _err("herramienta desconocida: %s" % name,
                    hint="Use tools/list para ver las disponibles.")
    args = arguments or {}
    _log.info("tool %s args=%s", name, sorted(args.keys()))
    try:
        return handler(client, args)
    except ToolError as exc:
        return _err(str(exc), hint=exc.hint, **exc.extra)
    except Exception as exc:  # noqa: BLE001 - last-resort normalization
        from odoo_client import OdooConnectionError
        if isinstance(exc, OdooConnectionError):
            return _err(str(exc), hint=exc.hint, kind="odoo_unreachable")
        _log.exception("tool %s failed", name)
        return _err("error interno en %s: %s" % (name, exc),
                    hint="Revise el log del servidor MCP (stderr).")
