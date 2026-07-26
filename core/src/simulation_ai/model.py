from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any


EPISTEMIC_CLASSES = {
    "observed",
    "inferred",
    "counterfactual",
    "speculative",
    "unknown",
}

LAYER_NAMES = (
    "sensorium",
    "signals",
    "objects",
    "states",
    "events",
    "goals",
    "plans",
    "causal_model",
    "meta_model",
    "identity",
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Serializable:
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvidenceRecord(Serializable):
    evidence_id: str
    kind: str
    source: str
    payload: dict[str, Any]
    logical_time: int
    branch: str
    epistemic_class: str = "observed"
    confidence: float = 1.0
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.epistemic_class not in EPISTEMIC_CLASSES:
            raise ValueError(f"unsupported epistemic class: {self.epistemic_class}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("evidence confidence must be in [0, 1]")


@dataclass(slots=True)
class ObservationReport(Serializable):
    observation_id: str
    event_id: str
    logical_time: int
    branch: str
    action: dict[str, Any]
    before: dict[str, Any]
    after: dict[str, Any]
    candidate_effects: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = "deterministic-observer"
    schema: str = "nmsr.observation/1"


@dataclass(slots=True)
class PatchOperation(Serializable):
    op: str
    path: str
    value: Any = None
    evidence_ids: list[str] = field(default_factory=list)
    epistemic_class: str = "observed"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.op not in {"test", "add", "replace", "remove"}:
            raise ValueError(f"unsupported patch operation: {self.op}")
        if self.epistemic_class not in EPISTEMIC_CLASSES:
            raise ValueError(f"unsupported epistemic class: {self.epistemic_class}")
        if not self.path.startswith("/"):
            raise ValueError("patch path must be an absolute JSON pointer")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("operation confidence must be in [0, 1]")


@dataclass(slots=True)
class PatchProposal(Serializable):
    proposal_id: str
    event_id: str
    parent_state_hash: str
    branch: str
    intent: dict[str, Any]
    operations: list[PatchOperation]
    expected_postconditions: list[dict[str, Any]] = field(default_factory=list)
    invariants_expected_to_hold: list[str] = field(default_factory=list)
    render_impact: dict[str, Any] = field(default_factory=dict)
    uncertainties: list[str] = field(default_factory=list)
    requires_review: bool = False
    model_id: str = "rule-proposer"
    schema: str = "nmsr.patch-proposal/1"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operations"] = [operation.as_dict() for operation in self.operations]
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PatchProposal":
        raw = dict(value)
        raw["operations"] = [PatchOperation(**item) for item in raw.get("operations", [])]
        return cls(**raw)


@dataclass(slots=True)
class EventEnvelope(Serializable):
    index: int
    event_id: str
    action: str
    arguments: dict[str, Any]
    target_id: str
    logical_time: int
    parent_state_hash: str
    resulting_state_hash: str
    branch: str
    evidence_ids: list[str] = field(default_factory=list)
    proposal_id: str = ""
    epistemic_class: str = "observed"
    status: str = "committed"
    actor: str = "operator"
    created_at: str = field(default_factory=utc_now)
    event_hash: str = ""

    def seal(self) -> "EventEnvelope":
        payload = asdict(self)
        payload["event_hash"] = ""
        self.event_hash = digest(payload)
        return self


@dataclass(slots=True)
class MemoryRecord(Serializable):
    memory_id: str
    memory_type: str
    branch_scope: str
    summary: str
    evidence_ids: list[str]
    state_hashes: list[str]
    object_ids: list[str]
    confidence: float
    epistemic_class: str
    retention: str = "persistent"
    tags: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    logical_time: int = 0
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.epistemic_class not in EPISTEMIC_CLASSES:
            raise ValueError(f"unsupported epistemic class: {self.epistemic_class}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("memory confidence must be in [0, 1]")


@dataclass(slots=True)
class RenderJob(Serializable):
    job_id: str
    event_id: str
    state_hash: str
    branch: str
    mode: str
    status: str
    base_frame_id: str
    affected_object_ids: list[str]
    semantic_changes: list[str]
    prompt: str
    mask_bounds: list[list[int]] = field(default_factory=list)
    preserve_anchors: list[str] = field(default_factory=list)
    forbidden_changes: list[str] = field(default_factory=list)
    retries: int = 0
    max_retries: int = 2
    verification: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class FrameManifest(Serializable):
    frame_id: str
    state_hash: str
    parent_frame_id: str
    branch: str
    render_mode: str
    status: str
    render_job_id: str
    verification: dict[str, Any]
    created_by: list[str]
    frame_hash: str = ""
    created_at: str = field(default_factory=utc_now)

    def seal(self) -> "FrameManifest":
        payload = asdict(self)
        payload["frame_hash"] = ""
        self.frame_hash = digest(payload)
        return self


@dataclass(slots=True)
class SurfaceState(Serializable):
    schema_version: str = "nmsr.surface-state/2"
    map_id: str = "simulation-ai"
    target: str = "semantic-topology"
    profile: str = "world-surface-studio"
    mode: str = "hybrid"
    seed: int = 42
    logical_time: int = 0
    branch: str = "main"
    parent_state_hash: str = ""
    state_hash: str = ""
    entropy_bits: float = 0.72
    coherence: float = 0.94
    selected_object_id: str = "node.surface"
    active_focus_id: str = "surface.viewport"
    objects: dict[str, dict[str, Any]] = field(default_factory=dict)
    ui: dict[str, Any] = field(default_factory=dict)
    goals: list[dict[str, Any]] = field(default_factory=list)
    plans: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    layer_state: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {name: {} for name in LAYER_NAMES}
    )
    render: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state_hash"] = ""
        return payload

    def seal(self) -> "SurfaceState":
        self.state_hash = digest(self.payload())
        return self

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SurfaceState":
        return cls(**value)
