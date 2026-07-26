from __future__ import annotations

from dataclasses import replace
from typing import Any

from .model import FrameManifest, PatchProposal, RenderJob, SurfaceState, digest, utc_now


IMAGE_MODES = {"regional_image_edit", "new_keyframe"}


def build_render_job(
    proposal: PatchProposal,
    state: SurfaceState,
    *,
    base_frame_id: str,
) -> RenderJob:
    impact = proposal.render_impact or {}
    mode = str(impact.get("class", "native_ui"))
    if mode not in {"none", "native_ui", "composite", *IMAGE_MODES}:
        mode = "native_ui"
    affected = [str(item) for item in impact.get("affected_object_ids", [])]
    changes = [
        f"{operation.op} {operation.path}"
        for operation in proposal.operations
        if operation.op != "test"
    ]
    job_id = "render_" + digest({"proposal": proposal.proposal_id, "event": proposal.event_id})[:24]
    status = "queued" if mode in IMAGE_MODES else "verified"
    prompt = _render_prompt(state, mode, changes, affected)
    return RenderJob(
        job_id=job_id,
        event_id=proposal.event_id,
        state_hash=state.state_hash,
        branch=state.branch,
        mode=mode,
        status=status,
        base_frame_id=base_frame_id,
        affected_object_ids=affected,
        semantic_changes=changes,
        prompt=prompt,
        preserve_anchors=[object_id for object_id in state.objects if object_id not in affected],
        forbidden_changes=[
            "camera drift",
            "new uncommitted objects",
            "functional UI text mutation",
            "identity changes outside affected objects",
        ],
        verification={"decision": "pass", "source": "deterministic-native"} if status == "verified" else {},
    )


def native_frame_for(job: RenderJob, state: SurfaceState, parent_frame_id: str) -> FrameManifest:
    if job.status != "verified":
        raise ValueError("only verified native jobs can produce immediate frames")
    return FrameManifest(
        frame_id="frame_" + digest({"job": job.job_id, "state": state.state_hash})[:24],
        state_hash=state.state_hash,
        parent_frame_id=parent_frame_id,
        branch=state.branch,
        render_mode=job.mode,
        status="verified",
        render_job_id=job.job_id,
        verification=dict(job.verification),
        created_by=["godot-native-renderer", "surface-compositor"],
    ).seal()


def verify_candidate(job: RenderJob, decision: dict[str, Any]) -> tuple[RenderJob, FrameManifest | None]:
    outcome = str(decision.get("decision", "retry"))
    if outcome not in {"pass", "retry", "fallback", "human_review", "reject"}:
        raise ValueError("invalid frame verification decision")
    updated = replace(job)
    updated.verification = dict(decision)
    updated.updated_at = utc_now()
    if outcome == "pass":
        updated.status = "verified"
        frame = FrameManifest(
            frame_id="frame_" + digest({"job": job.job_id, "verification": decision})[:24],
            state_hash=job.state_hash,
            parent_frame_id=job.base_frame_id,
            branch=job.branch,
            render_mode=job.mode,
            status="verified",
            render_job_id=job.job_id,
            verification=dict(decision),
            created_by=["image-edit-worker", "visual-verifier"],
        ).seal()
        return updated, frame
    if outcome == "retry" and updated.retries < updated.max_retries:
        updated.retries += 1
        updated.status = "queued"
        return updated, None
    if outcome in {"fallback", "retry"}:
        updated.status = "fallback"
        return updated, None
    updated.status = "rejected"
    return updated, None


def _render_prompt(state: SurfaceState, mode: str, changes: list[str], affected: list[str]) -> str:
    return "\n".join(
        [
            "Render the next verified projection of the Simulation AI world surface.",
            f"State hash: {state.state_hash}",
            f"Branch: {state.branch}",
            f"Mode: {mode}",
            "Authoritative changes:",
            *(f"- {change}" for change in changes),
            "Affected objects: " + (", ".join(affected) if affected else "none"),
            "Preserve camera, unaffected object identity, functional UI geometry, and all unmodified regions.",
            "Do not introduce objects absent from committed semantic state.",
        ]
    )
