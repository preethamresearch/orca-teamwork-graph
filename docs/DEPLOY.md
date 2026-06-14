# Deploying Orca (make it accessible to judges)

The official submission needs a **public GitHub repo + demo video** — judges can run Orca locally with `bash scripts/start.sh`. A **live hosted URL** is an optional bonus. Three routes, fastest first.

## Config knobs
- **Frontend → backend URL:** set `window.ORCA_API_BASE` before `app.js` loads (in `web/index.html`), e.g.
  ```html
  <script>window.ORCA_API_BASE = "https://your-backend.example.com";</script>
  ```
  Defaults to `http://127.0.0.1:8000`.
- **Microsoft sign-in (MSAL):** register the deployed frontend URL as an Entra **SPA redirect URI** (localhost is allowed for local testing without hosting).

## Option A — public URL in minutes (tunnel, no deploy)
Run both servers locally, then expose them over HTTPS:
```bash
bash scripts/start.sh                 # backend :8000, web :5500
# in two more terminals (cloudflared is free, no account needed):
cloudflared tunnel --url http://localhost:5500   # → https://<rand>.trycloudflare.com  (frontend)
cloudflared tunnel --url http://localhost:8000   # → https://<rand>.trycloudflare.com  (backend)
```
Set `window.ORCA_API_BASE` to the backend tunnel URL, and add the frontend tunnel URL as an Entra redirect URI. (ngrok works the same way.)

## Option B — Azure (on-brand for the hackathon)
- **Frontend → Azure Static Web Apps:** point it at the `web/` folder (no build). Add the SWA URL as an Entra redirect URI; set `ORCA_API_BASE` to the backend URL.
- **Backend → Azure Container Apps / App Service:** deploy `backend/Dockerfile`.
  ```bash
  az containerapp up --name orca-api --source backend --ingress external --target-port 8000
  ```

## Option C — Vercel/Netlify + Render/Railway
- **Frontend:** drag-drop `web/` to Netlify, or `vercel deploy web/`.
- **Backend:** Render/Railway from `backend/Dockerfile` (exposes :8000).

## Notes
- SQLite (`oracle.db`) is ephemeral per instance and reseeds the demo workspace on start — fine for a demo; use a managed DB for real persistence.
- CORS is open (`*`) so the hosted frontend can reach the backend.
- Never commit secrets — `.env`, `oracle.db`, keys are git-ignored.
