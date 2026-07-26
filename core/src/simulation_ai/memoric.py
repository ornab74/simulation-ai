"""Classical quantum-inspired Memoric world-model register.

This preserves uncertainty and constraints without claiming quantum hardware.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class MemoricRegister:
    SURFACES = ("geometry", "identity", "affordances", "causal", "temporal", "uncertainty")

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "schema": "memoric.register/1",
            "revision": 0,
            "surfaces": {name: [] for name in self.SURFACES},
            "hypotheses": [{"id": "h_default", "label": "desktop surface remains structurally continuous", "probability": 1.0, "constraints": []}],
            "contradictions": [],
            "entropy": {"value": 0.0, "target": 0.0, "novelty": 0.0, "occlusion": 0.0, "constraint_strength": 0.0},
            "last_measurement": None,
        }

    def deposit(self, packet: dict[str, Any], observation: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        action = dict(packet.get("action") or {})
        target = dict(packet.get("target") or {})
        telemetry = dict(observation.get("action", {}).get("telemetry", {}))
        event_id = str(packet.get("event_id", ""))
        point = action.get("pointer") or action.get("scroll") or {}
        label = str(target.get("accessible_label", "desktop surface"))
        deposition = {
            "event_id": event_id, "time": datetime.now(UTC).isoformat(timespec="seconds"),
            "latent": {"target": str(target.get("node_id", "surface.unknown")), "label": label, "action": action.get("kind"), "telemetry": telemetry},
            "phase": int(state.get("logical_time", 0)), "confidence": float(observation.get("confidence", 0.5)),
            "constraints": ["preserve desktop bounds", "preserve taskbar and icon anchors", "generated pixels are non-authoritative"],
            "point": point,
        }
        self.data["surfaces"]["geometry"].append({**deposition, "constraint": "pixel coordinate and desktop occupancy"})
        self.data["surfaces"]["identity"].append({**deposition, "constraint": label})
        self.data["surfaces"]["affordances"].append({**deposition, "constraint": f"{action.get('kind', 'interaction')} is available here"})
        self.data["surfaces"]["causal"].append({**deposition, "constraint": "interaction produces the next visible frame"})
        self.data["surfaces"]["temporal"].append({**deposition, "constraint": "follows previous frame"})
        self.data["surfaces"]["uncertainty"].append({**deposition, "constraint": "text/control identity requires visual confirmation"})
        for name in self.SURFACES:
            self.data["surfaces"][name] = self.data["surfaces"][name][-120:]
        self._attune(action, observation)
        self.data["revision"] += 1
        self._save()
        return self.summary()

    def _attune(self, action: dict[str, Any], observation: dict[str, Any]) -> None:
        novelty = 0.8 if action.get("kind") in {"double_click", "type"} else 0.35
        uncertainty = 0.75 if observation.get("unknowns") else 0.25
        strength = min(1.0, len(self.data["surfaces"]["causal"]) / 120.0)
        target = min(1.0, 0.08 + 0.42 * novelty + 0.32 * uncertainty - 0.18 * strength)
        recent = self.data["hypotheses"][-6:]
        probabilities = [max(0.001, float(h.get("probability", 0.001))) for h in recent] or [1.0]
        total = sum(probabilities)
        entropy = -sum((p / total) * math.log2(p / total) for p in probabilities)
        self.data["entropy"] = {"value": round(entropy, 4), "target": round(target, 4), "novelty": novelty, "occlusion": uncertainty, "constraint_strength": strength}

    def summary(self) -> dict[str, Any]:
        return {"schema": self.data["schema"], "revision": self.data["revision"], "surface_counts": {k: len(v) for k, v in self.data["surfaces"].items()}, "entropy": self.data["entropy"], "hypothesis_count": len(self.data["hypotheses"]), "contradiction_count": len(self.data["contradictions"]), "last_measurement": self.data.get("last_measurement")}

    def context(self, limit: int = 12) -> dict[str, Any]:
        return {"summary": self.summary(), "recent_constraints": self.data["surfaces"]["geometry"][-limit:], "recent_affordances": self.data["surfaces"]["affordances"][-limit:], "recent_causal": self.data["surfaces"]["causal"][-limit:]}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
