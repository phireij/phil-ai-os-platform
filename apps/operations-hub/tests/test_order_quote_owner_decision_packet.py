import unittest

from operations_hub.order_quote_approval_decision import build_order_quote_approval_decision_proposal
from operations_hub.order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from operations_hub.order_quote_approval_register import OrderQuoteApprovalRequestRegister
from operations_hub.order_quote_owner_decision_packet import (
    OrderQuoteOwnerDecisionPacketError,
    build_order_quote_owner_decision_packet,
)


def approval_request(request_id="quote-approval:abc123", total=1300):
    return {
        "schema": "rubys-order-quote-approval-request",
        "version": 1,
        "state": "approval_requested",
        "approval_request_id": request_id,
        "lifecycle_correlation_id": "order:correlation:1",
        "source_draft_id": "quote-draft:abc123",
        "requested_by": "staff",
        "reason": "ready for owner review",
        "pricing": {
            "quote_amount": 1000,
            "shipping_amount": 300,
            "total_amount": total,
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


class OrderQuoteOwnerDecisionPacketTests(unittest.TestCase):
    def setUp(self):
        self.approvals = OrderQuoteApprovalRequestRegister()
        self.proposals = OrderQuoteApprovalDecisionProposalRegister()
        self.request = approval_request()
        self.approvals.register(self.request)

    def _register_proposal(self, recommendation="recommend_quote_approval", reviewer="reviewer-1"):
        proposal = build_order_quote_approval_decision_proposal(
            self.request,
            recommendation=recommendation,
            reviewer_ref=reviewer,
            note="bounded recommendation",
        )
        self.proposals.register(proposal)
        return proposal

    def test_builds_owner_review_only_packet(self):
        proposal = self._register_proposal()
        packet = build_order_quote_owner_decision_packet(
            self.approvals,
            self.proposals,
            approval_request_id=self.request["approval_request_id"],
        )
        self.assertEqual(packet["state"], "awaiting_owner_decision")
        self.assertEqual(packet["recommendation"], "recommend_quote_approval")
        self.assertEqual(packet["decision_proposal_ids"], [proposal["decision_proposal_id"]])
        self.assertIsNone(packet["owner_decision"]["decision"])
        self.assertTrue(packet["authority"]["owner_review_only"])
        for field, value in packet["authority"].items():
            if field != "owner_review_only":
                self.assertIs(value, False)

    def test_revision_recommendation_remains_non_authorizing(self):
        self._register_proposal("request_quote_revision")
        packet = build_order_quote_owner_decision_packet(
            self.approvals,
            self.proposals,
            approval_request_id=self.request["approval_request_id"],
        )
        self.assertEqual(packet["recommendation"], "request_quote_revision")
        self.assertFalse(packet["authority"]["quote_authorized"])
        self.assertFalse(packet["authority"]["mutation_authorized"])

    def test_rejects_request_without_recommendation(self):
        with self.assertRaises(OrderQuoteOwnerDecisionPacketError):
            build_order_quote_owner_decision_packet(
                self.approvals,
                self.proposals,
                approval_request_id=self.request["approval_request_id"],
            )

    def test_rejects_conflicting_recommendations(self):
        self._register_proposal("recommend_quote_approval", "reviewer-1")
        self._register_proposal("request_quote_revision", "reviewer-2")
        with self.assertRaises(OrderQuoteOwnerDecisionPacketError):
            build_order_quote_owner_decision_packet(
                self.approvals,
                self.proposals,
                approval_request_id=self.request["approval_request_id"],
            )

    def test_rejects_unknown_request(self):
        self._register_proposal()
        with self.assertRaises(OrderQuoteOwnerDecisionPacketError):
            build_order_quote_owner_decision_packet(
                self.approvals,
                self.proposals,
                approval_request_id="quote-approval:missing",
            )


if __name__ == "__main__":
    unittest.main()
