#!/usr/bin/env bash
# Starts (or restarts) the Kudos FastAPI dev server on http://localhost:8000
# Usage: ./scripts/start.sh [--reload]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="$REPO_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "Virtualenv not found at $PYTHON. Create it first, e.g.:" >&2
    echo "  python -m venv .venv" >&2
    echo "  .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

echo "Freeing port 8000..."
lsof -ti tcp:8000 | xargs -r kill -9 2>/dev/null || true
sleep 0.5

UVICORN_ARGS=(-m uvicorn app.main:app --host 127.0.0.1 --port 8000)
if [[ "${1:-}" == "--reload" ]]; then
    UVICORN_ARGS+=(--reload)
fi

echo "Starting Kudos server at http://localhost:8000 ..."
exec "$PYTHON" "${UVICORN_ARGS[@]}"
