# Orca — Agents League Hackathon 2026 Submission

**Track:** Enterprise Agents
**Tagline:** The Teamwork Graph for AI agents — every product builder, decision, and dependency connected, grounded in Microsoft IQ, reasoned over by AI through any surface.

## The problem

In every growing company the same questions get asked over and over: *Who owns this? What's blocking the launch? Who decided this, and why? Who should I talk to?* The answers exist — scattered across docs, chats, meetings, and people's heads — but they're **disconnected**, so AI assistants bolted onto that pile can only do shallow, single-shot retrieval. They return documents, not understanding.

## The solution

Orca builds a **Teamwork Graph**: a living, always-current model of how the organization actually runs — people (product builders), projects, decisions, Pages, and the **dependencies, ownership, and teammate relationships** between them. It then gives AI agents the ability to **reason over that structure with multi-hop traversal**, grounded and cited at every step, and exposes it into **every AI surface** an org already uses.

*"Who do I need to unblock Checkout v2?"* is not a search — it's a traversal:
`Checkout v2 —depends_on→ Identity Tokens —owned_by→ Lena Petrova` and `Checkout v2 —depends_on→ Platform Service Mesh —owned_by→ David Chen`. Orca returns the people, the reasoning trace, and the source citations.

## How it uses Microsoft IQ (required)

- **Foundry IQ** — grounded retrieval (RAG) over the enterprise knowledge base and Foundry Pages, with hybrid semantic search + reranking. Every answer is cited back to a source. *(Submitted for the "Best Use of IQ Tools" award.)*
- **Work IQ** — populates and continuously refreshes the graph (people, projects, ownership) and overlays live M365 work signals (recent files, meetings, mail, Teams) via Microsoft Graph, keeping it *always current*.
- **Foundry Agent Service** — synthesizes the final grounded answer in live mode.

## Why it scores on every rubric dimension

- **Accuracy & Relevance (20%)** — answers grounded in graph facts + Foundry IQ retrieval; citations on every claim; refuses when unsupported.
- **Reasoning & Multi-step (20%)** — a 7-stage pipeline (safety → plan → traverse → ground → freshen → synthesize → safety) doing genuine multi-hop graph reasoning, with a visible reasoning trace.
- **Reliability & Safety (20%)** — responsible-AI guardrails: prompt-injection screening of scraped page content, PII redaction before logging, and a grounding/citation floor that makes the agent refuse rather than hallucinate.
- **Creativity & Originality (15%)** — a Teamwork Graph exposed through **MCP** (any AI client becomes a graph-aware agent), plus an interactive treemap/force-graph visualization.
- **UX & Presentation (15%)** — four polished surfaces: web control-room UI, CLI, MCP, and an inline Chrome panel that can ground answers in the page you're reading.
- **Community vote (10%)** — it answers the questions employees actually ask all day.

## Deliverables checklist (per official rules)

- [x] **Working agent** built with Microsoft tooling (Azure AI Foundry Agent Service + Foundry IQ + Work IQ).
- [x] **Public GitHub repository** with full source.
- [x] **Architecture diagram** — [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) (shows Foundry, Work IQ, Foundry Agent Service).
- [x] **≥1 Microsoft IQ layer** — Foundry IQ **and** Work IQ.
- [x] **Grounded intelligence (RAG)** — Foundry IQ retrieval with citations.
- [x] **Demo video (≤5 min)** — script in [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md).
- [ ] **Project description** — this document + repo README (paste into the submission form).
- [ ] Upload demo video to YouTube/Vimeo and add the link to the submission form.

## Reproducibility

The entire project runs offline in **local-demo mode** — no Azure provisioning required to evaluate it. The production code paths for Foundry IQ, Work IQ, and the Foundry Agent are implemented and selected automatically when credentials are present (`backend/.env.example`). This keeps judging frictionless while showing the real integration.

## Tech stack

Python (FastAPI) · dependency-free graph engine · Azure AI Foundry (Agent Service, Foundry IQ / Azure AI Search) · Microsoft Graph (Work IQ) · Model Context Protocol (MCP) · D3 + Cytoscape.js (web) · Manifest V3 (extension).

## Team

- Preetham (sjp.preetham@gmail.com)
