"""Seed demo users + data so Orca is never empty.

Creates a few sign-in-able accounts. The primary demo account ("Contoso") is
loaded with a rich Teamwork Graph (people, teams, projects, decisions, pages)
plus tasks/bugs and pages, and grounding documents.
Idempotent: re-running won't duplicate.
"""
from __future__ import annotations

from . import db, objects
from .config import MOCK_DATA_DIR
from .graph import get_graph

DEMO_USERS = [
    {"email": "demo@contoso.com", "name": "Priya Nair", "seed": "contoso"},
    {"email": "alex@northwind.com", "name": "Alex Rivera", "seed": "empty"},
]


def _seed_contoso(ws_id: str) -> None:
    if db.workspace_stats(ws_id)["nodes"] > 0:
        return
    # 1. core graph from the bundled sample (includes derived teammate/member_of edges)
    g = get_graph()
    src = db.add_source(ws_id, "microsoft365", "Microsoft 365 (Work IQ)", "connected",
                        {"note": "sample import"})["id"]
    for n in g.nodes.values():
        db.upsert_node(ws_id, n.id, n.kind, n.label, n.attrs, src)
    for e in g.edges:
        db.add_edge(ws_id, e.type, e.source, e.target, src)

    # 2. grounding documents (Foundry IQ corpus)
    doc_src = db.add_source(ws_id, "upload", "Enterprise Handbooks", "ingested")["id"]
    for path in sorted(MOCK_DATA_DIR.glob("kb_*.md")):
        body = path.read_text(encoding="utf-8")
        title = body.splitlines()[0].lstrip("# ").strip() if body else path.stem
        db.add_document(ws_id, doc_src, title, body)

    # 3. tasks/bugs + pages (custom business objects)
    issues_src = db.add_source(ws_id, "issues", "Issues", "connected")["id"]
    tasks = [
        ("task", "Wire tokenized payments into Checkout", {"status": "in_progress", "assignee": "Priya Nair", "priority": "high"}, "proj_checkout"),
        ("task", "Add refresh-token rotation", {"status": "todo", "assignee": "Raj Patel", "priority": "medium"}, "proj_tokens"),
        ("bug", "Cosmos emulator fails on Apple Silicon", {"status": "open", "severity": "low", "assignee": "Aisha Khan"}, "proj_mesh"),
        ("bug", "Checkout 500s under burst load", {"status": "in_progress", "severity": "high", "assignee": "Priya Nair"}, "proj_checkout"),
        ("task", "Define error-budget gates for rollout", {"status": "todo", "assignee": "Sofia Alvarez", "priority": "high"}, "proj_checkout"),
    ]
    for kind, label, fields, proj in tasks:
        o = objects.create_object(ws_id, kind, label, fields, issues_src)
        objects.link(ws_id, "part_of", o["id"], proj)
        assignee = fields.get("assignee")
        if assignee:
            objects.link(ws_id, "assigned_to", o["id"], f"p_{objects._slug(assignee)}")

    goals_src = db.add_source(ws_id, "objective", "Goals", "connected")["id"]
    g1 = objects.create_object(ws_id, "goal", "Ship Checkout v2 to 100% by Q3",
                               {"status": "on_track", "owner": "Sofia Alvarez"}, goals_src)
    objects.link(ws_id, "tracks", g1["id"], "proj_checkout")


def _seed_user(u: dict) -> None:
    user = db.get_or_create_user(u["email"], u["name"])
    ws = db.workspace_for_user(user["id"])
    if u["seed"] == "contoso":
        _seed_contoso(ws["id"])


def seed_all() -> None:
    for u in DEMO_USERS:
        _seed_user(u)


if __name__ == "__main__":
    seed_all()
    print("seeded demo users:", ", ".join(u["email"] for u in DEMO_USERS))
