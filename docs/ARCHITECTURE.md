# Orca — Architecture

## System overview

```mermaid
flowchart TB
    subgraph Surfaces["AI Surfaces"]
        WEB["Web Treemap UI<br/>(D3 + Cytoscape)"]
        MCP["MCP Server<br/>(Copilot / VS Code / any client)"]
        CLI["CLI"]
        EXT["Chrome Extension<br/>(popup + inline panel)"]
    end

    subgraph Backend["Orca Backend (FastAPI)"]
        API["REST API<br/>/ask /graph /node /search"]
        AGENT["Reasoning Agent<br/>7-stage pipeline"]
        SAFETY["Responsible-AI Layer<br/>injection guard · PII redaction · grounding floor"]
        GRAPH["Teamwork Graph Engine<br/>multi-hop traversal"]
    end

    subgraph IQ["Microsoft IQ"]
        FIQ["Foundry IQ<br/>grounded retrieval (RAG)"]
        WIQ["Work IQ<br/>live M365 context (MS Graph)"]
        FAGENT["Foundry Agent Service<br/>answer synthesis"]
    end

    subgraph Sources["Sources"]
        PAGES["Foundry Pages<br/>docs · decisions"]
        M365["Microsoft 365<br/>people · projects · ownership"]
        KB["Enterprise KB<br/>(local-demo corpus)"]
    end

    WEB & EXT -->|HTTP| API
    MCP & CLI -->|in-process import| AGENT
    API --> AGENT
    AGENT --> SAFETY
    AGENT --> GRAPH
    AGENT --> FIQ
    AGENT --> WIQ
    AGENT --> FAGENT
    GRAPH -.built & refreshed from.-> PAGES
    GRAPH -.built & refreshed from.-> M365
    FIQ --> KB
    FIQ --> PAGES
    WIQ --> M365
```

## Request flow for `POST /ask`

```mermaid
sequenceDiagram
    participant U as Surface
    participant A as Agent
    participant S as Safety
    participant G as Teamwork Graph
    participant F as Foundry IQ
    participant W as Work IQ
    participant L as LLM (Foundry Agent)

    U->>A: question (+ optional page_context)
    A->>S: screen_input()
    alt injection / exfiltration detected
        S-->>U: refuse (do not process)
    else safe
        A->>A: detect intent + resolve entities
        A->>G: multi-hop traversal (deps→owners, paths, decisions)
        G-->>A: reasoning trace + touched nodes
        A->>F: retrieve grounded excerpts (RAG)
        F-->>A: cited chunks
        A->>W: live work signals
        W-->>A: freshness overlay
        A->>L: synthesize(question, trace, evidence)
        L-->>A: grounded answer
        A->>S: screen_output() — grounding/citation floor
        S-->>U: answer + citations + trace + confidence
    end
```

## Data model — the Teamwork Graph

**Node kinds:** `person`, `project`, `decision`, `page`, `team`.

**Edge types** (each with forward/reverse natural-language phrasing for trace generation):

| Edge | Meaning |
|---|---|
| `reports_to` | person → manager |
| `member_of` | person → team |
| `teammate` | derived from shared team |
| `owns` | person → project |
| `contributes_to` | person → project |
| `depends_on` | project → project (traversed transitively) |
| `decided_for` | decision → project |
| `made_by` | decision → person |
| `documents` | page → project/decision |

**Multi-hop primitives** (`backend/app/graph.py`): `find_path` (BFS shortest path, direction-aware), `dependencies_of` (transitive), `blockers_for` (deps → owners), `owners_of` / `contributors_of`, `decisions_for`, `pages_for`, `neighbors`, `search`.

## Live vs. local-demo mode

| Layer | Live mode | Local-demo mode (default) |
|---|---|---|
| Graph source | Foundry Pages + Work IQ (MS Graph) | bundled `org_graph.json` |
| Retrieval | Foundry IQ → Azure AI Search (hybrid + semantic rerank) | dependency-free TF-IDF retriever over the bundled KB |
| Synthesis | Foundry Agent Service model | structured deterministic composition |
| Work context | live Microsoft Graph | bundled `work_iq_context.json` |

Mode is chosen automatically from environment (`backend/app/config.py`). The agent, graph, safety, and all surfaces are identical across modes — only the I/O adapters change, so the demo faithfully represents the production path.
