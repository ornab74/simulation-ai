#!/usr/bin/env python3
"""Build the local Surface Core into a standalone executable with PyInstaller."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "backend")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    name = "simulation-ai-core.exe" if sys.platform == "win32" else "simulation-ai-core"
    command = [
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--onefile",
        "--name", name.removesuffix(".exe"), "--paths", str(ROOT / "core" / "src"),
        "--distpath", str(args.output), "--workpath", str(ROOT / ".build" / "pyinstaller"),
        "--specpath", str(ROOT / ".build" / "pyinstaller"), str(ROOT / "core" / "src" / "simulation_ai" / "server.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
