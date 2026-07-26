from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import json

from jsonschema import Draft202012Validator

from simulation_ai.model import digest, utc_now
from simulation_ai.prompt_runs import PromptRunStore
from simulation_ai.prompts import PromptRegistry
from simulation_ai.workflows import PromptWorkflowRunner


class FakeExecutor:
    def __init__(self, prompts: PromptRegistry) -> None:
        self.prompts = prompts
        self.calls: list[str] = []

    def execute(self, invocation, **_kwargs):
        prompt_id = invocation["prompt_id"]
        self.calls.append(prompt_id)
        output = self._valid_output(prompt_id)
        validation = self.prompts.validate_output(prompt_id, output)
        return {
            "schema": "nmsr.prompt-run/1",
            "run_id": "run_" + digest({"prompt": prompt_id, "call": len(self.calls)})[:24],
            "kind": "model-prompt",
            "status": "validated",
            "provider": "test",
            "provider_response_id": "resp_" + str(len(self.calls)),
            "provider_request_id": "req_" + str(len(self.calls)),
            "provider_status": "completed",
            "credential_source": "test",
            "prompt_id": prompt_id,
            "prompt_version": invocation["prompt_version"],
            "prompt_sha256": invocation["prompt_sha256"],
            "pack_id": invocation["pack_id"],
            "pack_version": invocation["pack_version"],
            "invocation_id": invocation["invocation_id"],
            "request_sha256": digest({"invocation": invocation["invocation_id"]}),
            "model": "fake",
            "reasoning_effort": "none",
            "max_output_tokens": 1024,
            "attempts": 1,
            "latency_ms": 0.1,
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "output": output,
            "output_sha256": validation["output_sha256"],
            "validation": validation,
            "approval": {"status": "pending", "reviewed_by": "", "note": "", "reviewed_at": ""},
            "authority": invocation["authority"],
            "commit_authority": False,
            "deterministic_gate_required": True,
            "store_requested": False,
            "provider_strict_schema": False,
            "created_at": utc_now(),
        }

    @staticmethod
    def _valid_output(prompt_id: str):
        if prompt_id == "prompt_injection_detector":
            return {
                "schema": "nmsr.injection-review/1",
                "detected": False,
                "risk_level": "none",
                "findings": [],
                "affected_boundaries": [],
                "recommended_handling": ["continue as untrusted data"],
                "safe_to_continue_as_data": True,
                "confidence": 1.0,
            }
        if prompt_id == "data_minimization_reviewer":
            return {
                "schema": "nmsr.data-minimization-review/1",
                "allowed_fields": ["summary"],
                "removed_fields": [],
                "localized_fields": [],
                "transformations": [],
                "residual_risks": [],
                "provider_dispatch_allowed": True,
                "confidence": 1.0,
            }
        raise AssertionError(prompt_id)


class PromptWorkflowRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.prompts = PromptRegistry()
        self.store = PromptRunStore(Path(self.temp.name))
        self.executor = FakeExecutor(self.prompts)
        self.runner = PromptWorkflowRunner(self.prompts, self.executor, self.store)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_workflow_requires_explicit_inputs_and_stops_cleanly(self) -> None:
        record = self.runner.execute(
            "prompt_execution_governance",
            step_inputs={
                "prompt_injection_detector": {
                    "untrusted_content": {"text": "normal data"},
                    "instruction_boundary": {"system": "constitution"},
                },
                "data_minimization_reviewer": {
                    "candidate_inputs": {"summary": "normal data"},
                    "prompt_contract": {"id": "example"},
                    "privacy_policy": {"cloud_allowed": True},
                },
            },
            max_steps=3,
        )
        self.assertEqual("awaiting-input", record["status"])
        self.assertEqual(3, len(record["steps"]))
        self.assertEqual("awaiting-input", record["steps"][-1]["status"])
        self.assertFalse(record["commit_authority"])
        self.assertEqual(2, len(self.store.list_model_runs()))
        self.assertEqual(1, len(self.store.list_workflow_runs()))
        workflow_schema = json.loads((self.prompts.schema_dir / "prompt-workflow-run.schema.json").read_text())
        Draft202012Validator(workflow_schema).validate(record)
        run_schema = json.loads((self.prompts.schema_dir / "prompt-run.schema.json").read_text())
        for run in self.store.list_model_runs():
            Draft202012Validator(run_schema).validate(run)


if __name__ == "__main__":
    unittest.main()
