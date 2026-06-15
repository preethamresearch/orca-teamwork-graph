# Orca — the Teamwork Graph for AI agents

> **Every product builder — engineer, PM, designer — connected to the Pages, decisions, dependencies, owners, and teammates that define how your business actually runs. Built and kept current automatically from Microsoft Foundry + Work IQ, and reasoned over by AI through any surface: web, MCP, CLI, or browser.**

Orca doesn't just give AI agents *data* — it gives them **structure to think with**. Most enterprise AI bolts a chatbot onto a pile of documents and does single-shot retrieval. Orca builds a **living graph of how the organization works** and lets agents do **multi-hop reasoning** over it: *"Who do I need to talk to to unblock the Checkout launch?"* becomes a traversal — `Checkout v2 → depends_on → Identity Tokens → owned_by → Lena Petrova` — not a guess.

Built for the **Microsoft Agents League Hackathon 2026** — *Enterprise Agents* track.

## ▶ Watch the demo

[![Watch the Orca demo](https://img.youtube.com/vi/Fu12Xl7WK_s/maxresdefault.jpg)](https://www.youtube.com/watch?v=Fu12Xl7WK_s)

*▶ Watch the 5-minute demo: https://www.youtube.com/watch?v=Fu12Xl7WK_s*


---

## Why this wins (mapped to the official judging rubric)

| Criterion | Weight | How Orca delivers |
|---|---:|---|
| Accuracy & Relevance | 20% | Every answer is grounded in the graph + **Foundry IQ** retrieval; each fact carries a citation back to its source Page/decision. |
| Reasoning & Multi-step | 20% | A 7-stage agent pipeline does real **multi-hop graph traversal** (dependencies → owners → teammates, shortest-path between people, transitive blockers). |
| Reliability & Safety | 20% | A responsible-AI layer screens prompt-injection from page content, redacts PII before logging, and **refuses to answer when grounding is weak** instead of hallucinating. |
| Creativity & Originality | 15% | A Teamwork Graph exposed into **any AI surface via MCP** + an interactive treemap/force-graph. |
| UX & Presentation | 15% | Polished "control-room" web UI, a clean CLI, an inline browser panel, and a popup. |
| Community vote | 10% | Relatable demo: it answers the questions every employee actually asks. |

## Required: Microsoft IQ — used two ways

- **Foundry IQ** — the grounding/retrieval layer. Graph nodes and answers are grounded against an enterprise knowledge base (Azure AI Search–backed) with hybrid semantic retrieval and reranking. *(Targets the "Best Use of IQ Tools" prize.)*
- **Work IQ** — the freshness layer. The graph's people, projects, and ownership are populated and continuously refreshed from live Microsoft 365 work context (recent files, meetings, mail, Teams) via Microsoft Graph — so the graph is *always current*.

> The repo runs fully offline in **local-demo mode** (grounded retrieval over a bundled enterprise corpus + a rich sample org graph), so judges can reproduce everything without provisioning Azure. Drop in Azure AI Foundry credentials and the exact same code path goes live — see [`backend/.env.example`](backend/.env.example).

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full diagram and data flow.

```
            ┌──────────── AI SURFACES ────────────┐
   Web treemap UI   MCP server   CLI   Chrome extension
            └───────────────┬─────────────────────┘
                            │  (HTTP API / in-process)
                   ┌────────▼─────────┐
                   │  Orca Agent    │  7-stage reasoning pipeline
                   │  safety→plan→    │
                   │  traverse→ground │
                   │  →freshen→synth  │
                   └───┬─────────┬────┘
            ┌──────────▼──┐   ┌──▼───────────┐
            │ Teamwork    │   │  Foundry IQ  │  grounded retrieval
            │ Graph       │   │  (RAG)       │
            │ (multi-hop) │   └──────────────┘
            └──────┬──────┘   ┌──────────────┐
                   └──────────│   Work IQ    │  live M365 context
                              │  (MS Graph)  │
                              └──────────────┘
```

## The agent pipeline

1. **Safety (in)** — screen for prompt-injection / data-exfiltration embedded in page content.
2. **Plan** — detect intent (blockers / dependencies / owner / connection / decisions / expertise) and resolve the graph entities involved.
3. **Traverse** — run multi-hop queries over the Teamwork Graph, recording a human-readable reasoning trace.
4. **Ground** — retrieve supporting excerpts via Foundry IQ; attach the Pages that document each involved node as graph-native citations.
5. **Freshen** — overlay live Work IQ signals.
6. **Synthesize** — compose the answer (Foundry Agent model in live mode; structured composition in demo mode).
7. **Safety (out)** — enforce a grounding/citation floor; refuse rather than guess.

---

## Quickstart

### One command
```bash
bash scripts/start.sh
```
Boots the backend (`:8000`) and web app (`:5500`). Open **http://127.0.0.1:5500** and click **Sign in with Microsoft** to land in the seeded demo workspace. Then **Add source / knowledge** to ingest your own docs (Orca extracts objects + relationships into the graph), open the **agent terminal** (bottom-right) to reason over it, and the **Board** tab for a work-management view of tasks/bugs.

### Manual
```bash
# backend (required by all surfaces)
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-demo.txt        # local-demo deps (offline)
# (for live Azure AI Foundry: also `pip install -r requirements.txt` and fill in .env — see docs/AZURE_SETUP.md)
uvicorn app.main:app --host 127.0.0.1 --port 8000
# web app (new terminal)
cd web && python3 -m http.server 5500
```
Check: `curl -s http://127.0.0.1:8000/health`

### 3. CLI
```bash
cli/oracle ask "Who do I need to unblock Checkout v2?"
cli/oracle blockers "Checkout v2"
cli/oracle path "Priya Nair" "David Chen"
```

### 4. MCP server (bring the graph into Copilot / VS Code / any MCP client)
```bash
backend/.venv/bin/python mcp/server.py
```
Client config in [`mcp/README.md`](mcp/README.md).

### 5. Chrome extension
`chrome://extensions` → Developer mode → **Load unpacked** → select [`extension/`](extension/). Shortcut: <kbd>Cmd/Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>O</kbd>. See [`extension/README.md`](extension/README.md).

---

## Try these questions

- *Who do I need to unblock Checkout v2?* → walks transitive dependencies to their owners.
- *What does Checkout v2 depend on?* → direct + transitive dependency projects.
- *Who owns Identity Tokens?* → owners + contributors.
- *How is Priya connected to David Chen?* → shortest path across the org.
- *What decisions affect the Platform Service Mesh?* → decisions + who made them.
- *Who should I talk to about JWTs?* → expertise routing via ownership/decisions.

## Repository layout

```
backend/      FastAPI API, Teamwork Graph engine, reasoning agent, Foundry IQ + Work IQ, safety
  app/mock_data/   sample org graph + enterprise knowledge base
web/          interactive treemap + force-graph + Ask Orca panel (D3 + Cytoscape, no build step)
mcp/          MCP server exposing the graph as tools
cli/          stdlib CLI
extension/    Manifest V3 Chrome extension (popup + inline page panel)
docs/         architecture, submission write-up, demo script
```

## Project docs
- [Architecture & data flow](docs/ARCHITECTURE.md)
- [Submission write-up](docs/SUBMISSION.md)
- [5-minute demo script](docs/DEMO_SCRIPT.md)

## License
MIT — see [LICENSE](LICENSE).
