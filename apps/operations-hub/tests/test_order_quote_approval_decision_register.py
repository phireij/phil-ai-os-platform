import copy
import unittest

from operations_hub.order_quote_approval_decision import OrderQuoteApprovalDecisionError
from operations_hub.order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister


def proposal():
    return {
        "schema": "rubys-order-quote-approval-decision-proposal",
        "version": 1,
        "state": "recommendation_only",
        "decision_proposal_id": "quote-approval-proposal:0123456789abcdefghijklmn",
        "approval_request_id": "quote-approval:0123456789abcdefghijklmn",
        "lifecycle_correlation_id": "order-request:0123456789abcdefghijklmn",
        "source_draft_id": "quote-draft:0123456789abcdefghijklmn",
        "recommendation": "recommend_quote_approval",
        "reviewer_ref": "staff:ruby",
        "note": "Looks ready for explicit approval",
        "pricing": {
            "quote_amount": 5000,
            "shipping_amount": 800,
            "total_amount": 5800,
            "currency": "JPY",
            "customer_accepted": False,
        },
        "effects": {
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "fulfillment_confirmed": False,
            "woo_commerce_mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "production_publish_authorized": False,
        },
        "mutation_authorized": False,
    }


class OrderQuoteApprovalDecisionProposalRegisterTests(unittest.TestCase):
    def test_registers_non_authorizing_recommendation(self):
        register = OrderQuoteApprovalDecisionProposalRegister()
        result = register.register(proposal())
        self.assertTrue(result["accepted"])
        model = register.read_model()
        self.assertEqual(model["proposal_count"], 1)
        self.assertEqual(model["items"][0]["recommendation"], "recommend_quote_approval")
        self.assertFalse(model["approval_decided"])
        self.assertFalse(model["quote_authorized"])
        self.assertNotIn("reviewer_ref", model["items"][0])
        self.assertNotIn("note", model["items"][0])

    def test_deduplicates_same_proposal(self):
        register = OrderQuoteApprovalDecisionProposalRegister()
        register.register(proposal())
        duplicate = register.register(proposal())
        self.assertFalse(duplicate["accepted"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(register.read_model()["duplicate_proposals"], 1)

    def test_accepts_revision_recommendation_without_authority(self):
        payload = proposal()
        payload["recommendation"] = "request_quote_revision"
        register = OrderQuoteApprovalDecisionProposalRegister()
        register.register(payload)
        self.assertEqual(register.read_model()["items"][0]["recommendation"], "request_quote_revision")
        self.assertFalse(register.read_model()["mutation_authorized"])

    def test_rejects_effect_expansion(self):
        payload = copy.deepcopy(proposal())
        payload["effects"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "effects must remain false"):
            OrderQuoteApprovalDecisionProposalRegister().register(payload)

    def test_rejects_general_mutation_authority(self):
        payload = copy.deepcopy(proposal())
        payload["mutation_authorized"] = True
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "non-authorizing"):
            OrderQuoteApprovalDecisionProposalRegister().register(payload)

    def test_rejects_invalid_recommendation(self):
        payload = copy.deepcopy(proposal())
        payload["recommendation"] = "approve_quote"
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "unsupported quote approval recommendation"):
            OrderQuoteApprovalDecisionProposalRegister().register(payload)

    def test_rejects_mismatched_pricing(self):
        payload = copy.deepcopy(proposal())
        payload["pricing"]["total_amount"] = 6000
        with self.assertRaisesRegex(OrderQuoteApprovalDecisionError, "must reconcile"):
            OrderQuoteApprovalDecisionProposalRegister().register(payload)

    def test_detail_preserves_bounded_proposal(self):
        register = OrderQuoteApprovalDecisionProposalRegister()
        register.register(proposal())
        detail = register.proposal_detail("quote-approval-proposal:0123456789abcdefghijklmn")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["reviewer_ref"], "staff:ruby")
        self.assertFalse(detail["effects"]["approval_decided"])
        self.assertFalse(detail["effects"]["payment_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
