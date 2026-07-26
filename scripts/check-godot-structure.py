#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "ui").glob("*.gd")) + sorted((ROOT / "systems").glob("*.gd"))


def scan(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    stack: list[tuple[str, int]] = []
    matching = {")": "(", "]": "[", "}": "{"}
    in_string = False
    escaped = False
    line = 1
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\n":
            line += 1
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "#":
            newline = text.find("\n", index)
            if newline < 0:
                break
            index = newline
            continue
        if char in "([{":
            stack.append((char, line))
        elif char in ")]}":
            if not stack or stack[-1][0] != matching[char]:
                problems.append(f"line {line}: unmatched {char}")
            else:
                stack.pop()
        index += 1
    if in_string:
        problems.append("unterminated string")
    for opener, opener_line in stack:
        problems.append(f"line {opener_line}: unmatched {opener}")
    functions = re.findall(r"(?m)^func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text)
    duplicates = [name for name, count in Counter(functions).items() if count > 1]
    for name in duplicates:
        problems.append(f"duplicate function: {name}")
    return problems


def main() -> int:
    problems: list[str] = []
    for path in FILES:
        for problem in scan(path):
            problems.append(f"{path.relative_to(ROOT)}: {problem}")
    for scene in (ROOT / "ui").glob("*.tscn"):
        text = scene.read_text(encoding="utf-8")
        for resource in re.findall(r'path="res://([^"]+)"', text):
            if not (ROOT / resource).exists():
                problems.append(f"{scene.relative_to(ROOT)}: missing resource {resource}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"Godot structural checks passed for {len(FILES)} scripts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
