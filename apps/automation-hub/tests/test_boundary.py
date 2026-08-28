import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "automation-hub" / "src"))
sys.path.insert(0, str(ROOT / "operations-hub" / "src"))

from automation_hub import ApprovalSimulationStore, build_automation_plan  # noqa: E402
from automation_hub.boundary import BoundaryRequestError, build_dry_run_boundary_request  # noqa: E402
from operations_hub import evaluate_governance, normalize_channel_event  # noqa: E402

FIXTURES = ROOT / "operations-hub" / "fixtures"


def plan_and_release(source: str, approve: bool = False):
    payload = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))
    event = normalize_channel_event(payload)
    plan = build_automation_plan(event, evaluate_governance(event))
    store = ApprovalSimulationStore()
    store.register_plan(plan)
    if approve:
        store.decide(plan["plan_id"], "approve", f"decision-{source}")
    return plan, store.release_for_simulation(plan)


class DryRunBoundaryTests(unittest.TestCase):
    def test_not_required_plan_builds_dry_run_request(self):
        plan, release = plan_and_release("instagram")
        request = build_dry_run_boundary_request(plan, release)
        self.assertTrue(request["dry_run"])
        self.assertFalse(request["dispatch"])
        self.assertFalse(request["network_call"])

    def test_approved_plan_builds_dry_run_request(self):
        plan, release = plan_and_release("whatsapp", approve=True)
        request = build_dry_run_boundary_request(plan, release)
        self.assertEqual("execution_boundary", request["target"])
        self.assertEqual("preview_request", request["operation"])

    def test_request_never_grants_authority(self):
        plan, release = plan_and_release("telegram")
        request = build_dry_run_boundary_request(plan, release)
        for field in ("dispatch", "network_call", "automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
            self.assertFalse(request[field])
        self.assertEqual("none", request["authority_effect"])

    def test_request_id_is_deterministic(self):
        plan, release = plan_and_release("facebook")
        first = build_dry_run_boundary_request(plan, release)
        second = build_dry_run_boundary_request(plan, release)
        self.assertEqual(first["request_id"], second["request_id"])

    def test_identity_mismatch_fails_closed(self):
        plan, release = plan_and_release("instagram")
        release["plan_id"] = "wrong"
        with self.assertRaises(BoundaryRequestError):
            build_dry_run_boundary_request(plan, release)

    def test_authorizing_release_fails_closed(self):
        plan, release = plan_and_release("instagram")
        release["execution_authorized"] = True
        with self.assertRaises(BoundaryRequestError):
            build_dry_run_boundary_request(plan, release)

    def test_specialist_plan_fails_closed(self):
        plan, release = plan_and_release("instagram")
        plan["specialist_enabled"] = True
        with self.assertRaises(BoundaryRequestError):
            build_dry_run_boundary_request(plan, release)


if __name__ == "__main__":
    unittest.main()
