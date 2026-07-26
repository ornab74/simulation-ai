#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    (ROOT / "prompts", ROOT / "core/src/simulation_ai/prompt_pack", {".md", ".json"}),
    (ROOT / "schemas", ROOT / "core/src/simulation_ai/schema_pack", {".json"}),
]


def files(directory: Path, suffixes: set[str]) -> dict[str, bytes]:
    return {
        item.name: item.read_bytes()
        for item in sorted(directory.iterdir())
        if item.is_file() and item.suffix in suffixes
    }


def check() -> list[str]:
    problems: list[str] = []
    for source, mirror, suffixes in SOURCES:
        source_files = files(source, suffixes)
        mirror_files = files(mirror, suffixes) if mirror.exists() else {}
        if source_files.keys() != mirror_files.keys():
            problems.append(f"file set differs: {source.relative_to(ROOT)} -> {mirror.relative_to(ROOT)}")
        for name in sorted(source_files.keys() & mirror_files.keys()):
            if source_files[name] != mirror_files[name]:
                problems.append(f"content differs: {name}")
    return problems


def sync() -> None:
    for source, mirror, suffixes in SOURCES:
        mirror.mkdir(parents=True, exist_ok=True)
        for item in mirror.iterdir():
            if item.is_file() and item.suffix in suffixes:
                item.unlink()
        for item in sorted(source.iterdir()):
            if item.is_file() and item.suffix in suffixes:
                shutil.copy2(item, mirror / item.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize repository prompts and schemas into the Python package")
    parser.add_argument("--check", action="store_true", help="fail instead of modifying files")
    args = parser.parse_args()
    if args.check:
        problems = check()
        if problems:
            print("\n".join(problems), file=sys.stderr)
            raise SystemExit(1)
        print("prompt mirrors: synchronized")
        return
    sync()
    problems = check()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(1)
    print("prompt mirrors: synchronized")


if __name__ == "__main__":
    main()
