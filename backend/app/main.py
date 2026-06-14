"""Orca backend API (FastAPI).

Auth + per-workspace Teamwork Graph, business-object CRUD, connectors, and the
reasoning agent — served to the web app, CLI, MCP server, and extension.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import __version__, auth, connectors, db, objects, seed
from .agent import ask
from .config import settings
from .graph import get_graph_for_workspace

app = FastAPI(title="Orca — Teamwork Graph", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # token is passed via header, not cookie, for cross-port demo
    allow_methods=["*"],
    allow_headers=["*"],
)

seed.seed_all()


# ----------------------------- models -----------------------------
class LoginReq(BaseModel):
    email: str
    name: str | None = None


class AskReq(BaseModel):
    question: str
    page_context: str | None = None
    top_k: int = 4


class ObjectReq(BaseModel):
    kind: str
    label: str
    fields: dict = {}


class ObjectUpdateReq(BaseModel):
    label: str | None = None
    fields: dict = {}


class LinkReq(BaseModel):
    type: str
    source: str
    target: str


class UploadReq(BaseModel):
    title: str = ""
    text: str


class GithubReq(BaseModel):
    repo: str
    token: str = ""


class ConnectReq(BaseModel):
    kind: str


def _ws(request: Request):
    return auth.current_workspace(request)


# ----------------------------- public -----------------------------
@app.get("/health")
def health():
    return {"status": "ok", "version": __version__, "mode": settings.mode}


@app.get("/object-types")
def object_types():
    return objects.type_registry()


@app.post("/auth/login")
def login(req: LoginReq, response: Response):
    name = req.name or req.email.split("@")[0].replace(".", " ").title()
    user = db.get_or_create_user(req.email.strip().lower(), name)
    token = db.create_session(user["id"])
    ws = db.workspace_for_user(user["id"])
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="lax")
    return {"user": user, "workspace": ws, "token": token, "stats": db.workspace_stats(ws["id"])}


@app.post("/auth/demo")
def demo_login(response: Response):
    user = db.get_or_create_user("demo@contoso.com", "Priya Nair")
    seed.seed_all()
    token = db.create_session(user["id"])
    ws = db.workspace_for_user(user["id"])
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="lax")
    return {"user": user, "workspace": ws, "token": token, "stats": db.workspace_stats(ws["id"])}


@app.post("/auth/logout")
def logout(request: Request):
    tok = auth.token_from(request)
    if tok:
        db.delete_session(tok)
    return {"ok": True}


@app.get("/auth/me")
def me(request: Request):
    user, ws = _ws(request)
    return {"user": user, "workspace": ws, "stats": db.workspace_stats(ws["id"])}


# ----------------------------- graph -----------------------------
@app.get("/graph")
def graph(request: Request):
    _, ws = _ws(request)
    return get_graph_for_workspace(ws["id"]).to_cytoscape()


@app.get("/graph/stats")
def graph_stats(request: Request):
    _, ws = _ws(request)
    return {**get_graph_for_workspace(ws["id"]).stats(), **db.workspace_stats(ws["id"])}


@app.get("/search")
def search(request: Request, q: str, limit: int = 8):
    _, ws = _ws(request)
    g = get_graph_for_workspace(ws["id"])
    return {"query": q, "results": [n.to_dict() for n in g.search(q, limit=limit)]}


@app.get("/node/{node_id}")
def node(request: Request, node_id: str):
    _, ws = _ws(request)
    g = get_graph_for_workspace(ws["id"])
    n = g.get(node_id) or g.resolve(node_id)
    if not n:
        raise HTTPException(404, f"node not found: {node_id}")
    return {"node": n.to_dict(),
            "neighbors": [{**nb, "node": g.get(nb["node"]).to_dict()} for nb in g.neighbors(n.id)]}


@app.post("/ask")
def ask_endpoint(request: Request, req: AskReq):
    _, ws = _ws(request)
    if not req.question.strip():
        raise HTTPException(400, "question is required")
    return ask(req.question, page_context=req.page_context, top_k=req.top_k, workspace_id=ws["id"]).to_dict()


# ----------------------------- sources / connectors -----------------------------
@app.get("/sources")
def sources(request: Request):
    _, ws = _ws(request)
    return {"sources": db.list_sources(ws["id"])}


@app.post("/connectors/upload")
def upload(request: Request, req: UploadReq):
    _, ws = _ws(request)
    if not req.text.strip():
        raise HTTPException(400, "text is required")
    return connectors.ingest_text(ws["id"], req.title, req.text)


@app.post("/connectors/github")
def github(request: Request, req: GithubReq):
    _, ws = _ws(request)
    try:
        return connectors.ingest_github(ws["id"], req.repo, req.token)
    except Exception as e:
        raise HTTPException(400, f"GitHub ingest failed: {e}")


@app.post("/connectors/connect")
def connect(request: Request, req: ConnectReq):
    _, ws = _ws(request)
    try:
        return connectors.connect_sample(ws["id"], req.kind)
    except ValueError as e:
        raise HTTPException(400, str(e))


class McpReq(BaseModel):
    command: str | None = None
    args: list[str] = []
    name: str | None = None


def _mcp_demo_server() -> str:
    import os, pathlib
    return os.getenv("ORCA_MCP_SERVER") or str(pathlib.Path(__file__).resolve().parents[2] / "mcp" / "demo_resource_server.py")


@app.post("/connectors/mcp")
async def mcp_connect(request: Request, req: McpReq):
    _, ws = _ws(request)
    import sys
    command = req.command or sys.executable
    args = req.args or [_mcp_demo_server()]
    name = req.name or ("MCP · bundled demo server" if not req.command else None)
    try:
        return await connectors.ingest_mcp(ws["id"], command, args, name)
    except Exception as e:
        raise HTTPException(400, f"MCP connect failed: {e}")


# ----------------------------- objects CRUD -----------------------------
@app.get("/objects")
def list_objs(request: Request, kind: str | None = None):
    _, ws = _ws(request)
    return {"objects": objects.list_objects(ws["id"], kind)}


@app.post("/objects")
def create_obj(request: Request, req: ObjectReq):
    _, ws = _ws(request)
    try:
        return objects.create_object(ws["id"], req.kind, req.label, req.fields)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/objects/{node_id}")
def get_obj(request: Request, node_id: str):
    _, ws = _ws(request)
    o = db.get_node(ws["id"], node_id)
    if not o:
        raise HTTPException(404, "object not found")
    return o


@app.put("/objects/{node_id}")
def update_obj(request: Request, node_id: str, req: ObjectUpdateReq):
    _, ws = _ws(request)
    o = objects.update_object(ws["id"], node_id, req.label, req.fields)
    if not o:
        raise HTTPException(404, "object not found")
    return o


@app.delete("/objects/{node_id}")
def delete_obj(request: Request, node_id: str):
    _, ws = _ws(request)
    objects.delete_object(ws["id"], node_id)
    return {"ok": True}


@app.post("/links")
def add_link(request: Request, req: LinkReq):
    _, ws = _ws(request)
    objects.link(ws["id"], req.type, req.source, req.target)
    return {"ok": True}


@app.delete("/links")
def remove_link(request: Request, req: LinkReq):
    _, ws = _ws(request)
    objects.unlink(ws["id"], req.type, req.source, req.target)
    return {"ok": True}


# ----------------------------- workspace -----------------------------
@app.post("/workspace/seed-sample")
def seed_sample(request: Request):
    _, ws = _ws(request)
    seed._seed_contoso(ws["id"])
    return {"ok": True, "stats": db.workspace_stats(ws["id"])}


@app.post("/workspace/clear")
def clear(request: Request):
    _, ws = _ws(request)
    db.clear_workspace_graph(ws["id"])
    return {"ok": True, "stats": db.workspace_stats(ws["id"])}


# ----------------------------- static frontend (single-service deploy) -----------------------------
# When ORCA_WEB_DIR (or the repo's ../../web) exists, serve the web app from the same
# origin as the API. Mounted last so all API routes above take precedence.
import os as _os, pathlib as _pathlib
from fastapi.staticfiles import StaticFiles as _StaticFiles

_web_dir = _os.getenv("ORCA_WEB_DIR") or str(_pathlib.Path(__file__).resolve().parents[2] / "web")
if _os.path.isdir(_web_dir):
    app.mount("/", _StaticFiles(directory=_web_dir, html=True), name="web")
