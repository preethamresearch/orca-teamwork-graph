# Orca — Web UI

The web client for **Orca — the Teamwork Graph for AI agents**. A single-page,
no-build, vanilla-JS ES-module app. The graph is rendered with **Cytoscape.js**
using the **fcose** force layout (loaded from CDN) and styled to match the
a clean knowledge-graph style: rounded "chip" nodes (icon + label, color-coded by
object type) on a spacious dark canvas connected by thin gray lines.

## Run

The backend must be running at `http://127.0.0.1:8000` first.

Then serve this folder as static files:

```bash
cd /Users/preethams/Developer/oracle/web
python3 -m http.server 5500
```

Open http://127.0.0.1:5500/index.html

Restart the static server (kill any existing one first):

```bash
cd /Users/preethams/Developer/oracle/web
(pkill -f "http.server 5500"; nohup python3 -m http.server 5500 >/tmp/oracle_web.log 2>&1 &)
```

## Screens

1. **Landing / Sign in** — dark SaaS hero. "Sign in with Microsoft" calls
   `POST /auth/demo` (loads the seeded Contoso/Priya Nair workspace). "Use a
   blank workspace" calls `POST /auth/login` with email + name.
2. **Workspace** — 3 regions:
   - **Left**: workspace/user, Sources list (`GET /sources`), "+ Add source /
     knowledge" (Connect panel), Graph / Objects nav.
   - **Center**: the chip-node Cytoscape graph (`GET /graph`, `GET /object-types`
     for icons/colors). Toolbar: search (`GET /search`), fit, refresh.
   - **Right**: Ask Orca chat (`POST /ask`) — markdown answer, confidence meter,
     numbered reasoning trace, citations, Work IQ signals. Evidence nodes glow,
     others dim.
   - **Node detail**: click a node → attrs + neighbors (`GET /node/{id}`).
3. **Connect panel** — Upload/paste (`POST /connectors/upload`), GitHub
   (`POST /connectors/github`), Microsoft 365 / Notion / Google Drive
   (`POST /connectors/connect`), and "Load Contoso sample"
   (`POST /workspace/seed-sample`). Empty graph → empty-state with the same actions.
4. **Objects view** — work-management board with tabs per kind
   (`GET /objects?kind=`), "+ New" (`POST /objects`), inline delete (`DELETE`).

## Auth

Token-based. After login the `token` is stored in `localStorage` (`orca_token`)
and sent as the `X-Oracle-Token` header on every authenticated request.

## Tech

- Vanilla JS ES modules, no bundler, no npm.
- CDN libs: `cytoscape@3.30.2`, `layout-base@2.0.1`, `cose-base@2.2.0`,
  `cytoscape-fcose@2.2.0`, `marked`, Google Fonts (Inter + JetBrains Mono).
- Layout: **fcose** (registered via `cytoscape.use(window.cytoscapeFcose)`),
  with an automatic fallback to the built-in `cose` layout if fcose fails to
  load. After layout the graph always calls `cy.fit(undefined, 60)`.
