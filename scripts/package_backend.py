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
    parser.add_argument("--name", default="", help="Override the backend executable name")
    parser.add_argument("--with-gemma", action="store_true", help="Bundle the LiteRT-LM Python API and native library")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    name = args.name.strip() or ("simulation-ai-core.exe" if sys.platform == "win32" else "simulation-ai-core")
    command = [
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--onefile",
        "--name", name.removesuffix(".exe"), "--paths", str(ROOT / "core" / "src"),
        "--collect-all", "simulation_ai",
        "--distpath", str(args.output), "--workpath", str(ROOT / ".build" / "pyinstaller"),
        "--specpath", str(ROOT / ".build" / "pyinstaller"), str(ROOT / "scripts" / "package_backend_entry.py"),
    ]
    if args.with_gemma:
        command[4:4] = [
            "--collect-all", "litert_lm",
            "--copy-metadata", "litert-lm",
            "--copy-metadata", "litert-lm-api",
            "--hidden-import", "litert_lm",
        ]
    subprocess.run(command, cwd=ROOT, check=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
