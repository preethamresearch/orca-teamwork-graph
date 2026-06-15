"""Connectors — bring signals from your work into the Teamwork Graph.

* **upload/paste** — ingest your own text → extract objects + relationships (real).
* **github** — real GitHub REST API: repos → projects, contributors → people,
  language/topics → attrs (real API integration; works with a public repo with
  no token, or a token for private/higher rate limits).
* **microsoft365 / notion / googledrive** — connector cards; OAuth marked
  "coming soon", they ingest a representative sample on connect.

Every connector writes nodes/edges + grounding documents into the workspace DB,
so the graph is "automatically and always current" from connected sources.
"""
from __future__ import annotations

import httpx

from . import db, objects
from .extract import extract


# ---------------- upload / paste ----------------
def ingest_text(workspace_id: str, title: str, text: str) -> dict:
    from .foundry_iq import index_documents
    src = db.add_source(workspace_id, "upload", title or "Pasted knowledge", "ingested")["id"]
    # store the raw doc for grounding (Foundry IQ) — local store + live Azure AI Search index
    db.add_document(workspace_id, src, title or "Pasted knowledge", text)
    index_documents([{"id": src, "title": title or "Pasted knowledge", "content": text}])
    # extract objects + relationships
    frag = extract(text, title)
    for n in frag["nodes"]:
        db.upsert_node(workspace_id, n["id"], n["kind"], n["label"], n.get("attrs", {}), src)
    for e in frag["edges"]:
        db.add_edge(workspace_id, e["type"], e["source"], e["target"], src)
    return {"source_id": src, "extracted_nodes": len(frag["nodes"]), "extracted_edges": len(frag["edges"])}


# ---------------- GitHub (real API) ----------------
def ingest_github(workspace_id: str, repo: str, token: str = "") -> dict:
    """repo: 'owner/name'. Pulls repo + contributors + languages from GitHub REST API."""
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    if "/" not in repo:
        raise ValueError("repo must be in the form 'owner/name'")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "oracle-teamwork-graph"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    src = db.add_source(workspace_id, "github", f"GitHub · {repo}", "connected", {"repo": repo})["id"]
    with httpx.Client(base_url="https://api.github.com", headers=headers, timeout=20) as gh:
        meta = gh.get(f"/repos/{repo}")
        meta.raise_for_status()
        m = meta.json()
        proj_id = f"proj_{objects._slug(m['name'])}"
        db.upsert_node(workspace_id, proj_id, "project", m["name"],
                       {"status": "active", "summary": (m.get("description") or "")[:200],
                        "stars": m.get("stargazers_count", 0), "language": m.get("language") or ""}, src)
        if m.get("description"):
            db.add_document(workspace_id, src, m["name"], m["description"])

        people = 0
        contribs = gh.get(f"/repos/{repo}/contributors", params={"per_page": 15})
        if contribs.status_code == 200:
            for c in contribs.json():
                login = c.get("login")
                if not login:
                    continue
                pid = f"p_{objects._slug(login)}"
                db.upsert_node(workspace_id, pid, "person", login,
                               {"role": "Contributor", "github": c.get("html_url", ""),
                                "contributions": c.get("contributions", 0)}, src)
                db.add_edge(workspace_id, "contributes_to", pid, proj_id, src)
                people += 1

        # most-active contributor → owner
        if contribs.status_code == 200 and contribs.json():
            top = max(contribs.json(), key=lambda c: c.get("contributions", 0))
            if top.get("login"):
                db.add_edge(workspace_id, "owns", f"p_{objects._slug(top['login'])}", proj_id, src)

    return {"source_id": src, "repo": repo, "people": people, "project": proj_id}


# ---------------- Notion (real, token-based REST) ----------------
def ingest_notion(workspace_id: str, token: str, query: str = "", limit: int = 15) -> dict:
    """Pull pages from a Notion workspace via the Notion API (integration token) and
    ingest them as Page objects + grounding docs. Like the GitHub connector, this is
    a real API integration that needs only a token (no OAuth dance)."""
    token = (token or "").strip()
    if not token:
        raise ValueError("a Notion integration token is required")
    headers = {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28",
               "Content-Type": "application/json"}
    src = db.add_source(workspace_id, "notion", "Notion", "connected")["id"]

    with httpx.Client(base_url="https://api.notion.com/v1", headers=headers, timeout=20) as nz:
        body = {"page_size": limit, "filter": {"property": "object", "value": "page"}}
        if query:
            body["query"] = query
        r = nz.post("/search", json=body)
        r.raise_for_status()
        results = r.json().get("results", [])
        pages = 0
        for pg in results[:limit]:
            title = _notion_title(pg)
            text = _notion_page_text(nz, pg.get("id", ""))
            body_text = f"{title}\n{text}".strip()
            objects.create_object(workspace_id, "page", title or "Untitled",
                                  {"source": "Notion", "summary": (text or "")[:200],
                                   "url": pg.get("url", ""), "body": body_text}, src)
            from .extract import extract as _extract
            frag = _extract(body_text, title)
            for n in frag["nodes"]:
                db.upsert_node(workspace_id, n["id"], n["kind"], n["label"], n.get("attrs", {}), src)
            for e in frag["edges"]:
                db.add_edge(workspace_id, e["type"], e["source"], e["target"], src)
            pages += 1
    return {"source_id": src, "name": "Notion", "pages": pages}


def _notion_title(pg: dict) -> str:
    props = pg.get("properties", {})
    for v in props.values():
        if v.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in v.get("title", [])).strip()
    return pg.get("url", "Notion page").rsplit("/", 1)[-1].replace("-", " ")


def _notion_page_text(nz, page_id: str, max_blocks: int = 40) -> str:
    if not page_id:
        return ""
    try:
        r = nz.get(f"/blocks/{page_id}/children", params={"page_size": max_blocks})
        if r.status_code != 200:
            return ""
        out = []
        for b in r.json().get("results", []):
            bt = b.get(b.get("type", ""), {})
            rich = bt.get("rich_text", []) if isinstance(bt, dict) else []
            line = "".join(t.get("plain_text", "") for t in rich)
            if line:
                out.append(line)
        return "\n".join(out)
    except Exception:
        return ""


# ---------------- simulated connectors ----------------
_SAMPLES = {
    "notion": ("Notion", "page", [
        ("Engineering Wiki — Home", "Central hub for engineering docs, runbooks, and onboarding."),
        ("Incident Postmortems", "Blameless postmortems for all Sev1/Sev2 incidents."),
    ]),
    "googledrive": ("Google Drive", "document", [
        ("Q3 Planning.docx", "Quarterly objectives and key results across squads."),
    ]),
    "microsoft365": ("Microsoft 365 (Work IQ)", "page", [
        ("Org Handbook", "Company policies, benefits, and engineering standards."),
    ]),
}


def connect_sample(workspace_id: str, kind: str) -> dict:
    if kind not in _SAMPLES:
        raise ValueError(f"unknown connector: {kind}")
    name, obj_kind, items = _SAMPLES[kind]
    src = db.add_source(workspace_id, kind, name, "connected", {"oauth": "coming_soon"})["id"]
    for title, body in items:
        objects.create_object(workspace_id, obj_kind, title, {"source": name, "summary": body, "body": body}, src)
    return {"source_id": src, "name": name, "ingested": len(items)}


# ---------------- MCP client (consume any MCP server as a source) ----------------
def _ingest_docs(workspace_id: str, src_id: str, docs: list[tuple[str, str]]) -> dict:
    from .foundry_iq import index_documents
    nodes = edges = 0
    for title, text in docs:
        if not text:
            continue
        db.add_document(workspace_id, src_id, title, text)
        index_documents([{"id": f"{src_id}-{title}", "title": title, "content": text}])
        frag = extract(text, title)
        for n in frag["nodes"]:
            db.upsert_node(workspace_id, n["id"], n["kind"], n["label"], n.get("attrs", {}), src_id)
            nodes += 1
        for e in frag["edges"]:
            db.add_edge(workspace_id, e["type"], e["source"], e["target"], src_id)
            edges += 1
    return {"documents": len(docs), "extracted_nodes": nodes, "extracted_edges": edges}


async def ingest_mcp(workspace_id: str, command: str, args: list[str] | None = None,
                     name: str | None = None) -> dict:
    """Connect to an MCP server (stdio), read its resources, and ingest them into
    the graph. Works with any MCP server — point `command`/`args` at filesystem,
    GitHub, Notion servers, etc. Defaults to the bundled demo server.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    args = args or []
    params = StdioServerParameters(command=command, args=args)
    docs: list[tuple[str, str]] = []
    tool_names: list[str] = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            try:
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
            except Exception:
                pass
            try:
                listed = await session.list_resources()
                for r in listed.resources[:25]:
                    try:
                        content = await session.read_resource(r.uri)
                        text = "\n".join(getattr(c, "text", "") or "" for c in content.contents)
                        docs.append((r.name or str(r.uri), text))
                    except Exception:
                        continue
            except Exception:
                pass

    label = name or f"MCP · {command} {' '.join(args)}".strip()
    src = db.add_source(workspace_id, "mcp", label, "connected",
                        {"command": command, "args": args, "tools": tool_names})["id"]
    result = _ingest_docs(workspace_id, src, docs)
    return {"source_id": src, "server": label, "tools": tool_names, **result}
