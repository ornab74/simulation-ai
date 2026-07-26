from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .credentials import CredentialVaultError
from .engine import SurfaceEngine
from .model import ObservationReport, PatchProposal
from .model_execution import ModelExecutionError
from .prompt_runs import PromptRunStoreError
from .prompts import PromptPackError


class SurfaceHandler(BaseHTTPRequestHandler):
    engine: SurfaceEngine
    bearer_token: str = ""
    server_version = "SimulationAICore/0.6"

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._authorize()
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/health":
                self._send(
                    200,
                    {
                        "ok": True,
                        "schema": "nmsr.health/1",
                        "authority": "deterministic-core",
                        "version": "0.6.0",
                        "local_only": True,
                        "authenticated": bool(self.bearer_token),
                    },
                )
            elif parsed.path == "/v1/snapshot":
                self._send(200, {"ok": True, "snapshot": self.engine.snapshot()})
            elif parsed.path == "/v1/events":
                limit = min(200, max(1, int(query.get("limit", ["50"])[0])))
                events = [event.as_dict() for event in reversed(self.engine.store.list_events(limit=limit))]
                self._send(200, {"ok": True, "events": events})
            elif parsed.path == "/v1/branches":
                self._send(200, {"ok": True, "branches": self.engine.list_branches()})
            elif parsed.path == "/v1/render/jobs":
                jobs = [job.as_dict() for job in reversed(self.engine.store.list_render_jobs(limit=50))]
                self._send(200, {"ok": True, "render_jobs": jobs})
            elif parsed.path == "/v1/artifacts/images":
                self._send(200, {"ok": True, "images": self.engine.images.list(), "encrypted": True})
            elif parsed.path == "/v1/artifacts/images/latest":
                self._send(200, {"ok": True, "image": self.engine.latest_saved_image(), "encrypted": True})
            elif parsed.path == "/v1/credentials/openai":
                self._send(200, {"ok": True, "credential": self.engine.credential_status()})
            elif parsed.path == "/v1/prompts":
                include_shared = query.get("include_shared", ["1"])[0] not in {"0", "false", "no"}
                self._send(200, {"ok": True, "catalog": self.engine.prompt_catalog(include_shared=include_shared)})
            elif parsed.path == "/v1/prompt-workflows":
                self._send(200, {"ok": True, "workflows": self.engine.prompts.workflow_catalog()})
            elif parsed.path == "/v1/prompt-runs":
                limit = min(200, max(1, int(query.get("limit", ["50"])[0])))
                self._send(200, {"ok": True, "runs": self.engine.prompt_run_list(limit=limit)})
            elif parsed.path == "/v1/prompt-workflow-runs":
                limit = min(100, max(1, int(query.get("limit", ["25"])[0])))
                self._send(200, {"ok": True, "workflow_runs": self.engine.prompt_workflow_run_list(limit=limit)})
            elif parsed.path == "/v1/model-execution/status":
                current = self.engine.current()
                self._send(200, {
                    "ok": True,
                    "execution": {
                        "provider": "openai",
                        "model": self.engine.model_executor.config.default_model,
                        "reasoning_effort": self.engine.model_executor.config.default_reasoning_effort,
                        "max_output_tokens": self.engine.model_executor.config.default_max_output_tokens,
                        "cloud_allowed": bool(current.ui.get("privacy", {}).get("cloud_allowed", False)),
                        "credential": self.engine.credential_status(),
                        "commit_authority": False,
                        "store": False,
                    },
                })
            elif parsed.path == "/v1/models/gemma/status":
                self._send(200, {"ok": True, "model": self.engine.gemma.status()})
            elif parsed.path == "/v1/models/gemma/diagnostics":
                refresh = query.get("refresh", ["0"])[0] in {"1", "true", "yes"}
                self._send(200, {"ok": True, "diagnostics": self.engine.gemma.diagnostics(refresh=refresh)})
            elif parsed.path.startswith("/v1/prompt-runs/"):
                run_id = parsed.path.removeprefix("/v1/prompt-runs/").strip("/")
                if not run_id:
                    raise ValueError("prompt run id is required")
                self._send(200, {"ok": True, "run": self.engine.prompt_run_get(run_id)})
            elif parsed.path.startswith("/v1/prompts/"):
                prompt_id = parsed.path.removeprefix("/v1/prompts/").strip("/")
                if not prompt_id:
                    raise ValueError("prompt id is required")
                self._send(200, {"ok": True, "prompt": self.engine.prompt_details(prompt_id)})
            else:
                self._send(404, {"ok": False, "error": "route_not_found"})
        except PermissionError as exc:
            self._send(401, {"ok": False, "error": str(exc)})
        except CredentialVaultError as exc:
            self._send(400, {"ok": False, "error": exc.code, "detail": str(exc)})
        except ModelExecutionError as exc:
            status = 502 if exc.code.startswith("provider") or exc.code in {"response_not_completed", "empty_model_output"} else 400
            self._send(status, {"ok": False, "error": exc.code, "detail": str(exc), "provider_status": exc.status_code})
        except (ValueError, PromptPackError, PromptRunStoreError, json.JSONDecodeError) as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # defensive server boundary
            self._send(500, {"ok": False, "error": "internal_error", "detail": str(exc)[:240]})

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._authorize()
            payload = self._read_json()
            parsed = urlparse(self.path)
            route = parsed.path
            if route == "/health":
                self._send(200, {"ok": True, "schema": "nmsr.health/1", "authority": "deterministic-core"})
            elif route in {"/v1/interact", "/v1/interaction"}:
                self._send(200, {"ok": True, **self.engine.interact(payload)})
            elif route == "/v1/observe":
                observation = self.engine.observe(payload)
                self._send(200, {"ok": True, "observation": observation.as_dict()})
            elif route == "/v1/propose":
                packet = payload.get("packet", payload)
                observation_raw = payload.get("observation")
                observation = ObservationReport(**observation_raw) if isinstance(observation_raw, dict) else None
                proposal = self.engine.propose(packet, observation)
                self._send(200, {"ok": True, "proposal": proposal.as_dict()})
            elif route == "/v1/commit":
                proposal_raw = payload.get("proposal") or payload
                proposal = PatchProposal.from_dict(proposal_raw)
                state, event, artifacts = self.engine.commit_proposal(proposal)
                self._send(200, {"ok": True, "state": state.as_dict(), "event": event.as_dict(), **artifacts})
            elif route in {"/v1/branch", "/v1/branch/create"}:
                state = self.engine.create_branch(str(payload.get("name", "branch")))
                self._send(200, {"ok": True, "state": state.as_dict(), "branches": self.engine.list_branches()})
            elif route == "/v1/branch/switch":
                state = self.engine.switch_branch(str(payload.get("name", "main")))
                self._send(200, {"ok": True, "state": state.as_dict(), "branches": self.engine.list_branches()})
            elif route == "/v1/memory/query":
                results = self.engine.query_memory(
                    str(payload.get("query", "")),
                    branch=str(payload.get("branch", "")) or None,
                    object_ids=[str(item) for item in payload.get("object_ids", [])],
                    limit=int(payload.get("limit", 12)),
                )
                self._send(200, {"ok": True, "results": results})
            elif route == "/v1/render/verify":
                result = self.engine.verify_render(str(payload.get("job_id", "")), dict(payload.get("verification", {})))
                self._send(200, {"ok": True, **result})
            elif route == "/v1/credentials/openai/save":
                credential = self.engine.credential_save(
                    str(payload.get("api_key", "")),
                    str(payload.get("password", "")),
                )
                self._send(200, {"ok": True, "credential": credential})
            elif route == "/v1/credentials/openai/import-env":
                credential = self.engine.credential_import_environment(str(payload.get("password", "")))
                self._send(200, {"ok": True, "credential": credential})
            elif route == "/v1/credentials/openai/unlock":
                credential = self.engine.credential_unlock(str(payload.get("password", "")))
                self._send(200, {"ok": True, "credential": credential})
            elif route == "/v1/credentials/openai/lock":
                self._send(200, {"ok": True, "credential": self.engine.credential_lock()})
            elif route == "/v1/credentials/openai/clear":
                credential = self.engine.credential_clear(str(payload.get("password", "")))
                self._send(200, {"ok": True, "credential": credential})
            elif route == "/v1/credentials/openai/test":
                self._send(200, {"ok": True, "test": self.engine.credential_test(), "credential": self.engine.credential_status()})
            elif route == "/v1/prompts/render":
                prompt_id = str(payload.get("prompt_id", ""))
                inputs = payload.get("inputs", {})
                if not isinstance(inputs, dict):
                    raise ValueError("prompt inputs must be an object")
                self._send(200, {"ok": True, "invocation": self.engine.prompt_render(prompt_id, inputs)})
            elif route == "/v1/prompts/route":
                self._send(200, {"ok": True, "route": self.engine.prompt_route(str(payload.get("task_type", "")))})
            elif route == "/v1/prompts/validate":
                self._send(200, {"ok": True, "validation": self.engine.prompt_validate()})
            elif route == "/v1/prompts/validate-output":
                prompt_id = str(payload.get("prompt_id", ""))
                output = payload.get("output", {})
                if not isinstance(output, dict):
                    raise ValueError("model output must be an object")
                self._send(200, {"ok": True, "validation": self.engine.prompt_validate_output(prompt_id, output)})
            elif route == "/v1/prompts/execute":
                prompt_id = str(payload.get("prompt_id", ""))
                inputs = payload.get("inputs", {})
                if not isinstance(inputs, dict):
                    raise ValueError("prompt inputs must be an object")
                run = self.engine.prompt_execute(
                    prompt_id,
                    inputs,
                    model=str(payload.get("model", "")).strip() or None,
                    reasoning_effort=str(payload.get("reasoning_effort", "")).strip() or None,
                    max_output_tokens=int(payload["max_output_tokens"]) if payload.get("max_output_tokens") is not None else None,
                )
                self._send(200, {"ok": True, "run": run})
            elif route == "/v1/prompt-runs/review":
                run = self.engine.prompt_run_review(
                    str(payload.get("run_id", "")),
                    decision=str(payload.get("decision", "")),
                    note=str(payload.get("note", "")),
                    reviewed_by=str(payload.get("reviewed_by", "operator")),
                )
                self._send(200, {"ok": True, "run": run})
            elif route == "/v1/prompt-workflows/execute":
                step_inputs = payload.get("step_inputs", {})
                overrides = payload.get("model_overrides", {})
                if not isinstance(step_inputs, dict) or not isinstance(overrides, dict):
                    raise ValueError("step_inputs and model_overrides must be objects")
                workflow_run = self.engine.prompt_workflow_execute(
                    str(payload.get("workflow_id", "")),
                    step_inputs=step_inputs,
                    model=str(payload.get("model", "")).strip() or None,
                    model_overrides={str(key): str(value) for key, value in overrides.items()},
                    reasoning_effort=str(payload.get("reasoning_effort", "")).strip() or None,
                    max_output_tokens=int(payload["max_output_tokens"]) if payload.get("max_output_tokens") is not None else None,
                    stop_on_invalid=bool(payload.get("stop_on_invalid", True)),
                    max_steps=int(payload["max_steps"]) if payload.get("max_steps") is not None else None,
                )
                self._send(200, {"ok": True, "workflow_run": workflow_run})
            elif route == "/v1/replay":
                self._send(200, {"ok": True, "verification": self.engine.verify_replay()})
            elif route == "/v1/models/gemma/download":
                self._send(200, {"ok": True, "model": self.engine.gemma.start_download()})
            elif route == "/v1/artifacts/export":
                name = str(payload.get("name", "world-output.md"))[:120]
                if "/" in name or "\\" in name or name in {".", ".."}:
                    raise ValueError("artifact name must be a single safe filename")
                content = str(payload.get("content", ""))
                if len(content.encode("utf-8")) > 10 * 1024 * 1024:
                    raise ValueError("artifact too large")
                artifacts = Path(".simulation-ai") / "artifacts"
                artifacts.mkdir(parents=True, exist_ok=True)
                target = artifacts / name
                target.write_text(content, encoding="utf-8")
                self._send(200, {"ok": True, "artifact": {"name": name, "path": str(target), "bytes": target.stat().st_size, "executable": False}})
            elif route == "/v1/render/generate-boot":
                prompt = str(payload.get("prompt", "Create a 1536x1024 landscape Windows XP-era desktop boot screen, straight-on orthographic view, full desktop visible edge-to-edge, crisp readable UI geometry, blue Luna taskbar anchored to the bottom, stable desktop icon layout, no crop, no letterboxing, no cinematic perspective, no people, no extra panels, no modern UI, no readable brand logos."))[:4000]
                image = self.engine.edit_latest_image(prompt) if bool(payload.get("edit_previous", False)) else self.engine.generate_boot_image(prompt)
                self._send(200, {"ok": True, "image": image})
            elif route == "/v1/render/reset-desktop":
                self._send(200, {"ok": True, "image": self.engine.reset_desktop_image(), "encrypted": True})
            elif route == "/v1/vision/describe-click":
                x, y = float(payload.get("x", 0)), float(payload.get("y", 0))
                button = str(payload.get("button", "left"))
                double_click = bool(payload.get("double_click", False))
                gemma_result = self.engine.describe_click_with_gemma(x, y, button=button, double_click=double_click)
                if bool(gemma_result.get("ok", False)):
                    self._send(200, {**gemma_result, "description": json.dumps(gemma_result.get("observation", {}), ensure_ascii=False)})
                    return
                gesture = ("double-" if bool(payload.get("double_click", False)) else "") + f"{button}-click"
                normalized_x, normalized_y = x / 1536.0, y / 1024.0
                region = "bottom-left Start menu area" if normalized_y > 0.84 and normalized_x < 0.16 else ("desktop shortcut area" if normalized_x < 0.24 and normalized_y < 0.82 else ("taskbar process area" if normalized_y > 0.84 else ("system tray and clock area" if normalized_x > 0.82 and normalized_y > 0.84 else "desktop surface")))
                diagnostics = gemma_result.get("diagnostics", {})
                self._send(200, {"ok": True, "description": f"Local vision fallback: zoom into the USER {gesture.upper()} HERE annotation at local pixel ({x:.0f}, {y:.0f}); the user interacted with the {region}. Read any nearby label or text box and report its text and bounding region before applying the action.", "coordinate_space": "world-surface-local-pixels", "annotation": "USER DOUBLE-CLICKED HERE" if bool(payload.get("double_click", False)) else "USER CLICKED HERE", "model": "deterministic-fallback", "vision_runtime": "unavailable", "vision_error": gemma_result.get("detail", gemma_result.get("error", "Gemma vision unavailable")), "diagnostics": diagnostics})
            else:
                self._send(404, {"ok": False, "error": "route_not_found"})
        except PermissionError as exc:
            self._send(401, {"ok": False, "error": str(exc)})
        except CredentialVaultError as exc:
            self._send(400, {"ok": False, "error": exc.code, "detail": str(exc)})
        except ModelExecutionError as exc:
            status = 502 if exc.code.startswith("provider") or exc.code in {"response_not_completed", "empty_model_output"} else 400
            self._send(status, {"ok": False, "error": exc.code, "detail": str(exc), "provider_status": exc.status_code})
        except (ValueError, PromptPackError, PromptRunStoreError, json.JSONDecodeError, TypeError) as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # defensive server boundary
            self._send(500, {"ok": False, "error": "internal_error", "detail": str(exc)[:240]})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[surface-core] {self.address_string()} {format % args}")

    def _authorize(self) -> None:
        if not self.bearer_token:
            return
        supplied = self.headers.get("Authorization", "")
        if supplied != f"Bearer {self.bearer_token}":
            raise PermissionError("unauthorized")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 256 * 1024:
            raise ValueError("request too large")
        raw = self.rfile.read(length)
        value = json.loads(raw or b"{}")
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def _send(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Image requests can outlive the UI timeout; do not turn a client
            # disconnect into a second traceback while handling the response.
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulation AI deterministic Surface Core")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47890)
    parser.add_argument("--home", type=Path, default=Path(".simulation-ai"))
    parser.add_argument("--models", type=Path, default=None)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("SIMULATION_AI_ALLOW_REMOTE") != "1":
        raise SystemExit("Refusing non-loopback bind without SIMULATION_AI_ALLOW_REMOTE=1")
    engine = SurfaceEngine(args.home, models_dir=args.models)
    SurfaceHandler.engine = engine
    SurfaceHandler.bearer_token = os.environ.get("SIMULATION_AI_TOKEN", "").strip()
    server = ThreadingHTTPServer((args.host, args.port), SurfaceHandler)
    auth_note = "authenticated" if SurfaceHandler.bearer_token else "development-no-token"
    print(f"Simulation AI Surface Core listening on http://{args.host}:{args.port} ({auth_note})")
    server.serve_forever()


if __name__ == "__main__":
    main()
