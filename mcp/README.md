# Orca MCP Server — the Teamwork Graph for AI agents

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server that
exposes **Orca's Teamwork Graph** — the org graph of people, projects,
decisions, pages and teams plus typed relationships — and its multi-hop
reasoning agent as tools. Any MCP client (VS Code, Copilot, etc.) can
plug in and reason over the org graph: "who do I need to unblock X", "who owns
Y", "how is person A connected to person B", and so on.

- **Transport:** stdio
- **Implementation:** official Python MCP SDK (`mcp[cli]`,
  `mcp.server.fastmcp.FastMCP`). No hand-rolled JSON-RPC fallback was needed —
  the SDK installs and runs fine on this Python 3.14 environment.
- **Offline:** the graph runs fully in "local-demo" mode — no cloud creds
  required.

## How it works

`server.py` adds the Orca backend package (`../backend`) to `sys.path` at
runtime and calls into it directly, reading the **live SQLite-backed workspace
graph** (`backend/oracle.db`):

- On startup it calls `app.seed.seed_all()` (idempotent) and resolves the
  default workspace — the Contoso demo (`demo@contoso.com`, Priya Nair).
- `app.graph.get_graph_for_workspace(ws)` — the `TeamworkGraph` query
  primitives over that workspace's live nodes/edges.
- `app.agent.ask(question, workspace_id=ws)` — the full multi-hop reasoning
  pipeline, grounded against the workspace graph + ingested documents.

To point at a different workspace, set `ORCA_WORKSPACE` (an explicit workspace
id) or `ORCA_USER_EMAIL` (resolve that user's workspace) in the server's
environment.

Human names/labels passed to tools are resolved to graph nodes via
`graph.resolve(...)` / `graph.search(...)`; when a name can't be resolved the
tool returns a helpful `{"error": ..., "did_you_mean": [...]}` dict instead of
failing. Human-facing fields return labels (not raw ids) where practical.

## Tools

| Tool | Description |
| --- | --- |
| `ask_oracle(question)` / `ask_orca(question)` | Ask the Orca reasoning agent a natural-language question (the two names are aliases). Returns the full agent result (answer, citations, reasoning_trace, graph_evidence, work_iq, confidence, intent, mode, refused). |
| `search_graph(query, limit=8)` | Full-text search the graph for matching nodes. |
| `get_node(node_id)` | Look up a node (by id or label) plus its immediate neighbors. |
| `find_path(from_node, to_node)` | Shortest path (≤6 hops) between two entities, as human-readable steps. |
| `who_owns(project)` | Owners + contributors of a project. |
| `dependencies_of(project, transitive=True)` | Projects a project depends on (direct + transitive). |
| `blockers_for(project)` | Who to talk to in order to unblock a project. |
| `decisions_for(project)` | Decisions affecting a project and who made them. |

## Run

Use the backend venv (it already has both the backend deps and `mcp[cli]`):

```bash
/Users/preethams/Developer/oracle/backend/.venv/bin/python /Users/preethams/Developer/oracle/mcp/server.py
```

The process speaks MCP over stdio and waits for a client. To exercise the tool
logic directly without a client, run the self-test:

```bash
/Users/preethams/Developer/oracle/backend/.venv/bin/python /Users/preethams/Developer/oracle/mcp/selftest.py
```

### Fresh install (optional)

If you'd rather use a separate environment, install both the SDK and the
backend's own requirements into it:

```bash
pip install -r /Users/preethams/Developer/oracle/mcp/requirements.txt
pip install -r /Users/preethams/Developer/oracle/backend/requirements.txt
```

## Client configuration

Point your MCP client at the venv python and the absolute path to `server.py`.

### Desktop MCP client

Add this to your MCP client's server config (a `mcpServers` map):

```json
{
  "mcpServers": {
    "orca-teamwork-graph": {
      "command": "/Users/preethams/Developer/oracle/backend/.venv/bin/python",
      "args": ["/Users/preethams/Developer/oracle/mcp/server.py"]
    }
  }
}
```

### VS Code (MCP)

In `.vscode/mcp.json` (or your user `mcp.json`):

```json
{
  "servers": {
    "orca-teamwork-graph": {
      "type": "stdio",
      "command": "/Users/preethams/Developer/oracle/backend/.venv/bin/python",
      "args": ["/Users/preethams/Developer/oracle/mcp/server.py"]
    }
  }
}
```

After saving, restart the client. The tools above will appear under the
`orca-teamwork-graph` server.

## Example prompts to try in a client

- "Who do I need to unblock Checkout v2?"
- "Who owns Identity Tokens?"
- "How is Priya Nair connected to David Chen?"
- "What decisions affect Checkout v2 and who made them?"
- "What does Mobile Wallet depend on?"
