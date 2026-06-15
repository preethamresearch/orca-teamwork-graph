// Orca — The Teamwork Graph for AI agents
// Vanilla JS ES module. No build step. Talks to backend at API_BASE.

// API base:
//  - explicit override: window.ORCA_API_BASE (set in index.html)
//  - local dev (frontend on :5500, backend on :8000): point at :8000
//  - hosted single-service (backend serves this page): same-origin ("")
const API_BASE =
  (typeof window !== "undefined" && window.ORCA_API_BASE != null) ? window.ORCA_API_BASE
  : (typeof location !== "undefined" && location.port === "5500") ? "http://127.0.0.1:8000"
  : "";
const TOKEN_KEY = "orca_token";

// ---------------------------------------------------------------------------
// API layer
// ---------------------------------------------------------------------------
const Store = {
  get token() { return localStorage.getItem(TOKEN_KEY); },
  set token(t) { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); },
  user: null,
  workspace: null,
  stats: null,
  objectTypes: null, // {objects, relationships}
};

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && Store.token) headers["X-Oracle-Token"] = Store.token;
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try { const j = await res.json(); msg = j.detail || j.error || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

const API = {
  health: () => api("/health", { auth: false }),
  objectTypes: () => api("/object-types", { auth: false }),
  demo: () => api("/auth/demo", { method: "POST", auth: false }),
  login: (email, name) => api("/auth/login", { method: "POST", auth: false, body: { email, name } }),
  me: () => api("/auth/me"),
  logout: () => api("/auth/logout", { method: "POST" }),
  graph: () => api("/graph"),
  graphStats: () => api("/graph/stats"),
  node: (id) => api("/node/" + encodeURIComponent(id)),
  search: (q) => api("/search?q=" + encodeURIComponent(q)),
  ask: (question) => api("/ask", { method: "POST", body: { question } }),
  sources: () => api("/sources"),
  upload: (title, text) => api("/connectors/upload", { method: "POST", body: { title, text } }),
  github: (repo, token) => api("/connectors/github", { method: "POST", body: { repo, token: token || undefined } }),
  connect: (kind) => api("/connectors/connect", { method: "POST", body: { kind } }),
  mcp: (command, args, name) => api("/connectors/mcp", { method: "POST", body: { command, args, name } }),
  notion: (token, query) => api("/connectors/notion", { method: "POST", body: { token, query } }),
  composioLink: (toolkit) => api("/connectors/composio/link", { method: "POST", body: { toolkit } }),
  composioSync: (toolkit) => api("/connectors/composio/sync", { method: "POST", body: { toolkit } }),
  objects: (kind) => api("/objects?kind=" + encodeURIComponent(kind)),
  createObject: (kind, label, fields) => api("/objects", { method: "POST", body: { kind, label, fields } }),
  updateObject: (id, body) => api("/objects/" + encodeURIComponent(id), { method: "PUT", body }),
  deleteObject: (id) => api("/objects/" + encodeURIComponent(id), { method: "DELETE" }),
  seedSample: () => api("/workspace/seed-sample", { method: "POST" }),
  clearWorkspace: () => api("/workspace/clear", { method: "POST" }),
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
const app = document.getElementById("app");
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const initials = (s) => (s || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();

// ---- Integrations marketing strip (real Composio toolkits: 1,000+) ----
const INTEGRATION_SLUGS = [
  "googledrive", "one_drive", "slack", "gmail", "jira", "notion", "github", "linear",
  "salesforce", "hubspot", "confluence", "asana", "outlook", "share_point", "excel",
  "microsoft_teams", "dropbox", "figma", "zoom", "trello", "clickup", "airtable", "gitlab", "intercom",
];
const logoImg = (s) => `<img class="int-logo" src="https://logos.composio.dev/api/${s}" alt="${s}" loading="lazy" onerror="this.style.visibility='hidden'"/>`;
function integrationsMarquee() {
  const row = INTEGRATION_SLUGS.map(logoImg).join("");
  return `<div class="logo-marquee"><div class="logo-track">${row}${row}</div></div>`;
}

function toast(msg, kind = "") {
  const el = h(`<div class="toast ${kind}">${esc(msg)}</div>`);
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; }, 2600);
  setTimeout(() => el.remove(), 3000);
}

// styled confirm dialog (replaces native confirm())
function confirmDialog(message, { title = "Are you sure?", confirmText = "Confirm", danger = true } = {}) {
  return new Promise((resolve) => {
    const overlay = h(`
      <div class="modal-overlay">
        <div class="modal confirm-modal">
          <div class="confirm-ic ${danger ? "danger" : ""}"><span class="msi">${danger ? "delete" : "help"}</span></div>
          <h2>${esc(title)}</h2>
          <p class="sub">${esc(message)}</p>
          <div class="modal-actions">
            <button class="btn btn-sm btn-ghost" data-no>Cancel</button>
            <button class="btn btn-sm ${danger ? "btn-danger" : "btn-primary"}" data-yes>${esc(confirmText)}</button>
          </div>
        </div>
      </div>`);
    document.body.appendChild(overlay);
    const finish = (v) => { overlay.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => { if (e.key === "Escape") finish(false); if (e.key === "Enter") finish(true); };
    overlay.addEventListener("click", (e) => { if (e.target === overlay) finish(false); });
    overlay.querySelector("[data-no]").addEventListener("click", () => finish(false));
    overlay.querySelector("[data-yes]").addEventListener("click", () => finish(true));
    document.addEventListener("keydown", onKey);
    overlay.querySelector("[data-yes]").focus();
  });
}

function kindMeta(kind) {
  const ot = Store.objectTypes && Store.objectTypes.objects[kind];
  return ot || { display: kind, icon: "•", color: "#9aa6b2", fill: true, fields: [] };
}

// Whether to use near-black text on a light fill color
function isLightColor(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return false;
  const n = parseInt(m[1], 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return (0.299 * r + 0.587 * g + 0.114 * b) > 180;
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
(async function boot() {
  try { Store.objectTypes = await API.objectTypes(); }
  catch (e) { console.warn("object-types failed", e); }

  if (Store.token) {
    try {
      const me = await API.me();
      Store.user = me.user; Store.workspace = me.workspace; Store.stats = me.stats;
      return renderWorkspace();
    } catch { Store.token = null; }
  }
  renderLanding();
})();

// ===========================================================================
// LANDING
// ===========================================================================
function renderLanding() {
  app.innerHTML = "";
  const view = h(`
    <div class="landing">
      <nav class="landing-nav">
        <div class="brand"><span class="logo">${orcaSvg()}</span> <span class="wordmark">Orca</span></div>
        <div class="nav-links">
          <a data-scroll="features">Product</a>
          <a data-scroll="integrations">Integrations</a>
          <a data-scroll="hero">Agents</a>
          <a href="https://github.com/preethamresearch/orca-teamwork-graph" target="_blank" rel="noopener">Docs ↗</a>
        </div>
      </nav>

      <section class="hero" id="hero">
        <div>
          <div class="hero-eyebrow">◈ Built for the Microsoft Agents League · Enterprise Agents</div>
          <h1>The <span class="grad">Teamwork Graph</span><br/>for AI agents.</h1>
          <p class="tagline">Orca turns every signal from your work into one always-current graph — so your agents reason over structure instead of rediscovering it.</p>
          <div class="hero-actions">
            <button class="btn btn-primary" id="msSignin">
              <span class="ms-logo"><i></i><i></i><i></i><i></i></span>
              Sign in with Microsoft
            </button>
            <button class="btn btn-ghost btn-sm" id="blankWs">Use a blank workspace</button>
          </div>
        </div>
        <div class="hero-visual">
          <div class="mini-graph" id="miniGraph"></div>
        </div>
      </section>

      <section class="features" id="features">
        <div class="feature">
          <span class="ic"><span class="msi">hub</span></span>
          <h3>Your work as a living graph</h3>
          <p>People, projects, decisions and dependencies linked into one model that stays in step with how your team actually works.</p>
        </div>
        <div class="feature">
          <span class="ic"><span class="msi">psychology</span></span>
          <h3>Structure agents can reason over</h3>
          <p>Orca hands AI the relationships and ownership behind your work, so answers follow how things connect — not just what a page says.</p>
        </div>
        <div class="feature">
          <span class="ic"><span class="msi">device_hub</span></span>
          <h3>On every surface you work</h3>
          <p>Ask from the web, the agent terminal, or any MCP-compatible client your team already uses.</p>
        </div>
        <div class="feature">
          <span class="ic"><span class="msi">verified</span></span>
          <h3>Grounded, cited, and traceable</h3>
          <p>Every answer traces back to its source page or decision and shows the path it walked — built to refuse rather than guess.</p>
        </div>
      </section>

      <section class="integrations" id="integrations">
        <div class="int-eyebrow">◈ Connect your entire stack</div>
        <h2 class="int-title"><span class="grad">1,000+</span> integrations, one graph</h2>
        <p class="int-sub">Google Drive, Microsoft 365, Slack, Jira, Notion, GitHub, Salesforce and more — connected through open standards like <b>MCP</b>. Every tool your team runs on, unified into context your agents can reason over.</p>
        ${integrationsMarquee()}
      </section>
    </div>
  `);
  app.appendChild(view);
  drawMiniGraph(view.querySelector("#miniGraph"));
  view.querySelectorAll(".nav-links [data-scroll]").forEach((a) => a.addEventListener("click", () => {
    const el = view.querySelector("#" + a.dataset.scroll);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }));

  view.querySelector("#msSignin").addEventListener("click", signInMicrosoft);
  view.querySelector("#blankWs").addEventListener("click", openBlankWorkspaceModal);
}

function orcaSvg() {
  return `<svg viewBox="0 0 24 24" fill="none"><path d="M4 13c0-4 3.5-7 8-7s8 3 8 7c0 1.6-.6 3-1.6 4.1.2 1 .8 1.9.8 1.9s-1.8-.2-2.7-.8A9.4 9.4 0 0 1 12 19c-4.5 0-8-2.7-8-6z" fill="#fff"/><circle cx="9.5" cy="12" r="1.3" fill="#4c9aff"/></svg>`;
}

function drawMiniGraph(host) {
  const nodes = [
    { x: 50, y: 40, label: "◉ Priya", c: "#4c9aff", fill: true },
    { x: 200, y: 30, label: "◆ Checkout v2", c: "#4c9aff", fill: true },
    { x: 110, y: 130, label: "⧉ Payments", c: "#b3bac5", fill: false },
    { x: 245, y: 130, label: "◆ Identity Tokens", c: "#4c9aff", fill: true },
    { x: 40, y: 220, label: "◈ Phased rollout", c: "#a17bff", fill: false },
    { x: 210, y: 235, label: "◉ David Chen", c: "#4c9aff", fill: true },
  ];
  const links = [[0, 2], [0, 1], [1, 3], [1, 2], [1, 4], [3, 5], [2, 5]];
  const svg = `<svg class="mini-svg" viewBox="0 0 320 300">${links
    .map(([a, b], i) => `<line class="mini-link" style="animation-delay:${(i * 0.12).toFixed(2)}s" x1="${nodes[a].x + 30}" y1="${nodes[a].y + 12}" x2="${nodes[b].x + 30}" y2="${nodes[b].y + 12}" stroke="rgba(120,140,180,0.45)" stroke-width="1.4"/>`)
    .join("")}</svg>`;
  const N = nodes.length;
  host.innerHTML = svg + nodes.map((n, i) => {
    const pale = isLightColor(n.c);
    const dIn = (0.4 + i * 0.13).toFixed(2);   // entrance order
    const dSpot = (1 + i).toFixed(2);          // spotlight travels node→node (1s apart)
    const base = n.fill
      ? `left:${n.x}px;top:${n.y}px;background:${n.c};color:${pale ? "#172b4d" : "#fff"};`
      : `left:${n.x}px;top:${n.y}px;background:#ffffff;color:${pale ? "#42526e" : n.c};border:1.5px solid ${pale ? "#c1c7d0" : n.c};`;
    return `<div class="mini-chip" style="${base}--spot-dur:${N}s;animation-delay:${dIn}s, ${dSpot}s">${esc(n.label)}</div>`;
  }).join("");
}

// Microsoft Entra (MSAL) — real sign-in. Configure the Client ID once (stored locally
// or set MSAL_CLIENT_ID). Authority "common" allows any work/school/personal account.
const MSAL_CLIENT_ID = ""; // optionally hard-code; otherwise set via the in-app dialog
const MSAL_AUTHORITY = "https://login.microsoftonline.com/common";
function msalClientId() {
  return localStorage.getItem("orca_msal_client")
    || (typeof window !== "undefined" && window.ORCA_MSAL_CLIENT_ID)
    || MSAL_CLIENT_ID;
}

async function signInMicrosoft() {
  const clientId = msalClientId();
  if (!clientId) { return openMsConfigModal(); }      // only ask if truly unconfigured
  if (!window.msal) { toast("Sign-in is still loading — try again in a second.", "err"); return; }
  const btn = document.getElementById("msSignin");
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Signing in…`;
  try {
    const pca = new msal.PublicClientApplication({
      auth: { clientId, authority: MSAL_AUTHORITY, redirectUri: location.origin + location.pathname },
      cache: { cacheLocation: "localStorage" },
    });
    await pca.initialize();
    const result = await pca.loginPopup({ scopes: ["User.Read"] });
    const acct = result.account;
    const email = acct.username || (acct.idTokenClaims && acct.idTokenClaims.preferred_username) || "user@unknown";
    const name = acct.name || email.split("@")[0];
    const r = await API.login(email, name);          // YOUR own workspace (empty), not the sample
    Store.token = r.token; Store.user = r.user; Store.workspace = r.workspace; Store.stats = r.stats;
    renderWorkspace();
  } catch (e) {
    toast("Microsoft sign-in failed: " + (e.message || e), "err");
    btn.disabled = false; btn.innerHTML = `<span class="ms-logo"><i></i><i></i><i></i><i></i></span> Sign in with Microsoft`;
  }
}

// Shown when no Entra Client ID is configured yet — gives setup steps + a field to paste it.
function openMsConfigModal() {
  const overlay = h(`
    <div class="modal-overlay">
      <div class="modal" style="width:520px">
        <h2>Connect Microsoft sign-in</h2>
        <p class="sub">Real Microsoft sign-in needs a free Entra app registration (one-time, ~5 min).</p>
        <ol class="ms-steps">
          <li>Go to <b>portal.azure.com → Microsoft Entra ID → App registrations → New registration</b>.</li>
          <li>Name it "Orca". Under <b>Redirect URI</b> pick <b>Single-page application (SPA)</b> and enter <code>${esc(location.origin + location.pathname)}</code>.</li>
          <li>Supported accounts: "Accounts in any org directory and personal Microsoft accounts".</li>
          <li>Register, then copy the <b>Application (client) ID</b> and paste it below.</li>
        </ol>
        <div class="field"><label>Application (client) ID</label><input id="msClientId" placeholder="00000000-0000-0000-0000-000000000000" /></div>
        <div class="modal-actions">
          <button class="btn btn-sm btn-ghost" data-close>Cancel</button>
          <button class="btn btn-sm btn-primary" id="msSave">Save & sign in</button>
        </div>
      </div>
    </div>`);
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.addEventListener("click", (e) => { if (e.target === overlay || e.target.dataset.close !== undefined) close(); });
  overlay.querySelector("#msSave").addEventListener("click", () => {
    const id = overlay.querySelector("#msClientId").value.trim();
    if (!/^[0-9a-f-]{30,40}$/i.test(id)) { toast("Enter a valid client ID (GUID)", "err"); return; }
    localStorage.setItem("orca_msal_client", id);
    close(); signInMicrosoft();
  });
}

function openBlankWorkspaceModal() {
  const overlay = h(`
    <div class="modal-overlay">
      <div class="modal">
        <h2>Create a blank workspace</h2>
        <p class="sub">Start empty, then connect a source or paste knowledge to build your graph.</p>
        <div class="field"><label>Name</label><input id="bwName" placeholder="Ada Lovelace" /></div>
        <div class="field"><label>Email</label><input id="bwEmail" type="email" placeholder="you@company.com" /></div>
        <div class="modal-actions">
          <button class="btn btn-sm btn-ghost" data-close>Cancel</button>
          <button class="btn btn-sm btn-primary" id="bwCreate">Create workspace</button>
        </div>
      </div>
    </div>
  `);
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.addEventListener("click", (e) => { if (e.target === overlay || e.target.dataset.close !== undefined) close(); });
  overlay.querySelector("#bwCreate").addEventListener("click", async () => {
    const name = overlay.querySelector("#bwName").value.trim() || "New User";
    const email = overlay.querySelector("#bwEmail").value.trim() || `user${Date.now()}@orca.local`;
    const btn = overlay.querySelector("#bwCreate");
    btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
    try {
      const r = await API.login(email, name);
      Store.token = r.token; Store.user = r.user; Store.workspace = r.workspace; Store.stats = r.stats;
      close(); renderWorkspace();
    } catch (e) { toast("Failed: " + e.message, "err"); btn.disabled = false; btn.textContent = "Create workspace"; }
  });
}

// ===========================================================================
// WORKSPACE
// ===========================================================================
let WS = {
  view: "graph",            // "graph" | "objects"
  cy: null,
  layoutName: null,
  evidenceActive: false,
  sources: [],
  activeKind: "task",
};

function renderWorkspace() {
  app.innerHTML = "";
  const view = h(`
    <div class="workspace">
      <!-- SIDEBAR -->
      <aside class="sidebar">
        <div class="sidebar-head">
          <div class="brand"><span class="logo">${orcaSvg()}</span> Orca</div>
          <div class="ws-card">
            <div class="ws-avatar">${esc(initials(Store.user?.name))}</div>
            <div class="meta">
              <div class="nm">${esc(Store.user?.name || "User")}</div>
              <div class="sub">${esc(Store.workspace?.name || "")}</div>
            </div>
          </div>
        </div>
        <div class="side-section">
          <div class="hdr"><span>Space</span></div>
          <div class="space-row"><span class="msi">workspaces</span><span class="space-row-nm">${esc(Store.workspace?.name || "Workspace")}</span></div>
          <div class="group-sub">Groups</div>
          <div id="groupList"></div>
        </div>
        <div class="side-section">
          <div class="hdr"><span>Sources</span><span id="srcCount"></span></div>
          <div id="sourceList"></div>
        </div>
        <button class="add-source-btn" id="addSource"><span class="msi">add</span> Add source / knowledge</button>
        <div class="sidebar-foot">
          <button class="btn btn-sm btn-ghost" id="logoutBtn" style="width:100%">Sign out</button>
        </div>
      </aside>

      <!-- CENTER -->
      <main class="center" id="center">
        <div class="appbar">
          <div class="appbar-search">
            <span class="msi">search</span>
            <input id="graphSearch" placeholder="Search ${esc(Store.workspace?.name || "your graph")}…" />
          </div>
          <button class="btn btn-primary btn-sm" id="createBtn"><span class="msi">add</span> Create</button>
          <button class="tool-btn" id="refreshBtn" title="Refresh"><span class="msi">refresh</span></button>
          <button class="tool-btn" id="fitBtn" title="Fit to screen"><span class="msi">fit_screen</span></button>
          <button class="tool-btn" id="termBtn" title="Agent terminal"><span class="msi">terminal</span></button>
        </div>
        <div class="spacehdr">
          <div class="space-name"><span class="space-ic"><span class="msi">workspaces</span></span> ${esc(Store.workspace?.name || "Workspace")}</div>
          <div class="tabbar">
            <button data-nav="graph" class="tab active"><span class="msi">hub</span> Graph</button>
            <button data-nav="objects" class="tab"><span class="msi">view_kanban</span> Board</button>
          </div>
        </div>
        <div class="stage">
          <div id="cy"></div>
          <div class="cy-loading" id="cyLoading">Building the graph…</div>
          <div class="graph-legend" id="legend"></div>
          <div class="evidence-bar" id="evidenceBar">
            <span id="evidenceText">Highlighting evidence</span>
            <button id="clearEvidence">Clear</button>
          </div>
          <div class="detail-drawer" id="detailDrawer"></div>
        </div>
      </main>

      <!-- ASK ORCA — floating bottom-right assistant -->
      <aside class="askpanel terminal" id="askPanel">
        <div class="askpanel-head">
          <button class="tdot r" id="termClose" title="Close"></button><button class="tdot y" id="termMin" title="Minimize"></button><button class="tdot g" id="termMax" title="Maximize"></button>
          <div class="hd"><div class="t">orca — agent terminal</div></div>
        </div>
        <div class="ask-body" id="askBody">
          <div class="ask-intro"><span class="tprompt">orca ❯</span> agent terminal · powered by Microsoft Foundry. Ask about owners, dependencies, decisions — Orca traverses the graph and shows its reasoning. Try:</div>
          <div class="chips" id="exampleChips"></div>
        </div>
        <div class="ask-input-bar">
          <span class="tprompt">❯</span>
          <input id="askInput" placeholder="type a question…" />
          <button class="ask-send" id="askSend">⏎</button>
        </div>
      </aside>
      <button class="ask-fab" id="askFab" title="Open agent terminal"><span class="msi">terminal</span><span>Terminal</span></button>
    </div>
  `);
  app.appendChild(view);

  // nav
  view.querySelectorAll("[data-nav]").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.nav)));
  view.querySelector("#logoutBtn").addEventListener("click", doLogout);
  view.querySelector("#addSource").addEventListener("click", openConnectPanel);
  view.querySelector("#fitBtn").addEventListener("click", () => WS.cy && WS.cy.fit(undefined, 60));
  view.querySelector("#refreshBtn").addEventListener("click", () => loadGraph(true));
  view.querySelector("#createBtn").addEventListener("click", () => openNewObjectModal(WS.activeKind || "task"));

  // search
  const search = view.querySelector("#graphSearch");
  search.addEventListener("keydown", (e) => { if (e.key === "Enter") doGraphSearch(search.value.trim()); });

  // ask
  const askInput = view.querySelector("#askInput");
  const doSend = () => { const v = (askInput.value || "").trim(); if (v) sendAsk(v); };
  view.querySelector("#askSend").addEventListener("click", (e) => { e.preventDefault(); doSend(); });
  askInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doSend(); } });

  // example chips
  const examples = [
    "Who do I need to unblock Checkout v2?",
    "What does Checkout v2 depend on?",
    "Who owns Identity Tokens?",
    "How is Priya connected to David Chen?",
    "What decisions affect the Platform Service Mesh?",
  ];
  const chipHost = view.querySelector("#exampleChips");
  examples.forEach((q) => {
    const c = h(`<button class="chip">${esc(q)}</button>`);
    c.addEventListener("click", () => sendAsk(q));
    chipHost.appendChild(c);
  });

  view.querySelector("#clearEvidence").addEventListener("click", clearEvidence);
  loadGroups();

  // floating chat widget open/close
  const panel = view.querySelector("#askPanel");
  const fab = view.querySelector("#askFab");
  const termBtn = view.querySelector("#termBtn");
  const centerEl = view.querySelector("#center");
  const setChat = (open) => {
    panel.classList.toggle("open", open);
    fab.classList.toggle("hidden", open);
    termBtn.classList.toggle("active", open);
    centerEl.classList.toggle("term-open", open); // shrink content so terminal never covers it
    // re-fit the graph into the new visible area
    setTimeout(() => { if (WS.cy) { WS.cy.resize(); WS.cy.fit(undefined, 60); if (WS.cy.zoom() < 0.62) { WS.cy.zoom(0.7); WS.cy.center(); } } }, 240);
  };
  fab.addEventListener("click", () => { setChat(true); askInput.focus(); });
  termBtn.addEventListener("click", () => { const open = !panel.classList.contains("open"); setChat(open); if (open) askInput.focus(); });
  view.querySelector("#termClose").addEventListener("click", () => setChat(false));
  view.querySelector("#termMin").addEventListener("click", () => setChat(false));
  view.querySelector("#termMax").addEventListener("click", () => {
    panel.classList.toggle("maximized");
    centerEl.classList.toggle("term-max", panel.classList.contains("maximized"));
    setTimeout(() => { if (WS.cy) { WS.cy.resize(); WS.cy.fit(undefined, 60); } }, 240);
  });
  setChat(false); // start minimized; open from the header terminal button or the launcher

  loadSources();
  loadGraph();
  buildLegend();
}

function switchView(name) {
  WS.view = name;
  document.querySelectorAll("[data-nav]").forEach((b) => b.classList.toggle("active", b.dataset.nav === name));
  const existing = document.getElementById("objectsView");
  if (existing) existing.remove();
  if (name === "objects") renderObjectsView();
}

async function doLogout() {
  try { await API.logout(); } catch {}
  Store.token = null; Store.user = null; Store.workspace = null;
  renderLanding();
}

// ---------------------------------------------------------------------------
// Groups (teams within the space)
// ---------------------------------------------------------------------------
async function loadGroups() {
  const host = document.getElementById("groupList");
  if (!host) return;
  let teams = [];
  try { teams = (await API.objects("team")).objects || []; } catch { teams = []; }
  if (!teams.length) {
    host.innerHTML = `<div class="group-empty">No groups yet</div>`;
    return;
  }
  host.innerHTML = "";
  teams.forEach((t) => {
    const item = h(`<button class="group-item" data-group="${esc(t.id)}"><span class="msi">groups</span><span class="gn">${esc(t.label)}</span></button>`);
    item.addEventListener("click", () => toggleGroup(t.id, item));
    host.appendChild(item);
  });
}

function setActiveGroup(item) {
  document.querySelectorAll(".group-item.active").forEach((b) => b.classList.remove("active"));
  if (item) item.classList.add("active");
}

// Click a group to focus its cluster; click the same group again to clear.
async function toggleGroup(teamId, item) {
  if (WS.activeGroup === teamId) {        // second click → deselect
    WS.activeGroup = null;
    setActiveGroup(null);
    clearEvidence();
    return;
  }
  WS.activeGroup = teamId;
  setActiveGroup(item);
  try {
    const { neighbors } = await API.node(teamId);
    const ids = [teamId, ...(neighbors || []).map((n) => n.node.id)];
    if (WS.view !== "graph") switchView("graph");
    highlightEvidence(ids);
    if (WS.cy) {
      const sel = WS.cy.collection();
      ids.forEach((id) => { const n = WS.cy.getElementById(id); if (n.length) sel.merge(n); });
      if (sel.length) WS.cy.animate({ fit: { eles: sel, padding: 80 } }, { duration: 400 });
    }
  } catch (e) { toast("Could not focus group: " + e.message, "err"); }
}

// ---------------------------------------------------------------------------
// Sources
// ---------------------------------------------------------------------------
const SOURCE_ICONS = {
  microsoft365: "window", issues: "task_alt", pages: "menu_book", github: "code",
  upload: "upload_file", notion: "description", googledrive: "add_to_drive",
  objective: "flag", object: "category", default: "link",
};

async function loadSources() {
  try {
    const r = await API.sources();
    WS.sources = r.sources || [];
  } catch { WS.sources = []; }
  const host = document.getElementById("sourceList");
  const count = document.getElementById("srcCount");
  if (!host) return;
  count.textContent = WS.sources.length || "";
  if (!WS.sources.length) {
    host.innerHTML = `<div style="padding:10px 8px;font-size:12.5px;color:var(--text-faint)">No sources yet. Add one to build your graph.</div>`;
    return;
  }
  host.innerHTML = "";
  WS.sources.forEach((s) => {
    const ic = SOURCE_ICONS[s.type] || SOURCE_ICONS.default;
    host.appendChild(h(`
      <div class="source-item">
        <div class="source-ic"><span class="msi">${ic}</span></div>
        <div style="flex:1;min-width:0">
          <div class="nm">${esc(s.name)}</div>
          <div class="ty">${esc(s.type)}</div>
        </div>
        <span class="badge ${esc(s.status)}">${esc(s.status)}</span>
      </div>
    `));
  });
}

// ---------------------------------------------------------------------------
// Graph
// ---------------------------------------------------------------------------
function nodeStyleFns() {
  return [
    {
      selector: "node",
      style: {
        "shape": "round-rectangle",
        "width": "label", "height": "label",
        "padding": "11px",
        "text-valign": "center", "text-halign": "center",
        "label": "data(displayLabel)",
        "font-family": "Inter, sans-serif",
        "font-size": "13px",
        "font-weight": 600,
        "color": "data(textColor)",
        "background-color": "data(bg)",
        "border-width": "data(borderW)",
        "border-color": "data(borderColor)",
        "corner-radius": 9,
        "text-wrap": "none",
        "background-opacity": 1,
        "transition-property": "opacity, border-width, border-color",
        "transition-duration": "120ms",
      },
    },
    {
      selector: "edge",
      style: {
        "width": 1.2,
        "line-color": "rgba(160,170,185,0.32)",
        "curve-style": "bezier",
        "target-arrow-shape": "none",
        "opacity": 1,
        "transition-property": "opacity, line-color, width",
        "transition-duration": "120ms",
      },
    },
    { selector: "node.dim", style: { "opacity": 0.12 } },
    { selector: "edge.dim", style: { "opacity": 0.05 } },
    { selector: "node.faded", style: { "opacity": 0.18 } },
    { selector: "edge.faded", style: { "opacity": 0.06 } },
    {
      selector: "node.evidence",
      style: {
        "border-width": 3, "border-color": "#0052cc",
        "shadow-blur": 22, "shadow-color": "#4c9aff", "shadow-opacity": 0.7, "shadow-offset-x": 0, "shadow-offset-y": 0,
        "z-index": 99,
      },
    },
    {
      selector: "node:selected",
      style: { "border-width": 3, "border-color": "#4c9aff", "shadow-blur": 20, "shadow-color": "#4c9aff", "shadow-opacity": 0.8 },
    },
    {
      selector: "node.hl",
      style: { "border-width": 2.5, "border-color": "#9ec7ff", "z-index": 50 },
    },
    { selector: "edge.hl", style: { "line-color": "rgba(120,170,255,0.8)", "width": 2, "opacity": 1 } },
    {
      selector: 'node[kind="space"]',
      style: {
        "font-size": "15px", "font-weight": 800, "padding": "16px",
        "shadow-blur": 26, "shadow-color": "#6366f1", "shadow-opacity": 0.45, "shadow-offset-x": 0, "shadow-offset-y": 0,
        "z-index": 90,
      },
    },
    { selector: 'edge[label="in"]', style: { "line-color": "rgba(99,102,241,0.45)", "width": 1.6 } },
  ];
}

const SPACE_ID = "__space__";

function toCyElements(graph) {
  const els = [];
  // central namespace/workspace node that everything hangs off of
  els.push({
    data: {
      id: SPACE_ID, kind: "space", label: Store.workspace?.name || "Workspace",
      displayLabel: `◳  ${Store.workspace?.name || "Workspace"}`,
      bg: "#6366f1", textColor: "#ffffff", borderW: 0, borderColor: "rgba(0,0,0,0)",
    },
  });
  // connect the hub to top-level groups (teams) — or to projects/all if no teams
  const teams = graph.nodes.filter((n) => n.data.kind === "team");
  const hubTargets = teams.length ? teams
    : graph.nodes.filter((n) => n.data.kind === "project");
  const hubSet = hubTargets.length ? hubTargets : graph.nodes;
  hubSet.forEach((n) => els.push({ data: { id: `${SPACE_ID}->${n.data.id}`, source: SPACE_ID, target: n.data.id, label: "in" } }));

  for (const n of graph.nodes) {
    const d = n.data;
    const meta = kindMeta(d.kind);
    const fill = meta.fill;
    const pale = isLightColor(meta.color); // very light colors (white/grey) need neutral treatment
    let bg, textColor, borderW, borderColor;
    if (fill) {
      bg = meta.color;
      textColor = pale ? "#172b4d" : "#ffffff";
      borderW = pale ? 1 : 0;
      borderColor = pale ? "#c1c7d0" : "rgba(0,0,0,0)";
    } else {
      // outline chip on a light canvas: white fill, colored border + text
      bg = "#ffffff";
      borderW = 1.5;
      borderColor = pale ? "#c1c7d0" : meta.color;
      textColor = pale ? "#42526e" : meta.color;
    }
    els.push({
      data: {
        id: d.id, kind: d.kind, label: d.label,
        displayLabel: `${meta.icon}  ${d.label}`,
        bg, textColor, borderW, borderColor,
      },
    });
  }
  for (const e of graph.edges) {
    const d = e.data;
    if (d.label === "teammate") continue; // too dense — hide per spec
    els.push({ data: { id: d.id, source: d.source, target: d.target, label: d.label } });
  }
  return els;
}

async function loadGraph(isRefresh) {
  const loading = document.getElementById("cyLoading");
  if (loading) { loading.style.display = "grid"; loading.textContent = isRefresh ? "Refreshing…" : "Building the graph…"; }
  let graph;
  try { graph = await API.graph(); }
  catch (e) { if (loading) loading.textContent = "Failed to load graph: " + e.message; return; }

  // remove old empty-state
  const old = document.getElementById("emptyState");
  if (old) old.remove();

  if (!graph.nodes || !graph.nodes.length) {
    if (loading) loading.style.display = "none";
    if (WS.cy) { WS.cy.destroy(); WS.cy = null; }
    return renderEmptyState();
  }

  const els = toCyElements(graph);
  if (WS.cy) WS.cy.destroy();

  WS.cy = cytoscape({
    container: document.getElementById("cy"),
    elements: els,
    style: nodeStyleFns(),
    wheelSensitivity: 0.2,
    minZoom: 0.15, maxZoom: 3,
    boxSelectionEnabled: false,
  });

  runLayout(() => { if (loading) loading.style.display = "none"; });
  wireGraphInteractions();
}

function runLayout(done) {
  const cy = WS.cy;
  let name = "fcose";
  // Register fcose if available
  if (window.cytoscapeFcose && WS.layoutName !== "fcose-registered") {
    try { cytoscape.use(window.cytoscapeFcose); WS.layoutName = "fcose-registered"; }
    catch (e) { /* already registered */ }
  }
  if (!window.cytoscapeFcose) name = "cose";

  const fcoseOpts = {
    name: "fcose",
    quality: "proof",
    randomize: true,
    animate: false,
    nodeSeparation: 220,
    idealEdgeLength: 170,
    nodeRepulsion: 32000,
    gravity: 0.06,
    gravityRange: 3.8,
    packComponents: true,
    tilingPaddingVertical: 40,
    tilingPaddingHorizontal: 40,
    padding: 80,
  };
  const coseOpts = {
    name: "cose",
    animate: false,
    nodeOverlap: 24,
    idealEdgeLength: 130,
    nodeRepulsion: 420000,
    gravity: 60,
    padding: 60,
    componentSpacing: 140,
  };

  let layout;
  try {
    layout = cy.layout(name === "fcose" ? fcoseOpts : coseOpts);
    WS.layoutName = name;
  } catch (e) {
    console.warn("fcose failed, falling back to cose", e);
    layout = cy.layout(coseOpts);
    WS.layoutName = "cose";
  }
  const fitReadable = () => {
    cy.fit(undefined, 70);
    // keep chips legible: don't let fit zoom out below a readable threshold
    if (cy.zoom() < 0.62) { cy.zoom(0.7); cy.center(); }
  };
  layout.one("layoutstop", () => { fitReadable(); done && done(); });
  // safety: in case layoutstop doesn't fire
  setTimeout(() => { try { fitReadable(); } catch {} done && done(); }, 2500);
  layout.run();
}

function wireGraphInteractions() {
  const cy = WS.cy;
  cy.on("mouseover", "node", (e) => {
    if (WS.evidenceActive) return;
    const n = e.target;
    const nh = n.closedNeighborhood();
    cy.elements().addClass("faded");
    nh.removeClass("faded");
    n.addClass("hl");
    nh.edges().addClass("hl").removeClass("faded");
  });
  cy.on("mouseout", "node", () => {
    if (WS.evidenceActive) return;
    cy.elements().removeClass("faded hl");
  });
  cy.on("tap", "node", (e) => {
    const id = e.target.id();
    cy.animate({ center: { eles: e.target }, duration: 350, easing: "ease-out" });
    if (id === SPACE_ID) { closeNodeDetail(); return; } // hub node has no detail record
    openNodeDetail(id);
  });
  cy.on("tap", (e) => { if (e.target === cy) closeNodeDetail(); });
}

function buildLegend() {
  const host = document.getElementById("legend");
  if (!host || !Store.objectTypes) return;
  const wanted = ["person", "team", "project", "goal", "task", "bug", "decision", "page"];
  host.innerHTML = wanted.map((k) => {
    const m = kindMeta(k);
    const sw = m.fill ? `background:${m.color}` : `background:#1c2128;border:1.5px solid ${m.color}`;
    return `<span class="lg"><span class="sw" style="${sw}"></span>${esc(m.display)}</span>`;
  }).join("");
}

function renderEmptyState() {
  const center = document.querySelector(".stage") || document.getElementById("center");
  if (document.getElementById("emptyState")) return;
  const first = (Store.user?.name || "there").split(/\s+/)[0];
  const el = h(`
    <div class="empty-state onboarding" id="emptyState">
      <div class="big"><span class="msi">hub</span></div>
      <h2>Welcome, ${esc(first)} 👋</h2>
      <p>Let's build your Teamwork Graph. Connect a source or paste some knowledge — Orca extracts the people, projects, decisions and dependencies automatically.</p>
      <div class="onb-steps">
        <div class="onb-step done"><span class="msi">check_circle</span><div><b>Signed in</b><span>Your workspace is ready</span></div></div>
        <div class="onb-step"><span class="msi">cloud_upload</span><div><b>Connect or upload</b><span>GitHub, or paste your docs/notes</span></div></div>
        <div class="onb-step"><span class="msi">terminal</span><div><b>Ask the agent</b><span>Reason over your graph in the terminal</span></div></div>
      </div>
      <div class="row">
        <button class="btn btn-primary" id="esAddSource"><span class="msi">add</span> Add source / knowledge</button>
        <button class="btn" id="esLoadSample">Or load sample data</button>
      </div>
    </div>
  `);
  center.appendChild(el);
  el.querySelector("#esAddSource").addEventListener("click", openConnectPanel);
  el.querySelector("#esLoadSample").addEventListener("click", async () => {
    const b = el.querySelector("#esLoadSample");
    b.disabled = true; b.innerHTML = `<span class="spinner"></span> Loading…`;
    try { await API.seedSample(); await loadSources(); await loadGraph(true); toast("Contoso sample loaded", "ok"); }
    catch (e) { toast("Failed: " + e.message, "err"); b.disabled = false; b.textContent = "Load Contoso sample"; }
  });
}

// ---------------------------------------------------------------------------
// Graph search
// ---------------------------------------------------------------------------
async function doGraphSearch(q) {
  if (!q || !WS.cy) return;
  try {
    const r = await API.search(q);
    const first = (r.results || [])[0];
    if (!first) { toast("No matches for “" + q + "”", "err"); return; }
    const node = WS.cy.getElementById(first.id);
    if (node && node.nonempty()) {
      WS.cy.elements().removeClass("faded hl");
      WS.cy.animate({ center: { eles: node }, zoom: 1.4, duration: 450, easing: "ease-out" });
      node.flashClass ? node.flashClass("hl", 1500) : node.addClass("hl");
      setTimeout(() => node.removeClass("hl"), 1600);
      openNodeDetail(first.id);
    } else { toast("Found “" + first.label + "” but not in current graph", "err"); }
  } catch (e) { toast("Search failed: " + e.message, "err"); }
}

// ---------------------------------------------------------------------------
// Node detail drawer
// ---------------------------------------------------------------------------
async function openNodeDetail(id) {
  const drawer = document.getElementById("detailDrawer");
  if (!drawer) return;
  drawer.classList.add("show");
  drawer.innerHTML = `<div style="padding:24px;color:var(--text-faint);font-size:13px">Loading…</div>`;
  let data;
  try { data = await API.node(id); }
  catch (e) { drawer.innerHTML = `<div style="padding:24px;color:var(--red)">Failed: ${esc(e.message)}</div>`; return; }

  const node = data.node;
  const meta = kindMeta(node.kind);
  const chipStyle = meta.fill
    ? `background:${meta.color};color:${isLightColor(meta.color) ? "#0d1117" : "#fff"}`
    : `background:#1c2128;color:${meta.color};border:1px solid ${meta.color}`;

  const skip = new Set(["id", "kind", "label"]);
  const attrs = Object.entries(node).filter(([k, v]) => !skip.has(k) && v != null && v !== "");
  const attrsHtml = attrs.length
    ? attrs.map(([k, v]) => `<div class="attr"><span class="k">${esc(k.replace(/_/g, " "))}</span><span class="v">${esc(resolveRef(v))}</span></div>`).join("")
    : `<div style="font-size:12px;color:var(--text-faint);padding:8px 0">No additional attributes.</div>`;

  const neighbors = data.neighbors || [];
  const nbHtml = neighbors.length
    ? neighbors.map((nb) => {
        const m = kindMeta(nb.node.kind);
        const ic = m.fill ? `background:${m.color};color:${isLightColor(m.color) ? "#0d1117" : "#fff"}` : `background:#1c2128;color:${m.color};border:1px solid ${m.color}`;
        return `<div class="neighbor" data-id="${esc(nb.node.id)}">
          <div class="ic" style="${ic}">${m.icon}</div>
          <div style="flex:1;min-width:0">
            <div class="nb-nm">${esc(nb.node.label)}</div>
            <div class="nb-rel">${esc(nb.phrase || nb.edge)}</div>
          </div>
        </div>`;
      }).join("")
    : `<div style="font-size:12px;color:var(--text-faint);padding:8px 0">No connections.</div>`;

  drawer.innerHTML = `
    <button class="detail-close" id="dClose">×</button>
    <div class="detail-head">
      <span class="kind-chip" style="${chipStyle}">${meta.icon} ${esc(meta.display)}</span>
      <div class="nm">${esc(node.label)}</div>
    </div>
    <div class="detail-body">
      <div class="section-label">Attributes</div>
      ${attrsHtml}
      <div class="section-label" style="margin-top:18px">Connections · ${neighbors.length}</div>
      ${nbHtml}
    </div>
  `;
  drawer.querySelector("#dClose").addEventListener("click", closeNodeDetail);
  drawer.querySelectorAll(".neighbor").forEach((nbEl) => {
    nbEl.addEventListener("click", () => {
      const nid = nbEl.dataset.id;
      const cyNode = WS.cy && WS.cy.getElementById(nid);
      if (cyNode && cyNode.nonempty()) { cyNode.select(); WS.cy.animate({ center: { eles: cyNode }, duration: 350 }); }
      openNodeDetail(nid);
    });
  });
}

// resolve "team_payments" style refs to a label if we have it in the graph
function resolveRef(v) {
  if (typeof v === "string" && WS.cy) {
    const n = WS.cy.getElementById(v);
    if (n && n.nonempty()) return n.data("label");
  }
  return v;
}

function closeNodeDetail() {
  const d = document.getElementById("detailDrawer");
  if (d) d.classList.remove("show");
  if (WS.cy && !WS.evidenceActive) WS.cy.elements().unselect();
}

// ---------------------------------------------------------------------------
// Ask Orca
// ---------------------------------------------------------------------------
async function sendAsk(question) {
  if (!question) return;
  const input = document.getElementById("askInput");
  if (input) input.value = "";
  const body = document.getElementById("askBody");

  // remove intro/chips on first ask
  const intro = body.querySelector(".ask-intro"); if (intro) intro.remove();
  const chips = body.querySelector("#exampleChips"); if (chips) chips.remove();

  const block = h(`
    <div class="qa">
      <div class="q"><span class="tprompt">orca ❯</span><div class="txt">${esc(question)}</div></div>
      <div class="answer-card"><div class="thinking"><span></span><span></span><span></span></div></div>
    </div>
  `);
  body.appendChild(block);
  body.scrollTop = body.scrollHeight;

  let r;
  try { r = await API.ask(question); }
  catch (e) {
    block.querySelector(".answer-card").innerHTML = `<div style="color:var(--red);font-size:13px">Failed: ${esc(e.message)}</div>`;
    return;
  }
  renderAnswer(block.querySelector(".answer-card"), r);
  body.scrollTop = body.scrollHeight;
  if (r.graph_evidence && r.graph_evidence.nodes && r.graph_evidence.nodes.length) {
    highlightEvidence(r.graph_evidence.nodes);
  }
}

function renderAnswer(card, r) {
  card.classList.toggle("refused", !!r.refused);
  const conf = Math.round((r.confidence || 0) * 100);
  const md = window.marked ? window.marked.parse(r.answer || "") : esc(r.answer || "");

  const trace = (r.reasoning_trace || []).map((s) => `<div class="step"><div class="body">${inlineMd(s)}</div></div>`).join("");
  const citations = (r.citations || []).map((c) => `
    <div class="citation">
      <div class="top"><span class="n">${esc(c.n)}</span><span class="cl">${esc(c.label)}</span></div>
      <div class="src">${esc(c.source)}${c.score != null ? " · " + Math.round(c.score * 100) + "%" : ""}</div>
      <div class="ex">${esc(c.excerpt || "")}</div>
    </div>`).join("");

  let workiq = "";
  const wq = r.work_iq;
  if (wq && (wq.user || (wq.signals && wq.signals.length))) {
    const sigIcons = { teams_message: "forum", meeting: "event", email: "mail", default: "circle" };
    const signals = (wq.signals || []).map((s) => `
      <div class="signal"><span class="si"><span class="msi">${sigIcons[s.type] || sigIcons.default}</span></span>
      <div class="sx"><b>${esc(s.title || s.subject || s.channel || s.type)}</b><br/>${esc(s.snippet || "")}</div></div>`).join("");
    workiq = `
      <div class="section-label"><span class="msi">bolt</span> Work IQ signals</div>
      <div class="workiq">
        ${wq.user ? `<div class="who">${esc(wq.user.displayName || "")}</div><div class="role">${esc(wq.user.jobTitle || "")}${wq.user.department ? " · " + esc(wq.user.department) : ""}</div>` : ""}
        ${signals}
      </div>`;
  }

  const followups = (r.suggested_questions || []);

  card.innerHTML = `
    ${r.refused ? `<div class="refused-tag"><span class="msi">block</span> Refused</div>` : ""}
    <div class="confidence">
      <span class="label">Confidence</span>
      <div class="track"><div class="fill" style="width:0%"></div></div>
      <span class="pct">${conf}%</span>
    </div>
    <div class="md">${md}</div>
    ${trace ? `<div class="section-label"><span class="msi">route</span> Reasoning trace</div><div class="trace">${trace}</div>` : ""}
    ${citations ? `<div class="section-label"><span class="msi">description</span> Citations</div>${citations}` : ""}
    ${workiq}
    ${followups.length ? `<div class="section-label"><span class="msi">subdirectory_arrow_right</span> Related</div><div class="followups"></div>` : ""}
  `;
  // wire follow-up chips
  if (followups.length) {
    const host = card.querySelector(".followups");
    followups.forEach((q) => {
      const c = h(`<button class="chip followup">${esc(q)}</button>`);
      c.addEventListener("click", () => sendAsk(q));
      host.appendChild(c);
    });
  }
  // animate confidence
  requestAnimationFrame(() => { const f = card.querySelector(".confidence .fill"); if (f) f.style.width = conf + "%"; });
}

// minimal inline markdown for trace lines (**bold** + `code`)
function inlineMd(s) {
  return esc(s)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function highlightEvidence(ids) {
  if (!WS.cy) return;
  WS.evidenceActive = true;
  const cy = WS.cy;
  cy.elements().removeClass("evidence hl faded");
  cy.elements().addClass("dim");
  let found = 0;
  ids.forEach((id) => {
    const n = cy.getElementById(id);
    if (n && n.nonempty()) { n.removeClass("dim").addClass("evidence"); found++; }
  });
  // un-dim edges between evidence nodes
  const evNodes = cy.nodes(".evidence");
  evNodes.connectedEdges().filter((e) => e.source().hasClass("evidence") && e.target().hasClass("evidence")).removeClass("dim");
  if (found) {
    cy.animate({ fit: { eles: evNodes, padding: 90 }, duration: 600, easing: "ease-out" });
  }
  const bar = document.getElementById("evidenceBar");
  if (bar) { bar.classList.add("show"); document.getElementById("evidenceText").textContent = `Showing ${found} evidence node${found === 1 ? "" : "s"}`; }
}

function clearEvidence() {
  WS.evidenceActive = false;
  WS.activeGroup = null;
  setActiveGroup(null);
  if (WS.cy) { WS.cy.elements().removeClass("evidence dim hl faded"); WS.cy.fit(undefined, 60); }
  const bar = document.getElementById("evidenceBar");
  if (bar) bar.classList.remove("show");
}

// ===========================================================================
// CONNECT PANEL (modal)
// ===========================================================================
function openConnectPanel() {
  const overlay = h(`
    <div class="modal-overlay">
      <div class="modal" style="width:560px">
        <h2>Add source / knowledge</h2>
        <p class="sub">Connect a tool or paste knowledge. Orca extracts objects and links into your graph.</p>
        <div class="int-banner">
          <div class="int-banner-text"><b>1,000+ integrations</b> · via MCP &amp; open connectors</div>
          ${integrationsMarquee()}
        </div>

        <div class="connector-grid">
          <div class="connector-card full">
            <div class="ch"><div class="ci"><span class="msi">upload_file</span></div><div><div class="cn">Upload / paste knowledge</div><div class="cd">Plain text, notes, docs — Orca extracts entities</div></div></div>
            <div class="field"><input id="upTitle" placeholder="Title (e.g. Q3 planning notes)" /></div>
            <div class="field"><textarea id="upText" placeholder="Paste text here…"></textarea></div>
            <button class="btn btn-sm btn-primary" id="upBtn">Extract into graph</button>
            <div class="connect-result" id="upRes"></div>
          </div>

          <div class="connector-card full">
            <div class="ch"><div class="ci"><span class="msi">code</span></div><div><div class="cn">GitHub</div><div class="cd">Import a repo's people & project</div></div></div>
            <div class="field"><input id="ghRepo" placeholder="owner/name (e.g. microsoft/vscode)" /></div>
            <div class="field"><input id="ghToken" placeholder="Personal access token (optional)" /></div>
            <button class="btn btn-sm btn-primary" id="ghBtn">Connect repo</button>
            <div class="connect-result" id="ghRes"></div>
          </div>

          <div class="connector-card full">
            <div class="ch"><div class="ci"><span class="msi">cable</span></div><div><div class="cn">MCP server</div><div class="cd">Ingest from any MCP server — filesystem, GitHub, Notion… (open standard)</div></div></div>
            <div class="field"><input id="mcpCmd" placeholder="Launch command (leave blank for the bundled demo server)" /></div>
            <button class="btn btn-sm btn-primary" id="mcpBtn">Connect via MCP</button>
            <div class="connect-result" id="mcpRes"></div>
          </div>

          <div class="connector-card full">
            <div class="ch"><div class="ci"><span class="msi">description</span></div><div><div class="cn">Notion</div><div class="cd">Pull your Notion pages into the graph (integration token)</div></div></div>
            <div class="field"><input id="nzToken" placeholder="Notion integration token (ntn_… / secret_…)" /></div>
            <div class="field"><input id="nzQuery" placeholder="Filter pages by keyword (optional)" /></div>
            <button class="btn btn-sm btn-primary" id="nzBtn">Connect Notion</button>
            <div class="connect-result" id="nzRes"></div>
          </div>

          <div class="connector-card">
            <div class="ch"><div class="ci"><span class="msi">window</span></div><div><div class="cn">Microsoft 365</div><div class="cd">OneDrive via Composio OAuth</div></div></div>
            <div class="cmp-row"><button class="btn btn-sm" data-cmp-link="one_drive" style="flex:1">Connect</button><button class="btn btn-sm btn-primary" data-cmp-sync="one_drive" style="flex:1">Sync</button></div>
            <div class="connect-result" data-cmp-res="one_drive"></div>
          </div>
          <div class="connector-card">
            <div class="ch"><div class="ci"><span class="msi">add_to_drive</span></div><div><div class="cn">Google Drive</div><div class="cd">via Composio OAuth</div></div></div>
            <div class="cmp-row"><button class="btn btn-sm" data-cmp-link="googledrive" style="flex:1">Connect</button><button class="btn btn-sm btn-primary" data-cmp-sync="googledrive" style="flex:1">Sync</button></div>
            <div class="connect-result" data-cmp-res="googledrive"></div>
          </div>
          <div class="connector-card">
            <div class="ch"><div class="ci"><span class="msi">dataset</span></div><div><div class="cn">Contoso sample</div></div></div>
            <button class="btn btn-sm btn-primary" id="seedBtn" style="width:100%">Load sample</button>
          </div>
        </div>

        <div class="modal-actions" style="margin-top:18px">
          <button class="btn btn-sm btn-ghost" data-close>Close</button>
        </div>
      </div>
    </div>
  `);
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.addEventListener("click", (e) => { if (e.target === overlay || e.target.dataset.close !== undefined) close(); });

  // Upload
  overlay.querySelector("#upBtn").addEventListener("click", async () => {
    const title = overlay.querySelector("#upTitle").value.trim() || "Pasted knowledge";
    const text = overlay.querySelector("#upText").value.trim();
    const res = overlay.querySelector("#upRes");
    if (!text) { res.className = "connect-result err"; res.textContent = "Paste some text first."; return; }
    const b = overlay.querySelector("#upBtn"); b.disabled = true; b.innerHTML = `<span class="spinner"></span> Extracting…`;
    try {
      const r = await API.upload(title, text);
      res.className = "connect-result";
      res.textContent = `✓ Extracted ${r.extracted_nodes} objects, ${r.extracted_edges} links.`;
      await refreshAfterConnect();
    } catch (e) { res.className = "connect-result err"; res.textContent = "Failed: " + e.message; }
    b.disabled = false; b.textContent = "Extract into graph";
  });

  // GitHub
  overlay.querySelector("#ghBtn").addEventListener("click", async () => {
    const repo = overlay.querySelector("#ghRepo").value.trim();
    const token = overlay.querySelector("#ghToken").value.trim();
    const res = overlay.querySelector("#ghRes");
    if (!repo.includes("/")) { res.className = "connect-result err"; res.textContent = "Use owner/name format."; return; }
    const b = overlay.querySelector("#ghBtn"); b.disabled = true; b.innerHTML = `<span class="spinner"></span> Connecting…`;
    try {
      const r = await API.github(repo, token);
      res.className = "connect-result";
      res.textContent = `✓ Imported ${r.repo} — ${(r.people || []).length} people.`;
      await refreshAfterConnect();
    } catch (e) { res.className = "connect-result err"; res.textContent = "Failed: " + e.message; }
    b.disabled = false; b.textContent = "Connect repo";
  });

  // Composio (Drive / M365) — real OAuth: Connect opens consent, Sync ingests
  overlay.querySelectorAll("[data-cmp-link]").forEach((b) => b.addEventListener("click", async () => {
    const tk = b.dataset.cmpLink; const res = overlay.querySelector(`[data-cmp-res="${tk}"]`);
    res.className = "connect-result"; res.textContent = "Opening consent…";
    try {
      const r = await API.composioLink(tk);
      if (r.redirect_url) { window.open(r.redirect_url, "_blank", "noopener"); res.textContent = "↗ Authorize in the new tab, then click Sync."; }
      else { res.className = "connect-result err"; res.textContent = "No consent link returned."; }
    } catch (e) { res.className = "connect-result err"; res.textContent = "Failed: " + e.message; }
  }));
  overlay.querySelectorAll("[data-cmp-sync]").forEach((b) => b.addEventListener("click", async () => {
    const tk = b.dataset.cmpSync; const res = overlay.querySelector(`[data-cmp-res="${tk}"]`);
    b.disabled = true; b.innerHTML = `<span class="spinner"></span>`;
    try {
      const r = await API.composioSync(tk);
      res.className = "connect-result"; res.textContent = `✓ ${r.name}: ${r.files} files → ${r.extracted_nodes} objects.`;
      await refreshAfterConnect();
    } catch (e) { res.className = "connect-result err"; res.textContent = "Failed: " + e.message + " — click Connect & authorize first."; }
    b.disabled = false; b.textContent = "Sync";
  }));

  // Notion connector — real token-based ingestion
  overlay.querySelector("#nzBtn").addEventListener("click", async () => {
    const token = overlay.querySelector("#nzToken").value.trim();
    const query = overlay.querySelector("#nzQuery").value.trim();
    const res = overlay.querySelector("#nzRes");
    if (!token) { res.className = "connect-result err"; res.textContent = "Paste your Notion integration token."; return; }
    const b = overlay.querySelector("#nzBtn"); b.disabled = true; b.innerHTML = `<span class="spinner"></span> Connecting…`;
    try {
      const r = await API.notion(token, query);
      res.className = "connect-result"; res.textContent = `✓ Imported ${r.pages} Notion page(s).`;
      await refreshAfterConnect();
    } catch (e) { res.className = "connect-result err"; res.textContent = "Failed: " + e.message; }
    b.disabled = false; b.textContent = "Connect Notion";
  });

  // MCP server connector — Orca acts as an MCP client and ingests the server's resources
  overlay.querySelector("#mcpBtn").addEventListener("click", async () => {
    const raw = overlay.querySelector("#mcpCmd").value.trim();
    const res = overlay.querySelector("#mcpRes");
    const parts = raw ? raw.split(/\s+/) : [];
    const command = parts[0] || null;        // blank → backend uses the bundled demo server
    const args = parts.slice(1);
    const b = overlay.querySelector("#mcpBtn"); b.disabled = true; b.innerHTML = `<span class="spinner"></span> Connecting…`;
    try {
      const r = await API.mcp(command, args, null);
      res.className = "connect-result";
      res.textContent = `✓ ${r.server}: ${r.documents} docs, ${r.extracted_nodes} objects, ${r.extracted_edges} links.`;
      await refreshAfterConnect();
    } catch (e) { res.className = "connect-result err"; res.textContent = "Failed: " + e.message; }
    b.disabled = false; b.textContent = "Connect via MCP";
  });

  // OAuth-soon connectors — these do NOT inject any data; OAuth via MCP connectors is coming soon
  overlay.querySelectorAll("[data-connect]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const kind = btn.dataset.connect;
      const res = overlay.querySelector(`[data-res="${kind}"]`);
      res.className = "connect-result soon-note";
      res.textContent = "OAuth connection coming soon (via MCP connectors). For now, use Upload or GitHub above.";
    });
  });

  // Seed sample
  overlay.querySelector("#seedBtn").addEventListener("click", async () => {
    const b = overlay.querySelector("#seedBtn"); b.disabled = true; b.innerHTML = `<span class="spinner"></span> Loading…`;
    try { await API.seedSample(); await refreshAfterConnect(); toast("Contoso sample loaded", "ok"); close(); }
    catch (e) { toast("Failed: " + e.message, "err"); b.disabled = false; b.textContent = "Load sample"; }
  });
}

async function refreshAfterConnect() {
  await loadSources();
  if (WS.view === "graph") await loadGraph(true);
  if (WS.view === "objects") renderObjectsView();
}

// ===========================================================================
// OBJECTS VIEW
// ===========================================================================
const OBJECT_KINDS = ["task", "bug", "page", "goal", "project", "decision"];

function renderObjectsView() {
  const center = document.querySelector(".stage") || document.getElementById("center");
  let view = document.getElementById("objectsView");
  if (view) view.remove();
  view = h(`
    <div class="objects-view" id="objectsView">
      <div class="objects-head">
        <h2>Objects</h2>
        <p>Work-management view of everything in your graph. Create and delete — it reflects in the graph instantly.</p>
        <div class="obj-tabs" id="objTabs"></div>
      </div>
      <div class="objects-body" id="objBody"></div>
    </div>
  `);
  center.appendChild(view);

  const tabs = view.querySelector("#objTabs");
  OBJECT_KINDS.forEach((k) => {
    const m = kindMeta(k);
    const t = h(`<button class="obj-tab ${k === WS.activeKind ? "active" : ""}" data-kind="${k}">${m.icon} ${esc(m.display)}</button>`);
    t.addEventListener("click", () => { WS.activeKind = k; renderObjectsView(); });
    tabs.appendChild(t);
  });

  loadObjects(WS.activeKind);
}

async function loadObjects(kind) {
  const body = document.getElementById("objBody");
  if (!body) return;
  body.innerHTML = `<div style="color:var(--text-faint);font-size:13px">Loading ${kind}s…</div>`;
  let objects = [];
  try { const r = await API.objects(kind); objects = r.objects || []; }
  catch (e) { body.innerHTML = `<div style="color:var(--red)">Failed: ${esc(e.message)}</div>`; return; }

  const meta = kindMeta(kind);
  const hasStatus = (meta.fields || []).includes("status");

  const toolbar = `
    <div class="obj-toolbar">
      <div style="font-size:13px;color:var(--text-dim)">${objects.length} ${esc(meta.display)}${objects.length === 1 ? "" : "s"}</div>
      <button class="btn btn-sm btn-primary" id="newObjBtn">＋ New ${esc(meta.display)}</button>
    </div>`;

  if (hasStatus) {
    body.innerHTML = toolbar + renderBoard(kind, meta, objects);
  } else {
    const fieldCols = (meta.fields || []).slice(0, 4);
    const rows = objects.map((o) => {
      const cells = fieldCols.map((f) => `<td>${esc(formatAttr(o.attrs && o.attrs[f]))}</td>`).join("");
      return `<tr><td class="lbl">${meta.icon} ${esc(o.label)}</td>${cells}
        <td style="text-align:right"><button class="del-btn" data-del="${esc(o.id)}" title="Delete">🗑</button></td></tr>`;
    }).join("");
    body.innerHTML = toolbar + `
      <table class="obj-table">
        <thead><tr><th>Name</th>${fieldCols.map((f) => `<th>${esc(f.replace(/_/g, " "))}</th>`).join("")}<th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="${fieldCols.length + 2}" style="color:var(--text-faint);padding:20px;text-align:center">No ${esc(meta.display.toLowerCase())}s yet. Create one.</td></tr>`}</tbody>
      </table>`;
  }

  body.querySelector("#newObjBtn").addEventListener("click", () => openNewObjectModal(kind));
  body.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!(await confirmDialog("This permanently removes the object and its links from your graph.", { title: "Delete object?", confirmText: "Delete", danger: true }))) return;
    try { await API.deleteObject(b.dataset.del); toast("Deleted", "ok"); loadObjects(kind); }
    catch (e) { toast("Delete failed: " + e.message, "err"); }
  }));
  if (hasStatus) wireBoardDnD(body, kind);
}

// board columns
const BOARD_COLUMNS = [
  { key: "todo", label: "To Do", match: ["todo", "backlog", "open", "proposed", "new", ""] },
  { key: "inprogress", label: "In Progress", match: ["in_progress", "in progress", "doing", "active", "wip"] },
  { key: "inreview", label: "In Review", match: ["in_review", "review", "qa", "testing"] },
  { key: "done", label: "Done", match: ["done", "closed", "resolved", "approved", "shipped", "complete"] },
];

function columnFor(status) {
  const s = String(status || "").toLowerCase().trim();
  for (const col of BOARD_COLUMNS) if (col.match.includes(s)) return col.key;
  return "todo";
}

// Validated value sets — statuses are per kind so they map cleanly to board columns
const STATUS_BY_KIND = {
  task: ["todo", "in_progress", "in_review", "done"],
  bug: ["open", "in_progress", "in_review", "closed"],
  project: ["planned", "in_progress", "on_hold", "done"],
  decision: ["proposed", "approved", "rejected"],
  goal: ["on_track", "at_risk", "done"],
  request: ["open", "in_progress", "done"],
  sprint: ["planned", "active", "done"],
  release: ["planned", "released"],
};
const FIELD_OPTIONS = { priority: ["low", "medium", "high"], severity: ["low", "medium", "high", "critical"] };
function statusOptions(kind) { return STATUS_BY_KIND[kind] || ["todo", "in_progress", "done"]; }
function optionsFor(kind, field) { return field === "status" ? statusOptions(kind) : (FIELD_OPTIONS[field] || null); }
// representative status to apply when a card is dropped into a column
function statusForColumn(kind, colKey) {
  const opts = statusOptions(kind);
  return opts.find((s) => columnFor(s) === colKey) || opts[0];
}
const prettyVal = (v) => String(v).replace(/_/g, " ");

// normalize a stored status to one of the kind's defined options
function normStatus(kind, raw) {
  const opts = statusOptions(kind);
  const s = String(raw || "").toLowerCase().trim().replace(/\s+/g, "_");
  return opts.includes(s) ? s : opts[0];
}

function renderBoard(kind, meta, objects) {
  // columns are this object type's OWN statuses, so every column is a valid drop target
  const statuses = statusOptions(kind);
  const buckets = {};
  statuses.forEach((s) => (buckets[s] = []));
  objects.forEach((o) => buckets[normStatus(kind, (o.attrs || {}).status)].push(o));

  const cols = statuses.map((s) => {
    const cards = buckets[s].map((o) => {
      const a = o.attrs || {};
      const badges = [];
      if (a.priority) badges.push(`<span class="kbadge pri-${esc(a.priority)}">${esc(a.priority)}</span>`);
      if (a.severity) badges.push(`<span class="kbadge sev-${esc(a.severity)}">${esc(a.severity)}</span>`);
      const key = (kind === "bug" ? "BUG-" : kind.slice(0, 4).toUpperCase() + "-") + o.id.slice(-4).toUpperCase();
      return `<div class="kcard" draggable="true" data-card-id="${esc(o.id)}">
        <div class="kcard-title">${meta.icon} ${esc(o.label)}</div>
        <div class="kcard-meta">
          <span class="kkey">${esc(key)}</span>
          ${badges.join("")}
          ${a.assignee ? `<span class="kassignee" title="${esc(a.assignee)}">${esc(initials(a.assignee))}</span>` : ""}
          <button class="del-btn" data-del="${esc(o.id)}" title="Delete"><span class="msi">delete</span></button>
        </div>
      </div>`;
    }).join("");
    return `<div class="kcol" data-col="${esc(s)}">
      <div class="kcol-head"><span>${esc(prettyVal(s))}</span><span class="kcount">${buckets[s].length}</span></div>
      <div class="kcol-body" data-col="${esc(s)}">${cards || `<div class="kempty">Drop here</div>`}</div>
    </div>`;
  }).join("");
  return `<div class="kboard">${cols}</div>`;
}

// drag a card between columns → updates its status (validated per kind)
function wireBoardDnD(body, kind) {
  let dragId = null;
  body.querySelectorAll(".kcard").forEach((c) => {
    c.addEventListener("dragstart", (e) => { dragId = c.dataset.cardId; c.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; });
    c.addEventListener("dragend", () => { dragId = null; c.classList.remove("dragging"); });
  });
  body.querySelectorAll(".kcol-body").forEach((col) => {
    col.addEventListener("dragover", (e) => { e.preventDefault(); col.classList.add("drop-over"); });
    col.addEventListener("dragleave", () => col.classList.remove("drop-over"));
    col.addEventListener("drop", async (e) => {
      e.preventDefault(); col.classList.remove("drop-over");
      if (!dragId) return;
      const newStatus = col.dataset.col;  // column IS the exact status for this kind
      try {
        await API.updateObject(dragId, { fields: { status: newStatus } });
        loadObjects(kind);
        if (WS.cy) loadGraph(true);
      } catch (err) { toast("Move failed: " + err.message, "err"); }
    });
  });
}

function formatAttr(v) {
  if (v == null || v === "") return "—";
  return String(v);
}

function openNewObjectModal(kind) {
  const meta = kindMeta(kind);
  const fields = meta.fields || [];
  const overlay = h(`
    <div class="modal-overlay">
      <div class="modal">
        <h2>New ${esc(meta.display)}</h2>
        <p class="sub">Adds a ${esc(meta.display.toLowerCase())} object to your graph.</p>
        <div class="field"><label>Label</label><input id="noLabel" placeholder="${esc(meta.display)} name" /></div>
        ${fields.map((f) => {
          const opts = optionsFor(kind, f);
          if (opts) {
            return `<div class="field"><label>${esc(f.replace(/_/g, " "))}</label>` +
              `<select data-field="${esc(f)}">${opts.map((o) => `<option value="${esc(o)}">${esc(prettyVal(o))}</option>`).join("")}</select></div>`;
          }
          return `<div class="field"><label>${esc(f.replace(/_/g, " "))}</label><input data-field="${esc(f)}" placeholder="${esc(f.replace(/_/g, " "))}" /></div>`;
        }).join("")}
        <div class="modal-actions">
          <button class="btn btn-sm btn-ghost" data-close>Cancel</button>
          <button class="btn btn-sm btn-primary" id="noCreate">Create</button>
        </div>
      </div>
    </div>
  `);
  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.addEventListener("click", (e) => { if (e.target === overlay || e.target.dataset.close !== undefined) close(); });
  overlay.querySelector("#noCreate").addEventListener("click", async () => {
    const label = overlay.querySelector("#noLabel").value.trim();
    if (!label) { toast("Label is required", "err"); return; }
    const fieldVals = {};
    overlay.querySelectorAll("[data-field]").forEach((inp) => { if (inp.value.trim()) fieldVals[inp.dataset.field] = inp.value.trim(); });
    const b = overlay.querySelector("#noCreate"); b.disabled = true; b.innerHTML = `<span class="spinner"></span>`;
    try {
      await API.createObject(kind, label, fieldVals);
      close(); toast("Created", "ok");
      loadObjects(kind);
      // keep graph fresh under the hood
      if (WS.cy) loadGraph(true);
    } catch (e) { toast("Failed: " + e.message, "err"); b.disabled = false; b.textContent = "Create"; }
  });
}
