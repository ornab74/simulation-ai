#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/core/src${PYTHONPATH:+:$PYTHONPATH}"
python -m compileall -q "$ROOT/core/src"
python "$ROOT/scripts/sync-prompt-pack.py" --check
python -m simulation_ai.prompts --validate
python -m unittest discover -s "$ROOT/core/tests" -v
python - <<'PY'
from pathlib import Path
import tempfile
from simulation_ai.engine import SurfaceEngine

with tempfile.TemporaryDirectory() as directory:
    engine = SurfaceEngine(Path(directory))
    snapshot = engine.snapshot()
    assert snapshot["replay"]["verified"]
    assert snapshot["state"]["provenance"]["pixel_state_authoritative"] is False
    assert snapshot["prompt_pack"]["valid"] is True
    assert snapshot["prompt_pack"]["callable_prompt_count"] == 68
print("surface smoke: verified")
PY
