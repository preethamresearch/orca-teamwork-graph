# Going live on Azure AI Foundry

Orca runs offline in **local-demo mode** by default. To run the exact same code
against live Microsoft IQ, provide credentials in `backend/.env`. The backend
auto-detects them (`backend/app/config.py`) and switches the I/O adapters — no
code changes.

## 0. Prerequisites
- An Azure subscription with **Azure AI Foundry** access.
- `pip install -r backend/requirements.txt` (adds the Azure SDKs on top of the demo deps).
- (Optional, for Work IQ) a Microsoft Entra app registration with Microsoft Graph permissions.

## 1. Foundry IQ — grounded retrieval (RAG)
Foundry IQ grounds answers against an enterprise knowledge base. Under the hood
Orca queries an **Azure AI Search** index (hybrid semantic retrieval + reranking).

1. Create an **Azure AI Search** service.
2. Create an index named `oracle-enterprise-kb` (or set `FOUNDRY_IQ_SEARCH_INDEX`)
   with fields: `id`, `doc_id`, `title`, `section`, `content`, and a vector field;
   enable a **semantic configuration** named `default`.
3. Ingest your sources (the bundled `backend/app/mock_data/*.md` are a starting
   point; in production, point a Foundry IQ knowledge source at SharePoint / Foundry Pages).
4. Fill in `.env`:
   ```
   FOUNDRY_IQ_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
   FOUNDRY_IQ_SEARCH_INDEX=oracle-enterprise-kb
   FOUNDRY_IQ_SEARCH_KEY=<query-key>
   ```
   Code path: `backend/app/foundry_iq.py` → `_retrieve_live()`.

## 2. Foundry Agent Service — answer synthesis
1. Create an **Azure AI Foundry project**; deploy a model (e.g. `gpt-4o`).
2. Fill in `.env`:
   ```
   AZURE_AI_PROJECT_ENDPOINT=https://<your-project>.services.ai.azure.com/api/projects/<project>
   AZURE_AI_AGENT_MODEL=gpt-4o
   ```
3. Auth uses `DefaultAzureCredential` — run `az login` (or set a managed identity /
   service principal env vars). Code path: `backend/app/llm.py` → `_synthesize_live()`.

> Setting `AZURE_AI_PROJECT_ENDPOINT` + `FOUNDRY_IQ_SEARCH_ENDPOINT` flips `mode`
> to `live-foundry` (see `/health`). Set `ORACLE_LOCAL_DEMO=true` to force demo mode.

## 3. Work IQ — live M365 context (optional)
Populates/refreshes the graph and overlays recent work signals via Microsoft Graph.

1. Register an Entra app; grant Microsoft Graph permissions (e.g. `User.Read`,
   `Mail.Read`, `Files.Read.All`, `Sites.Read.All`) and admin-consent as needed.
2. Fill in `.env`:
   ```
   WORK_IQ_TENANT_ID=<tenant-guid>
   WORK_IQ_CLIENT_ID=<app-id>
   WORK_IQ_CLIENT_SECRET=<secret>
   ```
   Code path: `backend/app/work_iq.py` → `_live_work_context()`.

## 4. Verify live mode
```bash
cd backend && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
curl -s http://127.0.0.1:8000/health    # expect "mode":"live-foundry"
curl -s -X POST http://127.0.0.1:8000/ask -H 'content-type: application/json' \
  -d '{"question":"Who do I need to unblock Checkout v2?"}'
```
Then re-run `bash scripts/test_all.sh` — the same scenarios should pass against live services.

## Security notes
- `.env` is git-ignored; never commit secrets.
- Prefer **managed identity** over client secrets in production.
- The responsible-AI layer (`backend/app/safety.py`) applies in both modes.
