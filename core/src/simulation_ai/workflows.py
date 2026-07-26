from __future__ import annotations

from typing import Any

from .model import digest, utc_now
from .model_execution import ModelExecutionError, OpenAIResponsesExecutor
from .prompt_runs import PromptRunStore
from .prompts import PromptPackError, PromptRegistry


class PromptWorkflowRunner:
    """Run explicitly supplied workflow steps without implicit state mutation."""

    def __init__(
        self,
        prompts: PromptRegistry,
        executor: OpenAIResponsesExecutor,
        store: PromptRunStore,
    ) -> None:
        self.prompts = prompts
        self.executor = executor
        self.store = store

    def execute(
        self,
        workflow_id: str,
        *,
        step_inputs: dict[str, Any],
        model: str | None = None,
        model_overrides: dict[str, str] | None = None,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
        stop_on_invalid: bool = True,
        max_steps: int | None = None,
    ) -> dict[str, Any]:
        workflow = self._workflow(workflow_id)
        if not isinstance(step_inputs, dict):
            raise PromptPackError("step_inputs must be an object keyed by prompt id")
        model_overrides = model_overrides or {}
        unknown = sorted(set(step_inputs) - set(workflow.get("prompts", [])))
        if unknown:
            raise PromptPackError(f"workflow inputs reference unknown steps: {', '.join(unknown)}")
        planned_prompts = list(workflow.get("prompts", []))
        if max_steps is not None:
            planned_prompts = planned_prompts[: max(1, min(len(planned_prompts), int(max_steps)))]
        workflow_run_id = "workflow_" + digest({
            "workflow": workflow_id,
            "pack": self.prompts.pack_sha256(),
            "step_input_hashes": {key: digest(value) for key, value in sorted(step_inputs.items())},
            "model": model or "default",
            "overrides": model_overrides,
        })[:24]
        steps: list[dict[str, Any]] = []
        status = "completed"
        for index, prompt_id in enumerate(planned_prompts):
            raw_inputs = step_inputs.get(prompt_id)
            if raw_inputs is None:
                steps.append({
                    "index": index,
                    "prompt_id": prompt_id,
                    "status": "awaiting-input",
                    "run_id": "",
                    "output_sha256": "",
                    "valid": False,
                    "detail": "Explicit step inputs were not supplied.",
                })
                status = "awaiting-input"
                break
            if not isinstance(raw_inputs, dict):
                raise PromptPackError(f"step inputs for {prompt_id} must be an object")
            try:
                invocation = self.prompts.render(prompt_id, raw_inputs)
                record = self.executor.execute(
                    invocation,
                    model=model_overrides.get(prompt_id) or model,
                    reasoning_effort=reasoning_effort,
                    max_output_tokens=max_output_tokens,
                )
                stored = self.store.save_model_run(record)
                valid = bool(stored.get("validation", {}).get("valid", False))
                steps.append({
                    "index": index,
                    "prompt_id": prompt_id,
                    "status": stored.get("status", "unknown"),
                    "run_id": stored.get("run_id", ""),
                    "output_sha256": stored.get("output_sha256", ""),
                    "valid": valid,
                    "detail": "Candidate validated locally." if valid else "Candidate failed local schema validation.",
                })
                if not valid and stop_on_invalid:
                    status = "stopped-invalid"
                    break
            except (ModelExecutionError, PromptPackError) as exc:
                steps.append({
                    "index": index,
                    "prompt_id": prompt_id,
                    "status": "failed",
                    "run_id": "",
                    "output_sha256": "",
                    "valid": False,
                    "detail": str(exc)[:500],
                })
                status = "failed"
                break
        record = {
            "schema": "nmsr.prompt-workflow-run/1",
            "workflow_run_id": workflow_run_id,
            "workflow_id": workflow_id,
            "workflow_title": workflow.get("title", workflow_id),
            "status": status,
            "steps": steps,
            "deterministic_gates": list(workflow.get("deterministic_gates", [])),
            "gate_status": "pending",
            "pack_id": self.prompts.pack_id,
            "pack_version": self.prompts.pack_version,
            "pack_sha256": self.prompts.pack_sha256(),
            "commit_authority": False,
            "deterministic_gate_required": True,
            "created_at": utc_now(),
        }
        return self.store.save_workflow_run(record)

    def _workflow(self, workflow_id: str) -> dict[str, Any]:
        for workflow in self.prompts.workflows:
            if workflow.get("id") == workflow_id:
                return dict(workflow)
        raise PromptPackError(f"unknown prompt workflow: {workflow_id}")
