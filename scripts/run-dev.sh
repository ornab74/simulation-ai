#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${SIMULATION_AI_HOST:-127.0.0.1}"
PORT="${SIMULATION_AI_PORT:-47890}"
HOME_DIR="${SIMULATION_AI_HOME:-$ROOT/.simulation-ai}"

RUNTIME_PYTHON="${SIMULATION_AI_PYTHON:-$ROOT/.runtime/venv/bin/python}"
if [ ! -x "$RUNTIME_PYTHON" ]; then
  BOOTSTRAP_ARGS=()
  if [ "${SIMULATION_AI_WITH_GEMMA:-0}" = "1" ]; then
    BOOTSTRAP_ARGS+=("--with-gemma")
  fi
  python3 "$ROOT/scripts/bootstrap_runtime.py" "${BOOTSTRAP_ARGS[@]}"
fi

export PYTHONPATH="$ROOT/core/src${PYTHONPATH:+:$PYTHONPATH}"

PYTHONPATH="$ROOT/core/src${PYTHONPATH:+:$PYTHONPATH}" "$RUNTIME_PYTHON" -m simulation_ai.server --host "$HOST" --port "$PORT" --home "$HOME_DIR" &
CORE_PID=$!

cleanup() {
  kill "$CORE_PID" 2>/dev/null || true
  wait "$CORE_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 40); do
  if python - <<PY >/dev/null 2>&1
from urllib.request import Request, urlopen
import os
headers = {}
token = os.environ.get("SIMULATION_AI_TOKEN", "")
if token:
    headers["Authorization"] = f"Bearer {token}"
urlopen(Request("http://$HOST:$PORT/health", headers=headers), timeout=0.25).read()
PY
  then
    break
  fi
  sleep 0.1
done

if command -v godot >/dev/null 2>&1; then
  godot --path "$ROOT"
elif command -v godot4 >/dev/null 2>&1; then
  godot4 --path "$ROOT"
else
  echo "Simulation AI Surface Core: http://$HOST:$PORT"
  echo "Godot 4.6+ was not found. Open this project manually: $ROOT"
  wait "$CORE_PID"
fi
