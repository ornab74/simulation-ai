from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from simulation_ai.engine import SurfaceEngine
from simulation_ai.model import PatchOperation, PatchProposal


def packet(
    engine: SurfaceEngine,
    *,
    event_id: str,
    kind: str = "click",
    target_id: str = "node.memory",
    action_extra: dict | None = None,
    target_extra: dict | None = None,
) -> dict:
    action = {"kind": kind, **(action_extra or {})}
    target = {
        "node_id": target_id,
        "accessible_label": target_id,
        "sensitive": False,
        **(target_extra or {}),
    }
    current = engine.current()
    return {
        "schema": "nmsr.interaction/1",
        "event_id": event_id,
        "session_id": "test-session",
        "branch": current.branch,
        "logical_time": current.logical_time + 1,
        "parent_state_hash": current.state_hash,
        "action": action,
        "target": target,
        "privacy": {"cloud_allowed": False, "frame_retention": "bounded"},
    }


class SurfaceEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.engine = SurfaceEngine(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_boot_is_content_addressed_and_layered(self) -> None:
        state = self.engine.current()
        self.assertEqual(64, len(state.state_hash))
        self.assertEqual("nmsr.surface-state/2", state.schema_version)
        self.assertEqual("main", state.branch)
        self.assertEqual(10, len(state.layer_state))
        self.assertFalse(state.provenance["pixel_state_authoritative"])
        self.assertEqual("frame_genesis", state.render["committed_frame_id"])

    def test_interaction_produces_linked_artifacts(self) -> None:
        result = self.engine.interact(packet(self.engine, event_id="evt_000001"))
        self.assertEqual("node.memory", result["state"]["selected_object_id"])
        self.assertEqual(result["state"]["state_hash"], result["event"]["resulting_state_hash"])
        self.assertEqual(result["observation"]["observation_id"], result["event"]["evidence_ids"][0])
        self.assertEqual(result["proposal"]["proposal_id"], result["event"]["proposal_id"])
        self.assertEqual("verified", result["render_job"]["status"])
        self.assertEqual("episodic", result["memory"]["memory_type"])
        self.assertTrue(self.engine.verify_replay()["verified"])

    def test_sensitive_typing_never_persists_text(self) -> None:
        result = self.engine.interact(
            packet(
                self.engine,
                event_id="evt_sensitive",
                kind="type",
                target_id="surface.secret",
                action_extra={"text": "do-not-store", "typed_character_count": 12},
                target_extra={"sensitive": True},
            )
        )
        stored = result["state"]["ui"]["inputs"]["surface_secret"]
        self.assertTrue(stored["sensitive"])
        self.assertEqual(12, stored["character_count"])
        self.assertNotIn("text", stored)
        self.assertIsNone(result["observation"]["action"]["telemetry"]["text"])
        self.assertIsNone(result["event"]["arguments"]["text"])
        event_log = self.engine.store.events_path.read_text(encoding="utf-8")
        self.assertNotIn("do-not-store", event_log)

    def test_stale_parent_is_rejected(self) -> None:
        bad = packet(self.engine, event_id="evt_bad")
        bad["parent_state_hash"] = "not-current"
        with self.assertRaisesRegex(ValueError, "stale"):
            self.engine.interact(bad)

    def test_duplicate_event_id_is_rejected(self) -> None:
        self.engine.interact(packet(self.engine, event_id="evt_duplicate"))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.engine.interact(packet(self.engine, event_id="evt_duplicate"))

    def test_branch_switching_is_isolated(self) -> None:
        main = self.engine.current()
        branch = self.engine.create_branch("experiment-a")
        self.assertEqual("experiment-a", branch.branch)
        branch_result = self.engine.interact(
            packet(self.engine, event_id="evt_branch", target_id="node.renderer")
        )
        self.assertEqual("experiment-a", branch_result["state"]["branch"])
        restored = self.engine.switch_branch("main")
        self.assertEqual(main.state_hash, restored.state_hash)
        self.assertEqual("node.surface", restored.selected_object_id)

    def test_memory_retrieval_is_branch_aware(self) -> None:
        self.engine.interact(packet(self.engine, event_id="evt_memory", target_id="node.memory"))
        results = self.engine.query_memory("memory click", object_ids=["node.memory"])
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual("node.memory", results[0]["record"]["object_ids"][0])
        self.assertGreater(results[0]["score"], 0.5)

    def test_keyframe_command_creates_queued_render_job(self) -> None:
        result = self.engine.interact(
            packet(
                self.engine,
                event_id="evt_keyframe",
                kind="command",
                target_id="surface.command",
                action_extra={"name": "render:keyframe"},
            )
        )
        job = result["render_job"]
        self.assertEqual("new_keyframe", job["mode"])
        self.assertEqual("queued", job["status"])
        self.assertEqual(job["job_id"], result["state"]["render"]["pending_job_id"])
        verified = self.engine.verify_render(
            job["job_id"],
            {
                "decision": "pass",
                "scores": {
                    "semantic_fidelity": 0.97,
                    "temporal_continuity": 0.95,
                    "identity_stability": 0.99,
                    "protected_region_stability": 0.98,
                    "ui_usability": 1.0,
                },
            },
        )
        self.assertEqual("verified", verified["job"]["status"])
        self.assertIsNotNone(verified["frame"])
        self.assertEqual(verified["frame"]["frame_id"], verified["state"]["render"]["committed_frame_id"])
        self.assertEqual("render:verify", self.engine.store.list_events()[-1].action)
        self.assertTrue(self.engine.verify_replay()["verified"])

    def test_protected_patch_path_is_rejected(self) -> None:
        current = self.engine.current()
        proposal = PatchProposal(
            proposal_id="proposal_bad",
            event_id="evt_bad_patch",
            parent_state_hash=current.state_hash,
            branch=current.branch,
            intent={"summary": "rewrite identity"},
            operations=[PatchOperation("replace", "/target", "different-world")],
        )
        with self.assertRaisesRegex(ValueError, "unauthorized"):
            self.engine.commit_proposal(proposal)

    def test_spawn_command_adds_counterfactual_object(self) -> None:
        result = self.engine.interact(
            packet(
                self.engine,
                event_id="evt_spawn",
                kind="command",
                target_id="surface.command",
                action_extra={"name": "spawn:weather_node:environment"},
            )
        )
        created = result["state"]["objects"]["world.weather_node"]
        self.assertEqual("counterfactual", created["epistemic_class"])
        self.assertEqual("composite", result["render_job"]["mode"])


    def test_repeated_observation_is_idempotent(self) -> None:
        value = packet(self.engine, event_id="evt_observe_twice")
        first = self.engine.observe(value)
        second = self.engine.observe(value)
        self.assertEqual(first.observation_id, second.observation_id)
        self.assertEqual(1, self.engine.store.counts()["evidence"])

    def test_runtime_policy_commands_commit_semantic_ui_state(self) -> None:
        result = self.engine.interact(
            packet(
                self.engine,
                event_id="evt_policy",
                kind="command",
                target_id="surface.command",
                action_extra={"name": "privacy:cloud:on"},
            )
        )
        self.assertTrue(result["state"]["ui"]["privacy"]["cloud_allowed"])
        result = self.engine.interact(
            packet(
                self.engine,
                event_id="evt_render_policy",
                kind="command",
                target_id="surface.command",
                action_extra={"name": "render-policy:composite-first"},
            )
        )
        self.assertEqual("composite-first", result["state"]["ui"]["render_policy"])

    def test_snapshot_contains_operational_planes(self) -> None:
        self.engine.interact(packet(self.engine, event_id="evt_snapshot"))
        snapshot = self.engine.snapshot()
        self.assertEqual(4, len(snapshot["adapters"]))
        self.assertIn("branches", snapshot)
        self.assertIn("render_jobs", snapshot)
        self.assertTrue(snapshot["replay"]["verified"])
        self.assertGreater(snapshot["counts"]["states"], 1)


if __name__ == "__main__":
    unittest.main()
