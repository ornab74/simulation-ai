from __future__ import annotations

from copy import deepcopy
from typing import Any

from .model import PatchOperation, PatchProposal, SurfaceState


PROTECTED_ROOTS = {
    "schema_version",
    "map_id",
    "target",
    "profile",
    "mode",
    "seed",
    "logical_time",
    "branch",
    "parent_state_hash",
    "state_hash",
    "provenance",
}

ALLOWED_ROOTS = {
    "selected_object_id",
    "active_focus_id",
    "objects",
    "ui",
    "goals",
    "plans",
    "hypotheses",
    "claims",
    "layer_state",
    "render",
}


def validate_interaction(packet: dict[str, Any]) -> None:
    if packet.get("schema") != "nmsr.interaction/1":
        raise ValueError("unsupported interaction schema")
    for key in ("event_id", "session_id", "branch", "action", "target"):
        if key not in packet:
            raise ValueError(f"interaction missing {key}")
    if not isinstance(packet["action"], dict) or not isinstance(packet["target"], dict):
        raise ValueError("interaction action and target must be objects")
    if not str(packet["event_id"]).strip():
        raise ValueError("event_id is empty")
    kind = str(packet["action"].get("kind", ""))
    if kind not in {"click", "double_click", "drag", "scroll", "type", "command", "focus"}:
        raise ValueError(f"unsupported action kind: {kind}")
    privacy = packet.get("privacy", {})
    if privacy and not isinstance(privacy, dict):
        raise ValueError("privacy must be an object")


def validate_proposal(proposal: PatchProposal, current: SurfaceState) -> None:
    if proposal.parent_state_hash != current.state_hash:
        raise ValueError("proposal parent does not match branch HEAD")
    if proposal.branch != current.branch:
        raise ValueError("proposal branch does not match branch HEAD")
    if not proposal.operations:
        raise ValueError("proposal contains no operations")
    for operation in proposal.operations:
        segments = _segments(operation.path)
        if not segments:
            raise ValueError("root replacement is forbidden")
        root = segments[0]
        if root in PROTECTED_ROOTS or root not in ALLOWED_ROOTS:
            raise ValueError(f"unauthorized patch path: {operation.path}")
        if root == "layer_state" and len(segments) > 1 and segments[1] in {"identity"}:
            raise ValueError("identity layer is immutable through the proposal plane")
        if root == "objects" and len(segments) < 2:
            raise ValueError("objects root cannot be replaced wholesale")
        if operation.op == "test" and operation.value is None:
            raise ValueError("test operation requires a value")


def apply_proposal(current: SurfaceState, proposal: PatchProposal) -> SurfaceState:
    validate_proposal(proposal, current)
    document = deepcopy(current.as_dict())
    for operation in proposal.operations:
        _apply_operation(document, operation)
    document["parent_state_hash"] = current.state_hash
    document["logical_time"] = current.logical_time + 1
    document["state_hash"] = ""
    next_state = SurfaceState.from_dict(document)
    validate_state_invariants(next_state)
    return next_state.seal()


def validate_state_invariants(state: SurfaceState) -> None:
    if state.selected_object_id not in state.objects and state.selected_object_id != "surface.command":
        raise ValueError("selected object does not exist")
    if not 0.0 <= state.coherence <= 1.0:
        raise ValueError("coherence must be in [0, 1]")
    if state.entropy_bits < 0.0:
        raise ValueError("entropy cannot be negative")
    for object_id, value in state.objects.items():
        if not object_id.startswith("node.") and not object_id.startswith("world."):
            raise ValueError(f"object ID outside allowed namespace: {object_id}")
        if not isinstance(value, dict) or "type" not in value or "status" not in value:
            raise ValueError(f"object is missing required fields: {object_id}")
    render_status = str(state.render.get("status", "verified"))
    if render_status not in {"verified", "queued", "candidate", "fallback", "rejected"}:
        raise ValueError("invalid render status")


def _apply_operation(document: dict[str, Any], operation: PatchOperation) -> None:
    segments = _segments(operation.path)
    if operation.op == "test":
        actual = _get(document, segments)
        if actual != operation.value:
            raise ValueError(f"patch test failed at {operation.path}")
        return
    if operation.op == "remove":
        _remove(document, segments)
        return
    _set(document, segments, operation.value, add=operation.op == "add")


def _segments(path: str) -> list[str]:
    if path == "/":
        return []
    return [segment.replace("~1", "/").replace("~0", "~") for segment in path.lstrip("/").split("/")]


def _get(document: Any, segments: list[str]) -> Any:
    cursor = document
    for segment in segments:
        if isinstance(cursor, list):
            cursor = cursor[int(segment)]
        elif isinstance(cursor, dict):
            if segment not in cursor:
                raise ValueError(f"patch path does not exist: {'/'.join(segments)}")
            cursor = cursor[segment]
        else:
            raise ValueError("patch traversed a scalar value")
    return cursor


def _set(document: Any, segments: list[str], value: Any, *, add: bool) -> None:
    parent = _get(document, segments[:-1]) if len(segments) > 1 else document
    key = segments[-1]
    if isinstance(parent, list):
        if key == "-":
            if not add:
                raise ValueError("only add may append to an array")
            parent.append(value)
        else:
            index = int(key)
            if add:
                parent.insert(index, value)
            else:
                parent[index] = value
        return
    if not isinstance(parent, dict):
        raise ValueError("patch parent is not an object")
    if not add and key not in parent:
        raise ValueError(f"replace path does not exist: {'/'.join(segments)}")
    parent[key] = value


def _remove(document: Any, segments: list[str]) -> None:
    parent = _get(document, segments[:-1]) if len(segments) > 1 else document
    key = segments[-1]
    if isinstance(parent, list):
        del parent[int(key)]
    elif isinstance(parent, dict) and key in parent:
        del parent[key]
    else:
        raise ValueError(f"remove path does not exist: {'/'.join(segments)}")
