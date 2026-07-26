from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime, UTC
import uuid
import os
from pathlib import Path
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .credentials import OpenAICredentialVault
from .encrypted_images import EncryptedImageStore

IMAGE_MODEL = os.environ.get("SIMULATION_AI_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"
MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_IMAGE_PIXELS = 8_294_400
MAX_IMAGE_EDGE = 3840


def _sanitize_prompt(prompt: str) -> str:
    return "".join(
        char for char in str(prompt)
        if char in "\t\n" or (ord(char) >= 32 and unicodedata.category(char) not in {"Cc", "Cf"})
    ).strip()[:4000]


def _validate_png(image: bytes, operation: str) -> None:
    if len(image) > MAX_IMAGE_BYTES:
        raise ValueError(f"{operation} image exceeds the 50 MiB safety limit")
    if len(image) < 33 or image[:8] != b"\x89PNG\r\n\x1a\n" or image[12:16] != b"IHDR":
        raise ValueError(f"{operation} image is not a valid PNG")
    width = int.from_bytes(image[16:20], "big")
    height = int.from_bytes(image[20:24], "big")
    if not width or not height or width > MAX_IMAGE_EDGE or height > MAX_IMAGE_EDGE or width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"{operation} image has unsafe dimensions")
    if b"IEND" not in image[-32:]:
        raise ValueError(f"{operation} image is truncated")


def _decode_image(value: object, operation: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError(f"OpenAI {operation} returned no image data")
    try:
        image = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(f"OpenAI {operation} returned invalid base64 image data") from None
    _validate_png(image, f"OpenAI {operation} returned")
    return image


def _provider_json(request: Request, operation: str) -> dict[str, object]:
    try:
        with urlopen(request, timeout=210) as response:
            payload = json.loads(response.read(16 * 1024 * 1024))
    except HTTPError as exc:
        detail = "provider rejected the request"
        try:
            body = json.loads(exc.read(512 * 1024))
            error = body.get("error", {}) if isinstance(body, dict) else {}
            if isinstance(error, dict):
                detail = str(error.get("message") or error.get("code") or detail)
            elif error:
                detail = str(error)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        request_id = exc.headers.get("x-request-id", "") if exc.headers else ""
        suffix = f"; request id {request_id}" if request_id else ""
        raise ValueError(f"OpenAI {operation} failed with HTTP {exc.code}: {detail}{suffix}") from None
    except TimeoutError as exc:
        raise ValueError(f"OpenAI {operation} timed out: {exc}") from None
    except URLError as exc:
        raise ValueError(f"OpenAI {operation} could not connect: {exc.reason}") from None
    if not isinstance(payload, dict):
        raise ValueError(f"OpenAI {operation} returned an invalid response")
    return payload


def generate_image(credentials: OpenAICredentialVault, prompt: str, output_dir: Path) -> dict[str, object]:
    api_key, source = credentials.resolve_api_key()
    safe_prompt = _sanitize_prompt(prompt)
    body = json.dumps({"model": IMAGE_MODEL, "prompt": safe_prompt, "size": "1536x1024", "quality": "high"}).encode()
    request = Request("https://api.openai.com/v1/images/generations", data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "simulation-ai/0.7",
    })
    payload = _provider_json(request, "image generation")
    items = payload.get("data", []) if isinstance(payload, dict) else []
    if not items or not isinstance(items[0], dict) or not items[0].get("b64_json"):
        raise ValueError("OpenAI returned no image data")
    image = _decode_image(items[0]["b64_json"], "image generation")
    record = EncryptedImageStore(output_dir.parent, credentials).save(image, safe_prompt)
    target = EncryptedImageStore(output_dir.parent, credentials).materialize(str(record["id"]))
    return {"path": str(target), **record, "provider": "openai", "credential_source": source, "model": IMAGE_MODEL, "encrypted": True}

def edit_image(credentials: OpenAICredentialVault, prompt: str, source: Path, output_dir: Path) -> dict[str, object]:
    api_key, source_name = credentials.resolve_api_key()
    if source.is_symlink():
        raise ValueError("source image must not be a symbolic link")
    source_path = source.resolve(strict=True)
    source_bytes = source_path.read_bytes()
    _validate_png(source_bytes, "source")
    safe_prompt = _sanitize_prompt(prompt)
    boundary = "----simulation-ai-%s" % uuid.uuid4().hex
    chunks = []
    def field(name: str, value: str) -> None:
        chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode())
    field("model", IMAGE_MODEL)
    field("prompt", safe_prompt)
    field("size", "1536x1024")
    chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"desktop.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + source_bytes + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    request = Request("https://api.openai.com/v1/images/edits", data=b"".join(chunks), method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "simulation-ai/0.7"})
    payload = _provider_json(request, "image edit")
    items = payload.get("data", []) if isinstance(payload, dict) else []
    if not items or not isinstance(items[0], dict) or not items[0].get("b64_json"):
        raise ValueError("OpenAI returned no edited image data")
    image = _decode_image(items[0]["b64_json"], "image edit")
    record = EncryptedImageStore(output_dir.parent, credentials).save(image, safe_prompt)
    target = EncryptedImageStore(output_dir.parent, credentials).materialize(str(record["id"]))
    return {"path": str(target), **record, "provider": "openai", "credential_source": source_name, "model": IMAGE_MODEL, "encrypted": True, "edited": True}
