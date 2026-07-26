"""Safe, resumable setup for the bundled Gemma LiteRT model."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

GEMMA_MODEL = "gemma-4-E2B-it.litertlm"
GEMMA_SHA256 = "ab7838cdfc8f77e54d8ca45eadceb20452d9f01e4bfade03e5dce27911b27e42"
GEMMA_URL = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/7fa1d78473894f7e736a21d920c3aa80f950c0db/" + GEMMA_MODEL


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GemmaSetup:
    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self.path = models_dir / GEMMA_MODEL

    def status(self) -> dict[str, object]:
        if not self.path.exists():
            return {"id": "gemma4-e2b", "state": "missing", "verified": False, "path": str(self.path)}
        actual = sha256_file(self.path)
        return {"id": "gemma4-e2b", "state": "ready" if actual == GEMMA_SHA256 else "corrupt", "verified": actual == GEMMA_SHA256, "sha256": actual, "expected_sha256": GEMMA_SHA256, "bytes": self.path.stat().st_size, "path": str(self.path)}

    def download(self) -> dict[str, object]:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        partial = self.path.with_suffix(self.path.suffix + ".part")
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "simulation-ai/0.7", "Accept": "application/octet-stream"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(GEMMA_URL, headers=headers)
        with urlopen(request, timeout=90) as response, partial.open("ab") as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                output.write(chunk)
        actual = sha256_file(partial)
        if actual != GEMMA_SHA256:
            raise ValueError(f"Gemma SHA-256 mismatch: {actual}")
        os.replace(partial, self.path)
        return self.status()
