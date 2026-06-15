# Orca — Agents League Hackathon 2026 Submission

**Track:** Enterprise Agents (also competing for **Best Use of IQ Tools**)
**Tagline:** The context engine that turns how your business actually runs into a live Teamwork Graph your AI agents can reason over — grounded in Microsoft Foundry IQ.

## Links
- **🌐 Live demo:** https://orca.icysea-801c5df3.centralindia.azurecontainerapps.io
- **💻 Public repo:** https://github.com/preethamresearch/orca-teamwork-graph
- **🎥 Demo video:** _(add your YouTube/Vimeo link)_

> Sign in with Microsoft (real Entra/MSAL), or "Use a blank workspace." A seeded demo workspace is available via the in‑app **Load sample data**.

## The problem (a measurable, billion-dollar tax)
Every company runs on questions like *who owns this, what's blocking the launch, who decided this and why.* The answers exist — scattered across docs, chats, tickets and people's heads — so AI assistants bolted onto that pile do shallow, single-shot retrieval and **guess**.
- Knowledge workers spend **~1.8 hrs/day (≈20% of the week)** just searching and gathering information (McKinsey).
- **IDC** puts time lost to search + recreating existing work at **~30%** of the knowledge-worker day.
- For a **1,000-person org at a ~$80K loaded cost**, that's **~$16M/yr** of lost capacity; recovering even **10% = ~$1.6M/yr**.
- **42%** of institutional knowledge lives only in individuals (Panopto) — and walks out when they leave.

## The solution
**Orca** builds a **Teamwork Graph** — a living model of people, projects, decisions, tasks, pages and the **dependencies, ownership and teammate** links between them — then lets agents **reason over that structure with multi-hop traversal**, grounded and cited at every step.

*"Who do I need to unblock Checkout v2?"* isn't a search — it's a traversal: `Checkout v2 → depends_on → Identity Tokens → owned_by → Lena Petrova`. Orca returns the people, the reasoning trace, and the citations.

## How it uses Microsoft IQ (required) — live on Azure
- **Foundry IQ** — grounded retrieval is **running live on Azure AI Search** (`mode: foundry-iq-live`). Every answer is grounded in indexed enterprise sources and **cited**. *(This is a real, deployed Microsoft integration — no OpenAI quota needed.)*
- **Work IQ** — the Teamwork Graph itself (organizational intelligence: relationships + work patterns), exposed over REST **and MCP**.
- **Azure AI Foundry Agent Service** — the generative-synthesis code path (auto-activates when a Foundry model is available; on the student tier the model deploy is quota-gated, so generation currently runs via a pluggable provider — see below).

## Architecture (what's actually deployed)
```
Web app + Agent terminal + Board ─┐
CLI ──────────────────────────────┤→ FastAPI backend (Azure Container Apps)
MCP server / MCP client ──────────┘     │
                                        ├─ Teamwork Graph (multi-hop reasoning, SQLite)
                                        ├─ Foundry IQ grounding → Azure AI Search (LIVE)
                                        ├─ Generative synthesis (pluggable LLM)
                                        ├─ Responsible-AI guardrails
                                        └─ Connectors → graph
```
- **Hosting:** Azure Container Apps (Central India), single-service image, always-on, public HTTPS.
- **Auth:** Microsoft Entra (MSAL) real sign-in.
- **Agent pipeline:** safety → plan → traverse → ground (Foundry IQ) → freshen (Work IQ) → synthesize → safety, with citations + suggested follow-ups.

## Connectors (bring your work into the graph)
| Connector | Status |
|---|---|
| **Upload / paste** | ✅ real — extracts entities + relationships |
| **GitHub** | ✅ real — GitHub REST API (repo→project, contributors→people) |
| **Notion** | ✅ real — token-based Notion API → pages into the graph |
| **MCP server** | ✅ real — Orca is an **MCP client**, ingests any MCP server's resources |
| **Microsoft 365 / Google Drive** | ✅ real OAuth via a managed open-source connector layer (Connect → consent → Sync) |
| **1,000+ apps** | breadth via MCP + managed OAuth (Slack, Jira, Salesforce, …) |

## Surfaces ("context wherever work happens")
**Web** (graph + Jira-style board + agent terminal) · **CLI** · **MCP server** (any AI client reaches the graph) · **Chrome extension**.

## Why it scores on every rubric dimension
- **Accuracy (20%)** — grounded in Foundry IQ (live), citations on every claim, refuses when unsupported.
- **Reasoning (20%)** — genuine multi-hop graph traversal (dependencies → owners → teammates, shortest-path, transitive blockers) with a visible trace.
- **Reliability & Safety (20%)** — prompt-injection screening, PII redaction, grounding/citation floor (refuse, don't hallucinate).
- **Creativity (15%)** — a Teamwork Graph exposed via **MCP** to any agent; 1,000+ integrations; animated graph UI.
- **UX (15%)** — polished light enterprise UI, board, agent terminal, real Microsoft sign-in.
- **Community (10%)** — answers the questions employees actually ask all day.

## Business case / unit economics
- **Value:** ~$1.6M/yr recovered per 1,000 employees (10% of the search tax) + faster onboarding + retained institutional knowledge.
- **Cost:** runs on Azure free/consumption tiers; a pilot is low-hundreds of $/month against $1M+ recovered → **>90% gross-margin** SaaS.
- **Distribution:** rides **400M+ Microsoft 365 seats** + Copilot momentum as the missing context layer.
- **Moat:** the graph compounds — every connected source makes every future answer better (data network effect).

## Deliverables checklist (per official rules)
- [x] **Working agent** built with Microsoft tooling (Foundry IQ live + Foundry Agent path + Work IQ)
- [x] **Public GitHub repository** (full source)
- [x] **≥1 Microsoft IQ layer** — Foundry IQ (live on Azure AI Search) + Work IQ
- [x] **Grounded intelligence (RAG)** — Foundry IQ retrieval with citations
- [x] **Live hosted demo** on Azure
- [x] **Architecture diagram** — `docs/ARCHITECTURE.md`
- [ ] **Demo video (≤5 min)** — script in `docs/DEMO_SCRIPT.md`; add the link above
- [ ] Submit the form (repo + live URL + video links + this description)

## Tech stack
Python (FastAPI) · SQLite · Azure AI Foundry / **Azure AI Search (Foundry IQ, live)** · Microsoft Entra (MSAL) · Azure Container Apps · Model Context Protocol (MCP, server + client) · managed OAuth connector layer (Composio) · pluggable generative LLM (NVIDIA NIM today; Azure AI Foundry Agent when quota clears) · Cytoscape + fcose (web).

## Reproducibility & honesty
The repo runs offline in **local-demo mode** (deterministic graph reasoning + local grounding) and flips to **live Foundry IQ** automatically when Azure AI Search creds are set (they are, in the live deployment). The generative layer is pluggable: Azure OpenAI model deployment is **quota-gated on the student subscription**, so generation currently uses an NVIDIA model — the Azure AI Foundry Agent path is wired and activates on quota approval. All secrets are environment/secret-managed; none are committed.

## Team
- Preetham (preetham.s@benisontech.com)
