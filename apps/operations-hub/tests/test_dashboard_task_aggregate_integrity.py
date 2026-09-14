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


def sources():
    return (
        OperationsQueue(),
        OrderReviewQueue(),
        OrderQuoteApprovalRequestRegister(),
        OrderQuoteApprovalDecisionProposalRegister(),
        OrderQuoteOwnerDecisionPacketRegister(),
    )


def task_queue_with(model):
    queue = TaskCandidateQueue()
    queue.read_model = lambda: model
    return queue


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
            {"task_candidate_id": "ops-task:1", "mutation_authorized": False},
            {"task_candidate_id": "ops-task:2", "mutation_authorized": False},
        ],
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
    }


class OperationsDashboardTaskAggregateIntegrityTests(unittest.TestCase):
    def test_rejects_task_state_counts_that_do_not_match_task_count(self):
        model = task_model()
        model["ready_for_operator_review"] = 0
        with self.assertRaisesRegex(OperationsDashboardError, "state counts must match"):
            build_operations_dashboard(*sources(), task_queue_with(model))

    def test_rejects_task_type_counts_that_do_not_match_task_count(self):
        model = task_model()
        model["task_type_counts"] = {"customer_message_review": 1}
        with self.assertRaisesRegex(OperationsDashboardError, "task_type_counts must match"):
            build_operations_dashboard(*sources(), task_queue_with(model))

    def test_rejects_task_source_counts_that_do_not_match_task_count(self):
        model = task_model()
        model["source_counts"] = {"facebook": 1}
        with self.assertRaisesRegex(OperationsDashboardError, "source_counts must match"):
            build_operations_dashboard(*sources(), task_queue_with(model))

    def test_rejects_invalid_task_duplicate_count(self):
        model = task_model()
        model["duplicate_tasks"] = -1
        with self.assertRaisesRegex(OperationsDashboardError, "duplicate_tasks"):
            build_operations_dashboard(*sources(), task_queue_with(model))


if __name__ == "__main__":
    unittest.main()
