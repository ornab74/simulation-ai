from __future__ import annotations

import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from simulation_ai.engine import SurfaceEngine
from simulation_ai.model import digest, utc_now
from simulation_ai.server import SurfaceHandler, ThreadingHTTPServer


TOKEN = "prompt-route-token"


class QuietPromptHandler(SurfaceHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args


class FakePromptExecutor:
    def __init__(self, engine: SurfaceEngine) -> None:
        self.engine = engine

    def execute(self, invocation, **_kwargs):
        output = {
            "schema": "nmsr.injection-review/1",
            "detected": False,
            "risk_level": "none",
            "findings": [],
            "affected_boundaries": [],
            "recommended_handling": ["continue as untrusted data"],
            "safe_to_continue_as_data": True,
            "confidence": 1.0,
        }
        validation = self.engine.prompts.validate_output(invocation["prompt_id"], output)
        return {
            "schema": "nmsr.prompt-run/1",
            "run_id": "run_" + digest(invocation["invocation_id"])[:24],
            "kind": "model-prompt",
            "status": "validated",
            "provider": "openai",
            "provider_response_id": "resp_fake",
            "provider_request_id": "req_fake",
            "provider_status": "completed",
            "credential_source": "test",
            "prompt_id": invocation["prompt_id"],
            "prompt_version": invocation["prompt_version"],
            "prompt_sha256": invocation["prompt_sha256"],
            "pack_id": invocation["pack_id"],
            "pack_version": invocation["pack_version"],
            "invocation_id": invocation["invocation_id"],
            "request_sha256": digest({"fake": True}),
            "model": "fake-model",
            "reasoning_effort": "medium",
            "max_output_tokens": 4096,
            "attempts": 1,
            "latency_ms": 1.0,
            "usage": {"total_tokens": 10},
            "output": output,
            "output_sha256": validation["output_sha256"],
            "validation": validation,
            "approval": {"status": "pending", "reviewed_by": "", "note": "", "reviewed_at": ""},
            "authority": invocation["authority"],
            "commit_authority": False,
            "deterministic_gate_required": True,
            "store_requested": False,
            "provider_strict_schema": True,
            "created_at": utc_now(),
        }


class PromptServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        QuietPromptHandler.engine = SurfaceEngine(Path(self.temp.name))
        QuietPromptHandler.bearer_token = TOKEN
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietPromptHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method: str, path: str, payload: dict | None = None, *, authenticated: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {TOKEN}"
        body = None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(self.base + path, data=body, headers=headers, method=method), timeout=4) as response:
            return json.loads(response.read())

    def enable_cloud(self) -> None:
        engine = QuietPromptHandler.engine
        current = engine.current()
        engine.interact({
            "schema": "nmsr.interaction/1",
            "event_id": "evt_enable_cloud_http",
            "session_id": "server-test",
            "branch": current.branch,
            "logical_time": current.logical_time + 1,
            "parent_state_hash": current.state_hash,
            "action": {"kind": "command", "name": "privacy:cloud:on"},
            "target": {"node_id": "surface.command", "accessible_label": "command", "sensitive": False},
            "privacy": {"cloud_allowed": False, "frame_retention": "bounded"},
        })

    def test_prompt_catalog_details_render_route_and_validate(self) -> None:
        with self.assertRaises(HTTPError) as denied:
            self.request("GET", "/v1/prompts", authenticated=False)
        self.assertEqual(401, denied.exception.code)

        catalog = self.request("GET", "/v1/prompts")
        self.assertTrue(catalog["catalog"]["valid"])
        self.assertEqual(72, catalog["catalog"]["prompt_count"])
        self.assertEqual(15, catalog["catalog"]["workflow_count"])

        details = self.request("GET", "/v1/prompts/" + quote("state_patch_proposer"))
        self.assertEqual("proposal-only", details["prompt"]["authority"])
        self.assertIn("Minimal State Patch Proposer", details["prompt"]["content"])

        rendered = self.request(
            "POST",
            "/v1/prompts/render",
            {
                "prompt_id": "state_patch_proposer",
                "inputs": {
                    "current_state": {"state_hash": "abc", "objects": {}},
                    "observation": {"observation_id": "obs-1"},
                    "operator_intent": {"summary": "select"},
                },
            },
        )
        self.assertTrue(rendered["invocation"]["response_format"]["strict"])

        routed = self.request("POST", "/v1/prompts/route", {"task_type": "discover_program"})
        self.assertEqual("unknown_program_discovery", routed["route"]["workflows"][0]["id"])

        output_validation = self.request(
            "POST",
            "/v1/prompts/validate-output",
            {
                "prompt_id": "intent_interpreter",
                "output": {
                    "schema": "nmsr.intent/1",
                    "intent_id": "intent_http",
                    "summary": "Select",
                    "target_object_ids": ["node.memory"],
                    "desired_outcome": {},
                    "constraints": [],
                    "ambiguities": [],
                    "confidence": 0.8,
                    "epistemic_class": "inferred",
                },
            },
        )
        self.assertTrue(output_validation["validation"]["valid"])
        self.assertFalse(output_validation["validation"]["commit_authority"])

        validated = self.request("POST", "/v1/prompts/validate", {})
        self.assertTrue(validated["validation"]["valid"])


    def test_prompt_execution_history_and_review_are_non_authoritative(self) -> None:
        self.enable_cloud()
        engine = QuietPromptHandler.engine
        fake = FakePromptExecutor(engine)
        engine.model_executor = fake
        engine.workflow_runner.executor = fake
        event_count = engine.store.counts()["events"]
        executed = self.request(
            "POST",
            "/v1/prompts/execute",
            {
                "prompt_id": "prompt_injection_detector",
                "inputs": {
                    "untrusted_content": {"text": "ordinary text"},
                    "instruction_boundary": {"system": "constitution"},
                },
            },
        )
        self.assertTrue(executed["run"]["validation"]["valid"])
        self.assertFalse(executed["run"]["commit_authority"])
        self.assertEqual(event_count, engine.store.counts()["events"])

        runs = self.request("GET", "/v1/prompt-runs")
        self.assertEqual(1, len(runs["runs"]))
        reviewed = self.request(
            "POST",
            "/v1/prompt-runs/review",
            {"run_id": executed["run"]["run_id"], "decision": "approve", "note": "continue to gate"},
        )
        self.assertEqual("approved-for-deterministic-review", reviewed["run"]["approval"]["status"])
        self.assertFalse(reviewed["run"]["commit_authority"])
        self.assertEqual(event_count, engine.store.counts()["events"] )


if __name__ == "__main__":
    unittest.main()
