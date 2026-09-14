import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation-hub" / "src"))
sys.path.insert(0, str(ROOT / "operations-hub" / "src"))

from automation_hub import (  # noqa: E402
    ApprovalSimulationStore,
    RecoveryPlanError,
    RecoveryPlanQueue,
    build_automation_plan,
    build_dry_run_boundary_request,
    build_recovery_plan,
)
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402

FIXTURES = ROOT / "operations-hub" / "fixtures"


def build_plan(source: str, *, retryable: bool, attempt: int = 1, max_attempts: int = 3):
    payload = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    automation_plan = build_automation_plan(event, evaluate_governance(event))
    store = ApprovalSimulationStore()
    store.register_plan(automation_plan)
    if automation_plan["approval_required"]:
        store.decide(automation_plan["plan_id"], "approve", f"decision-{source}")
    release = store.release_for_simulation(automation_plan)
    request = build_dry_run_boundary_request(automation_plan, release)
    return build_recovery_plan(
        request,
        error_code=f"synthetic_{source}",
        retryable=retryable,
        attempt=attempt,
        max_attempts=max_attempts,
    )


class RecoveryPlanQueueTests(unittest.TestCase):
    def test_projects_bounded_recovery_workload(self):
        queue = RecoveryPlanQueue()
        queue.ingest(build_plan("telegram", retryable=True, attempt=1))
        queue.ingest(build_plan("facebook", retryable=False, attempt=1))
        model = queue.read_model()
        self.assertEqual("read_only", model["status"])
        self.assertEqual(2, model["plan_count"])
        self.assertEqual(1, model["retry_simulation_count"])
        self.assertEqual(1, model["stop_for_review_count"])
        self.assertFalse(model["plan_fingerprints_exposed"])
        self.assertFalse(model["automatic_retry"])
        self.assertFalse(model["retry_authorized"])
        self.assertFalse(model["automatic_rollback"])
        self.assertFalse(model["rollback_authorized"])
        self.assertFalse(model["execution_authorized"])
        self.assertFalse(model["mutation_authorized"])
        self.assertEqual("none", model["authority_effect"])

    def test_duplicate_recovery_plan_is_deduplicated(self):
        queue = RecoveryPlanQueue()
        plan = build_plan("telegram", retryable=True, attempt=1)
        first = queue.ingest(plan)
        second = queue.ingest(plan)
        self.assertTrue(first["accepted"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(1, queue.read_model()["duplicate_plans"])

    def test_conflicting_duplicate_recovery_id_fails_closed(self):
        queue = RecoveryPlanQueue()
        plan = build_plan("telegram", retryable=True, attempt=1)
        queue.ingest(plan)
        changed = json.loads(json.dumps(plan))
        changed["lifecycle_correlation_id"] = "tampered-correlation"
        self.assertEqual(plan["recovery_id"], changed["recovery_id"])
        with self.assertRaisesRegex(RecoveryPlanError, "content changed"):
            queue.ingest(changed)
        self.assertEqual(0, queue.read_model()["duplicate_plans"])

    def test_read_model_does_not_expose_request_payload_or_fingerprint(self):
        queue = RecoveryPlanQueue()
        queue.ingest(build_plan("instagram", retryable=True, attempt=1))
        model = queue.read_model()
        serialized = json.dumps(model, ensure_ascii=False)
        self.assertNotIn("customer_context", serialized)
        self.assertNotIn("request_payload", serialized)
        self.assertNotIn("dispatch", serialized)
        self.assertNotIn("network_call", serialized)
        self.assertFalse(model["plan_fingerprints_exposed"])
        self.assertNotIn('"plan_fingerprint":', serialized)

    def test_retry_limit_routes_to_review(self):
        queue = RecoveryPlanQueue()
        queue.ingest(build_plan("instagram", retryable=True, attempt=3, max_attempts=3))
        model = queue.read_model()
        self.assertEqual(0, model["retry_simulation_count"])
        self.assertEqual(1, model["stop_for_review_count"])
        self.assertEqual("stop_for_review", model["items"][0]["next_action"])

    def test_rejects_authority_expansion(self):
        queue = RecoveryPlanQueue()
        plan = build_plan("facebook", retryable=False, attempt=1)
        plan["retry_authorized"] = True
        with self.assertRaisesRegex(RecoveryPlanError, "retry_authorized"):
            queue.ingest(plan)

    def test_rejects_inconsistent_retry_state(self):
        queue = RecoveryPlanQueue()
        plan = build_plan("telegram", retryable=True, attempt=1)
        plan["next_action"] = "stop_for_review"
        with self.assertRaisesRegex(RecoveryPlanError, "next_action"):
            queue.ingest(plan)


if __name__ == "__main__":
    unittest.main()
