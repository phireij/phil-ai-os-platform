from __future__ import annotations

import unittest

from operations_hub.order_quote_approval_decision import build_order_quote_approval_decision_proposal
from operations_hub.order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from operations_hub.order_quote_approval_decision_workspace import (
    OrderQuoteApprovalDecisionWorkspaceError,
    build_order_quote_approval_decision_workspace,
)
from operations_hub.order_quote_approval_register import OrderQuoteApprovalRequestRegister


def approval_request(request_id: str = "quote-approval:1234567890abcdef12345678") -> dict:
    return {
        "schema": "rubys-order-quote-approval-request",
        "version": 1,
        "state": "approval_requested",
        "approval_request_id": request_id,
        "lifecycle_correlation_id": "order-review:abc123",
        "source_draft_id": "quote-draft:1234567890abcdef12345678",
        "requested_by": "staff-1",
        "reason": "ready for approval review",
        "pricing": {
            "quote_amount": 4000,
            "shipping_amount": 500,
            "total_amount": 4500,
            "currency": "JPY",
            "customer_accepted": False,
        },
        "approval": {
            "required": True,
            "decision": None,
            "approved_by": None,
            "approved_at": None,
        },
        "authority": {
            "approval_request_only": True,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "fulfillment_confirmed": False,
            "woo_commerce_mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "production_publish_authorized": False,
            "mutation_authorized": False,
        },
    }


class OrderQuoteApprovalDecisionWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.approvals = OrderQuoteApprovalRequestRegister()
        self.proposals = OrderQuoteApprovalDecisionProposalRegister()
        self.request = approval_request()
        self.approvals.register(self.request)

    def test_reports_request_awaiting_recommendation(self) -> None:
        workspace = build_order_quote_approval_decision_workspace(
            self.approvals, self.proposals
        )
        self.assertEqual(workspace["awaiting_recommendation_count"], 1)
        self.assertEqual(workspace["recommendation_ready_count"], 0)
        self.assertEqual(
            workspace["items"][0]["recommendation_status"],
            "recommendation_not_proposed",
        )
        self.assertFalse(workspace["approval_decided"])
        self.assertFalse(workspace["quote_authorized"])
        self.assertFalse(workspace["mutation_authorized"])

    def test_correlates_single_recommendation_without_deciding(self) -> None:
        proposal = build_order_quote_approval_decision_proposal(
            self.request,
            recommendation="recommend_quote_approval",
            reviewer_ref="reviewer-1",
            note="looks ready",
        )
        self.proposals.register(proposal)

        workspace = build_order_quote_approval_decision_workspace(
            self.approvals, self.proposals
        )
        row = workspace["items"][0]
        self.assertEqual(row["recommendation_status"], "recommendation_proposed")
        self.assertEqual(row["recommendations"], ["recommend_quote_approval"])
        self.assertEqual(row["proposal_count"], 1)
        self.assertIsNone(row["decision"])
        self.assertNotIn("reviewer_ref", row)
        self.assertNotIn("note", row)
        self.assertEqual(workspace["recommendation_ready_count"], 1)
        self.assertEqual(workspace["recommendation_conflict_count"], 0)

    def test_surfaces_conflicting_recommendations_without_resolving_them(self) -> None:
        approve = build_order_quote_approval_decision_proposal(
            self.request,
            recommendation="recommend_quote_approval",
            reviewer_ref="reviewer-1",
        )
        revise = build_order_quote_approval_decision_proposal(
            self.request,
            recommendation="request_quote_revision",
            reviewer_ref="reviewer-2",
        )
        self.proposals.register(approve)
        self.proposals.register(revise)

        workspace = build_order_quote_approval_decision_workspace(
            self.approvals, self.proposals
        )
        row = workspace["items"][0]
        self.assertEqual(row["recommendation_status"], "recommendation_conflict")
        self.assertEqual(
            row["recommendations"],
            ["recommend_quote_approval", "request_quote_revision"],
        )
        self.assertEqual(workspace["recommendation_conflict_count"], 1)
        self.assertFalse(row["approval_decided"])
        self.assertFalse(row["quote_authorized"])

    def test_rejects_orphan_proposal(self) -> None:
        orphan_source = approval_request("quote-approval:abcdefabcdefabcdefabcdef")
        proposal = build_order_quote_approval_decision_proposal(
            orphan_source,
            recommendation="request_quote_revision",
            reviewer_ref="reviewer-2",
        )
        orphan_register = OrderQuoteApprovalDecisionProposalRegister()
        orphan_register.register(proposal)

        with self.assertRaises(OrderQuoteApprovalDecisionWorkspaceError):
            build_order_quote_approval_decision_workspace(
                self.approvals, orphan_register
            )

    def test_rejects_proposal_pricing_that_differs_from_request(self) -> None:
        proposal = build_order_quote_approval_decision_proposal(
            self.request,
            recommendation="recommend_quote_approval",
            reviewer_ref="reviewer-1",
        )
        proposal["pricing"] = dict(proposal["pricing"])
        proposal["pricing"]["quote_amount"] = 4100
        proposal["pricing"]["total_amount"] = 4600
        self.proposals.register(proposal)

        with self.assertRaises(OrderQuoteApprovalDecisionWorkspaceError):
            build_order_quote_approval_decision_workspace(
                self.approvals, self.proposals
            )

    def test_rejects_proposal_correlation_mismatch(self) -> None:
        proposal = build_order_quote_approval_decision_proposal(
            self.request,
            recommendation="recommend_quote_approval",
            reviewer_ref="reviewer-1",
        )
        proposal["lifecycle_correlation_id"] = "order-review:different"
        self.proposals.register(proposal)

        with self.assertRaises(OrderQuoteApprovalDecisionWorkspaceError):
            build_order_quote_approval_decision_workspace(
                self.approvals, self.proposals
            )

    def test_rejects_proposal_source_draft_mismatch(self) -> None:
        proposal = build_order_quote_approval_decision_proposal(
            self.request,
            recommendation="recommend_quote_approval",
            reviewer_ref="reviewer-1",
        )
        proposal["source_draft_id"] = "quote-draft:different"
        self.proposals.register(proposal)

        with self.assertRaisesRegex(
            OrderQuoteApprovalDecisionWorkspaceError,
            "source_draft_id does not match",
        ):
            build_order_quote_approval_decision_workspace(
                self.approvals, self.proposals
            )


if __name__ == "__main__":
    unittest.main()
