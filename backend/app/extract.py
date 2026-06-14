"""Entity + relationship extraction — the engine that turns *your* knowledge
into a Teamwork Graph.

Given free text (pasted notes, an uploaded doc, a brain-dump), it extracts:
  - people (with roles + team), projects, decisions, teams
  - relationships: owns, contributes_to, depends_on, reports_to, decided_for, made_by

In **live mode** it asks an Azure AI Foundry model to return a structured graph
(handles arbitrary prose). In **local-demo mode** it uses a deterministic
pattern extractor that handles natural lines like:

    # Team: Payments
    Priya Nair (Software Engineer) works on Checkout v2
    Sofia Alvarez (PM) owns Checkout v2
    Checkout v2 depends on Identity Tokens
    Priya reports to Marcus Lee
    Decision: Phased rollout of Checkout v2, decided by Sofia Alvarez

Every ingested document also becomes a `page` node so answers stay grounded and
citable even when no explicit relationship is found.
"""
from __future__ import annotations

import re

from .config import settings

ROLE_WORDS = (
    "engineer|developer|manager|designer|lead|director|scientist|analyst|"
    "architect|sre|pm|product manager|vp|head|owner|founder|cto|ceo|intern|"
    "consultant|specialist|coordinator|administrator|researcher|qa|tester"
)

_NAME = r"[A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+){0,2}"
_THING = r"[A-Z0-9][\w.+ /&-]{1,48}"

# relationship patterns: (regex, builder) where builder(m) -> list of (kind/edge ops)
OWN_RE      = re.compile(rf"({_NAME})\s+(?:owns|leads|manages the|is the owner of|heads)\s+({_THING})", re.I)
OWN_BY_RE   = re.compile(rf"({_THING})\s+is\s+(?:owned|led)\s+by\s+({_NAME})", re.I)
CONTRIB_RE  = re.compile(rf"({_NAME})\s+(?:works on|contributes to|is working on|builds|supports)\s+({_THING})", re.I)
DEPEND_RE   = re.compile(rf"({_THING})\s+(?:depends on|requires|needs|is blocked by|relies on)\s+({_THING})", re.I)
REPORTS_RE  = re.compile(rf"({_NAME})\s+reports to\s+({_NAME})", re.I)
DECISION_RE = re.compile(r"(?:decision|we decided(?: to)?|decided)\s*[:\-]?\s*(.+)", re.I)
DECIDED_BY  = re.compile(rf"(.+?)\s*[,(]?\s*(?:decided|made|approved)\s+by\s+({_NAME})", re.I)
AFFECTS_RE  = re.compile(rf"(?:for|affecting|on)\s+({_THING})\s*$", re.I)
PERSON_DECL = re.compile(rf"^({_NAME})\s*[\(,\-–]\s*((?:{ROLE_WORDS})[\w /]*)", re.I)
TEAM_HEAD   = re.compile(r"^#*\s*team\s*[:\-]\s*(.+)$", re.I)
PROJECT_DECL = re.compile(r"^#*\s*project\s*[:\-]\s*(.+)$", re.I)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")[:48]


class Builder:
    """Accumulates nodes/edges with dedup by id."""

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self._edge_keys: set[tuple] = set()

    def node(self, kind: str, label: str, **attrs) -> str:
        label = label.strip().rstrip(".,;:")
        prefix = {"person": "p", "project": "proj", "decision": "dec", "team": "team", "page": "page"}.get(kind, kind[:3])
        nid = f"{prefix}_{slug(label)}"
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "kind": kind, "label": label, "attrs": {}}
        self.nodes[nid]["attrs"].update({k: v for k, v in attrs.items() if v})
        return nid

    def edge(self, type_: str, src: str, tgt: str):
        if not src or not tgt or src == tgt:
            return
        key = (type_, src, tgt)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append({"type": type_, "source": src, "target": tgt})

    def merge_partial_people(self) -> None:
        """Merge single-token person refs ('Dana') into a unique full name ('Dana Cole')."""
        persons = [n for n in self.nodes.values() if n["kind"] == "person"]
        for s in [p for p in persons if " " not in p["label"]]:
            if s["id"] not in self.nodes:
                continue
            first = s["label"].lower()
            matches = [p for p in persons if p["id"] != s["id"]
                       and p["id"] in self.nodes and p["label"].lower().split()[0] == first]
            if len(matches) == 1:
                tgt = matches[0]["id"]
                self.nodes[tgt]["attrs"].update({k: v for k, v in s["attrs"].items() if v})
                for e in self.edges:
                    if e["source"] == s["id"]:
                        e["source"] = tgt
                    if e["target"] == s["id"]:
                        e["target"] = tgt
                del self.nodes[s["id"]]
        # de-dup edges after redirects
        seen, kept = set(), []
        for e in self.edges:
            k = (e["type"], e["source"], e["target"])
            if e["source"] == e["target"] or k in seen:
                continue
            seen.add(k)
            kept.append(e)
        self.edges = kept

    def result(self) -> dict:
        return {"nodes": list(self.nodes.values()), "edges": self.edges}


def extract(text: str, doc_title: str = "") -> dict:
    """Extract a graph fragment from text. Returns {nodes, edges}."""
    if settings.live_foundry:
        try:
            return _extract_live(text, doc_title)
        except Exception:
            pass  # fall back to deterministic extractor
    return _extract_local(text, doc_title)


def _is_personish(label: str, b: Builder) -> bool:
    nid = f"p_{slug(label)}"
    return nid in b.nodes


def _extract_local(text: str, doc_title: str) -> dict:
    b = Builder()
    current_team = ""

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        m = TEAM_HEAD.match(line)
        if m:
            current_team = m.group(1).strip()
            b.node("team", current_team)
            continue
        m = PROJECT_DECL.match(line)
        if m:
            b.node("project", m.group(1).strip(), team=current_team)
            continue

        # person declaration: "Name (Role)"
        m = PERSON_DECL.match(line)
        if m:
            pid = b.node("person", m.group(1), role=m.group(2).strip(), team=current_team)
            if current_team:
                b.edge("member_of", pid, b.node("team", current_team))

        # relationships — strip "(Role)" parentheticals so verbs match across them
        rel = re.sub(r"\([^)]*\)", " ", line)
        for rm in OWN_RE.finditer(rel):
            p = b.node("person", rm.group(1)); pr = b.node("project", rm.group(2), team=current_team)
            b.edge("owns", p, pr)
        for rm in OWN_BY_RE.finditer(rel):
            pr = b.node("project", rm.group(1), team=current_team); p = b.node("person", rm.group(2))
            b.edge("owns", p, pr)
        for rm in CONTRIB_RE.finditer(rel):
            p = b.node("person", rm.group(1)); pr = b.node("project", rm.group(2), team=current_team)
            b.edge("contributes_to", p, pr)
        for rm in REPORTS_RE.finditer(rel):
            a = b.node("person", rm.group(1)); mgr = b.node("person", rm.group(2))
            b.edge("reports_to", a, mgr)
        for rm in DEPEND_RE.finditer(rel):
            a = b.node("project", rm.group(1), team=current_team); dep = b.node("project", rm.group(2))
            b.edge("depends_on", a, dep)

        # decisions
        if re.match(r"(?:decision|we decided|decided)\b", line, re.I):
            body = DECISION_RE.match(line).group(1).strip()
            author = None
            mb = DECIDED_BY.search(line)
            affect = None
            if mb:
                body = mb.group(1).strip().rstrip(" ,(")
                author = mb.group(2)
            ma = AFFECTS_RE.search(body)
            if ma:
                affect = ma.group(1)
                body = body[: ma.start()].strip().rstrip(" ,")
            did = b.node("decision", body[:80])
            if author:
                b.edge("made_by", did, b.node("person", author))
            if affect:
                b.edge("decided_for", did, b.node("project", affect, team=current_team))

    # merge first-name refs into full names, then derive teammate edges from shared team
    b.merge_partial_people()
    by_team: dict[str, list[str]] = {}
    for n in b.nodes.values():
        if n["kind"] == "person" and n["attrs"].get("team"):
            by_team.setdefault(n["attrs"]["team"], []).append(n["id"])
    for members in by_team.values():
        for i, a in enumerate(members):
            for c in members[i + 1:]:
                b.edge("teammate", a, c)
                b.edge("teammate", c, a)

    return b.result()


def _extract_live(text: str, doc_title: str) -> dict:
    """Use an Azure AI Foundry model to extract a structured graph from prose."""
    import json as _json

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    client = AIProjectClient(endpoint=settings.ai_project_endpoint, credential=DefaultAzureCredential())
    agent = client.agents.create_agent(
        model=settings.ai_agent_model,
        name="oracle-extractor",
        instructions=(
            "Extract an organizational knowledge graph from the user's text. Return ONLY JSON "
            '{"nodes":[{"id","kind","label","attrs"}],"edges":[{"type","source","target"}]}. '
            "kind in [person,project,decision,team]. edge type in "
            "[owns,contributes_to,depends_on,reports_to,decided_for,made_by,member_of]. "
            "ids are stable slugs like p_jane_doe, proj_checkout. Only include facts present in the text."
        ),
    )
    thread = client.agents.threads.create()
    client.agents.messages.create(thread_id=thread.id, role="user", content=text[:8000])
    run = client.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
    if run.status == "failed":
        raise RuntimeError(run.last_error)
    msgs = client.agents.messages.list(thread_id=thread.id)
    for m in msgs:
        if m.role == "assistant" and m.text_messages:
            raw = m.text_messages[-1].text.value
            raw = raw[raw.find("{"): raw.rfind("}") + 1]
            data = _json.loads(raw)
            for n in data.get("nodes", []):
                n.setdefault("attrs", {})
            return data
    raise RuntimeError("no extraction response")
