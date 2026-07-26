"""Safe, resumable, chunked setup for the bundled Gemma LiteRT model."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
from threading import Lock, Thread
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

GEMMA_MODEL = "gemma-4-E2B-it.litertlm"
GEMMA_SHA256 = "ab7838cdfc8f77e54d8ca45eadceb20452d9f01e4bfade03e5dce27911b27e42"
GEMMA_URL = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/7fa1d78473894f7e736a21d920c3aa80f950c0db/" + GEMMA_MODEL
GEMMA_CHUNK_BYTES = 16 * 1024 * 1024
GEMMA_DOWNLOAD_WORKERS = 4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GemmaSetup:
    """Model vault with resumable ranged chunks and background progress."""

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self.path = models_dir / GEMMA_MODEL
        self.chunk_dir = models_dir / f".{GEMMA_MODEL}.chunks"
        self.manifest_path = self.chunk_dir / "manifest.json"
        self._lock = Lock()
        self._thread: Thread | None = None
        self._progress: dict[str, object] = {}
        self._cached_hash = ""
        self._cached_stat: tuple[int, int] | None = None

    def status(self) -> dict[str, object]:
        with self._lock:
            progress = dict(self._progress)
            active = self._thread is not None and self._thread.is_alive()

        if self.path.exists():
            actual = self._file_hash_cached()
            verified = actual == GEMMA_SHA256
            if verified:
                total = self.path.stat().st_size
                return self._status_payload(
                    state="ready",
                    verified=True,
                    downloaded=total,
                    total=total,
                    chunks=1,
                    completed_chunks=1,
                    sha256=actual,
                )
            progress.setdefault("error", f"SHA-256 mismatch: {actual}")
            progress.setdefault("state", "corrupt")

        manifest = self._read_manifest()
        total = int(progress.get("total_bytes", manifest.get("total_bytes", 0)) or 0)
        chunk_size = int(manifest.get("chunk_size", GEMMA_CHUNK_BYTES))
        chunks = int(manifest.get("chunks", 0))
        completed, downloaded = self._chunk_progress(total, chunk_size, chunks)
        state = str(progress.get("state", ""))
        if active:
            state = "downloading"
        elif state not in {"error", "paused", "corrupt"}:
            state = "paused" if downloaded else "missing"
        return self._status_payload(
            state=state,
            verified=False,
            downloaded=downloaded,
            total=total,
            chunks=chunks,
            completed_chunks=completed,
            chunk_size=chunk_size,
            error=str(progress.get("error", manifest.get("error", ""))),
        )

    def start_download(self) -> dict[str, object]:
        current = self.status()
        if current.get("state") == "ready":
            return current
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                active = True
            else:
                active = False
                self._progress = {"state": "starting", "error": ""}
                self._thread = Thread(target=self._download_worker, name="gemma-download", daemon=True)
                self._thread.start()
        if active:
            return self.status()
        return self.status()

    # Backward-compatible route name used by older clients.
    def download(self) -> dict[str, object]:
        return self.start_download()

    def _download_worker(self) -> None:
        try:
            total, supports_ranges = self._probe_remote()
            if self.path.exists() and self._file_hash_cached() != GEMMA_SHA256:
                self.path.unlink()
                self._cached_stat = None
                self._cached_hash = ""
            if supports_ranges:
                self._download_chunks(total)
            else:
                self._download_stream(total)
            actual = sha256_file(self.path)
            if actual != GEMMA_SHA256:
                raise ValueError(f"SHA-256 mismatch: {actual}")
            with self._lock:
                self._progress = {"state": "ready", "error": "", "total_bytes": total}
            self._cleanup_chunks()
        except Exception as exc:  # preserve chunks and make the next click resume
            with self._lock:
                self._progress = {"state": "error", "error": str(exc)[:400]}
            manifest = self._read_manifest()
            if manifest:
                manifest["state"] = "error"
                manifest["error"] = str(exc)[:400]
                self._write_manifest(manifest)

    def _probe_remote(self) -> tuple[int, bool]:
        request = Request(GEMMA_URL, headers={"User-Agent": "simulation-ai/0.8", "Range": "bytes=0-0"})
        with urlopen(request, timeout=90) as response:
            status = int(getattr(response, "status", 200) or 200)
            content_range = response.headers.get("Content-Range", "")
            match = re.search(r"bytes\s+\d+-\d+/(\d+)", content_range)
            if status == 206 and match:
                return int(match.group(1)), True
            length = int(response.headers.get("Content-Length", "0") or 0)
            if length <= 0:
                raise ValueError("Model server did not provide a content length")
            return length, False

    def _download_chunks(self, total: int) -> None:
        chunks = (total + GEMMA_CHUNK_BYTES - 1) // GEMMA_CHUNK_BYTES
        manifest = self._read_manifest()
        if manifest.get("sha256") != GEMMA_SHA256 or int(manifest.get("total_bytes", 0)) != total:
            manifest = {
                "model": GEMMA_MODEL,
                "url": GEMMA_URL,
                "sha256": GEMMA_SHA256,
                "total_bytes": total,
                "chunk_size": GEMMA_CHUNK_BYTES,
                "chunks": chunks,
                "state": "downloading",
                "error": "",
                "updated_at": time.time(),
            }
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        self._write_manifest(manifest)
        pending = []
        for index in range(chunks):
            expected = self._chunk_length(index, total)
            part = self._chunk_path(index)
            if part.exists() and part.stat().st_size == expected:
                continue
            pending.append((index, total))
        with self._lock:
            self._progress.update({"state": "downloading", "total_bytes": total, "chunks": chunks, "error": ""})
        with ThreadPoolExecutor(max_workers=GEMMA_DOWNLOAD_WORKERS) as pool:
            futures = [pool.submit(self._download_chunk, index, total) for index, total in pending]
            for future in as_completed(futures):
                future.result()
        assemble = self.path.with_suffix(self.path.suffix + ".assemble.part")
        with assemble.open("wb") as output:
            for index in range(chunks):
                part = self._chunk_path(index)
                expected = self._chunk_length(index, total)
                if not part.exists() or part.stat().st_size != expected:
                    raise ValueError(f"Missing model chunk {index + 1}/{chunks}")
                with part.open("rb") as source:
                    for data in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(data)
        os.replace(assemble, self.path)

    def _download_chunk(self, index: int, total: int) -> None:
        start = index * GEMMA_CHUNK_BYTES
        end = min(total - 1, start + GEMMA_CHUNK_BYTES - 1)
        expected = end - start + 1
        part = self._chunk_path(index)
        part.parent.mkdir(parents=True, exist_ok=True)
        existing = part.stat().st_size if part.exists() else 0
        if existing > expected:
            part.unlink()
            existing = 0
        if existing == expected:
            return
        range_start = start + existing
        last_error: Exception | None = None
        for attempt in range(3):
            request = Request(
                GEMMA_URL,
                headers={
                    "User-Agent": "simulation-ai/0.8",
                    "Accept": "application/octet-stream",
                    "Range": f"bytes={range_start}-{end}",
                },
            )
            try:
                with urlopen(request, timeout=90) as response:
                    if int(getattr(response, "status", 200) or 200) != 206:
                        raise ValueError("Model server stopped honoring ranged requests")
                    with part.open("ab") as output:
                        for data in iter(lambda: response.read(1024 * 1024), b""):
                            output.write(data)
                            self._set_download_progress(total)
                break
            except HTTPError as exc:
                last_error = ValueError(f"Model chunk {index + 1} failed with HTTP {exc.code}")
            except OSError as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        if last_error is not None:
            raise last_error
        if not part.exists() or part.stat().st_size != expected:
            raise ValueError(f"Model chunk {index + 1} is incomplete")

    def _download_stream(self, total: int) -> None:
        partial = self.path.with_suffix(self.path.suffix + ".part")
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "simulation-ai/0.8", "Accept": "application/octet-stream"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = Request(GEMMA_URL, headers=headers)
        with urlopen(request, timeout=90) as response:
            status = int(getattr(response, "status", 200) or 200)
            if offset and status != 206:
                offset = 0
                partial.write_bytes(b"")
            with partial.open("ab" if offset else "wb") as output:
                downloaded = offset
                for data in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(data)
                    downloaded += len(data)
                    with self._lock:
                        self._progress.update({"state": "downloading", "downloaded_bytes": downloaded, "total_bytes": total})
        os.replace(partial, self.path)

    def _set_download_progress(self, total: int) -> None:
        _, downloaded = self._chunk_progress(total, GEMMA_CHUNK_BYTES, (total + GEMMA_CHUNK_BYTES - 1) // GEMMA_CHUNK_BYTES)
        with self._lock:
            self._progress.update({"state": "downloading", "downloaded_bytes": downloaded, "total_bytes": total})

    def _chunk_progress(self, total: int, chunk_size: int, chunks: int) -> tuple[int, int]:
        if not self.chunk_dir.exists() or chunks <= 0:
            return 0, 0
        completed = 0
        downloaded = 0
        for index in range(chunks):
            part = self._chunk_path(index)
            if not part.exists():
                continue
            length = min(chunk_size, total - index * chunk_size)
            size = min(part.stat().st_size, max(0, length))
            downloaded += size
            if size == length:
                completed += 1
        return completed, downloaded

    def _chunk_length(self, index: int, total: int) -> int:
        return min(GEMMA_CHUNK_BYTES, total - index * GEMMA_CHUNK_BYTES)

    def _chunk_path(self, index: int) -> Path:
        return self.chunk_dir / f"chunk-{index:06d}.part"

    def _read_manifest(self) -> dict[str, object]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _write_manifest(self, value: dict[str, object]) -> None:
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        value["updated_at"] = time.time()
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, self.manifest_path)

    def _file_hash_cached(self) -> str:
        stat = self.path.stat()
        marker = (stat.st_size, stat.st_mtime_ns)
        if self._cached_stat != marker:
            self._cached_hash = sha256_file(self.path)
            self._cached_stat = marker
        return self._cached_hash

    def _cleanup_chunks(self) -> None:
        if not self.chunk_dir.exists():
            return
        for item in self.chunk_dir.iterdir():
            if item.is_file():
                item.unlink()
        self.chunk_dir.rmdir()

    def _status_payload(
        self,
        *,
        state: str,
        verified: bool,
        downloaded: int,
        total: int,
        chunks: int,
        completed_chunks: int,
        chunk_size: int = GEMMA_CHUNK_BYTES,
        error: str = "",
        sha256: str = "",
    ) -> dict[str, object]:
        with self._lock:
            progress = dict(self._progress)
        downloaded = max(downloaded, int(progress.get("downloaded_bytes", 0) or 0))
        total = max(total, int(progress.get("total_bytes", 0) or 0))
        ratio = downloaded / total if total else 0.0
        return {
            "id": "gemma4-e2b",
            "state": state,
            "verified": verified,
            "path": str(self.path),
            "expected_sha256": GEMMA_SHA256,
            "sha256": sha256,
            "bytes": self.path.stat().st_size if self.path.exists() else 0,
            "downloaded_bytes": downloaded,
            "total_bytes": total,
            "progress": round(min(1.0, ratio), 4),
            "chunk_size": chunk_size,
            "chunks": chunks,
            "completed_chunks": completed_chunks,
            "resumable": state in {"missing", "paused", "error", "corrupt", "downloading"},
            "error": error,
        }
