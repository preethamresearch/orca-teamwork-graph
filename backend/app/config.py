"""Central configuration for the Orca backend.

Reads from environment (.env). The backend is designed to run in two modes:

* **Live mode** — when Azure AI Foundry credentials are present, Orca grounds
  answers through Foundry IQ (retrieval) and synthesizes them with a Foundry
  Agent Service model, optionally enriched with Work IQ (Microsoft Graph).
* **Local-demo mode** — when credentials are absent (or ORACLE_LOCAL_DEMO=true),
  Orca runs an equivalent grounded-RAG pipeline over the bundled enterprise
  knowledge base so the full experience is reproducible offline for judging.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
MOCK_DATA_DIR = APP_DIR / "mock_data"


def _b(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # --- server ---
    host: str = os.getenv("ORACLE_HOST", "127.0.0.1")
    port: int = int(os.getenv("ORACLE_PORT", "8000"))
    allowed_origins: list[str] = [
        o.strip() for o in os.getenv("ORACLE_ALLOWED_ORIGINS", "chrome-extension://*").split(",")
    ]

    # --- Azure AI Foundry (Foundry IQ + Agent Service) ---
    ai_project_endpoint: str = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip()
    ai_agent_model: str = os.getenv("AZURE_AI_AGENT_MODEL", "gpt-4o").strip()
    foundry_iq_search_endpoint: str = os.getenv("FOUNDRY_IQ_SEARCH_ENDPOINT", "").strip()
    foundry_iq_search_index: str = os.getenv("FOUNDRY_IQ_SEARCH_INDEX", "oracle-enterprise-kb").strip()
    foundry_iq_search_key: str = os.getenv("FOUNDRY_IQ_SEARCH_KEY", "").strip()

    # --- Work IQ (Microsoft Graph) ---
    work_iq_tenant_id: str = os.getenv("WORK_IQ_TENANT_ID", "").strip()
    work_iq_client_id: str = os.getenv("WORK_IQ_CLIENT_ID", "").strip()
    work_iq_client_secret: str = os.getenv("WORK_IQ_CLIENT_SECRET", "").strip()

    force_local_demo: bool = _b("ORACLE_LOCAL_DEMO", False)

    @property
    def live_foundry(self) -> bool:
        """True when we have enough config to call live Azure AI Foundry."""
        return bool(self.ai_project_endpoint and self.foundry_iq_search_endpoint) and not self.force_local_demo

    @property
    def live_work_iq(self) -> bool:
        return bool(self.work_iq_tenant_id and self.work_iq_client_id and self.work_iq_client_secret)

    @property
    def mode(self) -> str:
        return "live-foundry" if self.live_foundry else "local-demo"


settings = Settings()
