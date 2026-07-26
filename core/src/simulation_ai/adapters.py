from __future__ import annotations

from typing import Any

from .model import (
    ObservationReport,
    PatchOperation,
    PatchProposal,
    SurfaceState,
    digest,
)


class DeterministicObserver:
    model_id = "deterministic-observer-v1"

    def observe(self, packet: dict[str, Any], state: SurfaceState) -> ObservationReport:
        action = dict(packet.get("action") or {})
        target = dict(packet.get("target") or {})
        target_id = str(target.get("node_id", "surface.unknown"))
        sensitive = bool(target.get("sensitive", False))
        if sensitive and action.get("kind") == "type":
            action["text"] = None
            action["typed_character_count"] = int(action.get("typed_character_count", 0))
        target_exists = target_id in state.objects or target_id.startswith("surface.") or target_id.startswith("world.")
        contradictions = [] if target_exists else [f"Target {target_id} was not present in committed object state."]
        confidence = 1.0 if target_exists else 0.58
        event_id = str(packet["event_id"])
        return ObservationReport(
            observation_id="obs_" + digest({"event": event_id, "state": state.state_hash})[:24],
            event_id=event_id,
            logical_time=state.logical_time + 1,
            branch=state.branch,
            action={
                "kind": action.get("kind"),
                "status": "accepted" if target_exists else "ambiguous",
                "target_id": target_id,
                "target_label": target.get("accessible_label"),
                "telemetry": action,
                "sensitive": sensitive,
            },
            before={
                "focus_id": state.active_focus_id,
                "selected_object_id": state.selected_object_id,
            },
            after={
                "focus_id": target_id,
                "visible_objects_added": [],
                "visible_objects_removed": [],
                "visible_properties_changed": [],
            },
            candidate_effects=[
                {
                    "description": f"Apply {action.get('kind')} to {target_id}",
                    "evidence_ids": [],
                    "confidence": confidence,
                }
            ],
            contradictions=contradictions,
            unknowns=[] if target_exists else ["semantic target identity"],
            confidence=confidence,
            source=self.model_id,
        )


class RulePatchProposer:
    model_id = "rule-patch-proposer-v2"

    def propose(
        self,
        packet: dict[str, Any],
        observation: ObservationReport,
        state: SurfaceState,
    ) -> PatchProposal:
        action = packet.get("action") or {}
        target = packet.get("target") or {}
        kind = str(action.get("kind", "unknown"))
        target_id = str(target.get("node_id", "surface.unknown"))
        evidence_ids = [observation.observation_id]
        operations: list[PatchOperation] = [
            PatchOperation("test", "/selected_object_id", state.selected_object_id, evidence_ids),
        ]
        render_class = "native_ui"
        affected = [target_id]
        intent_summary = f"Apply {kind} to {target_id}"

        if kind in {"click", "double_click", "focus", "drag", "scroll"}:
            if target_id in state.objects:
                operations.extend(
                    [
                        PatchOperation("replace", "/selected_object_id", target_id, evidence_ids),
                        PatchOperation("replace", "/active_focus_id", target_id, evidence_ids),
                        PatchOperation(
                            "replace",
                            f"/objects/{_escape(target_id)}/status",
                            "selected" if kind in {"click", "double_click"} else "active",
                            evidence_ids,
                        ),
                    ]
                )
            else:
                operations.append(PatchOperation("replace", "/active_focus_id", target_id, evidence_ids, "inferred", 0.58))
        elif kind == "type":
            sensitive = bool(target.get("sensitive", False))
            typed_value: Any
            if sensitive:
                typed_value = {
                    "sensitive": True,
                    "character_count": int(action.get("typed_character_count", 0)),
                }
            else:
                typed_value = {
                    "sensitive": False,
                    "text": str(action.get("text", ""))[:4000],
                    "character_count": len(str(action.get("text", ""))),
                }
            input_key = _safe_key(target_id)
            if input_key in state.ui.get("inputs", {}):
                operations.append(PatchOperation("replace", f"/ui/inputs/{input_key}", typed_value, evidence_ids))
            else:
                operations.append(PatchOperation("add", f"/ui/inputs/{input_key}", typed_value, evidence_ids))
            operations.append(PatchOperation("replace", "/active_focus_id", target_id, evidence_ids))
        elif kind == "command":
            command = str(action.get("name", "")).strip()
            intent_summary = f"Execute surface command: {command}"
            operations, render_class, affected = self._command_operations(command, state, evidence_ids)
        else:
            raise ValueError(f"unsupported proposal action: {kind}")

        last_action = {"kind": kind, "target_id": target_id, "event_id": packet["event_id"]}
        operations.append(PatchOperation("replace", "/layer_state/events/last_action", last_action, evidence_ids))
        proposal_id = "proposal_" + digest(
            {"event": packet["event_id"], "parent": state.state_hash, "operations": [item.as_dict() for item in operations]}
        )[:24]
        return PatchProposal(
            proposal_id=proposal_id,
            event_id=str(packet["event_id"]),
            parent_state_hash=state.state_hash,
            branch=state.branch,
            intent={"summary": intent_summary, "confidence": observation.confidence, "goal_id": None},
            operations=operations,
            expected_postconditions=[{"path": "/logical_time", "predicate": "increments by one"}],
            invariants_expected_to_hold=[
                "state hash is canonical",
                "identity and rights boundary unchanged",
                "selected object exists or is a surface control",
                "generated pixels remain non-authoritative",
            ],
            render_impact={"class": render_class, "affected_object_ids": affected, "affected_regions": []},
            uncertainties=list(observation.unknowns),
            requires_review=bool(observation.contradictions),
            model_id=self.model_id,
        )

    def _command_operations(
        self,
        command: str,
        state: SurfaceState,
        evidence_ids: list[str],
    ) -> tuple[list[PatchOperation], str, list[str]]:
        operations: list[PatchOperation] = []
        render_class = "native_ui"
        affected = ["node.surface"]
        if command in {"toggle_run", "pause", "resume"}:
            current = bool(state.ui.get("simulation_running", True))
            value = not current if command == "toggle_run" else command == "resume"
            operations.append(PatchOperation("replace", "/ui/simulation_running", value, evidence_ids))
        elif command.startswith("render:keyframe"):
            operations.extend(
                [
                    PatchOperation("replace", "/render/status", "queued", evidence_ids),
                    PatchOperation("replace", "/render/requested_mode", "new_keyframe", evidence_ids),
                    PatchOperation("replace", "/objects/node.renderer/status", "queued", evidence_ids),
                ]
            )
            render_class = "new_keyframe"
            affected = ["node.renderer", "node.surface"]
        elif command.startswith("render:regional"):
            operations.extend(
                [
                    PatchOperation("replace", "/render/status", "queued", evidence_ids),
                    PatchOperation("replace", "/render/requested_mode", "regional_image_edit", evidence_ids),
                    PatchOperation("replace", "/objects/node.renderer/status", "queued", evidence_ids),
                ]
            )
            render_class = "regional_image_edit"
            affected = ["node.renderer", state.selected_object_id]
        elif command.startswith("goal:"):
            text = command.partition(":")[2].strip()
            if not text:
                raise ValueError("goal command requires text")
            operations.append(
                PatchOperation(
                    "add",
                    "/goals/-",
                    {"goal_id": "goal_" + digest(text)[:12], "text": text[:500], "status": "active"},
                    evidence_ids,
                    "observed",
                )
            )
            affected = ["node.planner"]
        elif command.startswith("spawn:"):
            parts = command.split(":", 2)
            if len(parts) != 3:
                raise ValueError("spawn expects spawn:<id>:<type>")
            object_id = parts[1] if parts[1].startswith(("node.", "world.")) else f"world.{parts[1]}"
            if object_id in state.objects:
                raise ValueError("spawn object already exists")
            object_type = parts[2] or "entity"
            operations.append(
                PatchOperation(
                    "add",
                    f"/objects/{_escape(object_id)}",
                    {
                        "type": object_type,
                        "label": object_id.split(".")[-1].replace("_", " ").title(),
                        "status": "active",
                        "epistemic_class": "counterfactual",
                        "layout": [0.5, 0.5],
                        "properties": {},
                    },
                    evidence_ids,
                    "counterfactual",
                    0.72,
                )
            )
            operations.append(PatchOperation("replace", "/selected_object_id", object_id, evidence_ids, "counterfactual", 0.72))
            affected = [object_id]
            render_class = "composite"
        elif command.startswith("set-status:"):
            parts = command.split(":", 2)
            if len(parts) != 3 or parts[1] not in state.objects:
                raise ValueError("set-status expects an existing object and a status")
            operations.append(PatchOperation("replace", f"/objects/{_escape(parts[1])}/status", parts[2][:80], evidence_ids))
            affected = [parts[1]]
        elif command.startswith("privacy:cloud:"):
            enabled = command.rsplit(":", 1)[-1] == "on"
            operations.append(PatchOperation("replace", "/ui/privacy/cloud_allowed", enabled, evidence_ids))
        elif command.startswith("privacy:redaction:"):
            enabled = command.rsplit(":", 1)[-1] == "on"
            operations.append(PatchOperation("replace", "/ui/privacy/redact_sensitive_inputs", enabled, evidence_ids))
        elif command.startswith("privacy:retention:"):
            retention = command.split(":", 2)[2]
            if retention not in {"ephemeral", "bounded", "persistent-keyframes"}:
                raise ValueError("unsupported frame retention policy")
            operations.append(PatchOperation("replace", "/ui/privacy/frame_retention", retention, evidence_ids))
        elif command.startswith("render-policy:"):
            policy = command.partition(":")[2]
            if policy not in {"native-first", "composite-first", "generative-keyframes"}:
                raise ValueError("unsupported render policy")
            operations.append(PatchOperation("replace", "/ui/render_policy", policy, evidence_ids))
        elif command.startswith("motion:reduced:"):
            enabled = command.rsplit(":", 1)[-1] == "on"
            operations.append(PatchOperation("replace", "/ui/reduced_motion", enabled, evidence_ids))
        else:
            operations.append(
                PatchOperation(
                    "replace",
                    "/ui/last_command",
                    command[:500],
                    evidence_ids,
                    "inferred",
                    0.7,
                )
            )
        return operations, render_class, affected


def _safe_key(value: str) -> str:
    return value.replace("/", "_").replace("~", "_").replace(".", "_")[:120]


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
