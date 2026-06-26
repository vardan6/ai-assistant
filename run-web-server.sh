#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

HOST="${AI_ASSISTANT_HOST:-127.0.0.1}"
PORT="${AI_ASSISTANT_PORT:-9006}"

exec .venv/bin/python -m uvicorn app.server:app --host "$HOST" --port "$PORT"
