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
    TaskCandidateQueue,
    build_operations_dashboard,
)


class StubChannelQueue(OperationsQueue):
    def __init__(self, model):
        self._model = model

    def read_model(self):
        return self._model


class StubTaskQueue(TaskCandidateQueue):
    def __init__(self, model):
        self._model = model

    def read_model(self):
        return self._model


def empty_workload_sources():
    return (
        OrderReviewQueue(),
        OrderQuoteApprovalRequestRegister(),
        OrderQuoteApprovalDecisionProposalRegister(),
        OrderQuoteOwnerDecisionPacketRegister(),
    )


def channel_model():
    return {
        "status": "read_only",
        "total_events": 2,
        "duplicate_events": 0,
        "review_required": 1,
        "standard_queue": 1,
        "source_counts": {"facebook": 1, "telegram": 1},
        "intent_counts": {"order": 2},
        "items": [
            {
                "source": "facebook",
                "normalized_intent": "order",
                "review_required": True,
                "mutation_authorized": False,
            },
            {
                "source": "telegram",
                "normalized_intent": "order",
                "review_required": False,
                "mutation_authorized": False,
            },
        ],
        "mutation_authorized": False,
    }


def task_model():
    return {
        "status": "read_only",
        "queue": "channel_task_candidates",
        "task_count": 2,
        "duplicate_tasks": 0,
        "awaiting_approval": 1,
        "ready_for_operator_review": 1,
        "task_type_counts": {"customer_message_review": 1, "order_intent_review": 1},
        "source_counts": {"facebook": 1, "telegram": 1},
        "items": [
            {
                "source": "facebook",
                "task_type": "customer_message_review",
                "state": "awaiting_approval",
                "mutation_authorized": False,
            },
            {
                "source": "telegram",
                "task_type": "order_intent_review",
                "state": "ready_for_operator_review",
                "mutation_authorized": False,
            },
        ],
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
    }


class OperationsDashboardItemCardinalityIntegrityTests(unittest.TestCase):
    def test_preserves_matching_channel_item_cardinality(self):
        dashboard = build_operations_dashboard(
            StubChannelQueue(channel_model()),
            *empty_workload_sources(),
        )
        self.assertEqual(2, dashboard["channels"]["total_events"])

    def test_rejects_channel_total_that_does_not_match_items(self):
        model = channel_model()
        model["items"] = model["items"][:1]
        with self.assertRaisesRegex(OperationsDashboardError, "total_events must match channel items"):
            build_operations_dashboard(
                StubChannelQueue(model),
                *empty_workload_sources(),
            )

    def test_rejects_channel_source_labels_that_do_not_match_items(self):
        model = channel_model()
        model["source_counts"] = {"instagram": 1, "telegram": 1}
        with self.assertRaisesRegex(OperationsDashboardError, "source_counts must match channel items"):
            build_operations_dashboard(StubChannelQueue(model), *empty_workload_sources())

    def test_rejects_channel_intent_labels_that_do_not_match_items(self):
        model = channel_model()
        model["intent_counts"] = {"order": 1, "question": 1}
        with self.assertRaisesRegex(OperationsDashboardError, "intent_counts must match channel items"):
            build_operations_dashboard(StubChannelQueue(model), *empty_workload_sources())

    def test_rejects_channel_review_bucket_that_does_not_match_items(self):
        model = channel_model()
        model["items"][1]["review_required"] = True
        with self.assertRaisesRegex(OperationsDashboardError, "review_required must match channel items"):
            build_operations_dashboard(StubChannelQueue(model), *empty_workload_sources())

    def test_preserves_matching_task_item_cardinality(self):
        dashboard = build_operations_dashboard(
            OperationsQueue(),
            *empty_workload_sources(),
            task_queue=StubTaskQueue(task_model()),
        )
        self.assertEqual(2, dashboard["tasks"]["task_count"])

    def test_rejects_task_total_that_does_not_match_items(self):
        model = task_model()
        model["items"] = model["items"][:1]
        with self.assertRaisesRegex(OperationsDashboardError, "task_count must match task items"):
            build_operations_dashboard(
                OperationsQueue(),
                *empty_workload_sources(),
                task_queue=StubTaskQueue(model),
            )

    def test_rejects_task_source_labels_that_do_not_match_items(self):
        model = task_model()
        model["source_counts"] = {"instagram": 1, "telegram": 1}
        with self.assertRaisesRegex(OperationsDashboardError, "source_counts must match task items"):
            build_operations_dashboard(
                OperationsQueue(),
                *empty_workload_sources(),
                task_queue=StubTaskQueue(model),
            )

    def test_rejects_task_type_labels_that_do_not_match_items(self):
        model = task_model()
        model["task_type_counts"] = {"customer_message_review": 1, "quote_review": 1}
        with self.assertRaisesRegex(OperationsDashboardError, "task_type_counts must match task items"):
            build_operations_dashboard(
                OperationsQueue(),
                *empty_workload_sources(),
                task_queue=StubTaskQueue(model),
            )

    def test_rejects_task_state_bucket_that_does_not_match_items(self):
        model = task_model()
        model["items"][1]["state"] = "awaiting_approval"
        with self.assertRaisesRegex(OperationsDashboardError, "awaiting_approval must match task items"):
            build_operations_dashboard(
                OperationsQueue(),
                *empty_workload_sources(),
                task_queue=StubTaskQueue(model),
            )


if __name__ == "__main__":
    unittest.main()
