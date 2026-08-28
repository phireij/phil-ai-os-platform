import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation-hub" / "src"))
sys.path.insert(0, str(ROOT / "operations-hub" / "src"))

from automation_hub import ApprovalSimulationStore, build_automation_plan, build_dry_run_boundary_request  # noqa: E402
from automation_hub.recovery import RecoveryPlanError, build_recovery_plan  # noqa: E402
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402

FIXTURES = ROOT / "operations-hub" / "fixtures"


def build_request(source: str):
    payload = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    plan = build_automation_plan(event, evaluate_governance(event))
    store = ApprovalSimulationStore()
    store.register_plan(plan)
    if plan["approval_required"]:
        store.decide(plan["plan_id"], "approve", f"decision-{source}")
    release = store.release_for_simulation(plan)
    return build_dry_run_boundary_request(plan, release)


class RecoveryPlanTests(unittest.TestCase):
    def test_retryable_failure_plans_simulation_retry(self):
        request = build_request("telegram")
        plan = build_recovery_plan(request, error_code="synthetic_timeout", retryable=True, attempt=1)
        self.assertTrue(plan["retry_planned"])
        self.assertEqual("retry_simulation", plan["next_action"])
        self.assertFalse(plan["automatic_retry"])
        self.assertFalse(plan["retry_authorized"])

    def test_retry_stops_at_limit(self):
        request = build_request("instagram")
        plan = build_recovery_plan(request, error_code="synthetic_429", retryable=True, attempt=3, max_attempts=3)
        self.assertFalse(plan["retry_planned"])
        self.assertEqual("stop_for_review", plan["next_action"])

    def test_permanent_failure_stops_for_review(self):
        request = build_request("facebook")
        plan = build_recovery_plan(request, error_code="synthetic_invalid", retryable=False, attempt=1)
        self.assertEqual("stop_for_review", plan["next_action"])

    def test_dry_run_never_requires_rollback(self):
        request = build_request("google_business")
        plan = build_recovery_plan(request, error_code="synthetic_failure", retryable=False, attempt=1)
        self.assertFalse(plan["rollback_required"])
        self.assertEqual("dry_run_no_side_effect", plan["rollback_reason"])
        self.assertFalse(plan["automatic_rollback"])
        self.assertFalse(plan["rollback_authorized"])

    def test_side_effect_claim_fails_closed(self):
        request = build_request("instagram")
        with self.assertRaises(RecoveryPlanError):
            build_recovery_plan(request, error_code="synthetic_failure", retryable=False, attempt=1, side_effect_observed=True)

    def test_non_dry_run_request_fails_closed(self):
        request = build_request("telegram")
        request["mode"] = "live"
        with self.assertRaises(RecoveryPlanError):
            build_recovery_plan(request, error_code="synthetic_failure", retryable=False, attempt=1)

    def test_recovery_id_is_deterministic(self):
        request = build_request("facebook")
        first = build_recovery_plan(request, error_code="synthetic_timeout", retryable=True, attempt=1)
        second = build_recovery_plan(request, error_code="synthetic_timeout", retryable=True, attempt=1)
        self.assertEqual(first["recovery_id"], second["recovery_id"])


if __name__ == "__main__":
    unittest.main()
