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


def order_model(count=0, items=None):
    return {
        "status": "read_only",
        "pending_review": count,
        "duplicate_handoffs": 0,
        "items": [] if items is None else items,
        "mutation_authorized": False,
    }


def approval_model(count=0, items=None):
    return {
        "status": "read_only",
        "pending_approval_count": count,
        "duplicate_requests": 0,
        "items": [] if items is None else items,
        "mutation_authorized": False,
    }


def recommendation_model(count=0, items=None):
    return {
        "status": "read_only",
        "proposal_count": count,
        "duplicate_proposals": 0,
        "items": [] if items is None else items,
        "mutation_authorized": False,
    }


def owner_model(count=0, items=None, pending=False):
    return {
        "status": "read_only",
        "packet_count": count,
        "duplicate_packets": 0,
        "items": [] if items is None else items,
        "owner_decision_pending": pending,
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


class OperationsDashboardWorkloadCountIntegrityTests(unittest.TestCase):
    def test_preserves_valid_empty_workload_models(self):
        dashboard = build_dashboard()
        self.assertEqual(0, dashboard["orders"]["pending_staff_review"])
        self.assertEqual(0, dashboard["quotes"]["pending_approval"])
        self.assertEqual(0, dashboard["quotes"]["recommendation_proposals"])
        self.assertEqual(0, dashboard["owner_review"]["pending_packets"])
        self.assertFalse(dashboard["owner_review"]["owner_decision_pending"])
        self.assertFalse(dashboard["mutation_authorized"])

    def test_rejects_order_pending_count_that_does_not_match_items(self):
        with self.assertRaisesRegex(OperationsDashboardError, "pending_review must match"):
            build_dashboard(orders=order_model(count=2, items=[{}]))

    def test_rejects_approval_pending_count_that_does_not_match_items(self):
        with self.assertRaisesRegex(OperationsDashboardError, "pending_approval_count must match"):
            build_dashboard(approvals=approval_model(count=2, items=[{}]))

    def test_rejects_recommendation_count_that_does_not_match_items(self):
        with self.assertRaisesRegex(OperationsDashboardError, "proposal_count must match"):
            build_dashboard(recommendations=recommendation_model(count=2, items=[{}]))

    def test_rejects_owner_packet_count_that_does_not_match_items(self):
        with self.assertRaisesRegex(OperationsDashboardError, "packet_count must match"):
            build_dashboard(owner_packets=owner_model(count=2, items=[{}], pending=True))

    def test_rejects_owner_pending_state_that_does_not_match_items(self):
        with self.assertRaisesRegex(OperationsDashboardError, "owner_decision_pending must match"):
            build_dashboard(owner_packets=owner_model(count=1, items=[{}], pending=False))


if __name__ == "__main__":
    unittest.main()
