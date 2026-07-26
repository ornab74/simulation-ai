#!/usr/bin/env python3
"""Portable Simulation AI runtime bootstrap and Surface Core launcher."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import subprocess
import venv

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
VENV = RUNTIME / "venv"

def python_path() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("[simulation-ai] $", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)

def ensure_runtime(with_gemma: bool) -> Path:
    interpreter = python_path()
    if not interpreter.exists():
        print(f"[simulation-ai] creating isolated Python runtime ({platform.system()})", flush=True)
        RUNTIME.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=(os.name != "nt")).create(VENV)
    run([str(interpreter), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"])
    run([str(interpreter), "-m", "pip", "install", "--disable-pip-version-check", "-e", str(ROOT / "core")])
    gemma_installed = False
    if with_gemma:
        probe = subprocess.run(
            [str(interpreter), "-c", "import litert_lm"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        gemma_installed = probe.returncode == 0
    if with_gemma and not gemma_installed:
        run([str(interpreter), "-m", "pip", "install", "--disable-pip-version-check", "litert-lm==0.10.1"])
    return interpreter

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-gemma", action="store_true")
    parser.add_argument("--run-core", action="store_true")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SIMULATION_AI_PORT", "47890")))
    parser.add_argument("--home", type=Path, default=ROOT / ".simulation-ai")
    parser.add_argument("--models", type=Path, default=ROOT / "models")
    args = parser.parse_args()
    interpreter = ensure_runtime(args.with_gemma)
    if args.run_core:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "core" / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        run([
            str(interpreter), "-m", "simulation_ai.server", "--host", "127.0.0.1",
            "--port", str(args.port), "--home", str(args.home), "--models", str(args.models),
        ], env=env)
    else:
        print(f"[simulation-ai] ready: {interpreter}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
