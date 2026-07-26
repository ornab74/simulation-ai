from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from threading import RLock
from typing import Any

from .adapters import DeterministicObserver, RulePatchProposer
from .credentials import OpenAICredentialVault
from .memory import memory_from_transition, query_memories
from .model_execution import OpenAIResponsesExecutor
from .prompt_runs import PromptRunStore
from .prompts import PromptRegistry
from .workflows import PromptWorkflowRunner
from .model import (
    EventEnvelope,
    EvidenceRecord,
    FrameManifest,
    ObservationReport,
    PatchProposal,
    SurfaceState,
    digest,
)
from .render import build_render_job, native_frame_for, verify_candidate
from .model_setup import GemmaSetup
from .image_generation import generate_image, edit_image
from .encrypted_images import EncryptedImageStore
from .memoric import MemoricRegister
from .store import SurfaceStore
from .validation import apply_proposal, validate_interaction


DEFAULT_OBJECTS: dict[str, dict[str, Any]] = {
    "node.observer": {
        "type": "model",
        "label": "Local Observer",
        "status": "ready",
        "epistemic_class": "observed",
        "layout": [0.20, 0.35],
        "properties": {"adapter": "gemma-ready", "authority": "proposal-only"},
    },
    "node.planner": {
        "type": "planner",
        "label": "Patch Planner",
        "status": "ready",
        "epistemic_class": "inferred",
        "layout": [0.42, 0.20],
        "properties": {"adapter": "gpt-5.6-ready", "authority": "proposal-only"},
    },
    "node.surface": {
        "type": "world",
        "label": "World Surface",
        "status": "active",
        "epistemic_class": "observed",
        "layout": [0.48, 0.46],
        "properties": {"projection": "semantic-topology", "authority": "deterministic-core"},
    },
    "node.memory": {
        "type": "store",
        "label": "Memoric Store",
        "status": "indexed",
        "epistemic_class": "observed",
        "layout": [0.76, 0.34],
        "properties": {"branch_aware": True, "contradiction_retention": True},
    },
    "node.renderer": {
        "type": "render",
        "label": "Render Queue",
        "status": "verified",
        "epistemic_class": "observed",
        "layout": [0.66, 0.70],
        "properties": {"image_state_authoritative": False, "max_retries": 2},
    },
    "node.verifier": {
        "type": "verifier",
        "label": "Frame Verifier",
        "status": "watching",
        "epistemic_class": "observed",
        "layout": [0.34, 0.74],
        "properties": {"protected_regions": True, "anchor_checks": True},
    },
}

DEFAULT_LINKS = [
    ["node.observer", "node.surface", "observe"],
    ["node.surface", "node.planner", "state"],
    ["node.planner", "node.surface", "propose"],
    ["node.surface", "node.memory", "remember"],
    ["node.surface", "node.renderer", "render"],
    ["node.renderer", "node.verifier", "verify"],
    ["node.verifier", "node.surface", "present"],
    ["node.memory", "node.planner", "retrieve"],
]


class SurfaceEngine:
    """Canonical state authority and orchestration boundary.

    Observer, proposal, memory, and rendering adapters are replaceable. Only
    this engine validates and commits state, immutable events, and branch refs.
    """

    def __init__(self, home: Path) -> None:
        self.store = SurfaceStore(home)
        self.observer = DeterministicObserver()
        self.proposer = RulePatchProposer()
        self.credentials = OpenAICredentialVault(home)
        self.images = EncryptedImageStore(home, self.credentials)
        self.memoric = MemoricRegister(home / "memoric-register.json")
        self.prompts = PromptRegistry()
        self.prompt_runs = PromptRunStore(home)
        self.model_executor = OpenAIResponsesExecutor(self.credentials, self.prompts)
        self.workflow_runner = PromptWorkflowRunner(self.prompts, self.model_executor, self.prompt_runs)
        # The model is a project asset, not core state. Resolve it from the
        # process working directory so launching the server from scripts or
        # an IDE still finds <project>/models/gemma-4-E2B-it.litertlm.
        self.gemma = GemmaSetup(Path.cwd() / "models")
        self._lock = RLock()
        if not (self.store.refs / "HEAD").exists():
            self.boot()

    def boot(self) -> SurfaceState:
        with self._lock:
            state = SurfaceState(
                objects=deepcopy(DEFAULT_OBJECTS),
                ui={
                    "simulation_running": True,
                    "last_command": "",
                    "inputs": {},
                    "topology_links": deepcopy(DEFAULT_LINKS),
                    "privacy": {
                        "cloud_allowed": False,
                        "frame_retention": "bounded",
                        "redact_sensitive_inputs": True,
                    },
                    "render_policy": "native-first",
                    "reduced_motion": False,
                },
                hypotheses=[
                    {
                        "hypothesis_id": "h_native-first",
                        "label": "Native UI is sufficient for the next transition",
                        "probability": 0.78,
                        "epistemic_class": "inferred",
                    },
                    {
                        "hypothesis_id": "h_image-keyframe",
                        "label": "A generated keyframe may be required",
                        "probability": 0.22,
                        "epistemic_class": "inferred",
                    },
                ],
                claims=[
                    {
                        "claim_id": "claim_pixels_projection",
                        "statement": "Pixels are a projection of committed semantic state.",
                        "epistemic_class": "observed",
                        "confidence": 1.0,
                    }
                ],
                layer_state={
                    "sensorium": {},
                    "signals": {},
                    "objects": {"count": len(DEFAULT_OBJECTS)},
                    "states": {},
                    "events": {"last_action": {}},
                    "goals": {},
                    "plans": {},
                    "causal_model": {
                        "invariants": [
                            "models cannot directly commit state",
                            "generated pixels are non-authoritative",
                            "branch refs point to immutable states",
                        ]
                    },
                    "meta_model": {"failures": 0, "contradictions": 0},
                    "identity": {
                        "target_name": "Simulation AI World Surface",
                        "rights_boundary": "operator-supplied and generated assets only",
                    },
                },
                render={
                    "status": "verified",
                    "requested_mode": "native_ui",
                    "committed_frame_id": "frame_genesis",
                    "pending_job_id": "",
                },
                provenance={
                    "authority": "deterministic-core",
                    "generated_content_disclosure": True,
                    "pixel_state_authoritative": False,
                    "proposal_models": [self.observer.model_id, self.proposer.model_id],
                    "prompt_pack": {
                        "pack_id": self.prompts.pack_id,
                        "pack_version": self.prompts.pack_version,
                        "pack_sha256": self.prompts.pack_sha256(),
                    },
                    "rights_policy": "clean-room-world-surface",
                },
            ).seal()
            self.store.save_state(state)
            self.store.set_ref("HEAD", state.state_hash)
            self.store.set_ref("branch-main", state.state_hash)
            genesis = FrameManifest(
                frame_id="frame_genesis",
                state_hash=state.state_hash,
                parent_frame_id="",
                branch="main",
                render_mode="native_ui",
                status="verified",
                render_job_id="boot",
                verification={"decision": "pass", "source": "deterministic-boot"},
                created_by=["surface-core"],
            ).seal()
            self.store.save_frame(genesis)
            return state

    def current(self) -> SurfaceState:
        with self._lock:
            return self.store.load_state("HEAD")

    def snapshot(self, *, event_limit: int = 40, render_limit: int = 12) -> dict[str, Any]:
        with self._lock:
            state = self.current()
            return {
                "schema": "nmsr.snapshot/1",
                "state": state.as_dict(),
                "events": [event.as_dict() for event in reversed(self.store.list_events(limit=event_limit))],
                "branches": self.list_branches(),
                "render_jobs": [job.as_dict() for job in reversed(self.store.list_render_jobs(limit=render_limit))],
                "frames": [frame.as_dict() for frame in reversed(self.store.list_frames(limit=8))],
                "counts": self.store.counts(),
                "adapters": self.adapter_status(),
                "credentials": {"openai": self.credential_status()},
                "prompt_pack": self.prompt_summary(),
                "replay": self.verify_replay(),
                "memoric": self.memoric.context(),
            }

    def adapter_status(self) -> list[dict[str, Any]]:
        credential = self.credentials.status()
        openai_available = credential.unlocked or credential.env_available
        openai_status = "ready" if openai_available else ("locked" if credential.configured else "credential-required")
        credential_source = "encrypted-vault" if credential.unlocked else ("environment" if credential.env_available else "none")
        return [
            {
                "id": "local-observer",
                "label": "Gemma 4 E2B Observer",
                "status": "fallback-ready",
                "runtime": self.observer.model_id,
                "authority": "observation only",
                "prompt_ids": ["local_observer", "os_runtime_observer", "unknown_app_discovery_observer"],
                "local": True,
            },
            {
                "id": "state-planner",
                "label": "GPT-5.6 Patch Planner",
                "status": openai_status,
                "runtime": f"{self.proposer.model_id} / {credential_source}",
                "authority": "proposal only",
                "prompt_ids": ["state_patch_proposer", "patch_critic", "counterfactual_branch_planner", "semantic_merge_planner"],
                "local": False,
            },
            {
                "id": "image-worker",
                "label": "OpenAI Image Edit Worker",
                "status": openai_status,
                "runtime": f"openai-image-edit-adapter / {credential_source}",
                "authority": "candidate pixels only",
                "prompt_ids": ["render_director", "image_edit_director", "frame_verifier"],
                "local": False,
            },
            {
                "id": "surface-core",
                "label": "Deterministic Surface Core",
                "status": "online",
                "runtime": "python + encrypted credential vault",
                "authority": "canonical commit",
                "prompt_ids": [],
                "local": True,
            },
        ]

    def prompt_summary(self) -> dict[str, Any]:
        validation = self.prompts.validate_pack()
        return {
            "pack_id": self.prompts.pack_id,
            "pack_version": self.prompts.pack_version,
            "pack_sha256": validation["pack_sha256"],
            "prompt_count": validation["prompt_count"],
            "callable_prompt_count": sum(1 for item in self.prompts.specs.values() if item.callable),
            "workflow_count": validation["workflow_count"],
            "valid": validation["valid"],
            "problems": validation["problems"],
            "model_run_count": len(self.prompt_runs.list_model_runs(limit=500)),
            "workflow_run_count": len(self.prompt_runs.list_workflow_runs(limit=500)),
        }

    def generate_boot_image(self, prompt: str) -> dict[str, object]:
        result = generate_image(self.credentials, prompt, self.store.root / "artifacts")
        marker = self.store.root / "origin-image.id"
        if not marker.exists():
            marker.write_text(str(result["id"]), encoding="utf-8")
        return result

    def latest_saved_image(self) -> dict[str, object]:
        path = self.images.latest_path()
        return {"path": str(path), "restored": True} if path else {"path": "", "restored": False}

    def reset_desktop_image(self) -> dict[str, object]:
        path = self.images.origin_path()
        return {"path": str(path), "reset": True} if path else {"path": "", "reset": False}

    def edit_latest_image(self, prompt: str) -> dict[str, object]:
        images = self.images.list()
        if not images:
            return self.generate_boot_image(prompt)
        source = self.images.materialize(str(images[0]["id"]))
        history = "\n".join(
            f"- frame {item['id']} at {item['created_at']} sha256={item['sha256']}"
            for item in images[:8]
        )
        continuity = (
            "\nCROSS-FRAME SURFACE MEMORY:\n"
            "Treat the supplied previous frame as the canonical visual surface. "
            "Preserve stable anchors: desktop bounds, taskbar baseline, icon centers, window chrome, "
            "font scale, control geometry, and camera framing. Change only the user operation.\n"
            "RECENT FRAME HISTORY:\n" + history +
            "\nDISPLAY-MODULE CONTRACT:\n"
            "Infer the clicked module, its bounding box, visible label, control role, and resulting state. "
            "For text boxes, preserve caret/focus, placeholder/value, baseline, font size, and typed text. "
            "Never hallucinate a new textbox or move an unaffected control."
        )
        memoric = json.dumps(self.memoric.context(), ensure_ascii=False, separators=(",", ":"))
        return edit_image(self.credentials, prompt + continuity + "\nMEMORIC CONSTRAINT REGISTER:\n" + memoric, source, self.store.root / "artifacts")

    def prompt_catalog(self, *, include_shared: bool = True) -> dict[str, Any]:
        return self.prompts.catalog(include_shared=include_shared)

    def prompt_details(self, prompt_id: str) -> dict[str, Any]:
        return self.prompts.get_details(prompt_id)

    def prompt_render(self, prompt_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return self.prompts.render(prompt_id, inputs)

    def prompt_route(self, task_type: str) -> dict[str, Any]:
        return self.prompts.route(task_type)

    def prompt_validate(self) -> dict[str, Any]:
        return self.prompts.validate_pack()

    def prompt_validate_output(self, prompt_id: str, output: dict[str, Any]) -> dict[str, Any]:
        return self.prompts.validate_output(prompt_id, output)

    def prompt_execute(
        self,
        prompt_id: str,
        inputs: dict[str, Any],
        *,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            privacy = dict(self.current().ui.get("privacy", {}))
            if not bool(privacy.get("cloud_allowed", False)):
                raise PermissionError("cloud model execution is disabled by the committed privacy policy")
            invocation = self.prompts.render(prompt_id, inputs)
            record = self.model_executor.execute(
                invocation,
                model=model,
                reasoning_effort=reasoning_effort,
                max_output_tokens=max_output_tokens,
            )
            return self.prompt_runs.save_model_run(record)

    def prompt_run_list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.prompt_runs.list_model_runs(limit=limit)

    def prompt_run_get(self, run_id: str) -> dict[str, Any]:
        return self.prompt_runs.load_model_run(run_id)

    def prompt_run_review(
        self,
        run_id: str,
        *,
        decision: str,
        note: str = "",
        reviewed_by: str = "operator",
    ) -> dict[str, Any]:
        return self.prompt_runs.review_model_run(
            run_id, decision=decision, note=note, reviewed_by=reviewed_by
        )

    def prompt_workflow_execute(
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
        with self._lock:
            privacy = dict(self.current().ui.get("privacy", {}))
            if not bool(privacy.get("cloud_allowed", False)):
                raise PermissionError("cloud model execution is disabled by the committed privacy policy")
            return self.workflow_runner.execute(
                workflow_id,
                step_inputs=step_inputs,
                model=model,
                model_overrides=model_overrides,
                reasoning_effort=reasoning_effort,
                max_output_tokens=max_output_tokens,
                stop_on_invalid=stop_on_invalid,
                max_steps=max_steps,
            )

    def prompt_workflow_run_list(self, *, limit: int = 25) -> list[dict[str, Any]]:
        return self.prompt_runs.list_workflow_runs(limit=limit)

    def credential_status(self) -> dict[str, Any]:
        return self.credentials.status().as_dict()

    def credential_save(self, api_key: str, password: str) -> dict[str, Any]:
        return self.credentials.save(api_key, password).as_dict()

    def credential_import_environment(self, password: str) -> dict[str, Any]:
        return self.credentials.import_environment(password).as_dict()

    def credential_unlock(self, password: str) -> dict[str, Any]:
        return self.credentials.unlock(password).as_dict()

    def credential_lock(self) -> dict[str, Any]:
        return self.credentials.lock().as_dict()

    def credential_clear(self, password: str = "") -> dict[str, Any]:
        return self.credentials.clear(password).as_dict()

    def credential_test(self) -> dict[str, Any]:
        return self.credentials.test_connection()

    def observe(self, packet: dict[str, Any]) -> ObservationReport:
        with self._lock:
            packet = self._sanitize_packet(packet)
            validate_interaction(packet)
            current = self.current()
            self._validate_packet_parent(packet, current)
            observation = self.observer.observe(packet, current)
            if self.store.evidence_exists(observation.observation_id):
                stored = self.store.load_evidence(observation.observation_id)
                return ObservationReport(**stored.payload)
            evidence = EvidenceRecord(
                evidence_id=observation.observation_id,
                kind="interaction-observation",
                source=observation.source,
                payload=observation.as_dict(),
                logical_time=observation.logical_time,
                branch=observation.branch,
                epistemic_class="observed" if observation.confidence >= 0.8 else "inferred",
                confidence=observation.confidence,
            )
            self.store.save_evidence(evidence)
            return observation

    def propose(
        self,
        packet: dict[str, Any],
        observation: ObservationReport | None = None,
    ) -> PatchProposal:
        with self._lock:
            packet = self._sanitize_packet(packet)
            validate_interaction(packet)
            current = self.current()
            self._validate_packet_parent(packet, current)
            observation = observation or self.observe(packet)
            proposal = self.proposer.propose(packet, observation, current)
            self.store.save_proposal(proposal)
            return proposal

    def commit_proposal(
        self,
        proposal: PatchProposal | dict[str, Any],
        *,
        packet: dict[str, Any] | None = None,
        observation: ObservationReport | None = None,
    ) -> tuple[SurfaceState, EventEnvelope, dict[str, Any]]:
        with self._lock:
            proposal = proposal if isinstance(proposal, PatchProposal) else PatchProposal.from_dict(proposal)
            current = self.current()
            next_state = apply_proposal(current, proposal)
            next_state.entropy_bits = max(
                0.0,
                round(current.entropy_bits + (0.025 if proposal.uncertainties else -0.006), 6),
            )
            next_state.coherence = max(
                0.0,
                min(1.0, round(current.coherence - (0.018 if proposal.requires_review else 0.001), 6)),
            )
            render_mode = str((proposal.render_impact or {}).get("class", "native_ui"))
            render_status = "queued" if render_mode in {"regional_image_edit", "new_keyframe"} else "verified"
            render_job_id = "render_" + digest({"proposal": proposal.proposal_id, "event": proposal.event_id})[:24]
            next_state.render["status"] = render_status
            next_state.render["requested_mode"] = render_mode
            next_state.render["pending_job_id"] = render_job_id if render_status == "queued" else ""
            next_state.seal()
            action_kind = str((packet or {}).get("action", {}).get("kind", "proposal"))
            target_id = str((packet or {}).get("target", {}).get("node_id", next_state.selected_object_id))
            event = EventEnvelope(
                index=len(self.store.list_events()) + 1,
                event_id=proposal.event_id,
                action=action_kind,
                arguments=deepcopy((packet or {}).get("action", {"kind": action_kind})),
                target_id=target_id,
                logical_time=next_state.logical_time,
                parent_state_hash=current.state_hash,
                resulting_state_hash=next_state.state_hash,
                branch=next_state.branch,
                evidence_ids=[observation.observation_id] if observation else [],
                proposal_id=proposal.proposal_id,
                epistemic_class="inferred" if proposal.requires_review else "observed",
                status="committed",
            ).seal()
            if self.store.event_id_exists(event.event_id):
                raise ValueError("duplicate event_id")

            base_frame_id = str(current.render.get("committed_frame_id", "frame_genesis"))
            render_job = build_render_job(proposal, next_state, base_frame_id=base_frame_id)
            if render_job.job_id != render_job_id or render_job.status != render_status:
                raise ValueError("render planning produced an inconsistent job identity")
            if render_job.status == "verified":
                frame = native_frame_for(render_job, next_state, base_frame_id)
                next_state.render["committed_frame_id"] = frame.frame_id
                next_state.seal()
                render_job.state_hash = next_state.state_hash
                frame.state_hash = next_state.state_hash
                frame.frame_hash = ""
                frame.seal()
                self.store.save_frame(frame)
            else:
                render_job.state_hash = next_state.state_hash
            event.resulting_state_hash = next_state.state_hash
            event.seal()

            self.store.save_state(next_state)
            self.store.append_event(event)
            self.store.save_render_job(render_job)
            self.store.set_ref("HEAD", next_state.state_hash)
            self.store.set_ref(f"branch-{next_state.branch}", next_state.state_hash)

            if observation is None:
                observation = ObservationReport(
                    observation_id="obs_" + digest(event.event_hash)[:24],
                    event_id=event.event_id,
                    logical_time=event.logical_time,
                    branch=event.branch,
                    action={"kind": event.action, "target_id": event.target_id},
                    before={},
                    after={},
                    confidence=0.7,
                    source="commit-boundary",
                )
            memory = memory_from_transition(event, observation, next_state)
            self.store.save_memory(memory)
            return next_state, event, {
                "proposal": proposal.as_dict(),
                "render_job": render_job.as_dict(),
                "memory": memory.as_dict(),
            }

    def interact(self, packet: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            packet = self._sanitize_packet(packet)
            validate_interaction(packet)
            if self.store.event_id_exists(str(packet["event_id"])):
                raise ValueError("duplicate event_id")
            observation = self.observe(packet)
            proposal = self.propose(packet, observation)
            state, event, artifacts = self.commit_proposal(
                proposal,
                packet=packet,
                observation=observation,
            )
            artifacts["memoric"] = self.memoric.deposit(packet, observation.as_dict(), state.as_dict())
            return {
                "state": state.as_dict(),
                "event": event.as_dict(),
                "observation": observation.as_dict(),
                **artifacts,
            }

    def create_branch(self, name: str) -> SurfaceState:
        clean = self._clean_branch_name(name)
        with self._lock:
            if f"branch-{clean}" in self.store.list_refs("branch-"):
                raise ValueError("branch already exists")
            current = self.current()
            branch = SurfaceState.from_dict(deepcopy(current.as_dict()))
            branch.parent_state_hash = current.state_hash
            branch.logical_time += 1
            branch.branch = clean
            branch.layer_state["meta_model"]["forked_from"] = current.branch
            branch.layer_state["meta_model"]["fork_state_hash"] = current.state_hash
            branch.seal()
            self.store.save_state(branch)
            self.store.set_ref("HEAD", branch.state_hash)
            self.store.set_ref(f"branch-{clean}", branch.state_hash)
            event = EventEnvelope(
                index=len(self.store.list_events()) + 1,
                event_id="evt_branch_" + digest({"name": clean, "parent": current.state_hash})[:18],
                action="branch:create",
                arguments={"name": clean, "forked_from": current.branch},
                target_id="node.surface",
                logical_time=branch.logical_time,
                parent_state_hash=current.state_hash,
                resulting_state_hash=branch.state_hash,
                branch=clean,
                epistemic_class="counterfactual",
                actor="surface-core",
            ).seal()
            self.store.append_event(event)
            return branch

    def switch_branch(self, name: str) -> SurfaceState:
        clean = self._clean_branch_name(name)
        with self._lock:
            ref = f"branch-{clean}"
            if ref not in self.store.list_refs("branch-"):
                raise ValueError("branch does not exist")
            state_hash = self.store.read_ref(ref)
            self.store.set_ref("HEAD", state_hash)
            return self.store.load_state("HEAD")

    def list_branches(self) -> list[dict[str, Any]]:
        head_hash = self.store.read_ref("HEAD")
        branches: list[dict[str, Any]] = []
        for ref, state_hash in self.store.list_refs("branch-").items():
            state = self.store.load_state(state_hash)
            branches.append(
                {
                    "name": ref.removeprefix("branch-"),
                    "state_hash": state_hash,
                    "logical_time": state.logical_time,
                    "active": state_hash == head_hash,
                    "parent_state_hash": state.parent_state_hash,
                }
            )
        return sorted(branches, key=lambda item: (not item["active"], item["name"]))

    def query_memory(
        self,
        query: str,
        *,
        branch: str | None = None,
        object_ids: list[str] | None = None,
        limit: int = 12,
    ) -> list[dict[str, object]]:
        current = self.current()
        return query_memories(
            self.store.list_memories(),
            query,
            branch=branch or current.branch,
            object_ids=object_ids,
            limit=limit,
        )

    def verify_render(self, job_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job = self.store.load_render_job(job_id)
            updated, frame = verify_candidate(job, decision)
            self.store.save_render_job(updated, replace=True)
            state = self.current()
            if state.state_hash == job.state_hash:
                next_state = SurfaceState.from_dict(deepcopy(state.as_dict()))
                next_state.parent_state_hash = state.state_hash
                next_state.logical_time += 1
                next_state.render["status"] = updated.status
                next_state.render["pending_job_id"] = "" if updated.status != "queued" else updated.job_id
                next_state.objects["node.renderer"]["status"] = updated.status
                if frame is not None:
                    next_state.render["committed_frame_id"] = frame.frame_id
                next_state.seal()
                if frame is not None:
                    frame.state_hash = next_state.state_hash
                    frame.frame_hash = ""
                    frame.seal()
                    self.store.save_frame(frame)
                verification_event = EventEnvelope(
                    index=len(self.store.list_events()) + 1,
                    event_id="evt_verify_" + digest({"job": job_id, "decision": decision, "time": next_state.logical_time})[:18],
                    action="render:verify",
                    arguments={"job_id": job_id, "decision": str(decision.get("decision", "retry"))},
                    target_id="node.renderer",
                    logical_time=next_state.logical_time,
                    parent_state_hash=state.state_hash,
                    resulting_state_hash=next_state.state_hash,
                    branch=next_state.branch,
                    evidence_ids=[],
                    epistemic_class="observed",
                    actor="frame-verifier",
                ).seal()
                self.store.save_state(next_state)
                self.store.append_event(verification_event)
                self.store.set_ref("HEAD", next_state.state_hash)
                self.store.set_ref(f"branch-{next_state.branch}", next_state.state_hash)
                state = next_state
            return {
                "job": updated.as_dict(),
                "frame": frame.as_dict() if frame else None,
                "state": state.as_dict(),
            }

    def verify_replay(self) -> dict[str, Any]:
        problems: list[str] = []
        events = self.store.list_events()
        seen_ids: set[str] = set()
        for expected, event in enumerate(events, start=1):
            if event.index != expected:
                problems.append(f"event index mismatch: expected {expected}, got {event.index}")
            if event.event_id in seen_ids:
                problems.append(f"duplicate event ID: {event.event_id}")
            seen_ids.add(event.event_id)
            supplied_hash = event.event_hash
            copied = EventEnvelope(**event.as_dict())
            copied.event_hash = ""
            copied.seal()
            if copied.event_hash != supplied_hash:
                problems.append(f"event hash mismatch: {event.event_id}")
            if not self.store.state_exists(event.parent_state_hash):
                problems.append(f"event parent state missing: {event.event_id}")
            if not self.store.state_exists(event.resulting_state_hash):
                problems.append(f"event result state missing: {event.event_id}")
        for path in self.store.iter_states():
            state = SurfaceState.from_dict(self.store._read_json(path))
            supplied = state.state_hash
            state.seal()
            if supplied != state.state_hash:
                problems.append(f"state hash mismatch: {path.stem}")
        for ref, state_hash in self.store.list_refs().items():
            if not self.store.state_exists(state_hash):
                problems.append(f"ref points to missing state: {ref}")
        return {
            "verified": not problems,
            "event_count": len(events),
            "state_count": self.store.counts()["states"],
            "head": self.store.read_ref("HEAD"),
            "problems": problems,
        }

    @staticmethod
    def _sanitize_packet(packet: dict[str, Any]) -> dict[str, Any]:
        sanitized = deepcopy(packet)
        action = sanitized.setdefault("action", {})
        target = sanitized.setdefault("target", {})
        privacy = sanitized.setdefault("privacy", {})
        if bool(target.get("sensitive", False)) and str(action.get("kind", "")) == "type":
            raw_text = action.get("text")
            if "typed_character_count" not in action:
                action["typed_character_count"] = len(str(raw_text or ""))
            action["text"] = None
            redactions = list(privacy.get("redactions", []))
            if "sensitive-input" not in redactions:
                redactions.append("sensitive-input")
            privacy["redactions"] = redactions
        return sanitized

    @staticmethod
    def _clean_branch_name(name: str) -> str:
        clean = "".join(char for char in name.lower() if char.isalnum() or char in "-_").strip("-_")
        if not clean:
            raise ValueError("branch name is empty")
        if len(clean) > 64:
            raise ValueError("branch name is too long")
        return clean

    @staticmethod
    def _validate_packet_parent(packet: dict[str, Any], current: SurfaceState) -> None:
        expected_parent = str(packet.get("parent_state_hash", ""))
        if expected_parent not in {"", "genesis", current.state_hash}:
            raise ValueError("stale parent state hash")
        packet_branch = str(packet.get("branch", current.branch))
        if packet_branch != current.branch:
            raise ValueError("interaction branch does not match active branch")
