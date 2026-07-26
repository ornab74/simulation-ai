"""Safe, resumable, chunked setup for the bundled Gemma LiteRT model."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
from threading import Lock, Thread
import subprocess
import sys
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
        self._diagnostics_lock = Lock()
        self._last_diagnostics: dict[str, object] | None = None
        self._last_diagnostics_at = 0.0

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

    def diagnostics(self, *, refresh: bool = False) -> dict[str, object]:
        """Report every boot prerequisite without loading the 2.4 GB model.

        Creating a LiteRT engine is intentionally not part of this check: it
        allocates substantial memory and can peg a software CPU backend. The
        returned report proves the file, interpreter, Python package, native
        library, and CLI independently. ``probe`` is the explicit, heavier
        end-to-end check exposed by the server.
        """
        now = time.monotonic()
        with self._diagnostics_lock:
            if not refresh and self._last_diagnostics is not None and now - self._last_diagnostics_at < 5.0:
                return dict(self._last_diagnostics)

        checks: list[dict[str, object]] = []
        model_exists = self.path.is_file()
        actual_hash = ""
        model_bytes = 0
        model_error = ""
        if model_exists:
            try:
                model_bytes = self.path.stat().st_size
                actual_hash = self._file_hash_cached()
            except OSError as exc:
                model_error = str(exc)
        model_verified = bool(actual_hash) and actual_hash == GEMMA_SHA256
        checks.append({
            "id": "model_file",
            "ok": model_exists and not bool(model_error),
            "title": "Model file discovered",
            "detail": str(self.path) if model_exists else f"Missing {self.path.name} in {self.models_dir}",
        })
        checks.append({
            "id": "model_sha256",
            "ok": model_verified,
            "title": "SHA-256 verification",
            "detail": actual_hash if actual_hash else (model_error or "Model has not been downloaded"),
        })

        mode_detail = ""
        mode_ok = True
        if model_exists:
            try:
                mode = self.path.stat().st_mode & 0o777
                mode_ok = (mode & 0o077) == 0
                mode_detail = f"permissions {mode:03o}" + (" (private)" if mode_ok else " (other users can read it)")
            except OSError as exc:
                mode_ok = False
                mode_detail = str(exc)
        else:
            mode_detail = "checked after download"
        checks.append({
            "id": "model_permissions",
            "ok": mode_ok,
            "severity": "warning" if not mode_ok else "info",
            "title": "Model vault permissions",
            "detail": mode_detail,
        })

        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        checks.append({
            "id": "python_runtime",
            "ok": True,
            "title": "Python runtime",
            "detail": f"{sys.executable} · Python {python_version}",
        })

        package_found = False
        package_version = ""
        package_error = ""
        try:
            package_found = importlib.util.find_spec("litert_lm") is not None
            package_version = importlib.metadata.version("litert-lm") if package_found else ""
        except (ImportError, ModuleNotFoundError, importlib.metadata.PackageNotFoundError, ValueError) as exc:
            package_error = str(exc)
        checks.append({
            "id": "litert_lm_package",
            "ok": package_found,
            "title": "LiteRT-LM Python package",
            "detail": package_version or package_error or "Not installed in this interpreter",
        })

        cli_candidates = []
        found_cli = shutil.which("litert-lm")
        if found_cli:
            cli_candidates.append(found_cli)
        cli_name = "litert-lm.exe" if os.name == "nt" else "litert-lm"
        cli_candidates.extend([
            str(Path(sys.executable).parent / cli_name),
            str(self.models_dir.parent / ".venv-gemma" / ("Scripts" if os.name == "nt" else "bin") / cli_name),
            str(self.models_dir.parent / ".runtime" / "venv" / ("Scripts" if os.name == "nt" else "bin") / cli_name),
        ])
        cli_path = next((candidate for candidate in cli_candidates if Path(candidate).is_file()), "")
        cli_version = ""
        cli_error = ""
        if cli_path:
            try:
                result = subprocess.run(
                    [cli_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                cli_version = (result.stdout or result.stderr).strip()[:160]
                if result.returncode != 0:
                    cli_error = cli_version or f"exit code {result.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                cli_error = str(exc)
        checks.append({
            "id": "litert_lm_cli",
            "ok": bool(cli_path) and not bool(cli_error),
            "title": "LiteRT-LM command line",
            "detail": f"{cli_version} · {cli_path}" if cli_path and not cli_error else (cli_error or "litert-lm executable not found"),
        })

        native_library_ok = False
        native_library_detail = "Not checked because litert_lm is unavailable"
        if package_found:
            try:
                import litert_lm  # type: ignore[import-not-found]
                native_library_ok = hasattr(litert_lm, "Engine")
                native_library_detail = "Python bindings and native LiteRT-LM library loaded"
            except Exception as exc:  # native loader errors are environment-specific
                native_library_detail = f"Native library failed to load: {str(exc)[:240]}"
        checks.append({
            "id": "litert_lm_native",
            "ok": native_library_ok,
            "title": "LiteRT-LM native library",
            "detail": native_library_detail,
        })

        required_ok = model_verified and package_found and native_library_ok
        if required_ok:
            next_action = "LiteRT-LM is available. Run the explicit vision probe before first use."
        elif not model_verified:
            next_action = "Download or repair the model; the SHA-256 must match before inference."
        else:
            next_action = "Start the core with SIMULATION_AI_WITH_GEMMA=1 so this interpreter installs litert-lm."
        report = {
            "ok": True,
            "ready_for_inference": required_ok,
            "model_path": str(self.path),
            "model_bytes": model_bytes,
            "model_sha256": actual_hash,
            "expected_sha256": GEMMA_SHA256,
            "runtime_python": sys.executable,
            "runtime_version": python_version,
            "litert_lm_version": package_version,
            "litert_lm_cli": cli_path,
            "checks": checks,
            "next_action": next_action,
        }
        with self._diagnostics_lock:
            self._last_diagnostics = dict(report)
            self._last_diagnostics_at = now
        return report

    def vision_probe(self, image_path: Path, *, x: float = 0.0, y: float = 0.0, button: str = "left", double_click: bool = False) -> dict[str, object]:
        """Run a bounded, isolated multimodal LiteRT-LM smoke test.

        The model is loaded in a child process so a bad native backend cannot
        take down Surface Core, and so the UI can time out cleanly. This is an
        explicit probe/click operation, never part of the boot status poll.
        """
        diagnostics = self.diagnostics(refresh=True)
        if not bool(diagnostics.get("ready_for_inference", False)):
            return {
                "ok": False,
                "error": "gemma_runtime_unavailable",
                "detail": str(diagnostics.get("next_action", "LiteRT-LM is not ready")),
                "diagnostics": diagnostics,
            }
        if not image_path.is_file() or image_path.is_symlink():
            return {"ok": False, "error": "vision_image_unavailable", "detail": "The encrypted desktop frame could not be materialized safely."}
        model_path = self.path.resolve()
        safe_image_path = image_path.resolve()

        script = r'''
import json
import sys
from litert_lm import Backend, Content, Contents, Engine

model_path, image_path, x, y, button, double_click = sys.argv[1:]
backend_name = "cpu"
if __import__("os").environ.get("SIMULATION_AI_GEMMA_BACKEND", "cpu").lower() == "gpu":
    backend_name = "gpu"
backend = Backend.GPU() if backend_name == "gpu" else Backend.CPU()
# Keep LiteRT's model-derived compiled settings intact. Overriding
# max_num_images/max_num_tokens changes the Gemma 4 vision executor contract.
engine_kwargs = {"backend": backend}
if backend_name == "gpu":
    engine_kwargs["vision_backend"] = Backend.GPU()
else:
    engine_kwargs["vision_backend"] = Backend.CPU()
prompt = f"""You are the local Gemma desktop vision observer. Inspect the supplied desktop screenshot and the red USER CLICKED HERE marker is at local image pixel ({float(x):.1f}, {float(y):.1f}) in a 1536x1024 coordinate space. The gesture is {'double-' if double_click == 'true' else ''}{button}-click. Zoom conceptually into that marker and identify the exact visual control under it. Return compact JSON only with these keys: action, target_text, target_role, confidence, image_pixel_x, image_pixel_y, normalized_x, normalized_y, bounding_box, nearby_text, resulting_state_hint. Use null for unknown text, give bounding_box as [left,top,right,bottom] in image pixels, and never invent a control that is not visible."""
with Engine(model_path, **engine_kwargs) as engine:
    with engine.create_conversation(automatic_tool_calling=False, max_output_tokens=192) as conversation:
        message = Contents.of(Content.ImageFile(image_path), prompt)
        text_parts = []
        for chunk in conversation.send_message_async(message, max_output_tokens=192):
            for item in chunk.get("content", []):
                if item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
        print(json.dumps({"content": [{"type": "text", "text": "".join(text_parts)}]}, ensure_ascii=False))
'''
        backend = os.environ.get("SIMULATION_AI_GEMMA_BACKEND", "cpu").strip().lower()
        if backend not in {"cpu", "gpu"}:
            backend = "cpu"
        environment = os.environ.copy()
        environment["SIMULATION_AI_GEMMA_BACKEND"] = backend
        try:
            completed = subprocess.run(
                [sys.executable, "-c", script, str(model_path), str(safe_image_path), str(x), str(y), button, str(double_click).lower()],
                capture_output=True,
                text=True,
                timeout=150,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "gemma_vision_timeout", "detail": "LiteRT-LM did not finish the isolated vision probe within 150 seconds.", "backend": backend}
        except OSError as exc:
            return {"ok": False, "error": "gemma_vision_process", "detail": str(exc)[:240], "backend": backend}
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            stderr_excerpt = stderr[:500] if len(stderr) <= 1000 else stderr[:500] + " … " + stderr[-500:]
            stdout_excerpt = stdout[:500] if len(stdout) <= 1000 else stdout[:500] + " … " + stdout[-500:]
            detail = f"exit code {completed.returncode}; stderr={stderr_excerpt}; stdout={stdout_excerpt}"
            return {"ok": False, "error": "gemma_vision_failed", "detail": detail, "backend": backend}
        raw = (completed.stdout or "").strip().splitlines()
        if not raw:
            return {"ok": False, "error": "gemma_vision_empty", "detail": "LiteRT-LM returned no observation.", "backend": backend}
        try:
            response = json.loads(raw[-1])
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": "gemma_vision_invalid_json", "detail": str(exc), "raw": raw[-1][:1000], "backend": backend}
        return {
            "ok": True,
            "model": "gemma-4-E2B-it.litertlm",
            "backend": backend,
            "observation": response,
            "coordinate_space": "world-surface-local-pixels",
        }

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
