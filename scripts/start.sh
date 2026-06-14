#!/usr/bin/env bash
# Orca — one-command launcher. Boots the backend (:8000) and web app (:5500).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "▶ Orca — starting…"
# backend
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements-demo.txt 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/orca_api.log 2>&1 &
echo "  backend  → http://127.0.0.1:8000  (log: /tmp/orca_api.log)"

# web
cd "$ROOT/web"
pkill -f "http.server 5500" 2>/dev/null || true
nohup python3 -m http.server 5500 > /tmp/orca_web.log 2>&1 &
echo "  web      → http://127.0.0.1:5500"

sleep 2
curl -s -o /dev/null -w "  health   → %{http_code}\n" http://127.0.0.1:8000/health || echo "  backend not responding yet"
echo "✓ Open http://127.0.0.1:5500 and click 'Sign in with Microsoft' (demo workspace)."
echo "  CLI:  $ROOT/cli/oracle ask \"Who do I need to unblock Checkout v2?\""
echo "  MCP:  $ROOT/backend/.venv/bin/python $ROOT/mcp/server.py"
