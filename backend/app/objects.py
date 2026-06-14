"""Business objects & relationships — the "materialize your custom business
objects" layer, modelled on the Teamwork Graph pattern.

Everything in Orca is a typed **object** (a graph node): people, teams,
projects, goals, tasks, bugs, pages/docs, decisions, sprints, releases, etc.
Objects connect through typed **relationships** (edges). This module is the CRUD
layer (tasks, bugs, pages) and the type registry that
the graph viz uses for icons + colors.
"""
from __future__ import annotations

from . import db

# type -> display, icon glyph (monochrome, neat), color, whether chip is filled, editable fields
OBJECT_TYPES: dict[str, dict] = {
    "person":    {"display": "Person",    "icon": "◉", "color": "#4c9aff", "fill": True,  "fields": ["role", "team", "email"]},
    "team":      {"display": "Team",      "icon": "⧉", "color": "#b3bac5", "fill": False, "fields": ["mission"]},
    "project":   {"display": "Project",   "icon": "◆", "color": "#4c9aff", "fill": True,  "fields": ["status", "team", "summary"]},
    "goal":      {"display": "Goal",      "icon": "◎", "color": "#ffffff", "fill": False, "fields": ["status", "target_date", "owner"]},
    "key_result":{"display": "Key Result","icon": "❯", "color": "#4c9aff", "fill": False, "fields": ["metric", "target"]},
    "task":      {"display": "Task",      "icon": "▢", "color": "#4c9aff", "fill": True,  "fields": ["status", "assignee", "priority", "project"]},
    "bug":       {"display": "Bug",       "icon": "⬢", "color": "#ff5630", "fill": True,  "fields": ["status", "severity", "assignee", "project"]},
    "page":      {"display": "Page",      "icon": "▤", "color": "#4c9aff", "fill": True,  "fields": ["source", "summary", "body"]},
    "document":  {"display": "Document",  "icon": "▦", "color": "#4c9aff", "fill": True,  "fields": ["source", "summary", "body"]},
    "decision":  {"display": "Decision",  "icon": "◈", "color": "#a17bff", "fill": False, "fields": ["status", "date", "summary"]},
    "sprint":    {"display": "Sprint",    "icon": "↻", "color": "#57d9a3", "fill": False, "fields": ["status", "dates"]},
    "release":   {"display": "Release",   "icon": "⬆", "color": "#57d9a3", "fill": False, "fields": ["version", "date"]},
    "request":   {"display": "Request",   "icon": "✦", "color": "#ffab00", "fill": True,  "fields": ["status", "requester"]},
    "system":    {"display": "System",    "icon": "▥", "color": "#ffab00", "fill": False, "fields": ["owner"]},
}

# edge type -> (forward phrase, reverse phrase)
RELATIONSHIP_TYPES: dict[str, tuple[str, str]] = {
    "reports_to":     ("reports to", "manages"),
    "member_of":      ("is on", "includes"),
    "teammate":       ("is a teammate of", "is a teammate of"),
    "owns":           ("owns", "is owned by"),
    "contributes_to": ("contributes to", "has contributor"),
    "depends_on":     ("depends on", "is depended on by"),
    "blocks":         ("blocks", "is blocked by"),
    "decided_for":    ("is a decision for", "has decision"),
    "made_by":        ("was made by", "made"),
    "documents":      ("documents", "is documented by"),
    "assigned_to":    ("is assigned to", "is assigned"),
    "part_of":        ("is part of", "contains"),
    "tracks":         ("tracks", "is tracked by"),
    "relates_to":     ("relates to", "relates to"),
}

# fields whose value is long-form body text → also stored as a grounding document
BODY_FIELDS = {"body"}


def type_registry() -> dict:
    return {"objects": OBJECT_TYPES, "relationships": {k: {"forward": v[0], "reverse": v[1]}
                                                       for k, v in RELATIONSHIP_TYPES.items()}}


def _slug(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")[:48]


def create_object(workspace_id: str, kind: str, label: str, fields: dict | None = None, source_id: str = "") -> dict:
    if kind not in OBJECT_TYPES:
        raise ValueError(f"unknown object type: {kind}")
    fields = dict(fields or {})
    prefix = {"person": "p", "project": "proj", "decision": "dec", "team": "team"}.get(kind, kind)
    node_id = f"{prefix}_{_slug(label)}" or f"{kind}_{db.uid()}"
    body = fields.pop("body", "")
    db.upsert_node(workspace_id, node_id, kind, label, fields, source_id)
    if body:
        src = source_id or db.add_source(workspace_id, "object", f"{kind}:{label}", "ingested")["id"]
        db.add_document(workspace_id, src, label, body)
    return db.get_node(workspace_id, node_id)


def update_object(workspace_id: str, node_id: str, label: str | None = None, fields: dict | None = None) -> dict | None:
    fields = dict(fields or {})
    body = fields.pop("body", None)
    db.update_node(workspace_id, node_id, label=label, attrs=fields or None)
    if body:
        n = db.get_node(workspace_id, node_id)
        src = db.add_source(workspace_id, "object", f"edit:{node_id}", "ingested")["id"]
        db.add_document(workspace_id, src, n["label"] if n else node_id, body)
    return db.get_node(workspace_id, node_id)


def delete_object(workspace_id: str, node_id: str) -> None:
    db.delete_node(workspace_id, node_id)


def list_objects(workspace_id: str, kind: str | None = None) -> list[dict]:
    if kind:
        return db.list_nodes_by_kind(workspace_id, kind)
    return db.get_graph_rows(workspace_id)["nodes"]


def link(workspace_id: str, type_: str, src: str, tgt: str) -> None:
    db.add_edge(workspace_id, type_, src, tgt)


def unlink(workspace_id: str, type_: str, src: str, tgt: str) -> None:
    db.delete_edge(workspace_id, type_, src, tgt)
