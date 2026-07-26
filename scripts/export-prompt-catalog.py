#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "prompts/manifest.json"
OUTPUT = ROOT / "docs/PROMPT_CATALOG.md"


def code_list(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "—"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    prompts = manifest["prompts"]
    groups: dict[str, list[dict]] = defaultdict(list)
    for prompt in prompts:
        groups[prompt["stage"]].append(prompt)
    lines = [
        "# Prompt Catalog",
        "",
        "> Generated from `prompts/manifest.json` by `scripts/export-prompt-catalog.py`.",
        "",
        f"Pack: `{manifest['pack_id']}` v`{manifest['pack_version']}`",
        f"Roles: **{len(prompts)}** total, **{sum(bool(p.get('callable')) for p in prompts)}** callable",
        f"Workflows: **{len(manifest['workflows'])}**",
        "",
        "Every callable role is proposal, observation, review, routing, or verification only. A deterministic gate remains mandatory.",
        "",
    ]
    for stage in sorted(groups):
        lines += [f"## {stage.replace('_', ' ').title()}", "", "| Role | Authority | Risk | Runtime | Output schema | Tasks |", "|---|---|---:|---|---|---|"]
        for prompt in sorted(groups[stage], key=lambda item: item["id"]):
            schema = f"`{prompt['output_schema']}`" if prompt.get("output_schema") else "—"
            lines.append(
                f"| [`{prompt['id']}`](../prompts/{prompt['file']}) | `{prompt['authority']}` | `{prompt.get('risk_level', 'medium')}` | `{prompt.get('preferred_model_class', prompt['runtime_class'])}` | {schema} | {code_list(prompt.get('task_types', []))} |"
            )
        lines.append("")
    lines += ["# Workflows", ""]
    for workflow in manifest["workflows"]:
        lines += [
            f"## `{workflow['id']}` — {workflow['title']}",
            "",
            "```text",
            " -> ".join(workflow["prompts"]),
            "```",
            "",
            f"Deterministic gates: {code_list(workflow.get('deterministic_gates', []))}",
            "",
        ]
    OUTPUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
