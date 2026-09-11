import unittest

from operations_hub.order_quote_approval_decision import build_order_quote_approval_decision_proposal
from operations_hub.order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from operations_hub.order_quote_approval_register import OrderQuoteApprovalRequestRegister
from operations_hub.order_quote_owner_decision_packet import build_order_quote_owner_decision_packet
from operations_hub.order_quote_owner_decision_register import OrderQuoteOwnerDecisionPacketRegister
from operations_hub.order_quote_owner_decision_workspace import (
    OrderQuoteOwnerDecisionWorkspaceError,
    build_order_quote_owner_decision_workspace,
)


def approval_request(request_id="quote-approval:abc123", correlation="order:correlation:1"):
    return {
        "schema": "rubys-order-quote-approval-request",
        "version": 1,
        "state": "approval_requested",
        "approval_request_id": request_id,
        "lifecycle_correlation_id": correlation,
        "source_draft_id": "quote-draft:abc123",
        "requested_by": "staff",
        "reason": "ready for owner review",
        "pricing": {
            "quote_amount": 1000,
            "shipping_amount": 300,
            "total_amount": 1300,
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


class OrderQuoteOwnerDecisionWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.approvals = OrderQuoteApprovalRequestRegister()
        self.proposals = OrderQuoteApprovalDecisionProposalRegister()
        self.packets = OrderQuoteOwnerDecisionPacketRegister()
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

    def _register_packet(self):
        packet = build_order_quote_owner_decision_packet(
            self.approvals,
            self.proposals,
            approval_request_id=self.request["approval_request_id"],
        )
        self.packets.register(packet)
        return packet

    def test_marks_singular_recommendation_ready_for_owner_packet(self):
        self._register_proposal()
        workspace = build_order_quote_owner_decision_workspace(
            self.approvals,
            self.proposals,
            self.packets,
        )
        self.assertEqual(workspace["ready_for_owner_packet_count"], 1)
        self.assertEqual(workspace["awaiting_owner_decision_count"], 0)
        self.assertEqual(workspace["items"][0]["owner_review_status"], "ready_for_owner_packet")
        self.assertIsNone(workspace["items"][0]["owner_decision"])
        self.assertFalse(workspace["mutation_authorized"])

    def test_marks_registered_packet_awaiting_owner_decision(self):
        self._register_proposal()
        self._register_packet()
        workspace = build_order_quote_owner_decision_workspace(
            self.approvals,
            self.proposals,
            self.packets,
        )
        self.assertEqual(workspace["ready_for_owner_packet_count"], 0)
        self.assertEqual(workspace["awaiting_owner_decision_count"], 1)
        self.assertTrue(workspace["owner_decision_pending"])
        item = workspace["items"][0]
        self.assertEqual(item["owner_review_status"], "awaiting_owner_decision")
        self.assertEqual(item["recommendation"], "recommend_quote_approval")
        self.assertFalse(item["quote_authorized"])

    def test_surfaces_conflict_without_resolving_it(self):
        self._register_proposal("recommend_quote_approval", "reviewer-1")
        self._register_proposal("request_quote_revision", "reviewer-2")
        workspace = build_order_quote_owner_decision_workspace(
            self.approvals,
            self.proposals,
            self.packets,
        )
        self.assertEqual(workspace["blocked_recommendation_conflict_count"], 1)
        self.assertEqual(workspace["items"][0]["owner_review_status"], "blocked_recommendation_conflict")
        self.assertIsNone(workspace["items"][0]["recommendation"])

    def test_rejects_stale_packet_after_recommendation_conflict(self):
        self._register_proposal("recommend_quote_approval", "reviewer-1")
        self._register_packet()
        self._register_proposal("request_quote_revision", "reviewer-2")
        with self.assertRaises(OrderQuoteOwnerDecisionWorkspaceError):
            build_order_quote_owner_decision_workspace(
                self.approvals,
                self.proposals,
                self.packets,
            )

    def test_rejects_orphan_owner_packet(self):
        other_approvals = OrderQuoteApprovalRequestRegister()
        other_proposals = OrderQuoteApprovalDecisionProposalRegister()
        other_request = approval_request("quote-approval:other", "order:correlation:other")
        other_approvals.register(other_request)
        other_proposal = build_order_quote_approval_decision_proposal(
            other_request,
            recommendation="recommend_quote_approval",
            reviewer_ref="reviewer-other",
        )
        other_proposals.register(other_proposal)
        packet = build_order_quote_owner_decision_packet(
            other_approvals,
            other_proposals,
            approval_request_id=other_request["approval_request_id"],
        )
        self.packets.register(packet)
        with self.assertRaises(OrderQuoteOwnerDecisionWorkspaceError):
            build_order_quote_owner_decision_workspace(
                self.approvals,
                self.proposals,
                self.packets,
            )

    def test_rejects_packet_source_drift(self):
        self._register_proposal()
        packet = build_order_quote_owner_decision_packet(
            self.approvals,
            self.proposals,
            approval_request_id=self.request["approval_request_id"],
        )
        packet["source_draft_id"] = "quote-draft:different"
        self.packets.register(packet)
        with self.assertRaises(OrderQuoteOwnerDecisionWorkspaceError):
            build_order_quote_owner_decision_workspace(
                self.approvals,
                self.proposals,
                self.packets,
            )

    def test_summary_omits_proposal_ids_and_decision_metadata(self):
        self._register_proposal()
        self._register_packet()
        workspace = build_order_quote_owner_decision_workspace(
            self.approvals,
            self.proposals,
            self.packets,
        )
        item = workspace["items"][0]
        self.assertNotIn("decision_proposal_ids", item)
        self.assertNotIn("decided_by", item)
        self.assertNotIn("decided_at", item)
        self.assertIsNone(item["owner_decision"])


if __name__ == "__main__":
    unittest.main()
