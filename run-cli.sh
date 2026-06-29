#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

HOST="${AI_ASSISTANT_HOST:-127.0.0.1}"
PORT="${AI_ASSISTANT_PORT:-9006}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
BASE_URL="http://${HOST}:${PORT}"
SERVER_PID=""

require_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
}

server_ready() {
  "$PYTHON_BIN" - "$BASE_URL" <<'PY'
import json
import sys
import urllib.request

try:
    base_url = sys.argv[1]
    with urllib.request.urlopen(base_url + "/health", timeout=1.0) as resp:
        health = json.loads(resp.read().decode())
    with urllib.request.urlopen(base_url + "/api/settings/ui", timeout=1.0) as resp:
        ui = json.loads(resp.read().decode())

    is_our_server = (
        health.get("ok") is True
        and isinstance(health.get("dataset_today"), str)
        and "default_gating_mode" in ui
        and "verbose_trace" in ui
    )
    raise SystemExit(0 if is_our_server else 1)
except Exception:
    raise SystemExit(1)
PY
}

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT

require_file "$PYTHON_BIN"
require_file "app/cli.py"
require_file "app/server.py"

if server_ready; then
  echo "Using existing server at ${BASE_URL}"
else
  echo "Starting server at ${BASE_URL}"
  "$PYTHON_BIN" -m uvicorn app.server:app --host "$HOST" --port "$PORT" &
  SERVER_PID="$!"

  for _ in $(seq 1 50); do
    if server_ready; then
      break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      wait "$SERVER_PID" || true
      echo "Failed to start server at ${BASE_URL}. Another process may already be using that port." >&2
      exit 1
    fi
    sleep 0.2
  done

  if ! server_ready; then
    echo "Server did not become ready at ${BASE_URL}" >&2
    exit 1
  fi
fi

exec "$PYTHON_BIN" -m app.cli "$@"
