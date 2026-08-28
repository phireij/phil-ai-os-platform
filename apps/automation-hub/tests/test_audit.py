import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation-hub" / "src"))
sys.path.insert(0, str(ROOT / "operations-hub" / "src"))

from automation_hub import ApprovalSimulationStore, build_automation_plan, build_dry_run_boundary_request  # noqa: E402
from automation_hub.audit import AutomationAuditError, InMemoryAutomationAudit  # noqa: E402
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402

FIXTURES = ROOT / "operations-hub" / "fixtures"


def build_flow(source: str, approve: bool = False):
    payload = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    plan = build_automation_plan(event, evaluate_governance(event))
    store = ApprovalSimulationStore()
    store.register_plan(plan)
    if approve:
        store.decide(plan["plan_id"], "approve", f"decision-{source}")
    release = store.release_for_simulation(plan)
    request = build_dry_run_boundary_request(plan, release)
    return plan, release, request


class AutomationAuditTests(unittest.TestCase):
    def test_full_simulated_lifecycle_is_append_only(self):
        plan, release, request = build_flow("whatsapp", approve=True)
        audit = InMemoryAutomationAudit()
        audit.record_plan(plan)
        audit.record_approval(plan, release["approval_state"])
        audit.record_boundary_request(plan, request)
        audit.record_simulated_result(plan, request)
        model = audit.read_model()
        self.assertEqual(4, model["total_events"])
        self.assertEqual([1, 2, 3, 4], [item["sequence"] for item in model["items"]])

    def test_read_model_is_read_only_and_non_authorizing(self):
        plan, release, request = build_flow("instagram")
        audit = InMemoryAutomationAudit()
        audit.record_plan(plan)
        audit.record_approval(plan, release["approval_state"])
        audit.record_boundary_request(plan, request)
        model = audit.read_model()
        self.assertTrue(model["read_only"])
        self.assertEqual("none", model["authority_effect"])
        for item in model["items"]:
            self.assertFalse(item["execution_authorized"])
            self.assertFalse(item["channel_reply_authorized"])
            self.assertFalse(item["mutation_authorized"])

    def test_read_model_does_not_include_raw_customer_text(self):
        plan, release, request = build_flow("facebook")
        audit = InMemoryAutomationAudit()
        audit.record_plan(plan)
        audit.record_approval(plan, release["approval_state"])
        audit.record_boundary_request(plan, request)
        serialized = json.dumps(audit.read_model())
        self.assertNotIn("Can I order", serialized)

    def test_request_plan_mismatch_fails_closed(self):
        plan, _, request = build_flow("instagram")
        request["plan_id"] = "wrong"
        with self.assertRaises(AutomationAuditError):
            InMemoryAutomationAudit().record_boundary_request(plan, request)

    def test_non_dry_run_request_fails_closed(self):
        plan, _, request = build_flow("instagram")
        request["dry_run"] = False
        with self.assertRaises(AutomationAuditError):
            InMemoryAutomationAudit().record_boundary_request(plan, request)

    def test_authorizing_plan_fails_closed(self):
        plan, _, _ = build_flow("instagram")
        plan["mutation_authorized"] = True
        with self.assertRaises(AutomationAuditError):
            InMemoryAutomationAudit().record_plan(plan)

    def test_simulated_failure_can_be_recorded_without_execution(self):
        plan, _, request = build_flow("telegram")
        audit = InMemoryAutomationAudit()
        event = audit.record_simulated_result(plan, request, outcome="simulated_failure")
        self.assertEqual("simulated_failure", event["outcome"])
        self.assertFalse(event["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
