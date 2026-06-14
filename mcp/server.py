"""Orca MCP server — the Teamwork Graph for AI agents, over stdio.

Exposes the Orca Teamwork Graph (people, projects, decisions, pages, teams +
typed edges) and its multi-hop reasoning agent as MCP tools, so any MCP client
(VS Code, Copilot, etc.) can reason over the org graph.

Transport: stdio. Built on the official Python MCP SDK (`mcp[cli]`,
`mcp.server.fastmcp.FastMCP`).

Run:
    /Users/preethams/Developer/oracle/backend/.venv/bin/python server.py
"""
from __future__ import annotations

import os
import pathlib
import sys

# Make the backend package importable (read-only dependency).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

import app.db as db  # noqa: E402
import app.seed as seed  # noqa: E402
from app.agent import ask as _ask  # noqa: E402
from app.graph import EDGE_PHRASING, get_graph_for_workspace  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("orca-teamwork-graph")


# --------------------------------------------------------------------------- #
# Workspace resolution — read the live SQLite-backed workspace graph
# --------------------------------------------------------------------------- #
def _resolve_workspace() -> str:
    """Resolve the default workspace id, seeding demo data if needed.

    Defaults to the Contoso demo workspace (user demo@contoso.com). Override
    with the ORCA_WORKSPACE env var (an explicit workspace id) or the
    ORCA_USER_EMAIL env var (resolve that user's workspace).
    """
    seed.seed_all()
    explicit = os.environ.get("ORCA_WORKSPACE")
    if explicit:
        return explicit
    email = os.environ.get("ORCA_USER_EMAIL", "demo@contoso.com")
    name = "Priya Nair" if email == "demo@contoso.com" else email
    user = db.get_or_create_user(email, name)
    return db.workspace_for_user(user["id"])["id"]


_WS = _resolve_workspace()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _g():
    return get_graph_for_workspace(_WS)


def _label(nid: str) -> str:
    """Return a human-readable label for a node id (falls back to the id)."""
    n = _g().get(nid)
    return n.label if n else nid


def _resolve_or_error(query: str, kind: str | None = None):
    """Resolve a name/id to a node, or return (None, error_dict).

    If `kind` is given, prefer a node of that kind; otherwise return whatever
    resolves. On failure, suggest close matches via full-text search.
    """
    g = _g()
    node = g.resolve(query)
    if node is not None and (kind is None or node.kind == kind):
        return node, None

    # If resolve found the wrong kind (or nothing), try a kind-filtered search.
    if kind is not None:
        for cand in g.search(query, limit=8):
            if cand.kind == kind:
                return cand, None

    suggestions = [
        {"label": n.label, "kind": n.kind, "id": n.id}
        for n in g.search(query, limit=5)
    ]
    return None, {
        "error": f"Could not resolve {kind or 'node'} '{query}' in the Teamwork Graph.",
        "query": query,
        "did_you_mean": suggestions,
    }


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def ask_oracle(question: str) -> dict:
    """Ask the Orca reasoning agent a natural-language question about the org.

    Runs the full multi-hop reasoning pipeline over the Teamwork Graph (intent
    detection, graph traversal, grounding against Foundry IQ + linked Pages,
    Work IQ freshness overlay, synthesis). Best for open-ended questions like
    "Who do I need to unblock Checkout v2?" or "Why are we using passkeys?".

    Returns the full agent result: answer, citations, reasoning_trace,
    graph_evidence, work_iq, confidence, intent, mode, refused.
    """
    return _ask(question, workspace_id=_WS).to_dict()


@mcp.tool()
def ask_orca(question: str) -> dict:
    """Alias of `ask_oracle` — ask the Orca reasoning agent a question.

    Provided under the current "Orca" branding; behaves identically to
    `ask_oracle` and reasons over the live workspace Teamwork Graph + documents.
    """
    return _ask(question, workspace_id=_WS).to_dict()


@mcp.tool()
def search_graph(query: str, limit: int = 8) -> dict:
    """Full-text search the Teamwork Graph for matching nodes.

    Searches people, projects, decisions, pages and teams by label and
    attributes. Use this to discover the exact name/id of an entity before
    calling more specific tools.
    """
    nodes = _g().search(query, limit=limit)
    return {
        "query": query,
        "count": len(nodes),
        "results": [n.to_dict() for n in nodes],
    }


@mcp.tool()
def get_node(node_id: str) -> dict:
    """Look up a single node (by id OR label) and its immediate neighbors.

    Accepts either a raw node id (e.g. "proj_checkout_v2") or a human label
    (e.g. "Checkout v2", "Priya Nair"). Returns the node plus its neighbors
    with human-readable relationship phrases.
    """
    node, err = _resolve_or_error(node_id)
    if err:
        return err
    g = _g()
    neighbors = []
    for nb in g.neighbors(node.id):
        neighbors.append({
            "relationship": nb["phrase"],
            "edge": nb["edge"],
            "direction": nb["direction"],
            "node_id": nb["node"],
            "label": _label(nb["node"]),
            "kind": (g.get(nb["node"]).kind if g.get(nb["node"]) else None),
        })
    return {"node": node.to_dict(), "neighbors": neighbors}


@mcp.tool()
def find_path(from_node: str, to_node: str) -> dict:
    """Find how two entities are connected (shortest path through the graph).

    Resolves both endpoints from names/ids, then returns the shortest path
    (up to 6 hops) as a sequence of human-readable relationship steps. Great
    for "How is Priya Nair connected to David Chen?".
    """
    g = _g()
    start, err = _resolve_or_error(from_node)
    if err:
        return err
    end, err = _resolve_or_error(to_node)
    if err:
        return err

    path = g.find_path(start.id, end.id)
    if path is None:
        return {
            "from": start.label,
            "to": end.label,
            "connected": False,
            "message": f"No connection found between '{start.label}' and "
                       f"'{end.label}' within 6 hops.",
        }
    steps = []
    for s in path:
        forward, reverse = EDGE_PHRASING.get(s["edge"], (s["edge"], s["edge"]))
        phrase = forward if s.get("direction", "out") == "out" else reverse
        steps.append({
            "from": _label(s["from"]),
            "relationship": phrase,
            "to": _label(s["to"]),
        })
    return {
        "from": start.label,
        "to": end.label,
        "connected": True,
        "hops": len(steps),
        "path": steps,
    }


@mcp.tool()
def who_owns(project: str) -> dict:
    """Find who owns and contributes to a project.

    Resolves the project by name/id, then returns its owners and contributors
    (as human-readable labels with roles).
    """
    g = _g()
    proj, err = _resolve_or_error(project, kind="project")
    if err:
        return err

    def person(pid: str) -> dict:
        n = g.get(pid)
        return {
            "label": n.label if n else pid,
            "role": (n.attrs.get("role") if n else None),
            "id": pid,
        }

    owners = [person(p) for p in g.owners_of(proj.id)]
    contributors = [person(p) for p in g.contributors_of(proj.id)]
    return {
        "project": proj.label,
        "summary": proj.attrs.get("summary", ""),
        "status": proj.attrs.get("status", ""),
        "owners": owners,
        "contributors": contributors,
    }


@mcp.tool()
def dependencies_of(project: str, transitive: bool = True) -> dict:
    """List the projects a given project depends on.

    Resolves the project by name/id and walks `depends_on` edges. Set
    `transitive=False` for only direct dependencies.
    """
    g = _g()
    proj, err = _resolve_or_error(project, kind="project")
    if err:
        return err

    direct = g.dependencies_of(proj.id, transitive=False)
    deps = g.dependencies_of(proj.id, transitive=transitive)
    result = []
    for dep_id in deps:
        n = g.get(dep_id)
        result.append({
            "label": n.label if n else dep_id,
            "status": (n.attrs.get("status") if n else None),
            "kind": "direct" if dep_id in direct else "transitive",
            "id": dep_id,
        })
    return {
        "project": proj.label,
        "transitive": transitive,
        "count": len(result),
        "dependencies": result,
    }


@mcp.tool()
def blockers_for(project: str) -> dict:
    """Find who to talk to in order to unblock a project.

    Resolves the project, walks `depends_on` edges to every (transitive)
    dependency, then `owns` edges to find the people responsible for each
    blocking piece of work.
    """
    g = _g()
    proj, err = _resolve_or_error(project, kind="project")
    if err:
        return err

    blockers = g.blockers_for(proj.id)
    if not blockers:
        return {
            "project": proj.label,
            "blocked": False,
            "message": f"'{proj.label}' has no unresolved dependencies — "
                       f"nothing is blocking it right now.",
            "blockers": [],
        }
    people = []
    for b in blockers:
        owner = g.get(b["owner"])
        people.append({
            "person": owner.label if owner else b["owner"],
            "role": (owner.attrs.get("role") if owner else None),
            "owns_dependency": _label(b["dependency"]),
        })
    return {
        "project": proj.label,
        "blocked": True,
        "count": len(people),
        "blockers": people,
    }


@mcp.tool()
def decisions_for(project: str) -> dict:
    """List the decisions affecting a project and who made them.

    Resolves the project, collects `decided_for` edges, and resolves each
    decision's authors via `made_by` edges.
    """
    g = _g()
    proj, err = _resolve_or_error(project, kind="project")
    if err:
        return err

    decisions = []
    for did in g.decisions_for(proj.id):
        dn = g.get(did)
        authors = [g.get(s).label for et, s in g._out.get(did, [])
                   if et == "made_by" and g.get(s)]
        decisions.append({
            "title": dn.label if dn else did,
            "status": (dn.attrs.get("status") if dn else None),
            "date": (dn.attrs.get("date") if dn else None),
            "summary": (dn.attrs.get("summary") if dn else None),
            "made_by": authors,
        })
    return {
        "project": proj.label,
        "count": len(decisions),
        "decisions": decisions,
    }


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
