#!/usr/bin/env python3
"""Orca — the Teamwork Graph for AI agents. Command-line interface.

A pure-stdlib CLI over the Orca backend (the Teamwork Graph + reasoning agent).
It imports the backend package directly and renders graph queries and agent
answers for a clean terminal demo. Runs offline in local-demo mode.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import pathlib

# --- wire up the backend ---------------------------------------------------
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
import app.db as db  # noqa: E402
import app.seed as seed  # noqa: E402
from app.graph import get_graph_for_workspace  # noqa: E402
from app.agent import ask  # noqa: E402


# --- live workspace resolution ---------------------------------------------
# Resolved once in main() from CLI flags / env, defaulting to Contoso demo.
_WS: str = ""
_WS_NAME: str = "Contoso"


def _resolve_workspace(email: str | None) -> tuple[str, str]:
    """Seed demo data and resolve (workspace_id, workspace_label).

    Precedence: --workspace/ORCA_WORKSPACE (explicit id) > --user/ORCA_USER_EMAIL
    (resolve that user's workspace) > Contoso demo (demo@contoso.com).
    """
    seed.seed_all()
    explicit = os.environ.get("ORCA_WORKSPACE")
    if explicit:
        return explicit, "Contoso"
    user_email = email or os.environ.get("ORCA_USER_EMAIL") or "demo@contoso.com"
    name = "Priya Nair" if user_email == "demo@contoso.com" else user_email
    user = db.get_or_create_user(user_email, name)
    ws = db.workspace_for_user(user["id"])
    label = "Contoso" if user_email == "demo@contoso.com" else ws["name"]
    return ws["id"], label


def get_graph():
    """The live, DB-backed Teamwork Graph for the resolved workspace."""
    return get_graph_for_workspace(_WS)


def banner() -> None:
    print(color(bold("  Orca"), C.CYAN) + dim(" · Teamwork Graph")
          + dim(f"  (workspace: {_WS_NAME})"))


# --- color / formatting ----------------------------------------------------
class C:
    """ANSI styling that degrades to no-ops when stdout is not a TTY."""

    _on = sys.stdout.isatty()
    RESET = "\033[0m" if _on else ""
    BOLD = "\033[1m" if _on else ""
    DIM = "\033[2m" if _on else ""
    RED = "\033[31m" if _on else ""
    GREEN = "\033[32m" if _on else ""
    YELLOW = "\033[33m" if _on else ""
    BLUE = "\033[34m" if _on else ""
    MAGENTA = "\033[35m" if _on else ""
    CYAN = "\033[36m" if _on else ""


def bold(s: str) -> str:
    return f"{C.BOLD}{s}{C.RESET}"


def dim(s: str) -> str:
    return f"{C.DIM}{s}{C.RESET}"


def color(s: str, c: str) -> str:
    return f"{c}{s}{C.RESET}"


_MD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"_(.+?)_")


def render_md(s: str) -> str:
    """Render the lightweight markdown the backend emits (**bold**, _italic_)."""
    s = _MD.sub(lambda m: bold(m.group(1)), s)
    s = _MD_ITALIC.sub(lambda m: dim(m.group(1)), s)
    return s


def header(title: str) -> None:
    print()
    print(color(bold(f"  {title}  "), C.CYAN))
    print(dim("  " + "─" * (len(title) + 2)))


def err(msg: str) -> None:
    print(color("✗ " + msg, C.RED), file=sys.stderr)


def kind_badge(kind: str) -> str:
    palette = {
        "person": C.GREEN,
        "project": C.BLUE,
        "decision": C.MAGENTA,
        "page": C.YELLOW,
        "team": C.CYAN,
    }
    return color(f"[{kind}]", palette.get(kind, C.DIM))


# --- helpers ---------------------------------------------------------------
def resolve_or_die(g, query: str):
    node = g.resolve(query)
    if node is None:
        err(f"Could not find anything matching {query!r} in the Teamwork Graph.")
        hits = g.search(query, limit=5)
        if hits:
            print(dim("  Did you mean:"), file=sys.stderr)
            for n in hits:
                print(dim(f"    • {n.label} ({n.kind})"), file=sys.stderr)
        sys.exit(2)
    return node


def label_of(g, nid: str) -> str:
    n = g.get(nid)
    return n.label if n else nid


# --- subcommands -----------------------------------------------------------
def cmd_ask(args) -> int:
    result = ask(args.question, workspace_id=_WS).to_dict()

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    banner()
    if result.get("refused"):
        header("Orca refused")
        print("  " + render_md(result["answer"]))
        return 0

    header("Answer")
    for line in result["answer"].splitlines():
        print("  " + render_md(line))

    print()
    conf = result.get("confidence", 0.0)
    conf_c = C.GREEN if conf >= 0.75 else (C.YELLOW if conf >= 0.5 else C.RED)
    print(
        "  "
        + dim("confidence ")
        + color(f"{conf:.0%}", conf_c)
        + dim("   intent ")
        + bold(result.get("intent", "general"))
        + dim("   mode ")
        + bold(result.get("mode", "local-demo"))
    )

    trace = result.get("reasoning_trace", [])
    if trace:
        if args.trace:
            header("Reasoning trace")
            for i, step in enumerate(trace, 1):
                print(f"  {color(str(i) + '.', C.CYAN)} " + render_md(step))
        else:
            print()
            print(dim("  reasoning: " + str(len(trace)) + " steps (use --trace to expand)"))
            for step in trace[:2]:
                print(dim("    • " + re.sub(r"[*_`]", "", step)))

    citations = result.get("citations", [])
    if citations:
        header("Citations")
        for c in citations:
            print(
                f"  {color('[' + str(c['n']) + ']', C.YELLOW)} "
                + bold(c["label"])
                + dim(f"  ({c.get('source', '')}, score {c.get('score', 0):.2f})")
            )
            excerpt = (c.get("excerpt") or "").strip()
            if excerpt:
                print(dim("      " + excerpt))

    followups = result.get("suggested_questions", [])
    if followups:
        header("Related — ask next")
        for i, q in enumerate(followups, 1):
            print(f"  {color(str(i) + '.', C.CYAN)} {q}")
        print()
        print(dim("  run:  oracle ask \"<question>\""))
    return 0


def cmd_who_owns(args) -> int:
    g = get_graph()
    node = resolve_or_die(g, args.project)
    header(f"Ownership — {node.label}")
    if node.attrs.get("summary"):
        print(dim("  " + node.attrs["summary"]))
        print()

    owners = g.owners_of(node.id)
    contribs = g.contributors_of(node.id)

    print("  " + bold("Owners"))
    if owners:
        for oid in owners:
            o = g.get(oid)
            print(f"    {color('●', C.GREEN)} {o.label} " + dim(f"— {o.attrs.get('role', '')}"))
    else:
        print(dim("    (unassigned)"))

    print()
    print("  " + bold("Contributors"))
    if contribs:
        for cid in contribs:
            c = g.get(cid)
            print(f"    {color('○', C.BLUE)} {c.label} " + dim(f"— {c.attrs.get('role', '')}"))
    else:
        print(dim("    (none)"))
    return 0


def cmd_deps(args) -> int:
    g = get_graph()
    node = resolve_or_die(g, args.project)
    transitive = not args.direct
    deps = g.dependencies_of(node.id, transitive=transitive)
    direct = set(g.dependencies_of(node.id, transitive=False))

    scope = "direct" if args.direct else "transitive"
    header(f"Dependencies — {node.label} ({scope})")
    if not deps:
        print(dim("  No dependencies recorded — nothing this project waits on."))
        return 0
    for did in deps:
        d = g.get(did)
        tag = dim("(direct)") if did in direct else dim("(transitive)")
        print(f"  {color('→', C.BLUE)} {bold(d.label)} {tag} " + dim(f"— {d.attrs.get('status', '')}"))
    return 0


def cmd_blockers(args) -> int:
    g = get_graph()
    node = resolve_or_die(g, args.project)
    header(f"Blockers — {node.label}")
    blockers = g.blockers_for(node.id)
    if not blockers:
        print(color("  ✓ Nothing is blocking it right now.", C.GREEN))
        return 0
    print(dim("  Talk to these dependency owners to unblock it:"))
    print()
    seen = set()
    for b in blockers:
        owner = g.get(b["owner"])
        dep = g.get(b["dependency"])
        key = (b["owner"], b["dependency"])
        if key in seen:
            continue
        seen.add(key)
        print(
            f"  {color('●', C.YELLOW)} {bold(owner.label)} "
            + dim(f"— {owner.attrs.get('role', '')}")
        )
        print(dim(f"      owns {dep.label} (a dependency)"))
    return 0


def cmd_path(args) -> int:
    g = get_graph()
    a = resolve_or_die(g, getattr(args, "from"))
    b = resolve_or_die(g, args.to)
    header(f"Path — {a.label} → {b.label}")
    path = g.find_path(a.id, b.id)
    if path is None:
        print(color(f"  No connection found within 6 hops.", C.RED))
        return 0
    if not path:
        print(dim("  Same node."))
        return 0

    from app.graph import EDGE_PHRASING

    print(f"  {kind_badge(a.kind)} {bold(a.label)}")
    for i, step in enumerate(path, 1):
        forward, reverse = EDGE_PHRASING.get(step["edge"], (step["edge"], step["edge"]))
        phrase = forward if step.get("direction", "out") == "out" else reverse
        tgt = g.get(step["to"])
        print(dim(f"      │  {phrase}"))
        print(f"  {color(str(i) + '.', C.CYAN)} {kind_badge(tgt.kind)} {bold(tgt.label)}")
    return 0


def cmd_node(args) -> int:
    g = get_graph()
    node = resolve_or_die(g, args.id)
    header(f"{node.label}")
    print(f"  {kind_badge(node.kind)} " + dim(f"id={node.id}"))
    if node.attrs:
        print()
        for k, v in node.attrs.items():
            if v:
                print("  " + dim(f"{k}: ") + str(v))

    nbrs = g.neighbors(node.id, edge_types=tuple(
        t for t in ["owns", "contributes_to", "depends_on", "decided_for",
                    "made_by", "documents", "reports_to", "manages"]))
    if nbrs:
        print()
        print("  " + bold("Neighbors"))
        for nb in nbrs:
            t = g.get(nb["node"])
            print(f"    {dim(nb['phrase'])} {t.label} {kind_badge(t.kind)}")
    return 0


def cmd_search(args) -> int:
    g = get_graph()
    hits = g.search(args.text, limit=args.limit)
    header(f"Search — {args.text!r}")
    if not hits:
        print(dim("  No matching nodes."))
        return 0
    for n in hits:
        extra = n.attrs.get("role") or n.attrs.get("status") or n.attrs.get("summary") or ""
        print(f"  {kind_badge(n.kind)} {bold(n.label)} " + dim(f"— {extra}"[:80]))
    return 0


def cmd_stats(args) -> int:
    g = get_graph()
    s = g.stats()
    from app.config import settings

    banner()
    header("Teamwork Graph stats")
    print(f"  {bold(str(s['nodes']))} nodes   {bold(str(s['edges']))} edges")
    print()
    for kind, count in sorted(s["by_kind"].items(), key=lambda x: -x[1]):
        bar = color("█" * count, C.CYAN)
        print(f"  {kind_badge(kind):<22} {bar} {dim(str(count))}")
    print()
    print(dim("  backend mode: ") + bold(settings.mode))
    return 0


# --- argument parsing ------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="oracle",
        description="Orca — the Teamwork Graph for AI agents (agent terminal).",
    )
    p.add_argument("--workspace", metavar="WS_ID",
                   help="explicit workspace id (overrides ORCA_WORKSPACE)")
    p.add_argument("--user", metavar="EMAIL", dest="user_email",
                   help="resolve a user's workspace by email "
                        "(default: demo@contoso.com / ORCA_USER_EMAIL)")
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("ask", help="ask the reasoning agent a question")
    pa.add_argument("question")
    pa.add_argument("--json", action="store_true", help="dump raw JSON")
    pa.add_argument("--trace", action="store_true", help="always show the full reasoning trace")
    pa.set_defaults(func=cmd_ask)

    pw = sub.add_parser("who-owns", help="owners and contributors of a project")
    pw.add_argument("project")
    pw.set_defaults(func=cmd_who_owns)

    pd = sub.add_parser("deps", help="dependency projects (transitive by default)")
    pd.add_argument("project")
    pd.add_argument("--direct", action="store_true", help="direct dependencies only")
    pd.set_defaults(func=cmd_deps)

    pb = sub.add_parser("blockers", help="who to talk to to unblock a project")
    pb.add_argument("project")
    pb.set_defaults(func=cmd_blockers)

    pp = sub.add_parser("path", help="connection path between two nodes")
    pp.add_argument("from")
    pp.add_argument("to")
    pp.set_defaults(func=cmd_path)

    pn = sub.add_parser("node", help="node attributes and neighbors")
    pn.add_argument("id")
    pn.set_defaults(func=cmd_node)

    ps = sub.add_parser("search", help="search for matching nodes")
    ps.add_argument("text")
    ps.add_argument("--limit", type=int, default=8)
    ps.set_defaults(func=cmd_search)

    pst = sub.add_parser("stats", help="graph stats and backend mode")
    pst.set_defaults(func=cmd_stats)

    return p


def main(argv=None) -> int:
    global _WS, _WS_NAME
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "workspace", None):
        os.environ["ORCA_WORKSPACE"] = args.workspace
    _WS, _WS_NAME = _resolve_workspace(getattr(args, "user_email", None))
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
