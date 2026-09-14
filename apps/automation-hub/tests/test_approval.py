import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation-hub" / "src"))
sys.path.insert(0, str(ROOT / "operations-hub" / "src"))

from automation_hub import build_automation_plan  # noqa: E402
from automation_hub.approval import ApprovalReplayError, ApprovalSimulationError, ApprovalSimulationStore  # noqa: E402
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402

FIXTURES = ROOT / "operations-hub" / "fixtures"


def build_plan(source: str):
    payload = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    return build_automation_plan(event, evaluate_governance(event))


class ApprovalSimulationTests(unittest.TestCase):
    def test_required_plan_registers_required(self):
        store = ApprovalSimulationStore()
        state = store.register_plan(build_plan("whatsapp"))
        self.assertEqual("required", state["approval_state"])

    def test_approval_releases_simulation_without_authority(self):
        store = ApprovalSimulationStore()
        plan = build_plan("whatsapp")
        store.register_plan(plan)
        store.decide(plan["plan_id"], "approve", "decision-001")
        release = store.release_for_simulation(plan)
        self.assertTrue(release["simulation_release"])
        self.assertFalse(release["execution_authorized"])
        self.assertFalse(release["mutation_authorized"])

    def test_denial_blocks_simulation_release(self):
        store = ApprovalSimulationStore()
        plan = build_plan("google_business")
        store.register_plan(plan)
        store.decide(plan["plan_id"], "deny", "decision-002")
        with self.assertRaises(ApprovalSimulationError):
            store.release_for_simulation(plan)

    def test_pending_approval_blocks_release(self):
        store = ApprovalSimulationStore()
        plan = build_plan("whatsapp")
        store.register_plan(plan)
        with self.assertRaises(ApprovalSimulationError):
            store.release_for_simulation(plan)

    def test_decision_replay_is_rejected(self):
        store = ApprovalSimulationStore()
        plan = build_plan("whatsapp")
        store.register_plan(plan)
        store.decide(plan["plan_id"], "approve", "decision-003")
        with self.assertRaises(ApprovalReplayError):
            store.decide(plan["plan_id"], "approve", "decision-003")

    def test_not_required_plan_can_release_simulation(self):
        store = ApprovalSimulationStore()
        plan = build_plan("instagram")
        store.register_plan(plan)
        release = store.release_for_simulation(plan)
        self.assertEqual("not_required", release["approval_state"])

    def test_authorizing_plan_is_rejected(self):
        store = ApprovalSimulationStore()
        plan = build_plan("facebook")
        plan["execution_authorized"] = True
        with self.assertRaises(ApprovalSimulationError):
            store.register_plan(plan)

    def test_reregister_rejects_same_plan_id_with_changed_content(self):
        store = ApprovalSimulationStore()
        plan = build_plan("whatsapp")
        store.register_plan(plan)
        changed = json.loads(json.dumps(plan))
        changed["risk_level"] = "low" if plan["risk_level"] != "low" else "high"
        self.assertEqual(plan["plan_id"], changed["plan_id"])
        with self.assertRaisesRegex(ApprovalSimulationError, "plan content changed after registration"):
            store.register_plan(changed)

    def test_approved_plan_cannot_release_changed_content_under_same_plan_id(self):
        store = ApprovalSimulationStore()
        plan = build_plan("whatsapp")
        store.register_plan(plan)
        store.decide(plan["plan_id"], "approve", "decision-integrity-001")
        changed = json.loads(json.dumps(plan))
        changed["source"] = "tampered-source"
        self.assertEqual(plan["plan_id"], changed["plan_id"])
        with self.assertRaisesRegex(ApprovalSimulationError, "plan content changed after registration"):
            store.release_for_simulation(changed)

    def test_plan_fingerprint_is_not_exposed_in_read_surfaces(self):
        store = ApprovalSimulationStore()
        plan = build_plan("instagram")
        state = store.register_plan(plan)
        model = store.read_model()
        self.assertNotIn("plan_fingerprint", state)
        self.assertFalse(model["plan_fingerprints_exposed"])
        self.assertNotIn("plan_fingerprint", json.dumps(model, ensure_ascii=False))

    def test_read_model_projects_aggregate_approval_posture_without_decision_ids(self):
        store = ApprovalSimulationStore()
        whatsapp = build_plan("whatsapp")
        google = build_plan("google_business")
        instagram = build_plan("instagram")
        store.register_plan(whatsapp)
        store.register_plan(google)
        store.register_plan(instagram)
        store.decide(whatsapp["plan_id"], "approve", "secret-decision-001")
        store.decide(google["plan_id"], "deny", "secret-decision-002")

        model = store.read_model()
        self.assertEqual("read_only", model["status"])
        self.assertEqual(3, model["plan_count"])
        self.assertEqual(2, model["decision_count"])
        self.assertEqual(0, model["awaiting_decision"])
        self.assertEqual(2, model["simulation_releasable"])
        self.assertEqual(
            {"required": 0, "approved": 1, "denied": 1, "not_required": 1},
            model["by_state"],
        )
        self.assertFalse(model["decision_ids_exposed"])
        self.assertFalse(model["plan_fingerprints_exposed"])
        serialized = json.dumps(model, ensure_ascii=False)
        self.assertNotIn("secret-decision-001", serialized)
        self.assertNotIn("secret-decision-002", serialized)
        self.assertNotIn("plan_fingerprint", serialized)
        self.assertFalse(model["automatic_execution"])
        self.assertFalse(model["execution_authorized"])
        self.assertFalse(model["channel_reply_authorized"])
        self.assertFalse(model["mutation_authorized"])
        self.assertEqual("none", model["authority_effect"])

    def test_read_model_tracks_pending_approval(self):
        store = ApprovalSimulationStore()
        store.register_plan(build_plan("whatsapp"))
        store.register_plan(build_plan("facebook"))
        model = store.read_model()
        self.assertEqual(1, model["awaiting_decision"])
        self.assertEqual(1, model["simulation_releasable"])
        self.assertEqual(1, model["by_state"]["required"])
        self.assertEqual(1, model["by_state"]["not_required"])


if __name__ == "__main__":
    unittest.main()
