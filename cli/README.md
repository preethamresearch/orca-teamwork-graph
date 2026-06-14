# Orca CLI

A command-line interface for **Orca — the Teamwork Graph for AI agents**.

The "agent terminal" for Orca: it talks directly to the Orca Python backend
(the Teamwork Graph + reasoning agent) and reads the **live SQLite-backed
workspace graph** (`backend/oracle.db`), rendering graph queries and agent
answers for the terminal. Pure stdlib (just `argparse`) — no third-party
dependencies. Runs fully offline in local-demo mode.

On startup the CLI seeds the demo data (idempotent) and resolves a workspace,
defaulting to the **Contoso** demo (`demo@contoso.com`, Priya Nair). The `ask`
and `stats` commands print a small header, e.g.
`Orca · Teamwork Graph  (workspace: Contoso)`.

### Choosing a workspace

```bash
./oracle --user alex@northwind.com stats   # resolve another user's workspace
./oracle --workspace ws_abc123 stats       # explicit workspace id
```

Equivalent env vars are also honored: `ORCA_USER_EMAIL` and `ORCA_WORKSPACE`
(an explicit `--workspace` takes precedence).

## Setup

The CLI runs against the backend's virtualenv. The `oracle` wrapper script
already points at `../backend/.venv/bin/python`, so there is nothing to install:

```bash
cd cli
./oracle stats
```

If you prefer to invoke Python directly:

```bash
../backend/.venv/bin/python oracle.py stats
```

Colors are emitted only when stdout is a TTY; piping or redirecting output
produces clean, plain text.

## Commands

### `oracle ask "<question>"`

Run the reasoning agent. Prints the answer, confidence / intent / mode, a
compact reasoning trace, and citations.

```bash
./oracle ask "Who do I need to unblock Checkout v2?"
./oracle ask "What does Checkout v2 depend on?" --trace   # full numbered trace
./oracle ask "unblock checkout" --json                    # raw JSON result
```

- `--trace` always expands the full numbered reasoning trace.
- `--json` dumps the raw `AgentResult` as JSON (answer, citations,
  reasoning_trace, graph_evidence, work_iq, confidence, intent, mode, refused).

### `oracle who-owns "<project>"`

Owners and contributors of a project. Resolves a human label to its node id.

```bash
./oracle who-owns "Identity Tokens"
```

### `oracle deps "<project>" [--direct]`

Projects a project depends on. Transitive by default; `--direct` limits to
immediate dependencies.

```bash
./oracle deps "Checkout v2"
./oracle deps "Checkout v2" --direct
```

### `oracle blockers "<project>"`

Who you need to talk to to unblock a project (owners of every transitive
dependency).

```bash
./oracle blockers "Checkout v2"
```

### `oracle path "<from>" "<to>"`

Shortest connection path between two nodes (people, projects, etc.). Resolves
labels to ids.

```bash
./oracle path "Priya Nair" "David Chen"
```

### `oracle node "<id-or-label>"`

A node's attributes and its immediate graph neighborhood.

```bash
./oracle node "Checkout v2"
./oracle node "Lena Petrova"
```

### `oracle search "<text>"`

Nodes matching free text, ranked. `--limit` caps the number of results
(default 8).

```bash
./oracle search "identity"
./oracle search "platform" --limit 3
```

### `oracle stats`

Graph statistics (node/edge counts, breakdown by kind) and the backend mode
(`local-demo` or `live-foundry`).

```bash
./oracle stats
```

## Notes

- Labels are resolved case-insensitively (exact match, then substring). If a
  name can't be resolved the CLI prints a friendly error plus "did you mean"
  suggestions and exits with a non-zero status.
- The backend is imported by adding `../backend` to `sys.path`; the CLI reads
  from the backend package but never modifies it.
