"""SQLite persistence for Orca.

Real database involvement: users, sessions, workspaces, connected sources,
ingested documents, and the materialized Teamwork Graph (nodes + edges) all
persist here. Each user gets a workspace; the graph and documents are scoped to
that workspace, so every surface (web, CLI, MCP) reads the same live data.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from .config import APP_DIR

DB_PATH = Path(__file__).resolve().parent.parent / "oracle.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, user_id TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY, user_id TEXT, name TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, workspace_id TEXT, type TEXT, name TEXT,
  status TEXT, meta TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, workspace_id TEXT, source_id TEXT,
  title TEXT, content TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS nodes (
  workspace_id TEXT, id TEXT, kind TEXT, label TEXT, attrs TEXT,
  source_id TEXT, created_at REAL,
  PRIMARY KEY (workspace_id, id)
);
CREATE TABLE IF NOT EXISTS edges (
  id TEXT PRIMARY KEY, workspace_id TEXT, type TEXT, src TEXT, tgt TEXT,
  source_id TEXT, created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_nodes_ws ON nodes(workspace_id);
CREATE INDEX IF NOT EXISTS idx_edges_ws ON edges(workspace_id);
CREATE INDEX IF NOT EXISTS idx_docs_ws ON documents(workspace_id);
"""


def _now() -> float:
    return time.time()


def uid(prefix: str = "") -> str:
    return (prefix + "_" if prefix else "") + uuid.uuid4().hex[:12]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------------- users / sessions / workspaces ----------------
def get_or_create_user(email: str, name: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            return dict(row)
        u = {"id": uid("u"), "email": email, "name": name, "created_at": _now()}
        conn.execute("INSERT INTO users VALUES (:id,:email,:name,:created_at)", u)
        ws = {"id": uid("ws"), "user_id": u["id"], "name": f"{name}'s Workspace", "created_at": _now()}
        conn.execute("INSERT INTO workspaces VALUES (:id,:user_id,:name,:created_at)", ws)
        return u


def create_session(user_id: str) -> str:
    token = uid("sess")
    with get_conn() as conn:
        conn.execute("INSERT INTO sessions VALUES (?,?,?)", (token, user_id, _now()))
    return token


def user_for_token(token: str) -> dict | None:
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def workspace_for_user(user_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE user_id=? ORDER BY created_at LIMIT 1", (user_id,)
        ).fetchone()
        return dict(row) if row else None


# ---------------- sources ----------------
def add_source(workspace_id: str, type_: str, name: str, status: str = "connected", meta: dict | None = None) -> dict:
    s = {"id": uid("src"), "workspace_id": workspace_id, "type": type_, "name": name,
         "status": status, "meta": json.dumps(meta or {}), "created_at": _now()}
    with get_conn() as conn:
        conn.execute("INSERT INTO sources VALUES (:id,:workspace_id,:type,:name,:status,:meta,:created_at)", s)
    s["meta"] = meta or {}
    return s


def list_sources(workspace_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM sources WHERE workspace_id=? ORDER BY created_at", (workspace_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["meta"] = json.loads(d.get("meta") or "{}")
        out.append(d)
    return out


# ---------------- documents ----------------
def add_document(workspace_id: str, source_id: str, title: str, content: str) -> dict:
    d = {"id": uid("doc"), "workspace_id": workspace_id, "source_id": source_id,
         "title": title, "content": content, "created_at": _now()}
    with get_conn() as conn:
        conn.execute("INSERT INTO documents VALUES (:id,:workspace_id,:source_id,:title,:content,:created_at)", d)
    return d


def list_documents(workspace_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM documents WHERE workspace_id=? ORDER BY created_at", (workspace_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------- graph nodes / edges ----------------
def upsert_node(workspace_id: str, node_id: str, kind: str, label: str,
                attrs: dict | None = None, source_id: str = "") -> None:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT attrs FROM nodes WHERE workspace_id=? AND id=?", (workspace_id, node_id)
        ).fetchone()
        merged = attrs or {}
        if existing:
            old = json.loads(existing["attrs"] or "{}")
            old.update({k: v for k, v in merged.items() if v not in (None, "")})
            merged = old
            conn.execute("UPDATE nodes SET kind=?, label=?, attrs=? WHERE workspace_id=? AND id=?",
                         (kind, label, json.dumps(merged), workspace_id, node_id))
        else:
            conn.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?)",
                         (workspace_id, node_id, kind, label, json.dumps(merged), source_id, _now()))


def add_edge(workspace_id: str, type_: str, src: str, tgt: str, source_id: str = "") -> None:
    with get_conn() as conn:
        dup = conn.execute(
            "SELECT 1 FROM edges WHERE workspace_id=? AND type=? AND src=? AND tgt=?",
            (workspace_id, type_, src, tgt),
        ).fetchone()
        if dup:
            return
        conn.execute("INSERT INTO edges VALUES (?,?,?,?,?,?,?)",
                     (uid("e"), workspace_id, type_, src, tgt, source_id, _now()))


def get_graph_rows(workspace_id: str) -> dict:
    with get_conn() as conn:
        nodes = conn.execute("SELECT * FROM nodes WHERE workspace_id=?", (workspace_id,)).fetchall()
        edges = conn.execute("SELECT * FROM edges WHERE workspace_id=?", (workspace_id,)).fetchall()
    return {
        "nodes": [{"id": n["id"], "kind": n["kind"], "label": n["label"],
                   "attrs": json.loads(n["attrs"] or "{}")} for n in nodes],
        "edges": [{"type": e["type"], "source": e["src"], "target": e["tgt"]} for e in edges],
    }


def get_node(workspace_id: str, node_id: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM nodes WHERE workspace_id=? AND id=?", (workspace_id, node_id)).fetchone()
    if not r:
        return None
    return {"id": r["id"], "kind": r["kind"], "label": r["label"], "attrs": json.loads(r["attrs"] or "{}")}


def list_nodes_by_kind(workspace_id: str, kind: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM nodes WHERE workspace_id=? AND kind=? ORDER BY created_at DESC",
                            (workspace_id, kind)).fetchall()
    return [{"id": r["id"], "kind": r["kind"], "label": r["label"], "attrs": json.loads(r["attrs"] or "{}")} for r in rows]


def update_node(workspace_id: str, node_id: str, label: str | None = None, attrs: dict | None = None) -> bool:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM nodes WHERE workspace_id=? AND id=?", (workspace_id, node_id)).fetchone()
        if not r:
            return False
        new_label = label if label is not None else r["label"]
        merged = json.loads(r["attrs"] or "{}")
        if attrs is not None:
            merged.update(attrs)
        conn.execute("UPDATE nodes SET label=?, attrs=? WHERE workspace_id=? AND id=?",
                     (new_label, json.dumps(merged), workspace_id, node_id))
        return True


def delete_node(workspace_id: str, node_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM nodes WHERE workspace_id=? AND id=?", (workspace_id, node_id))
        conn.execute("DELETE FROM edges WHERE workspace_id=? AND (src=? OR tgt=?)", (workspace_id, node_id, node_id))


def delete_edge(workspace_id: str, type_: str, src: str, tgt: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM edges WHERE workspace_id=? AND type=? AND src=? AND tgt=?",
                     (workspace_id, type_, src, tgt))


def clear_workspace_graph(workspace_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM nodes WHERE workspace_id=?", (workspace_id,))
        conn.execute("DELETE FROM edges WHERE workspace_id=?", (workspace_id,))


def workspace_stats(workspace_id: str) -> dict:
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM nodes WHERE workspace_id=?", (workspace_id,)).fetchone()["c"]
        e = conn.execute("SELECT COUNT(*) c FROM edges WHERE workspace_id=?", (workspace_id,)).fetchone()["c"]
        d = conn.execute("SELECT COUNT(*) c FROM documents WHERE workspace_id=?", (workspace_id,)).fetchone()["c"]
        s = conn.execute("SELECT COUNT(*) c FROM sources WHERE workspace_id=?", (workspace_id,)).fetchone()["c"]
    return {"nodes": n, "edges": e, "documents": d, "sources": s}


init_db()
