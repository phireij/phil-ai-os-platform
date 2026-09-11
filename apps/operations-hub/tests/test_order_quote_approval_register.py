import copy
import unittest

from operations_hub.order_quote_approval import OrderQuoteApprovalRequestError
from operations_hub.order_quote_approval_register import OrderQuoteApprovalRequestRegister


def approval_request():
    return {
        "schema": "rubys-order-quote-approval-request",
        "version": 1,
        "state": "approval_requested",
        "approval_request_id": "quote-approval:0123456789abcdefghijklmn",
        "lifecycle_correlation_id": "order-request:0123456789abcdefghijklmn",
        "source_draft_id": "quote-draft:0123456789abcdefghijklmn",
        "requested_by": "staff:ruby",
        "reason": "Owner review before customer notification",
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


class OrderQuoteApprovalRequestRegisterTests(unittest.TestCase):
    def test_registers_pending_non_authorizing_approval_request(self):
        register = OrderQuoteApprovalRequestRegister()
        result = register.register(approval_request())
        self.assertTrue(result["accepted"])
        self.assertFalse(result["mutation_authorized"])
        model = register.read_model()
        self.assertEqual(model["pending_approval_count"], 1)
        self.assertEqual(model["items"][0]["total_amount"], 5800)
        self.assertIsNone(model["items"][0]["decision"])
        self.assertTrue(model["items"][0]["has_reason"])
        self.assertNotIn("requested_by", model["items"][0])
        self.assertNotIn("reason", model["items"][0])
        self.assertFalse(model["quote_authorized"])
        self.assertFalse(model["customer_notification_authorized"])

    def test_deduplicates_same_approval_request_id(self):
        register = OrderQuoteApprovalRequestRegister()
        register.register(approval_request())
        duplicate = register.register(approval_request())
        self.assertFalse(duplicate["accepted"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(register.read_model()["duplicate_requests"], 1)

    def test_rejects_predecided_approval(self):
        payload = copy.deepcopy(approval_request())
        payload["approval"]["decision"] = "approved"
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "decision must remain unset"):
            OrderQuoteApprovalRequestRegister().register(payload)

    def test_rejects_approval_metadata_before_decision(self):
        payload = copy.deepcopy(approval_request())
        payload["approval"]["approved_by"] = "owner:phil"
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "metadata must remain unset"):
            OrderQuoteApprovalRequestRegister().register(payload)

    def test_rejects_authority_expansion(self):
        payload = copy.deepcopy(approval_request())
        payload["authority"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "quote_authorized"):
            OrderQuoteApprovalRequestRegister().register(payload)

    def test_rejects_customer_acceptance_or_bad_total(self):
        payload = copy.deepcopy(approval_request())
        payload["pricing"]["customer_accepted"] = True
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "customer_accepted"):
            OrderQuoteApprovalRequestRegister().register(payload)

        payload = copy.deepcopy(approval_request())
        payload["pricing"]["total_amount"] = 6000
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "must reconcile"):
            OrderQuoteApprovalRequestRegister().register(payload)

    def test_detail_retains_bounded_review_metadata_without_authority(self):
        register = OrderQuoteApprovalRequestRegister()
        register.register(approval_request())
        detail = register.request_detail("quote-approval:0123456789abcdefghijklmn")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["requested_by"], "staff:ruby")
        self.assertEqual(detail["pricing"]["currency"], "JPY")
        self.assertIsNone(detail["approval"]["decision"])
        self.assertFalse(detail["authority"]["quote_authorized"])
        self.assertFalse(detail["authority"]["payment_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
