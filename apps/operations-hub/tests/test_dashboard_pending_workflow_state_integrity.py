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


class StubOrderReviewQueue(OrderReviewQueue):
    def __init__(self, model):
        self._model = model

    def read_model(self):
        return self._model


class StubApprovalRegister(OrderQuoteApprovalRequestRegister):
    def __init__(self, model):
        self._model = model

    def read_model(self):
        return self._model


class StubRecommendationRegister(OrderQuoteApprovalDecisionProposalRegister):
    def __init__(self, model):
        self._model = model

    def read_model(self):
        return self._model


class StubOwnerPacketRegister(OrderQuoteOwnerDecisionPacketRegister):
    def __init__(self, model):
        self._model = model

    def read_model(self):
        return self._model


def order_model(item=None):
    items = [] if item is None else [item]
    return {
        "status": "read_only",
        "pending_review": len(items),
        "duplicate_handoffs": 0,
        "items": items,
        "mutation_authorized": False,
    }


def approval_model(item=None):
    items = [] if item is None else [item]
    return {
        "status": "read_only",
        "pending_approval_count": len(items),
        "duplicate_requests": 0,
        "items": items,
        "mutation_authorized": False,
    }


def recommendation_model(item=None):
    items = [] if item is None else [item]
    return {
        "status": "read_only",
        "proposal_count": len(items),
        "duplicate_proposals": 0,
        "items": items,
        "mutation_authorized": False,
    }


def owner_model(item=None):
    items = [] if item is None else [item]
    return {
        "status": "read_only",
        "packet_count": len(items),
        "duplicate_packets": 0,
        "items": items,
        "owner_decision_pending": bool(items),
        "mutation_authorized": False,
    }


def build_dashboard(orders=None, approvals=None, recommendations=None, owner_packets=None):
    return build_operations_dashboard(
        OperationsQueue(),
        StubOrderReviewQueue(orders or order_model()),
        StubApprovalRegister(approvals or approval_model()),
        StubRecommendationRegister(recommendations or recommendation_model()),
        StubOwnerPacketRegister(owner_packets or owner_model()),
    )


class OperationsDashboardPendingWorkflowStateIntegrityTests(unittest.TestCase):
    def test_preserves_pending_read_only_workflow_states(self):
        dashboard = build_dashboard(
            orders=order_model({"review_state": "pending_staff_review", "mutation_authorized": False}),
            approvals=approval_model({
                "state": "approval_requested",
                "decision": None,
                "mutation_authorized": False,
            }),
            recommendations=recommendation_model({
                "approval_decided": False,
                "mutation_authorized": False,
            }),
            owner_packets=owner_model({
                "owner_decision_required": True,
                "owner_decision": None,
                "mutation_authorized": False,
            }),
        )
        self.assertEqual(1, dashboard["orders"]["pending_staff_review"])
        self.assertEqual(1, dashboard["quotes"]["pending_approval"])
        self.assertEqual(1, dashboard["quotes"]["recommendation_proposals"])
        self.assertEqual(1, dashboard["owner_review"]["pending_packets"])
        self.assertTrue(dashboard["owner_review"]["owner_decision_pending"])
        self.assertFalse(dashboard["mutation_authorized"])

    def test_rejects_order_item_that_is_not_pending_staff_review(self):
        with self.assertRaisesRegex(OperationsDashboardError, "review_state must remain pending_staff_review"):
            build_dashboard(orders=order_model({
                "review_state": "reviewed",
                "mutation_authorized": False,
            }))

    def test_rejects_approval_item_that_is_not_approval_requested(self):
        with self.assertRaisesRegex(OperationsDashboardError, "state must remain approval_requested"):
            build_dashboard(approvals=approval_model({
                "state": "approved",
                "decision": None,
                "mutation_authorized": False,
            }))

    def test_rejects_approval_item_with_injected_decision(self):
        with self.assertRaisesRegex(OperationsDashboardError, "decision must remain unset"):
            build_dashboard(approvals=approval_model({
                "state": "approval_requested",
                "decision": "approved",
                "mutation_authorized": False,
            }))

    def test_rejects_recommendation_item_marked_decided(self):
        with self.assertRaisesRegex(OperationsDashboardError, "approval_decided must remain false"):
            build_dashboard(recommendations=recommendation_model({
                "approval_decided": True,
                "mutation_authorized": False,
            }))

    def test_rejects_owner_packet_without_pending_decision_requirement(self):
        with self.assertRaisesRegex(OperationsDashboardError, "owner_decision_required must remain true"):
            build_dashboard(owner_packets=owner_model({
                "owner_decision_required": False,
                "owner_decision": None,
                "mutation_authorized": False,
            }))

    def test_rejects_owner_packet_with_injected_decision(self):
        with self.assertRaisesRegex(OperationsDashboardError, "owner_decision must remain unset"):
            build_dashboard(owner_packets=owner_model({
                "owner_decision_required": True,
                "owner_decision": "approve_quote",
                "mutation_authorized": False,
            }))


if __name__ == "__main__":
    unittest.main()
