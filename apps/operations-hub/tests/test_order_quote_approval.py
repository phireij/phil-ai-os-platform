import copy
import unittest

from operations_hub.order_quote_approval import (
    OrderQuoteApprovalRequestError,
    build_order_quote_approval_request,
)


def draft():
    return {
        "schema": "rubys-order-quote-draft",
        "version": 1,
        "state": "draft_for_staff_review",
        "draft_id": "quote-draft:0123456789abcdefghijklmn",
        "lifecycle_correlation_id": "order-request:0123456789abcdefghijklmn",
        "source_preparation_id": "quote-prep:0123456789abcdefghijklmn",
        "source_fingerprint": "a" * 64,
        "prepared_by": "staff:ruby",
        "note": "Review before sharing",
        "request_context": {"fulfillment": {"method": "pickup"}, "customization": {"cake_type": "custom"}},
        "pricing": {
            "quote_amount": 5000,
            "shipping_amount": 800,
            "total_amount": 5800,
            "currency": "JPY",
            "quote_calculated": True,
            "shipping_fee_calculated": True,
            "total_calculated": True,
            "customer_accepted": False,
        },
        "authority": {
            "staff_review_only": True,
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


class OrderQuoteApprovalRequestTests(unittest.TestCase):
    def test_builds_non_authorizing_approval_request(self):
        request = build_order_quote_approval_request(
            draft(), requested_by="staff:ruby", reason="Ready for owner review"
        )
        self.assertEqual(request["state"], "approval_requested")
        self.assertTrue(request["approval"]["required"])
        self.assertIsNone(request["approval"]["decision"])
        self.assertEqual(request["pricing"]["total_amount"], 5800)
        self.assertFalse(request["pricing"]["customer_accepted"])
        self.assertTrue(request["authority"]["approval_request_only"])
        self.assertFalse(request["authority"]["quote_authorized"])
        self.assertFalse(request["authority"]["customer_notification_authorized"])
        self.assertFalse(request["authority"]["order_creation_authorized"])
        self.assertFalse(request["authority"]["payment_execution_authorized"])

    def test_is_deterministic_for_same_inputs(self):
        first = build_order_quote_approval_request(draft(), requested_by="staff:ruby", reason="Owner review")
        second = build_order_quote_approval_request(draft(), requested_by="staff:ruby", reason="Owner review")
        self.assertEqual(first["approval_request_id"], second["approval_request_id"])

    def test_rejects_authority_expansion(self):
        payload = copy.deepcopy(draft())
        payload["authority"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "quote_authorized"):
            build_order_quote_approval_request(payload, requested_by="staff:ruby")

    def test_rejects_customer_accepted_draft(self):
        payload = copy.deepcopy(draft())
        payload["pricing"]["customer_accepted"] = True
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "customer_accepted"):
            build_order_quote_approval_request(payload, requested_by="staff:ruby")

    def test_rejects_non_reconciling_or_non_jpy_pricing(self):
        payload = copy.deepcopy(draft())
        payload["pricing"]["total_amount"] = 6000
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "must reconcile"):
            build_order_quote_approval_request(payload, requested_by="staff:ruby")

        payload = copy.deepcopy(draft())
        payload["pricing"]["currency"] = "USD"
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "currency must remain JPY"):
            build_order_quote_approval_request(payload, requested_by="staff:ruby")

    def test_rejects_wrong_draft_state(self):
        payload = copy.deepcopy(draft())
        payload["state"] = "quote_authorized"
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "draft_for_staff_review"):
            build_order_quote_approval_request(payload, requested_by="staff:ruby")

    def test_bounds_request_metadata(self):
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "requested_by exceeds"):
            build_order_quote_approval_request(draft(), requested_by="x" * 121)
        with self.assertRaisesRegex(OrderQuoteApprovalRequestError, "reason exceeds"):
            build_order_quote_approval_request(draft(), requested_by="staff:ruby", reason="x" * 1001)


if __name__ == "__main__":
    unittest.main()
