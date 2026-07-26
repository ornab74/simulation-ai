from __future__ import annotations

import re
from typing import Iterable

from .model import EventEnvelope, MemoryRecord, ObservationReport, SurfaceState, digest


TOKEN_RE = re.compile(r"[a-z0-9_.:-]+")


def memory_from_transition(
    event: EventEnvelope,
    observation: ObservationReport,
    state: SurfaceState,
) -> MemoryRecord:
    target_label = state.objects.get(event.target_id, {}).get("label", event.target_id)
    summary = f"{event.action} on {target_label} committed at logical time {event.logical_time}."
    memory_type = "episodic"
    tags = [event.action, event.target_id, state.branch]
    if observation.contradictions:
        memory_type = "contradiction"
        summary += " Unresolved: " + "; ".join(observation.contradictions)
    return MemoryRecord(
        memory_id="mem_" + digest({"event": event.event_hash, "type": memory_type})[:24],
        memory_type=memory_type,
        branch_scope=state.branch,
        summary=summary,
        evidence_ids=list(event.evidence_ids),
        state_hashes=[event.parent_state_hash, event.resulting_state_hash],
        object_ids=[event.target_id],
        confidence=observation.confidence,
        epistemic_class=event.epistemic_class,
        tags=tags,
        logical_time=event.logical_time,
    )


def query_memories(
    records: Iterable[MemoryRecord],
    query: str,
    *,
    branch: str,
    object_ids: list[str] | None = None,
    limit: int = 12,
) -> list[dict[str, object]]:
    query_tokens = _tokens(query)
    objects = set(object_ids or [])
    ranked: list[tuple[float, MemoryRecord]] = []
    for record in records:
        record_tokens = _tokens(" ".join([record.summary, *record.tags, *record.object_ids]))
        lexical = len(query_tokens & record_tokens) / max(1, len(query_tokens | record_tokens))
        object_overlap = len(objects & set(record.object_ids)) * 0.35
        branch_score = 0.35 if record.branch_scope in {branch, "global"} else -0.45
        verified = 0.15 if record.confidence >= 0.8 else 0.0
        failure_boost = 0.16 if record.memory_type in {"failure", "contradiction"} else 0.0
        recency = min(0.25, record.logical_time / 10000.0)
        score = lexical + object_overlap + branch_score + verified + failure_boost + recency
        if query_tokens and lexical == 0.0 and not object_overlap:
            score -= 0.25
        ranked.append((score, record))
    ranked.sort(key=lambda item: (item[0], item[1].logical_time), reverse=True)
    return [
        {"score": round(score, 4), "record": record.as_dict()}
        for score, record in ranked[: max(1, min(limit, 50))]
        if score > -0.2
    ]


def _tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.lower()))
