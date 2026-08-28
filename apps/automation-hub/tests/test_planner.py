import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation-hub" / "src"))
sys.path.insert(0, str(ROOT / "operations-hub" / "src"))

from automation_hub import AutomationPlanError, build_automation_plan  # noqa: E402
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402

FIXTURES = ROOT / "operations-hub" / "fixtures"


def load_event(source: str):
    payload = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    return event, evaluate_governance(event)


class AutomationPlannerTests(unittest.TestCase):
    def test_low_risk_event_is_ready_for_simulation_only(self):
        event, governance = load_event("instagram")
        plan = build_automation_plan(event, governance)
        self.assertEqual("ready_for_simulation", plan["plan_state"])
        self.assertFalse(plan["automatic_execution"])
        self.assertFalse(plan["execution_authorized"])

    def test_complaint_is_blocked_pending_approval(self):
        event, governance = load_event("whatsapp")
        plan = build_automation_plan(event, governance)
        self.assertEqual("blocked_pending_approval", plan["plan_state"])
        self.assertTrue(plan["approval_required"])
        self.assertIn("wait_for_human_approval", [step["name"] for step in plan["steps"]])

    def test_public_review_is_blocked_pending_approval(self):
        event, governance = load_event("google_business")
        self.assertEqual("blocked_pending_approval", build_automation_plan(event, governance)["plan_state"])

    def test_task_class_remains_general_and_specialist_disabled(self):
        event, governance = load_event("facebook")
        plan = build_automation_plan(event, governance)
        self.assertEqual("general", plan["task_class"])
        self.assertEqual("hermes", plan["assigned_agent"])
        self.assertFalse(plan["specialist_enabled"])

    def test_plan_id_is_deterministic(self):
        event, governance = load_event("telegram")
        self.assertEqual(build_automation_plan(event, governance)["plan_id"], build_automation_plan(event, governance)["plan_id"])

    def test_authorizing_event_fails_closed(self):
        event, governance = load_event("facebook")
        event["mutation_authorized"] = True
        with self.assertRaises(AutomationPlanError):
            build_automation_plan(event, governance)

    def test_authorizing_governance_fails_closed(self):
        event, governance = load_event("facebook")
        governance["execution_authorized"] = True
        with self.assertRaises(AutomationPlanError):
            build_automation_plan(event, governance)

    def test_correlation_mismatch_fails_closed(self):
        event, governance = load_event("telegram")
        governance["lifecycle_correlation_id"] = "wrong"
        with self.assertRaises(AutomationPlanError):
            build_automation_plan(event, governance)


if __name__ == "__main__":
    unittest.main()
