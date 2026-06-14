"""A tiny MCP server that exposes a few text resources.

Used to demonstrate Orca's MCP *client* connector ingesting from any MCP server
fully offline. The same client works against official servers (filesystem,
GitHub, Notion, etc.) — just point the connector at their launch command.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("orca-demo-docs")


@mcp.resource("doc://atlas-team")
def atlas_team() -> str:
    return (
        "# Team: Atlas\n"
        "Dana Cole (Engineer) works on Search Revamp\n"
        "Mo Park (PM) owns Search Revamp\n"
        "Search Revamp depends on Index Service\n"
        "Index Service depends on Data Lake\n"
        "Dana reports to Mo Park\n"
        "Decision: Adopt vector search for Search Revamp, decided by Mo Park\n"
    )


@mcp.resource("doc://atlas-runbook")
def atlas_runbook() -> str:
    return (
        "# Search Revamp Runbook\n"
        "Rollout is gated on recall@10 and p95 latency. "
        "On-call rotates weekly; Sev1 pages Mo Park.\n"
    )


if __name__ == "__main__":
    mcp.run()
