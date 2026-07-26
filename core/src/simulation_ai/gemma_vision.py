"""Isolated LiteRT-LM Gemma 4 vision worker used by dev and frozen builds."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def run_probe(model_path: Path, image_path: Path, x: float, y: float, button: str, double_click: bool) -> dict[str, object]:
    from litert_lm import Backend, Content, Contents, Engine

    backend_name = os.environ.get("SIMULATION_AI_GEMMA_BACKEND", "cpu").strip().lower()
    if backend_name not in {"cpu", "gpu"}:
        backend_name = "cpu"
    backend = Backend.GPU() if backend_name == "gpu" else Backend.CPU()
    engine_kwargs: dict[str, object] = {"backend": backend}
    engine_kwargs["vision_backend"] = Backend.GPU() if backend_name == "gpu" else Backend.CPU()
    prompt = f"""You are the local Gemma desktop vision observer. Inspect the supplied desktop screenshot and the red USER CLICKED HERE marker is at local image pixel ({x:.1f}, {y:.1f}) in a 1536x1024 coordinate space. The gesture is {'double-' if double_click else ''}{button}-click. Zoom conceptually into that marker and identify the exact visual control under it. Return compact JSON only with these keys: action, target_text, target_role, confidence, image_pixel_x, image_pixel_y, normalized_x, normalized_y, bounding_box, nearby_text, resulting_state_hint. Use null for unknown text, give bounding_box as [left,top,right,bottom] in image pixels, and never invent a control that is not visible."""
    with Engine(str(model_path), **engine_kwargs) as engine:
        with engine.create_conversation(automatic_tool_calling=False, max_output_tokens=192) as conversation:
            message = Contents.of(Content.ImageFile(str(image_path)), prompt)
            text_parts: list[str] = []
            for chunk in conversation.send_message_async(message, max_output_tokens=192):
                for item in chunk.get("content", []):
                    if item.get("type") == "text":
                        text_parts.append(str(item.get("text", "")))
    return {"content": [{"type": "text", "text": "".join(text_parts)}]}


def main() -> None:
    model_path, image_path, x, y, button, double_click = sys.argv[1:]
    print(json.dumps(run_probe(Path(model_path), Path(image_path), float(x), float(y), button, double_click == "true"), ensure_ascii=False))


if __name__ == "__main__":
    main()
