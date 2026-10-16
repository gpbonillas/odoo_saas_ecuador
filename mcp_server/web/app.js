/* SOMATECH-ODOO-BRIDGE — JS de la UI (vanilla, sin framework/build).
   Contrato: token Bearer en sessionStorage; nav derivada del rol
   (deny-by-default: lo que no viene en login.entities no se pinta —
   la UI sólo renderiza, el bridge decide, FR-BR-02/D-09). */
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
        // WIZ-02/FR-BR-07: se muestra la pregunta, se ingresa igual (no bloquea)
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
  views: {
    ops: { title: "Operación", entities: ["lotes"] },
    gestion: { title: "Gestión", entities: ["ciclos", "analisis"] },
    lotes: { title: "Lotes", entities: ["lotes"] },
    chat: { title: "Agente", entities: null },  // chat: cualquier rol autenticado
  },

  init() {
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
    this.renderNav();
    window.addEventListener("hashchange", () => this.route());
    if (!location.hash) location.hash = "#/ops";
    this.route();
  },

  allowed(viewKey) {
    const s = Bridge.session();
    const view = this.views[viewKey];
    if (!view) return false;
    if (!view.entities) return true;              // chat: autenticado basta
    return view.entities.every(e => (s.entities || []).includes(e));
  },

  renderNav() {
    const nav = document.getElementById("nav");
    const items = [
      ["ops", "Operación"], ["gestion", "Gestión"],
      ["lotes", "Lotes"], ["chat", "Agente"],
    ].filter(([k]) => this.allowed(k));
    nav.innerHTML = items.map(([k, label]) =>
      `<button class="btn" data-view="${k}">${label}</button>`).join("");
    nav.querySelectorAll("button").forEach(b => {
      b.onclick = () => { location.hash = "#/" + b.dataset.view; };
    });
  },

  current() { return (location.hash || "#/ops").replace("#/", "").split("/")[0]; },

  route() {
    const view = this.current();
    ["ops", "gestion", "lotes", "lote", "chat"].forEach(v => {
      const el = document.getElementById("view-" + v);
      if (el) el.hidden = true;
    });
    document.querySelectorAll("#nav button").forEach(b =>
      b.setAttribute("aria-current", String(b.dataset.view === view)));
    const id = (location.hash.split("/")[2] || "").trim();
    if (view === "lote" && id) { this.loadLote(id); return; }
    const el = document.getElementById("view-" + view);
    if (el) el.hidden = false;
    if (view === "ops") this.loadOps();
    else if (view === "gestion") this.loadGestion();
    else if (view === "lotes") this.loadLotes();
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
        <table><thead><tr><th>Ciclo</th><th>Cultivo</th><th>Variedad</th>
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
      <th>Cosecha</th><th>Lab</th><th class="num">Stock</th></tr></thead><tbody>
      ${items.map(l => `<tr class="rowlink" data-id="${l.id}">
        <td class="mono">${Bridge.esc(l.name)}</td>
        <td>${Bridge.esc((l.product_id || [])[1] || "")}</td>
        <td>${Bridge.esc((l.l10n_ec_crop_type || [])[1] || "—")}</td>
        <td>${Bridge.esc(l.l10n_ec_variety || "—")}</td>
        <td class="mono">${Bridge.esc(l.l10n_ec_harvest_date || "—")}</td>
        <td>${this.labPill(l.l10n_ec_lab_state)}</td>
        <td class="num">${Number(l.product_qty || 0).toFixed(2)}</td>
      </tr>`).join("")}</tbody></table>`;
  },

  bindRowLinks() {
    document.querySelectorAll("tr.rowlink").forEach(tr => {
      tr.onclick = () => { location.hash = "#/lote/" + tr.dataset.id; };
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
      this.bindRowLinks();
    } catch (e) { this.deny(e); }
  },

  /* -- Chat (agente con atribución) ---------------------------------- */
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
        const out = await Bridge.api("/api/chat", {
          method: "POST", body: JSON.stringify({ message: text }),
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
