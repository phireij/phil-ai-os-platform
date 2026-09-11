import copy
import unittest

from operations_hub.order_quote_approval_decision import (
    OrderQuoteApprovalDecisionError,
    build_order_quote_approval_decision_proposal,
)


def approval_request():
    return {
        "schema": "rubys-order-quote-approval-request",
        "version": 1,
        "state": "approval_requested",
        "approval_request_id": "quote-approval:0123456789abcdefghijklmn",
        "lifecycle_correlation_id": "order-request:0123456789abcdefghijklmn",
        "source_draft_id": "quote-draft:0123456789abcdefghijklmn",
        "pricing": {
            "quote_amount": 5000,
            "shipping_amount": 800,
            "total_amount": 5800,
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


class OrderQuoteApprovalDecisionProposalTests(unittest.TestCase):
    def test_builds_non_authorizing_recommendation(self):
        proposal = build_order_quote_approval_decision_proposal(
            approval_request(),
            recommendation="recommend_quote_approval",
            reviewer_ref="staff:ruby",
            note="Ready for owner approval",
        )
        self.assertEqual(proposal["state"], "recommendation_only")
        self.assertEqual(proposal["pricing"]["total_amount"], 5800)
        self.assertFalse(proposal["effects"]["approval_decided"])
        self.assertFalse(proposal["effects"]["quote_authorized"])
        self.assertFalse(proposal["effects"]["customer_notification_authorized"])
        self.assertFalse(proposal["mutation_authorized"])

    def test_is_deterministic(self):
        first = build_order_quote_approval_decision_proposal(
            approval_request(), recommendation="request_quote_revision", reviewer_ref="staff:ruby"
        )
        second = build_order_quote_approval_decision_proposal(
            approval_request(), recommendation="request_quote_revision", reviewer_ref="staff:ruby"
        )
        self.assertEqual(first["decision_proposal_id"], second["decision_proposal_id"])

    def test_rejects_unsupported_recommendation(self):
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "unsupported"):
            build_order_quote_approval_decision_proposal(
                approval_request(), recommendation="approve_and_send", reviewer_ref="staff:ruby"
            )

    def test_rejects_already_decided_request(self):
        payload = copy.deepcopy(approval_request())
        payload["approval"]["decision"] = "approved"
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "decision must remain unset"):
            build_order_quote_approval_decision_proposal(
                payload, recommendation="recommend_quote_approval", reviewer_ref="staff:ruby"
            )

    def test_rejects_authority_expansion(self):
        payload = copy.deepcopy(approval_request())
        payload["authority"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "quote_authorized"):
            build_order_quote_approval_decision_proposal(
                payload, recommendation="recommend_quote_approval", reviewer_ref="staff:ruby"
            )

    def test_rejects_bad_pricing(self):
        payload = copy.deepcopy(approval_request())
        payload["pricing"]["total_amount"] = 6000
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "must reconcile"):
            build_order_quote_approval_decision_proposal(
                payload, recommendation="recommend_quote_approval", reviewer_ref="staff:ruby"
            )

    def test_bounds_reviewer_metadata(self):
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "reviewer_ref exceeds"):
            build_order_quote_approval_decision_proposal(
                approval_request(), recommendation="recommend_quote_approval", reviewer_ref="x" * 121
            )
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "note exceeds"):
            build_order_quote_approval_decision_proposal(
                approval_request(), recommendation="recommend_quote_approval", reviewer_ref="staff:ruby", note="x" * 1001
            )


if __name__ == "__main__":
    unittest.main()
