/* SOMATECH-ODOO-BRIDGE — JS de la UI (vanilla, sin framework/build).
   Contrato: token Bearer en sessionStorage; nav derivada del ROL en el
   servidor (GET /api/nav, §5.2 — la UI sólo renderiza, el bridge decide,
   FR-BR-02/D-09). Si /api/nav falla, fallback a entities del login. */
"use strict";

const Bridge = {
  token() { return sessionStorage.getItem("bridge_token") || null; },
  session() {
    try { return JSON.parse(sessionStorage.getItem("bridge_session") || "{}"); }
    catch (e) { return {}; }
  },
  save(session) {
    sessionStorage.setItem("bridge_token", session.token);
    sessionStorage.setItem("bridge_session", JSON.stringify(session));
  },
  clear() {
    sessionStorage.removeItem("bridge_token");
    sessionStorage.removeItem("bridge_session");
  },
  async api(path, opts = {}) {
    const res = await fetch(path, Object.assign({
      headers: Object.assign(
        { "Content-Type": "application/json" },
        this.token() ? { "Authorization": "Bearer " + this.token() } : {}),
    }, opts));
    let data = {};
    try { data = await res.json(); } catch (e) { /* vacío */ }
    if (!res.ok) {
      const err = new Error((data.error && data.error.message) || res.statusText);
      err.status = res.status; err.data = data;
      throw err;
    }
    return data;
  },
  esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
      }[c]));
  },
  show(el, html) { const n = document.getElementById(el); if (n) n.innerHTML = html; },
};

/* ------------------------------------------------------------------ */
/* Login (index.html)                                                  */
/* ------------------------------------------------------------------ */
const BridgeLogin = {
  init() {
    if (Bridge.token()) { location.href = "/app.html"; return; }
    const form = document.getElementById("login-form");
    document.getElementById("db").value =
      new URLSearchParams(location.search).get("db") || "odooec";
    form.addEventListener("submit", ev => this.submit(ev));
  },
  async submit(ev) {
    ev.preventDefault();
    const err = document.getElementById("login-error");
    const nd = document.getElementById("needs-data");
    err.textContent = ""; nd.hidden = true; nd.innerHTML = "";
    const body = {
      db: document.getElementById("db").value.trim(),
      login: document.getElementById("login").value.trim(),
      password: document.getElementById("password").value,
    };
    try {
      const session = await Bridge.api("/auth/login", {
        method: "POST", body: JSON.stringify(body),
      });
      Bridge.save(session);
      if (session.needs_data && session.needs_data.length) {
        nd.innerHTML = session.needs_data.map(q =>
          `<div class="notice"><span class="micro">Dato faltante</span>
           <div>${Bridge.esc(q.question)}</div></div>`).join("");
        nd.hidden = false;
      } else {
        location.href = "/app.html";
      }
    } catch (e) {
      err.textContent = e.message || "Error de autenticación";
    }
  },
};

/* ------------------------------------------------------------------ */
/* App shell (app.html)                                                */
/* ------------------------------------------------------------------ */
const BridgeApp = {
  /* Mapa key→{title,entities} para fallback si /api/nav falla (escenario 7) */
  views: {
    ops: { title: "Operación", entities: ["lotes"] },
    gestion: { title: "Gestión", entities: ["ciclos", "analisis"] },
    lotes: { title: "Lotes", entities: ["lotes"] },
    predios: { title: "Predios", entities: ["predios"] },
    trazabilidad: { title: "Trazabilidad", entities: ["lotes"] },
    eventos: { title: "Eventos", entities: ["eventos"] },
    wizard: { title: "Wizard", entities: [], roles: ["admin", "gerente"] },
    chat: { title: "Agente", entities: null },
  },
  _navKeys: null,  // keys servidas por /api/nav (se puebla en init)

  async init() {
    if (!Bridge.token()) { location.href = "/index.html"; return; }
    const s = Bridge.session();
    document.getElementById("whoami").textContent =
      `${s.name || "?"} @ ${s.db || "?"}`;
    document.getElementById("role").textContent = s.role || "sin rol";
    document.getElementById("logout").onclick = () => {
      Bridge.clear(); location.href = "/index.html";
    };
    document.getElementById("theme").onclick = () => {
      const html = document.documentElement;
      html.classList.toggle("light"); html.classList.toggle("dark");
    };
    await this.loadNav();
    /* P3: botón "Ver trace" de la vista trazabilidad */
    const traceGo = document.getElementById("trace-go");
    if (traceGo) {
      traceGo.onclick = () => {
        const v = document.getElementById("trace-lot-id").value.trim();
        if (v) location.hash = "#/trazabilidad/" + encodeURIComponent(v);
      };
    }
    window.addEventListener("hashchange", () => this.route());
    if (!location.hash) location.hash = "#/ops";
    this.route();
  },

  async loadNav() {
    try {
      const nav = await Bridge.api("/api/nav");
      this._navKeys = new Set(nav.items.map(i => i.key));
      const el = document.getElementById("nav");
      el.innerHTML = nav.items.map(i =>
        `<button class="btn" data-view="${i.key}">${Bridge.esc(i.label)}</button>`
      ).join("");
      el.querySelectorAll("button").forEach(b => {
        b.onclick = () => { location.hash = "#/" + b.dataset.view; };
      });
    } catch (e) {
      /* /api/nav caído o 401/403 ⇒ fallback local (escenario 7) */
      this._navKeys = null;
      this.renderNavFallback();
    }
  },

  renderNavFallback() {
    const s = Bridge.session();
    const nav = document.getElementById("nav");
    const items = Object.entries(this.views)
      .filter(([k, v]) => this.allowedLocal(k, s));
    nav.innerHTML = items.map(([k, v]) =>
      `<button class="btn" data-view="${k}">${v.title}</button>`).join("");
    nav.querySelectorAll("button").forEach(b => {
      b.onclick = () => { location.hash = "#/" + b.dataset.view; };
    });
  },

  /* deny-by-default local (sólo fallback; el gate real es el servidor) */
  allowedLocal(viewKey, s) {
    const view = this.views[viewKey];
    if (!view) return false;
    if (view.roles) return view.roles.includes(s.role);
    if (!view.entities || !view.entities.length) return true;
    return view.entities.every(e => (s.entities || []).includes(e));
  },

  allowed(viewKey) {
    if (this._navKeys) return this._navKeys.has(viewKey);
    return this.allowedLocal(viewKey, Bridge.session());
  },

  current() { return (location.hash || "#/ops").replace("#/", "").split("/")[0]; },

  route() {
    const view = this.current();
    ["ops", "gestion", "lotes", "lote", "predios", "trazabilidad",
     "eventos", "wizard", "chat"].forEach(v => {
      const el = document.getElementById("view-" + v);
      if (el) el.hidden = true;
    });
    document.querySelectorAll("#nav button").forEach(b =>
      b.setAttribute("aria-current", String(b.dataset.view === view)));
    if (!this.allowed(view) && view !== "lote") {
      /* vista no permitida ⇒ volver a la primera permitida */
      const first = (this._navKeys
        ? [...this._navKeys][0]
        : Object.keys(this.views).find(k => this.allowedLocal(k, Bridge.session())));
      if (first) { location.hash = "#/" + first; return; }
    }
    const id = (location.hash.split("/")[2] || "").trim();
    if (view === "lote" && id) { this.loadLote(id); return; }
    if (view === "trazabilidad") { this.loadTrazabilidad(id); return; }
    const el = document.getElementById("view-" + view);
    if (el) el.hidden = false;
    if (view === "ops") this.loadOps();
    else if (view === "gestion") this.loadGestion();
    else if (view === "lotes") this.loadLotes();
    else if (view === "predios") this.loadPredios();
    else if (view === "eventos") this.loadEventos();
    else if (view === "wizard") this.loadWizard();
    else if (view === "chat") this.chatInit();
  },

  /* -- KPIs ---------------------------------------------------------- */
  async loadOps() {
    try {
      const k = await Bridge.api("/api/kpis/lotes");
      Bridge.show("ops-kpis", [
        this.kpi("Lotes totales", k.total),
        this.kpi("Bloqueados (gate)", k.bloqueados, k.bloqueados ? "bad" : "ok"),
        ...Object.entries(k.por_estado_lab || {}).map(([state, n]) =>
          this.kpi("Lab: " + state, n)),
      ].join(""));
      const failed = await Bridge.api("/api/list/lotes?lab_state=failed");
      Bridge.show("ops-alerts", failed.items.length
        ? this.lotesTable(failed.items)
        : `<p class="kpi-sub">Sin lotes reprobados. ✔</p>`);
      this.bindRowLinks();
    } catch (e) { this.deny(e); }
  },

  async loadGestion() {
    try {
      const [kc, ka] = await Promise.all([
        Bridge.api("/api/kpis/ciclos"), Bridge.api("/api/kpis/analisis"),
      ]);
      Bridge.show("gestion-kpis", [
        this.kpi("Ciclos", kc.total),
        ...Object.entries(kc.por_estado || {}).map(([state, n]) =>
          this.kpi("Ciclo: " + state, n)),
        this.kpi("Análisis", ka.total),
        this.kpi("No conformes", ka.no_conformes,
                 ka.no_conformes ? "bad" : "ok"),
      ].join(""));
      const ciclos = await Bridge.api("/api/list/ciclos");
      Bridge.show("ciclos-table", ciclos.items.length ? `
        <table><thead><tr><th>Predio</th><th>Cultivo</th><th>Variedad</th>
        <th>Siembra</th><th>Cosecha esp.</th><th>Estado</th></tr></thead><tbody>
        ${ciclos.items.map(c => `<tr>
          <td>${Bridge.esc((c.plot_id || [])[1] || "")}</td>
          <td>${Bridge.esc((c.crop_id || [])[1] || "")}</td>
          <td>${Bridge.esc(c.variety || "")}</td>
          <td class="mono">${Bridge.esc(c.sow_date || "—")}</td>
          <td class="mono">${Bridge.esc(c.expected_harvest_date || "—")}</td>
          <td><span class="pill">${Bridge.esc(c.state || "")}</span></td>
        </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin ciclos aún.</p>`);
    } catch (e) { this.deny(e); }
  },

  /* -- Lotes (lista → detalle, escenario 2) -------------------------- */
  async loadLotes() {
    try {
      const list = await Bridge.api("/api/list/lotes");
      Bridge.show("lotes-table", list.items.length
        ? this.lotesTable(list.items)
        : `<p class="kpi-sub">Sin lotes aún.</p>`);
      this.bindRowLinks();
    } catch (e) { this.deny(e); }
  },

  lotesTable(items) {
    return `<table><thead><tr>
      <th>Lote</th><th>Producto</th><th>Cultivo</th><th>Variedad</th>
      <th>Cosecha</th><th>Lab</th><th class="num">Stock</th>
      <th></th></tr></thead><tbody>
      ${items.map(l => `<tr class="rowlink" data-id="${l.id}">
        <td class="mono">${Bridge.esc(l.name)}</td>
        <td>${Bridge.esc((l.product_id || [])[1] || "")}</td>
        <td>${Bridge.esc((l.l10n_ec_crop_type || [])[1] || "—")}</td>
        <td>${Bridge.esc(l.l10n_ec_variety || "—")}</td>
        <td class="mono">${Bridge.esc(l.l10n_ec_harvest_date || "—")}</td>
        <td>${this.labPill(l.l10n_ec_lab_state)}</td>
        <td class="num">${Number(l.product_qty || 0).toFixed(2)}</td>
        <td><a href="#/trazabilidad/${l.id}" class="mono"
               style="color:var(--brand)">trace →</a></td>
      </tr>`).join("")}</tbody></table>`;
  },

  bindRowLinks() {
    document.querySelectorAll("tr.rowlink").forEach(tr => {
      tr.onclick = (ev) => {
        if (ev.target.tagName === "A") return;  // link trace: no abrir detalle
        location.hash = "#/lote/" + tr.dataset.id;
      };
    });
  },

  async loadLote(id) {
    document.getElementById("view-lote").hidden = false;
    try {
      const d = await Bridge.api("/api/detail/lotes/" + encodeURIComponent(id));
      const r = d.record;
      document.getElementById("lote-title").textContent =
        (r.name || "Lote") + (r.l10n_ec_variety ? " · " + r.l10n_ec_variety : "");
      Bridge.show("lote-detail", `
        <div class="grid">
          ${this.kpi("Producto", (r.product_id || [])[1] || "—")}
          ${this.kpi("Cultivo", (r.l10n_ec_crop_type || [])[1] || "—")}
          ${this.kpi("Ciclo", (r.l10n_ec_cycle_id || [])[1] || "—")}
          ${this.kpi("Cosecha", r.l10n_ec_harvest_date || "—")}
          ${this.kpi("Stock", Number(r.product_qty || 0).toFixed(2))}
          ${this.kpi("Registro sanitario", r.l10n_ec_sanitary_reg || "—")}
        </div>
        <p style="margin-top:14px"><a href="#/trazabilidad/${r.id}"
           class="mono" style="color:var(--brand)">Ver trazabilidad completa
           (genealogía + recall) →</a></p>
        <h2 style="margin-top:22px">Estado de laboratorio
          ${this.labPill(r.l10n_ec_lab_state)}</h2>
        <p class="kpi-sub">Análisis del lote (genealogía hacia abajo, FR-AG-04).</p>
        ${(r.analisis || []).length ? `<table><thead><tr>
          <th>Analito</th><th class="num">Valor</th><th class="num">Límite</th>
          <th>Estado</th><th>Laboratorio</th><th>Fecha</th></tr></thead><tbody>
          ${r.analisis.map(a => `<tr>
            <td>${Bridge.esc(a.analyte)}</td>
            <td class="num">${a.value} ${Bridge.esc(a.unit || "")}</td>
            <td class="num">${a.limit || "—"}</td>
            <td>${a.passed
              ? '<span class="pill ok">conforme</span>'
              : '<span class="pill bad">no conforme</span>'}</td>
            <td>${Bridge.esc(a.lab_name || "—")}</td>
            <td class="mono">${Bridge.esc(a.analysis_date || "—")}</td>
          </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin análisis registrados.</p>`}`);
    } catch (e) { this.deny(e); }
  },

  /* -- P3: Predios --------------------------------------------------- */
  async loadPredios() {
    try {
      const [k, list] = await Promise.all([
        Bridge.api("/api/kpis/predios"), Bridge.api("/api/list/predios"),
      ]);
      Bridge.show("predios-kpis", [
        this.kpi("Predios", k.total),
        this.kpi("Activos", k.activos),
      ].join(""));
      Bridge.show("predios-table", list.items.length ? `
        <table><thead><tr><th>Código</th><th>Nombre</th>
        <th class="num">Hectáreas</th><th>Ubicación</th><th>Responsable</th>
        <th>Activo</th></tr></thead><tbody>
        ${list.items.map(p => `<tr>
          <td class="mono">${Bridge.esc(p.code || "—")}</td>
          <td>${Bridge.esc(p.name)}</td>
          <td class="num">${Number(p.hectares || 0).toFixed(2)}</td>
          <td>${Bridge.esc(p.location || "—")}</td>
          <td>${Bridge.esc((p.responsible_id || [])[1] || "—")}</td>
          <td>${p.active
            ? '<span class="pill ok">sí</span>'
            : '<span class="pill">no</span>'}</td>
        </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin predios aún.</p>`);
    } catch (e) { this.deny(e); }
  },

  /* -- P3: Eventos (append-only viewer) ------------------------------ */
  async loadEventos() {
    try {
      const [k, list] = await Promise.all([
        Bridge.api("/api/kpis/eventos"), Bridge.api("/api/list/eventos?limit=50"),
      ]);
      Bridge.show("eventos-kpis", [
        this.kpi("Eventos", k.total),
        ...Object.entries(k.por_etapa || {}).map(([stage, n]) =>
          this.kpi("Etapa: " + stage, n)),
      ].join(""));
      Bridge.show("eventos-table", list.items.length ? `
        <table><thead><tr><th>Fecha</th><th>Etapa</th><th>Lote</th>
        <th class="num">Cantidad</th><th>Tercero</th><th>Comprobante</th>
        </tr></thead><tbody>
        ${list.items.map(e => `<tr>
          <td class="mono">${Bridge.esc(e.event_date || "—")}</td>
          <td><span class="pill">${Bridge.esc(e.stage || "")}</span></td>
          <td class="mono">${Bridge.esc((e.lot_id || [])[1] || "")}</td>
          <td class="num">${Number(e.qty || 0).toFixed(2)}</td>
          <td>${Bridge.esc((e.partner_id || [])[1] || "—")}</td>
          <td class="mono">${Bridge.esc(e.comprobante || "—")}</td>
        </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin eventos aún.</p>`);
    } catch (e) { this.deny(e); }
  },

  /* -- P3: Trazabilidad (genealogía up/down + recall, FR-AG-06/07) --- */
  async loadTrazabilidad(id) {
    document.getElementById("view-trazabilidad").hidden = false;
    const idInput = document.getElementById("trace-lot-id");
    if (id && idInput) idInput.value = id;
    if (!id && idInput && idInput.value) id = idInput.value.trim();
    if (!id) {
      Bridge.show("trace-detail",
        `<p class="kpi-sub">Seleccione un lote (ingrese el ID o use el enlace
         «trace →» desde la lista de lotes).</p>`);
      return;
    }
    Bridge.show("trace-detail", `<p class="kpi-sub">Cargando trazabilidad…</p>`);
    try {
      const t = await Bridge.api("/api/trace/lote/" + encodeURIComponent(id));
      const lot = t.lot;
      const up = t.up || {};
      const down = t.down || {};
      const recall = t.recall || {};
      Bridge.show("trace-title", (lot.name || "Lote") + " · trazabilidad");
      Bridge.show("trace-detail", `
        <div class="grid">
          ${this.kpi("Lote", lot.name || "—")}
          ${this.kpi("Producto", (lot.product_id || [])[1] || "—")}
          ${this.kpi("Cosecha", lot.l10n_ec_harvest_date || "—")}
          ${this.kpi("Stock", Number(lot.product_qty || 0).toFixed(2))}
        </div>
        <h2 style="margin-top:22px">Genealogía ↑ (ciclo → predio)</h2>
        ${up.cycle ? `<div class="grid">
          ${this.kpi("Ciclo", up.cycle.display_name || ("#" + up.cycle.id))}
          ${this.kpi("Predio", (up.plot || {}).name || "—")}
          ${this.kpi("Cultivo", (up.cycle.crop_id || [])[1] || "—")}
          ${this.kpi("Siembra", up.cycle.sow_date || "—")}
          ${this.kpi("Estado ciclo", up.cycle.state || "—")}
        </div>` : `<p class="kpi-sub">Sin ciclo asociado.</p>`}

        <h2 style="margin-top:22px">Análisis de laboratorio (↓)</h2>
        ${(down.analisis || []).length ? `<table><thead><tr>
          <th>Analito</th><th class="num">Valor</th><th>Estado</th>
          <th>Fecha</th></tr></thead><tbody>
          ${down.analisis.map(a => `<tr>
            <td>${Bridge.esc(a.analyte)}</td>
            <td class="num">${a.value} ${Bridge.esc(a.unit || "")}</td>
            <td>${a.passed
              ? '<span class="pill ok">conforme</span>'
              : '<span class="pill bad">no conforme</span>'}</td>
            <td class="mono">${Bridge.esc(a.analysis_date || "—")}</td>
          </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin análisis.</p>`}

        <h2 style="margin-top:22px">Eventos de trazabilidad (↓, append-only)</h2>
        ${(down.eventos || []).length ? `<table><thead><tr>
          <th>Fecha</th><th>Etapa</th><th class="num">Cantidad</th>
          <th>Comprobante</th></tr></thead><tbody>
          ${down.eventos.map(e => `<tr>
            <td class="mono">${Bridge.esc(e.event_date || "—")}</td>
            <td><span class="pill">${Bridge.esc(e.stage || "")}</span></td>
            <td class="num">${Number(e.qty || 0).toFixed(2)}</td>
            <td class="mono">${Bridge.esc(e.comprobante || "—")}</td>
          </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin eventos.</p>`}

        <h2 style="margin-top:22px">Movimientos de stock (↓)</h2>
        ${(down.movimientos || []).length ? `<table><thead><tr>
          <th>Fecha</th><th>Estado</th><th class="num">Cantidad</th>
          <th>Destino</th></tr></thead><tbody>
          ${down.movimientos.map(m => `<tr>
            <td class="mono">${Bridge.esc(m.date || "—")}</td>
            <td><span class="pill">${Bridge.esc(m.state || "")}</span></td>
            <td class="num">${Number(m.product_uom_qty || 0).toFixed(2)}</td>
            <td>${Bridge.esc((m.location_dest_id || [])[1] ||
                             m.location_dest_id || "—")}</td>
          </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin movimientos.</p>`}

        <h2 style="margin-top:22px">Recall (facturas desde cosecha,
          FR-AG-06/07)</h2>
        <p class="kpi-sub">Desde ${Bridge.esc(recall.harvest_date || "—")} —
          facturas del producto desde la fecha de cosecha.</p>
        ${(recall.invoices || []).length ? `<table><thead><tr>
          <th>Factura</th><th>Fecha</th><th class="num">Total</th>
          <th>Estado</th></tr></thead><tbody>
          ${recall.invoices.map(inv => `<tr>
            <td class="mono">${Bridge.esc(inv.name || "—" + inv.id)}</td>
            <td class="mono">${Bridge.esc(inv.invoice_date || "—")}</td>
            <td class="num">${Number(inv.amount_total || 0).toFixed(2)}</td>
            <td><span class="pill">${Bridge.esc(inv.state || "")}</span></td>
          </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin facturas desde la cosecha (o el producto no
           está facturado aún).</p>`}`);
    } catch (e) {
      Bridge.show("trace-detail",
        `<p class="kpi-sub">⚠ ${Bridge.esc(e.message)}</p>`);
    }
  },

  /* -- P3: Wizard (templates + params + preview/apply) --------------- */
  async loadWizard() {
    try {
      const [tpl, params] = await Promise.all([
        Bridge.api("/api/wizard/templates"), Bridge.api("/api/wizard/params"),
      ]);
      const isAdmin = (Bridge.session().role === "admin");
      Bridge.show("wizard-templates", tpl.templates.length ? tpl.templates.map(t => `
        <div class="card hover" style="margin-bottom:10px">
          <p class="micro">${Bridge.esc(t.code)} · v${Bridge.esc(t.version)}</p>
          <p>${Bridge.esc(t.name)}</p>
          <p class="kpi-sub">Aplicado: ${Bridge.esc(t.applied_version || "nunca")}
            ${t.applied_at ? " · " + Bridge.esc(t.applied_at) : ""}</p>
          <div class="quick" style="margin-top:8px">
            <button class="btn" data-tpl="${Bridge.esc(t.vertical)}"
                    data-size="${Bridge.esc(t.size)}" data-act="preview">Preview</button>
            ${isAdmin ? `<button class="btn primary" data-tpl="${Bridge.esc(t.vertical)}"
                    data-size="${Bridge.esc(t.size)}" data-act="apply">Apply (admin)</button>`
              : `<span class="kpi-sub">(apply requiere rol admin — AGT-01)</span>`}
          </div>
        </div>`).join("")
        : `<p class="kpi-sub">Sin plantillas en el catálogo.</p>`);
      Bridge.show("wizard-params", params.params.length ? `
        <table><thead><tr><th>Clave</th><th>Valor</th><th>Tipo</th>
        <th>Fuente</th></tr></thead><tbody>
        ${params.params.map(p => `<tr>
          <td class="mono">${Bridge.esc(p.key)}</td>
          <td>${Bridge.esc(p.value || "—")}</td>
          <td><span class="pill">${Bridge.esc(p.value_type || "")}</span></td>
          <td><span class="pill">${Bridge.esc(p.source || "")}</span></td>
        </tr>`).join("")}</tbody></table>`
        : `<p class="kpi-sub">Sin params configurados.</p>`);
      document.querySelectorAll("#wizard-templates button[data-act]").forEach(b => {
        b.onclick = () => this.wizardAction(b.dataset.tpl, b.dataset.size, b.dataset.act);
      });
    } catch (e) {
      Bridge.show("wizard-templates", `<p class="kpi-sub">⚠ ${Bridge.esc(e.message)}</p>`);
    }
  },

  async wizardAction(vertical, size, act) {
    const out = document.getElementById("wizard-result");
    out.hidden = false;
    out.innerHTML = `<p class="kpi-sub">${act === "apply" ? "Aplicando" : "Previsualizando"}
      ${Bridge.esc(vertical)}/${Bridge.esc(size)}…</p>`;
    try {
      const res = await Bridge.api("/api/wizard/" + act, {
        method: "POST", body: JSON.stringify({ vertical, size }),
      });
      const plan = res.plan || res.applied || {};
      const sum = plan.summary || {};
      Bridge.show("wizard-result", `
        <div class="notice">
          <span class="micro">${act === "apply" ? "Aplicado" : "Dry-run (preview)"}
            · ${Bridge.esc(vertical)}/${Bridge.esc(size)}</span>
          <div class="grid" style="margin-top:8px">
            ${this.kpi("Create", sum.create || 0, (sum.create || 0) ? "ok" : "")}
            ${this.kpi("Update", sum.update || 0)}
            ${this.kpi("Skip", sum.skip || 0)}
          </div>
          ${(plan.warnings || []).length
            ? `<p class="kpi-sub" style="color:var(--brand)">⚠ ${plan.warnings.map(Bridge.esc).join(" · ")}</p>`
            : ""}
          ${(plan.needs_data || []).length
            ? plan.needs_data.map(n => `<div class="notice">
                <span class="micro">Dato faltante</span>
                <div>${Bridge.esc(n.question)}</div></div>`).join("")
            : ""}
          ${(plan.auto_enable || []).length
            ? `<p class="kpi-sub">Auto-enable: ${plan.auto_enable.map(a =>
                Bridge.esc(a.key)).join(", ")}</p>`
            : ""}
        </div>`);
    } catch (e) {
      Bridge.show("wizard-result",
        `<p class="kpi-sub">⚠ ${Bridge.esc(e.message)}</p>`);
    }
  },

  /* -- Chat (agente con tools reales + contexto) --------------------- */
  chatInit() {
    if (this._chatReady) return;
    this._chatReady = true;
    const log = document.getElementById("chat-log");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-text");
    const quick = document.getElementById("chat-quick");
    quick.innerHTML = [
      "validar RUC 1793125212001",
      "validar cédula 1713488185",
      "stock lote CAF-SMOKE-01",
      "¿qué puedo hacer?",
    ].map(q => `<button class="btn ghost" type="button"
        style="font-size:12px">${Bridge.esc(q)}</button>`).join("");
    quick.querySelectorAll("button").forEach(b => {
      b.onclick = () => { input.value = b.textContent; form.requestSubmit(); };
    });
    form.addEventListener("submit", async ev => {
      ev.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      log.insertAdjacentHTML("beforeend", `
        <div class="msg user"><div class="bubble">${Bridge.esc(text)}</div></div>`);
      log.insertAdjacentHTML("beforeend",
        `<div class="msg"><div class="bubble">…</div></div>`);
      log.scrollTop = log.scrollHeight;
      try {
        /* contexto de la vista actual (§5.5) */
        const ctx = { view: this.current(), role: Bridge.session().role };
        const out = await Bridge.api("/api/chat", {
          method: "POST", body: JSON.stringify({ message: text, context: ctx }),
        });
        const last = log.querySelector(".msg:last-child .bubble");
        last.innerHTML = Bridge.esc(out.reply);
        if (out.attribution) {
          last.insertAdjacentHTML("afterend",
            `<div class="attribution">${Bridge.esc(out.attribution)}</div>`);
        }
      } catch (e) {
        const last = log.querySelector(".msg:last-child .bubble");
        last.textContent = "⚠ " + e.message;
      }
      log.scrollTop = log.scrollHeight;
    });
  },

  /* -- helpers -------------------------------------------------------- */
  kpi(label, value, cls) {
    return `<div class="card hover"><p class="micro">${Bridge.esc(label)}</p>
      <p class="kpi-value ${cls === "bad" ? "brand" : ""}"
         >${Bridge.esc(String(value))}</p></div>`;
  },
  labPill(state) {
    const map = { passed: ["ok", "conforme"], failed: ["bad", "reprobado"],
                  none: ["", "sin análisis"] };
    const [cls, label] = map[state] || ["", state || "—"];
    return `<span class="pill ${cls}">${Bridge.esc(label)}</span>`;
  },
  deny(e) {
    if (e.status === 401 || e.status === 403) {
      Bridge.clear(); location.href = "/index.html";
    }
  },
};
