import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from operations_hub.approval_gated_policy import (
    ApprovalGatedPolicyError,
    AssessmentRequest,
    assess,
)


def request(environment, effect, *factors):
    return AssessmentRequest(environment, effect, frozenset(factors), "approval-gated-policy-2026-10-25")


class ApprovalGatedPolicyTests(unittest.TestCase):
    def test_observation_is_auditable_but_non_authorizing(self):
        decision = assess(request("internal", "observe"))
        self.assertEqual(("R0", "audit_only", None), (decision.risk_level, decision.required_gate, decision.approval_ttl_minutes))
        self.assertFalse(decision.execution_authorized)
        self.assertFalse(decision.mutation_authorized)
        self.assertEqual("none", decision.authority_effect)

    def test_reversible_internal_action_requires_24_hour_ceo_approval(self):
        decision = assess(request("internal", "reversible_internal", "reversibility"))
        self.assertEqual(("R1", "ceo_approval", 1440), (decision.risk_level, decision.required_gate, decision.approval_ttl_minutes))

    def test_operational_mutation_requires_reauthentication(self):
        decision = assess(request("staging", "operational_mutation", "environment"))
        self.assertEqual(("R2", "ceo_reauthenticate", 240), (decision.risk_level, decision.required_gate, decision.approval_ttl_minutes))

    def test_production_or_customer_effect_requires_typed_confirmation(self):
        for item in (request("production", "observe", "environment"), request("sandbox", "external_or_customer", "external_visibility")):
            with self.subTest(item=item):
                decision = assess(item)
                self.assertEqual(("R3", "ceo_typed_confirmation", 15), (decision.risk_level, decision.required_gate, decision.approval_ttl_minutes))

    def test_unknown_or_restricted_request_is_blocked(self):
        for item in (request("unknown", "observe"), request("sandbox", "restricted"), request("sandbox", "observe", "uncertainty")):
            with self.subTest(item=item):
                decision = assess(item)
                self.assertEqual(("R4", "blocked", None), (decision.risk_level, decision.required_gate, decision.approval_ttl_minutes))

    def test_unrecognized_factors_fail_closed(self):
        with self.assertRaisesRegex(ApprovalGatedPolicyError, "assessment_factors_invalid"):
            assess(request("sandbox", "observe", "invented"))

    def test_result_is_json_safe_and_inert(self):
        record = assess(request("internal", "observe")).as_record()
        self.assertEqual("design_only_inactive", record["activation_state"])
        self.assertFalse(record["automatic_execution"])
        self.assertFalse(record["execution_authorized"])
        self.assertFalse(record["mutation_authorized"])
        self.assertEqual("none", record["authority_effect"])


if __name__ == "__main__":
    unittest.main()
