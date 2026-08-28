import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.governance import GovernanceEvaluationError, evaluate_governance  # noqa: E402
from operations_hub.normalizer import normalize_channel_event  # noqa: E402


def load_fixture(source: str):
    return json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))


class OperationsGovernanceTests(unittest.TestCase):
    def test_low_risk_product_inquiry_needs_no_approval(self):
        event = normalize_channel_event(load_fixture("instagram"))
        result = evaluate_governance(event)
        self.assertEqual("low", result["risk_level"])
        self.assertFalse(result["approval_required"])
        self.assertEqual("not_required", result["approval_state"])

    def test_order_inquiry_is_medium_without_auto_authority(self):
        event = normalize_channel_event(load_fixture("facebook"))
        result = evaluate_governance(event)
        self.assertEqual("medium", result["risk_level"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["channel_reply_authorized"])

    def test_complaint_requires_approval(self):
        event = normalize_channel_event(load_fixture("whatsapp"))
        result = evaluate_governance(event)
        self.assertEqual("high", result["risk_level"])
        self.assertTrue(result["approval_required"])
        self.assertEqual("sensitive_customer_issue", result["approval_reason"])

    def test_public_review_requires_approval(self):
        event = normalize_channel_event(load_fixture("google_business"))
        result = evaluate_governance(event)
        self.assertTrue(result["human_review_required"])
        self.assertEqual("public_review_response", result["approval_reason"])

    def test_correlation_id_is_preserved(self):
        event = normalize_channel_event(load_fixture("telegram"))
        result = evaluate_governance(event)
        self.assertEqual(event["lifecycle_correlation_id"], result["lifecycle_correlation_id"])

    def test_authorizing_event_fails_closed(self):
        event = normalize_channel_event(load_fixture("facebook"))
        event["mutation_authorized"] = True
        with self.assertRaises(GovernanceEvaluationError):
            evaluate_governance(event)

    def test_unknown_intent_fails_closed(self):
        event = normalize_channel_event(load_fixture("facebook"))
        event["normalized_intent"] = "unknown_action"
        with self.assertRaises(GovernanceEvaluationError):
            evaluate_governance(event)


if __name__ == "__main__":
    unittest.main()
