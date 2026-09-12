import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation-hub" / "src"))
sys.path.insert(0, str(ROOT / "operations-hub" / "src"))

from automation_hub import (  # noqa: E402
    AutomationPlanError,
    build_automation_plan,
    build_task_automation_plan,
)
from operations_hub import (  # noqa: E402
    build_task_candidate,
    evaluate_governance,
    normalize_channel_event,
)

FIXTURES = ROOT / "operations-hub" / "fixtures"


def load_event(source: str):
    payload = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    return event, evaluate_governance(event)


def load_task(source: str):
    event, governance = load_event(source)
    return event, governance, build_task_candidate(event, governance)


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

    def test_extracted_tasks_preserve_event_plan_identity_and_governance(self):
        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            with self.subTest(source=source):
                event, governance, task = load_task(source)
                event_plan = build_automation_plan(event, governance)
                task_plan = build_task_automation_plan(task)
                self.assertEqual(event_plan["plan_id"], task_plan["plan_id"])
                self.assertEqual(event_plan["lifecycle_correlation_id"], task_plan["lifecycle_correlation_id"])
                self.assertEqual(event_plan["source"], task_plan["source"])
                self.assertEqual(event_plan["normalized_intent"], task_plan["normalized_intent"])
                self.assertEqual(event_plan["risk_level"], task_plan["risk_level"])
                self.assertEqual(event_plan["approval_required"], task_plan["approval_required"])
                self.assertEqual(event_plan["approval_state"], task_plan["approval_state"])
                self.assertEqual(event_plan["plan_state"], task_plan["plan_state"])
                self.assertEqual("observe_task_candidate", task_plan["steps"][0]["name"])
                self.assertEqual("validate_task_governance", task_plan["steps"][1]["name"])
                self.assertFalse(task_plan["automatic_execution"])
                self.assertFalse(task_plan["execution_authorized"])
                self.assertFalse(task_plan["channel_reply_authorized"])
                self.assertFalse(task_plan["mutation_authorized"])

    def test_sensitive_task_still_requires_simulated_approval(self):
        _, _, task = load_task("whatsapp")
        plan = build_task_automation_plan(task)
        self.assertEqual("blocked_pending_approval", plan["plan_state"])
        self.assertTrue(plan["approval_required"])
        self.assertIn("wait_for_human_approval", [step["name"] for step in plan["steps"]])

    def test_non_sensitive_task_is_only_ready_for_simulation(self):
        _, _, task = load_task("instagram")
        plan = build_task_automation_plan(task)
        self.assertEqual("ready_for_simulation", plan["plan_state"])
        self.assertFalse(plan["approval_required"])
        self.assertIn("policy_clear_for_simulation", [step["name"] for step in plan["steps"]])
        self.assertEqual("hermes", plan["assigned_agent"])
        self.assertFalse(plan["specialist_enabled"])

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

    def test_task_authority_expansion_fails_closed(self):
        _, _, task = load_task("google_business")
        tampered = copy.deepcopy(task)
        tampered["authority"]["channel_reply_authorized"] = True
        with self.assertRaisesRegex(AutomationPlanError, "channel_reply_authorized"):
            build_task_automation_plan(tampered)

    def test_task_approval_state_mismatch_fails_closed(self):
        _, _, task = load_task("facebook")
        tampered = copy.deepcopy(task)
        tampered["approval_state"] = "required"
        with self.assertRaisesRegex(AutomationPlanError, "approval state"):
            build_task_automation_plan(tampered)


if __name__ == "__main__":
    unittest.main()
