import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    OperationsDashboardError,
    OperationsQueue,
    OrderQuoteApprovalDecisionProposalRegister,
    OrderQuoteApprovalRequestRegister,
    OrderQuoteOwnerDecisionPacketRegister,
    OrderReviewQueue,
    build_operations_dashboard,
)


class StubChannelQueue(OperationsQueue):
    def __init__(self, model):
        self._model = model

    def read_model(self):
        return self._model


def valid_channel_model():
    return {
        "status": "read_only",
        "total_events": 3,
        "duplicate_events": 1,
        "review_required": 1,
        "standard_queue": 2,
        "source_counts": {"facebook": 2, "telegram": 1},
        "intent_counts": {"order": 2, "question": 1},
        "items": [],
        "mutation_authorized": False,
    }


def build_dashboard(model):
    return build_operations_dashboard(
        StubChannelQueue(model),
        OrderReviewQueue(),
        OrderQuoteApprovalRequestRegister(),
        OrderQuoteApprovalDecisionProposalRegister(),
        OrderQuoteOwnerDecisionPacketRegister(),
    )


class OperationsDashboardChannelAggregateIntegrityTests(unittest.TestCase):
    def test_preserves_valid_read_only_channel_aggregate(self):
        dashboard = build_dashboard(valid_channel_model())
        channels = dashboard["channels"]
        self.assertEqual(3, channels["total_events"])
        self.assertEqual(1, channels["review_required"])
        self.assertEqual(2, channels["standard_queue"])
        self.assertEqual({"facebook": 2, "telegram": 1}, channels["source_counts"])
        self.assertEqual({"order": 2, "question": 1}, channels["intent_counts"])
        self.assertFalse(dashboard["mutation_authorized"])

    def test_rejects_channel_queue_counts_that_do_not_match_total(self):
        model = valid_channel_model()
        model["standard_queue"] = 1
        with self.assertRaisesRegex(OperationsDashboardError, "queue counts must match"):
            build_dashboard(model)

    def test_rejects_channel_source_counts_that_do_not_match_total(self):
        model = valid_channel_model()
        model["source_counts"] = {"facebook": 2}
        with self.assertRaisesRegex(OperationsDashboardError, "source_counts must match"):
            build_dashboard(model)

    def test_rejects_channel_intent_counts_that_do_not_match_total(self):
        model = valid_channel_model()
        model["intent_counts"] = {"order": 1, "question": 1}
        with self.assertRaisesRegex(OperationsDashboardError, "intent_counts must match"):
            build_dashboard(model)


if __name__ == "__main__":
    unittest.main()
