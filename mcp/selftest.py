"""Self-test for the Orca MCP server tools.

Imports the tool callables from server.py and exercises a representative set,
printing the results. Run with the backend venv python:

    /Users/preethams/Developer/oracle/backend/.venv/bin/python selftest.py
"""
from __future__ import annotations

import json

import server


def show(title: str, value) -> None:
    print("=" * 72)
    print(title)
    print("-" * 72)
    print(json.dumps(value, indent=2, default=str)[:2400])
    print()


def call(tool):
    """FastMCP wraps functions; .fn is the original callable (fallback to call)."""
    return getattr(tool, "fn", tool)


if __name__ == "__main__":
    show(
        'ask_oracle("Who do I need to unblock Checkout v2?")',
        call(server.ask_oracle)("Who do I need to unblock Checkout v2?"),
    )
    show('who_owns("Identity Tokens")', call(server.who_owns)("Identity Tokens"))
    show(
        'find_path("Priya Nair", "David Chen")',
        call(server.find_path)("Priya Nair", "David Chen"),
    )
    show('blockers_for("Checkout v2")', call(server.blockers_for)("Checkout v2"))

    print("Self-test completed.")
