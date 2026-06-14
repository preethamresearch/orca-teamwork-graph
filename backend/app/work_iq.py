"""Work IQ — live M365 work-context layer (Microsoft Graph).

Work IQ supplies the *freshness* and *personalization* that a static knowledge
base can't: the signed-in user's recent meetings, files, emails, and Teams
messages — already scoped to what they're allowed to see.

In **live mode** this calls Microsoft Graph with the app's delegated/again
app-only token. In **local-demo mode** it returns the bundled sample payload so
the demo shows answers that adapt to the user's recent work.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .config import MOCK_DATA_DIR, settings


@lru_cache(maxsize=1)
def _sample() -> dict:
    return json.loads((MOCK_DATA_DIR / "work_iq_context.json").read_text(encoding="utf-8"))


def get_work_context(query: str, max_signals: int = 3) -> dict:
    """Return user profile + the work signals most relevant to the query."""
    data = _live_work_context() if settings.live_work_iq else _sample()
    signals = data.get("recent_signals", [])
    q = query.lower()
    ranked = sorted(
        signals,
        key=lambda s: sum(t in (s.get("snippet", "") + s.get("title", "")).lower() for t in q.split()),
        reverse=True,
    )
    return {"user": data.get("user", {}), "signals": ranked[:max_signals]}


def _live_work_context() -> dict:
    """Fetch recent work signals from Microsoft Graph (Work IQ)."""
    import httpx
    from azure.identity import ClientSecretCredential

    cred = ClientSecretCredential(
        tenant_id=settings.work_iq_tenant_id,
        client_id=settings.work_iq_client_id,
        client_secret=settings.work_iq_client_secret,
    )
    token = cred.get_token("https://graph.microsoft.com/.default").token
    headers = {"Authorization": f"Bearer {token}"}
    signals: list[dict] = []
    with httpx.Client(base_url="https://graph.microsoft.com/v1.0", headers=headers, timeout=15) as g:
        # Recent files surfaced for the user
        try:
            for it in g.get("/me/insights/used", params={"$top": 3}).json().get("value", []):
                res = it.get("resourceVisualization", {})
                signals.append({
                    "type": "file",
                    "title": res.get("title", ""),
                    "location": res.get("containerDisplayName", ""),
                    "snippet": res.get("previewText", ""),
                })
        except Exception:
            pass
        # Recent messages
        try:
            for m in g.get("/me/messages", params={"$top": 3, "$select": "subject,bodyPreview,from"}).json().get("value", []):
                signals.append({
                    "type": "email",
                    "subject": m.get("subject", ""),
                    "from": m.get("from", {}).get("emailAddress", {}).get("address", ""),
                    "snippet": m.get("bodyPreview", ""),
                })
        except Exception:
            pass
    me = {}
    try:
        me = g.get("/me", params={"$select": "displayName,jobTitle,department"}).json()
    except Exception:
        pass
    return {"user": me, "recent_signals": signals}
