"""The Teamwork Graph — the structure agents reason over.

Loads the org graph (people, projects, decisions, pages, teams + typed edges),
derives implicit relationships (teammates from shared teams), and exposes the
multi-hop query primitives that the reasoning agent, MCP server, CLI, web UI and
extension all share.

The graph is intentionally dependency-free (plain adjacency lists) so it runs
anywhere. In production the same node/edge shape is populated from Foundry
(Pages, decisions) and Work IQ (people, projects, ownership) and refreshed
continuously — here it loads from the bundled sample org.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache

from .config import MOCK_DATA_DIR

NODE_KINDS = ("person", "project", "decision", "page", "team")

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "to", "of", "and", "or", "is", "are", "in", "on", "for",
    "with", "how", "do", "i", "my", "we", "you", "can", "what", "when", "be",
    "this", "that", "it", "as", "at", "by", "from", "if", "your", "our", "who",
    "need", "should", "talk", "about", "affect", "affects", "does", "did",
}


def _terms(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]

# Human-readable phrasing for each edge type, in both directions.
EDGE_PHRASING = {
    "reports_to": ("reports to", "manages"),
    "member_of": ("is on", "includes"),
    "owns": ("owns", "is owned by"),
    "contributes_to": ("contributes to", "has contributor"),
    "depends_on": ("depends on", "is depended on by"),
    "blocks": ("blocks", "is blocked by"),
    "decided_for": ("is a decision for", "has decision"),
    "made_by": ("was made by", "made the decision"),
    "documents": ("documents", "is documented by"),
    "assigned_to": ("is assigned to", "is assigned"),
    "part_of": ("is part of", "contains"),
    "tracks": ("tracks", "is tracked by"),
    "relates_to": ("relates to", "relates to"),
    "teammate": ("is a teammate of", "is a teammate of"),
}


@dataclass
class Node:
    id: str
    kind: str
    label: str
    attrs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "label": self.label, **self.attrs}


@dataclass
class Edge:
    type: str
    source: str
    target: str


class TeamworkGraph:
    def __init__(self, raw: dict):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._out: dict[str, list[tuple[str, str]]] = defaultdict(list)  # node -> [(edge_type, target)]
        self._in: dict[str, list[tuple[str, str]]] = defaultdict(list)   # node -> [(edge_type, source)]
        self._build(raw)

    # ----- construction -----
    def _add_node(self, node: Node):
        self.nodes[node.id] = node

    def _add_edge(self, etype: str, src: str, tgt: str):
        if src not in self.nodes or tgt not in self.nodes:
            return
        self.edges.append(Edge(etype, src, tgt))
        self._out[src].append((etype, tgt))
        self._in[tgt].append((etype, src))

    def _build(self, raw: dict):
        for t in raw.get("teams", []):
            self._add_node(Node(t["id"], "team", t["name"]))
        for p in raw.get("people", []):
            self._add_node(Node(p["id"], "person", p["name"],
                                {"role": p.get("role", ""), "team": p.get("team", ""), "email": p.get("email", "")}))
        for pr in raw.get("projects", []):
            self._add_node(Node(pr["id"], "project", pr["name"],
                                {"status": pr.get("status", ""), "team": pr.get("team", ""), "summary": pr.get("summary", "")}))
        for d in raw.get("decisions", []):
            self._add_node(Node(d["id"], "decision", d["title"],
                                {"date": d.get("date", ""), "status": d.get("status", ""), "summary": d.get("summary", "")}))
        for pg in raw.get("pages", []):
            self._add_node(Node(pg["id"], "page", pg["title"],
                                {"source": pg.get("source", ""), "summary": pg.get("summary", "")}))
        for e in raw.get("edges", []):
            self._add_edge(e["type"], e["source"], e["target"])
        # link people to their team + derive teammate edges
        self._derive_team_edges(raw.get("people", []))

    def _derive_team_edges(self, people: list[dict]):
        by_team: dict[str, list[str]] = defaultdict(list)
        for p in people:
            team = p.get("team")
            if team:
                self._add_edge("member_of", p["id"], team)
                by_team[team].append(p["id"])
        for members in by_team.values():
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    self._add_edge("teammate", a, b)
                    self._add_edge("teammate", b, a)

    # ----- lookups -----
    def get(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def resolve(self, query: str) -> Node | None:
        """Resolve a node by id or (case-insensitive) label/substring."""
        if query in self.nodes:
            return self.nodes[query]
        q = query.strip().lower()
        for n in self.nodes.values():
            if n.label.lower() == q:
                return n
        for n in self.nodes.values():
            if q in n.label.lower():
                return n
        return None

    def search(self, text: str, limit: int = 8) -> list[Node]:
        terms = _terms(text)
        if not terms:
            return []
        scored = []
        for n in self.nodes.values():
            label = n.label.lower()
            attrs = " ".join(str(v) for v in n.attrs.values()).lower()
            # label matches are worth far more than incidental attr/summary matches
            score = 0.0
            for t in terms:
                score += 4 * label.count(t)
                score += 1 * attrs.count(t)
            # bonus when most query terms land in this node's label
            label_terms = set(_terms(n.label))
            score += 3 * len(set(terms) & label_terms)
            if score:
                scored.append((score, n))
        scored.sort(key=lambda x: (x[0], x[1].kind == "project"), reverse=True)
        return [n for _, n in scored[:limit]]

    # ----- traversal -----
    def neighbors(self, node_id: str, edge_types: tuple[str, ...] | None = None) -> list[dict]:
        out = []
        for etype, tgt in self._out.get(node_id, []):
            if edge_types and etype not in edge_types:
                continue
            out.append({"direction": "out", "edge": etype, "phrase": EDGE_PHRASING.get(etype, (etype, etype))[0], "node": tgt})
        for etype, src in self._in.get(node_id, []):
            if edge_types and etype not in edge_types:
                continue
            out.append({"direction": "in", "edge": etype, "phrase": EDGE_PHRASING.get(etype, (etype, etype))[1], "node": src})
        return out

    def find_path(self, start: str, end: str, max_hops: int = 6) -> list[dict] | None:
        """Shortest path (BFS) between two nodes, returned as edge steps."""
        if start not in self.nodes or end not in self.nodes:
            return None
        if start == end:
            return []
        prev: dict[str, tuple[str, str, str]] = {}  # node -> (via_edge, from_node, direction)
        seen = {start}
        q = deque([(start, 0)])
        while q:
            cur, depth = q.popleft()
            if depth >= max_hops:
                continue
            # direction records the real edge orientation relative to the hop:
            #   "out" -> the real edge is cur -> tgt; "in" -> the real edge is tgt -> cur
            candidates = [(etype, tgt, "out") for etype, tgt in self._out.get(cur, [])]
            candidates += [(etype, src, "in") for etype, src in self._in.get(cur, [])]
            for etype, tgt, direction in candidates:
                if tgt in seen:
                    continue
                seen.add(tgt)
                prev[tgt] = (etype, cur, direction)
                if tgt == end:
                    return self._reconstruct(prev, start, end)
                q.append((tgt, depth + 1))
        return None

    def _reconstruct(self, prev, start, end) -> list[dict]:
        steps = []
        cur = end
        while cur != start:
            etype, frm, direction = prev[cur]
            steps.append({"from": frm, "edge": etype, "to": cur, "direction": direction})
            cur = frm
        steps.reverse()
        return steps

    # ----- semantic helpers (used by agent / MCP / CLI) -----
    def owners_of(self, project_id: str) -> list[str]:
        return [src for etype, src in self._in.get(project_id, []) if etype == "owns"]

    def contributors_of(self, project_id: str) -> list[str]:
        return [src for etype, src in self._in.get(project_id, []) if etype == "contributes_to"]

    def dependencies_of(self, project_id: str, transitive: bool = True) -> list[str]:
        """Projects this project depends on (optionally transitively)."""
        result: list[str] = []
        seen = set()
        stack = [project_id]
        first = True
        while stack:
            cur = stack.pop()
            for etype, tgt in self._out.get(cur, []):
                if etype == "depends_on" and tgt not in seen:
                    seen.add(tgt)
                    result.append(tgt)
                    if transitive:
                        stack.append(tgt)
            if not transitive and not first:
                break
            first = False
        return result

    def blockers_for(self, project_id: str) -> list[dict]:
        """Who you need to unblock a project: owners of every (transitive) dependency."""
        out = []
        for dep in self.dependencies_of(project_id, transitive=True):
            for owner in self.owners_of(dep):
                out.append({"dependency": dep, "owner": owner})
        return out

    def decisions_for(self, project_id: str) -> list[str]:
        return [src for etype, src in self._in.get(project_id, []) if etype == "decided_for"]

    def pages_for(self, node_id: str) -> list[str]:
        return [src for etype, src in self._in.get(node_id, []) if etype == "documents"]

    # ----- serialization for the UI / treemap -----
    def to_cytoscape(self) -> dict:
        nodes = [{"data": n.to_dict()} for n in self.nodes.values()]
        edges = [
            {"data": {"id": f"{e.source}->{e.target}:{e.type}", "source": e.source, "target": e.target, "label": e.type}}
            for e in self.edges
            if e.type != "teammate"  # teammate edges are dense; hide from the wire by default
        ]
        return {"nodes": nodes, "edges": edges}

    def to_treemap(self) -> dict:
        """Hierarchy: org → team → project → people, for the treemap view."""
        children = []
        for team in [n for n in self.nodes.values() if n.kind == "team"]:
            team_projects = [n for n in self.nodes.values() if n.kind == "project" and n.attrs.get("team") == team.id]
            proj_children = []
            for pr in team_projects:
                people = self.owners_of(pr.id) + self.contributors_of(pr.id)
                proj_children.append({
                    "name": pr.label, "id": pr.id, "kind": "project", "status": pr.attrs.get("status"),
                    "children": [
                        {"name": self.nodes[pid].label, "id": pid, "kind": "person",
                         "role": self.nodes[pid].attrs.get("role"), "value": 1}
                        for pid in dict.fromkeys(people) if pid in self.nodes
                    ] or [{"name": "(no builders yet)", "value": 1}],
                })
            children.append({"name": team.label, "id": team.id, "kind": "team", "children": proj_children or [{"name": "(no projects)", "value": 1}]})
        return {"name": "Contoso", "kind": "org", "children": children}

    def stats(self) -> dict:
        counts = defaultdict(int)
        for n in self.nodes.values():
            counts[n.kind] += 1
        return {"nodes": len(self.nodes), "edges": len(self.edges), "by_kind": dict(counts)}


def _graph_from_rows(rows: dict) -> "TeamworkGraph":
    """Build a TeamworkGraph from generic {nodes:[{id,kind,label,attrs}], edges:[{type,source,target}]}."""
    g = TeamworkGraph.__new__(TeamworkGraph)
    g.nodes = {}
    g.edges = []
    g._out = defaultdict(list)
    g._in = defaultdict(list)
    for n in rows.get("nodes", []):
        g._add_node(Node(n["id"], n.get("kind", "object"), n.get("label", n["id"]), n.get("attrs", {}) or {}))
    for e in rows.get("edges", []):
        g._add_edge(e["type"], e["source"], e["target"])
    return g


def get_graph_for_workspace(workspace_id: str) -> "TeamworkGraph":
    """Live, DB-backed Teamwork Graph for a workspace."""
    from . import db
    return _graph_from_rows(db.get_graph_rows(workspace_id))


@lru_cache(maxsize=1)
def get_graph() -> TeamworkGraph:
    """The bundled sample graph (used for seeding demo workspaces)."""
    raw = json.loads((MOCK_DATA_DIR / "org_graph.json").read_text(encoding="utf-8"))
    return TeamworkGraph(raw)
