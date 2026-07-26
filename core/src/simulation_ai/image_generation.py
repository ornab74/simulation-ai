from __future__ import annotations

import base64
import json
from datetime import datetime, UTC
import uuid
import os
from pathlib import Path
from urllib.request import Request, urlopen

from .credentials import OpenAICredentialVault
from .encrypted_images import EncryptedImageStore

IMAGE_MODEL = os.environ.get("SIMULATION_AI_IMAGE_MODEL", "gpt-image-1.5").strip() or "gpt-image-1"


def generate_image(credentials: OpenAICredentialVault, prompt: str, output_dir: Path) -> dict[str, object]:
    api_key, source = credentials.resolve_api_key()
    body = json.dumps({"model": IMAGE_MODEL, "prompt": prompt, "size": "1536x1024", "quality": "high"}).encode()
    request = Request("https://api.openai.com/v1/images/generations", data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "simulation-ai/0.7",
    })
    with urlopen(request, timeout=180) as response:
        payload = json.loads(response.read(16 * 1024 * 1024))
    items = payload.get("data", []) if isinstance(payload, dict) else []
    if not items or not isinstance(items[0], dict) or not items[0].get("b64_json"):
        raise ValueError("OpenAI returned no image data")
    image = base64.b64decode(items[0]["b64_json"])
    record = EncryptedImageStore(output_dir.parent, credentials).save(image, prompt)
    target = EncryptedImageStore(output_dir.parent, credentials).materialize(str(record["id"]))
    return {"path": str(target), **record, "provider": "openai", "credential_source": source, "model": IMAGE_MODEL, "encrypted": True}

def edit_image(credentials: OpenAICredentialVault, prompt: str, source: Path, output_dir: Path) -> dict[str, object]:
    api_key, source_name = credentials.resolve_api_key()
    boundary = "----simulation-ai-%s" % uuid.uuid4().hex
    chunks = []
    def field(name: str, value: str) -> None:
        chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode())
    field("model", IMAGE_MODEL)
    field("prompt", prompt[:4000])
    field("size", "1536x1024")
    chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"desktop.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + source.read_bytes() + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    request = Request("https://api.openai.com/v1/images/edits", data=b"".join(chunks), method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "simulation-ai/0.7"})
    with urlopen(request, timeout=180) as response:
        payload = json.loads(response.read(16 * 1024 * 1024))
    items = payload.get("data", []) if isinstance(payload, dict) else []
    if not items or not isinstance(items[0], dict) or not items[0].get("b64_json"):
        raise ValueError("OpenAI returned no edited image data")
    image = base64.b64decode(items[0]["b64_json"])
    record = EncryptedImageStore(output_dir.parent, credentials).save(image, prompt)
    target = EncryptedImageStore(output_dir.parent, credentials).materialize(str(record["id"]))
    return {"path": str(target), **record, "provider": "openai", "credential_source": source_name, "model": IMAGE_MODEL, "encrypted": True, "edited": True}
