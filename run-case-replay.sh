#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

HOST="${AI_ASSISTANT_HOST:-127.0.0.1}"
PORT="${AI_ASSISTANT_PORT:-9006}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
BASE_URL="http://${HOST}:${PORT}"
STARTUP_TIMEOUT_SECS="${AI_ASSISTANT_STARTUP_TIMEOUT_SECS:-30}"
READINESS_TIMEOUT_SECS="${AI_ASSISTANT_READINESS_TIMEOUT_SECS:-1.5}"
SERVER_PID=""
SERVER_LOG=""

require_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    echo "Missing required path: $path" >&2
    exit 1
  fi
}

server_ready() {
  "$PYTHON_BIN" - "$BASE_URL" "$READINESS_TIMEOUT_SECS" <<'PY'
import json
import sys
import urllib.request

try:
    base_url = sys.argv[1]
    timeout = float(sys.argv[2])
    with urllib.request.urlopen(base_url + "/health", timeout=timeout) as resp:
        health = json.loads(resp.read().decode())
    with urllib.request.urlopen(base_url + "/api/settings/ui", timeout=timeout) as resp:
        ui = json.loads(resp.read().decode())
    with urllib.request.urlopen(base_url + "/api/chat/commands", timeout=timeout) as resp:
        commands = json.loads(resp.read().decode())
    with urllib.request.urlopen(base_url + "/api/sessions", timeout=timeout) as resp:
        sessions = json.loads(resp.read().decode())

    is_our_server = (
        health.get("ok") is True
        and isinstance(health.get("dataset_today"), str)
        and "default_gating_mode" in ui
        and "verbose_trace" in ui
        and isinstance(commands.get("commands"), list)
        and isinstance(sessions.get("sessions"), list)
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
  if [[ -n "$SERVER_LOG" && -f "$SERVER_LOG" ]]; then
    rm -f "$SERVER_LOG"
  fi
}

trap cleanup EXIT

require_file "$PYTHON_BIN"
require_file "app/case_replay.py"
require_file "app/server.py"

if server_ready; then
  echo "Using existing server at ${BASE_URL}" >&2
else
  echo "Starting server at ${BASE_URL}" >&2
  SERVER_LOG="$(mktemp -t ai-assistant-replay-server.XXXXXX.log)"
  "$PYTHON_BIN" -m uvicorn app.server:app --host "$HOST" --port "$PORT" >"$SERVER_LOG" 2>&1 &
  SERVER_PID="$!"

  start_ts="$(date +%s)"
  while true; do
    if server_ready; then
      break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      wait "$SERVER_PID" || true
      echo "Failed to start server at ${BASE_URL}. Another process may already be using that port." >&2
      if [[ -f "$SERVER_LOG" ]]; then
        tail -n 40 "$SERVER_LOG" >&2 || true
      fi
      exit 1
    fi
    now_ts="$(date +%s)"
    if (( now_ts - start_ts >= STARTUP_TIMEOUT_SECS )); then
      break
    fi
    sleep 0.5
  done

  if ! server_ready; then
    echo "Server did not become ready at ${BASE_URL} within ${STARTUP_TIMEOUT_SECS}s" >&2
    if [[ -f "$SERVER_LOG" ]]; then
      echo "--- server log tail ---" >&2
      tail -n 40 "$SERVER_LOG" >&2 || true
    fi
    exit 1
  fi
fi

exec "$PYTHON_BIN" -m app.case_replay --server "$BASE_URL" "$@"
