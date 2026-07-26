from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Iterable, TypeVar

from .model import (
    EventEnvelope,
    EvidenceRecord,
    FrameManifest,
    MemoryRecord,
    PatchProposal,
    RenderJob,
    SurfaceState,
)

T = TypeVar("T")


class SurfaceStore:
    """Filesystem-backed content and record store.

    Canonical states are immutable and content-addressed. Mutable refs are tiny
    atomic pointers. Other records are immutable JSON objects keyed by IDs.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.states = root / "states"
        self.refs = root / "refs"
        self.evidence = root / "evidence"
        self.proposals = root / "proposals"
        self.memories = root / "memories"
        self.render_jobs = root / "render_jobs"
        self.frames = root / "frames"
        self.events_path = root / "events.jsonl"
        for directory in (
            self.states,
            self.refs,
            self.evidence,
            self.proposals,
            self.memories,
            self.render_jobs,
            self.frames,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def save_state(self, state: SurfaceState) -> None:
        if not state.state_hash:
            state.seal()
        self._write_json_once(self.states / f"{state.state_hash}.json", state.as_dict())

    def load_state(self, ref: str = "HEAD") -> SurfaceState:
        state_hash = ref if len(ref) == 64 and (self.states / f"{ref}.json").exists() else self.read_ref(ref)
        return SurfaceState.from_dict(self._read_json(self.states / f"{state_hash}.json"))

    def state_exists(self, state_hash: str) -> bool:
        return (self.states / f"{state_hash}.json").exists()

    def set_ref(self, name: str, state_hash: str) -> None:
        if not self.state_exists(state_hash):
            raise ValueError(f"cannot point ref at missing state: {state_hash}")
        tmp = self.refs / f".{name}.tmp"
        tmp.write_text(state_hash, encoding="utf-8")
        tmp.replace(self.refs / name)

    def read_ref(self, name: str) -> str:
        return (self.refs / name).read_text(encoding="utf-8").strip()

    def list_refs(self, prefix: str = "") -> dict[str, str]:
        refs: dict[str, str] = {}
        for path in sorted(self.refs.iterdir()):
            if path.name.startswith(".") or not path.is_file() or not path.name.startswith(prefix):
                continue
            refs[path.name] = path.read_text(encoding="utf-8").strip()
        return refs

    def append_event(self, event: EventEnvelope) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True, ensure_ascii=False) + "\n")

    def list_events(self, *, branch: str | None = None, limit: int | None = None) -> list[EventEnvelope]:
        if not self.events_path.exists():
            return []
        events = [
            EventEnvelope(**json.loads(line))
            for line in self.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if branch is not None:
            events = [event for event in events if event.branch == branch]
        if limit is not None:
            events = events[-max(0, limit):]
        return events

    def event_id_exists(self, event_id: str) -> bool:
        return any(event.event_id == event_id for event in self.list_events())

    def save_evidence(self, record: EvidenceRecord) -> None:
        self._write_json_once(self.evidence / f"{record.evidence_id}.json", record.as_dict())

    def load_evidence(self, evidence_id: str) -> EvidenceRecord:
        return EvidenceRecord(**self._read_json(self.evidence / f"{evidence_id}.json"))

    def evidence_exists(self, evidence_id: str) -> bool:
        return (self.evidence / f"{evidence_id}.json").exists()

    def list_evidence(self, limit: int | None = None) -> list[EvidenceRecord]:
        records = self._load_records(self.evidence, EvidenceRecord)
        return records[-limit:] if limit is not None else records

    def save_proposal(self, proposal: PatchProposal) -> None:
        self._write_json_once(self.proposals / f"{proposal.proposal_id}.json", proposal.as_dict())

    def load_proposal(self, proposal_id: str) -> PatchProposal:
        return PatchProposal.from_dict(self._read_json(self.proposals / f"{proposal_id}.json"))

    def save_memory(self, record: MemoryRecord) -> None:
        self._write_json_once(self.memories / f"{record.memory_id}.json", record.as_dict())

    def list_memories(self) -> list[MemoryRecord]:
        return self._load_records(self.memories, MemoryRecord)

    def save_render_job(self, job: RenderJob, *, replace: bool = False) -> None:
        path = self.render_jobs / f"{job.job_id}.json"
        if replace:
            self._atomic_write_json(path, job.as_dict())
        else:
            self._write_json_once(path, job.as_dict())

    def load_render_job(self, job_id: str) -> RenderJob:
        return RenderJob(**self._read_json(self.render_jobs / f"{job_id}.json"))

    def list_render_jobs(self, limit: int | None = None) -> list[RenderJob]:
        records = self._load_records(self.render_jobs, RenderJob)
        return records[-limit:] if limit is not None else records

    def save_frame(self, frame: FrameManifest) -> None:
        if not frame.frame_hash:
            frame.seal()
        self._write_json_once(self.frames / f"{frame.frame_id}.json", frame.as_dict())

    def list_frames(self, limit: int | None = None) -> list[FrameManifest]:
        records = self._load_records(self.frames, FrameManifest)
        return records[-limit:] if limit is not None else records

    def iter_states(self) -> Iterable[Path]:
        return self.states.glob("*.json")

    def counts(self) -> dict[str, int]:
        return {
            "states": sum(1 for _ in self.states.glob("*.json")),
            "events": len(self.list_events()),
            "evidence": sum(1 for _ in self.evidence.glob("*.json")),
            "proposals": sum(1 for _ in self.proposals.glob("*.json")),
            "memories": sum(1 for _ in self.memories.glob("*.json")),
            "render_jobs": sum(1 for _ in self.render_jobs.glob("*.json")),
            "frames": sum(1 for _ in self.frames.glob("*.json")),
        }

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json_once(path: Path, value: dict[str, Any]) -> None:
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != value:
                raise ValueError(f"immutable record collision: {path.name}")
            return
        SurfaceStore._atomic_write_json(path, value)

    @staticmethod
    def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    @staticmethod
    def _load_records(directory: Path, record_type: type[T]) -> list[T]:
        records: list[T] = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime_ns):
            records.append(record_type(**json.loads(path.read_text(encoding="utf-8"))))
        return records
