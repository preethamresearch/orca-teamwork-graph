"""Composio connector — managed OAuth for Google Drive, Microsoft 365 (OneDrive),
and 1,000+ apps. The Composio API key is app-level (one secret); each end user
authorizes their OWN account via a consent link (scoped by user_id).
"""
from __future__ import annotations

import json
import urllib.request

from . import db, objects
from .config import settings
from .extract import extract

BASE = "https://backend.composio.dev/api/v3"

TOOLKITS = {
    "googledrive": {"name": "Google Drive", "list_tool": "GOOGLEDRIVE_LIST_FILES", "args": {"page_size": 20}},
    "one_drive": {"name": "Microsoft 365 (OneDrive)", "list_tool": "ONE_DRIVE_GET_RECENT_ITEMS", "args": {}},
}


def _req(method: str, path: str, body: dict | None = None) -> dict:
    if not settings.composio_api_key:
        raise RuntimeError("Composio is not configured on the server")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"x-api-key": settings.composio_api_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _auth_config(slug: str) -> str:
    try:
        d = _req("GET", f"/auth_configs?toolkit_slug={slug}&limit=1")
        if d.get("items"):
            return d["items"][0]["id"]
    except Exception:
        pass
    d = _req("POST", "/auth_configs", {"toolkit": {"slug": slug}, "auth_config": {"type": "use_composio_managed_auth"}})
    return d["auth_config"]["id"]


def connect_link(user_id: str, slug: str) -> dict:
    if slug not in TOOLKITS:
        raise ValueError(f"unsupported toolkit: {slug}")
    ac = _auth_config(slug)
    d = _req("POST", "/connected_accounts/link", {"auth_config_id": ac, "user_id": user_id})
    return {"redirect_url": d.get("redirect_url"), "connected_account_id": d.get("connected_account_id"),
            "toolkit": TOOLKITS[slug]["name"]}


def _file_titles(resp: dict) -> list[str]:
    """Defensively pull file/item names out of a Composio tool-execution response."""
    titles: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            name = o.get("name") or o.get("title") or o.get("displayName")
            if isinstance(name, str) and name.strip():
                titles.append(name.strip())
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(resp.get("data", resp))
    # de-dup, keep order
    seen, out = set(), []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def sync(workspace_id: str, user_id: str, slug: str) -> dict:
    if slug not in TOOLKITS:
        raise ValueError(f"unsupported toolkit: {slug}")
    tk = TOOLKITS[slug]
    resp = _req("POST", f"/tools/execute/{tk['list_tool']}", {"user_id": user_id, "arguments": tk["args"]})
    if resp.get("successful") is False or resp.get("error"):
        raise RuntimeError(resp.get("error") or "tool execution failed — is the account connected?")
    titles = _file_titles(resp)[:25]
    src = db.add_source(workspace_id, slug, tk["name"], "connected")["id"]
    nodes = 0
    for title in titles:
        objects.create_object(workspace_id, "document", title, {"source": tk["name"]}, src)
        frag = extract(title, title)
        for n in frag["nodes"]:
            db.upsert_node(workspace_id, n["id"], n["kind"], n["label"], n.get("attrs", {}), src)
            nodes += 1
        for e in frag["edges"]:
            db.add_edge(workspace_id, e["type"], e["source"], e["target"], src)
    return {"name": tk["name"], "files": len(titles), "extracted_nodes": nodes}
