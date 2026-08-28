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


if __name__ == "__main__":
    unittest.main()
