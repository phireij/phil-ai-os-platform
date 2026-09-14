import copy
import unittest

from operations_hub.order_quote_preparation import (
    OrderQuotePreparationError,
    build_order_quote_preparation,
)
from operations_hub.order_review_decision import build_order_review_decision_proposal


def review_detail():
    return {
        "lifecycle_correlation_id": "order-request:0123456789abcdef01234567",
        "review_state": "pending_staff_review",
        "review_reason": "customer_order_request_requires_staff_confirmation",
        "entities": {
            "fulfillment": {
                "method": "pickup",
                "requested_date": "2026-09-14",
                "pickup_time": "15:30",
                "yamato_window": "none",
                "route_or_fee_confirmed": False,
                "fulfillment_confirmed": False,
            },
            "customization": {
                "cake_type": "custom",
                "custom_notes": "Soft pink flowers",
                "reference_images": [{"name": "reference.jpg", "type": "image/jpeg"}],
                "reference_image_count": 1,
                "photo_topper": True,
                "edible_topper": False,
                "addons": ["candles"],
                "icing_requested": True,
            },
        },
        "authority": {
            "staff_review_only": True,
            "mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "production_publish_authorized": False,
        },
    }


def accepted_proposal(review):
    return build_order_review_decision_proposal(
        review,
        "accept_for_quote_review",
        "staff:test",
        "Prepare a quote for staff review.",
    )


class OrderQuotePreparationTests(unittest.TestCase):
    def test_builds_deterministic_non_authorizing_quote_preparation(self):
        review = review_detail()
        proposal = accepted_proposal(review)
        first = build_order_quote_preparation(review, proposal)
        second = build_order_quote_preparation(review, proposal)

        self.assertEqual(first, second)
        self.assertEqual(first["state"], "prepared_for_quote_review")
        self.assertEqual(first["request_context"]["fulfillment"]["method"], "pickup")
        self.assertEqual(first["request_context"]["customization"]["reference_image_count"], 1)
        self.assertIsNone(first["pricing"]["quote_amount"])
        self.assertIsNone(first["pricing"]["shipping_amount"])
        self.assertIsNone(first["pricing"]["total_amount"])
        self.assertFalse(first["pricing"]["quote_calculated"])
        self.assertFalse(first["authority"]["quote_authorized"])
        self.assertFalse(first["authority"]["order_creation_authorized"])
        self.assertFalse(first["authority"]["payment_execution_authorized"])
        self.assertFalse(first["authority"]["mutation_authorized"])

    def test_source_mutation_does_not_change_built_reference_metadata(self):
        review = review_detail()
        proposal = accepted_proposal(review)
        packet = build_order_quote_preparation(review, proposal)
        fingerprint = packet["source_fingerprint"]

        review["entities"]["customization"]["reference_images"][0]["name"] = "mutated.jpg"

        self.assertEqual(
            packet["request_context"]["customization"]["reference_images"][0]["name"],
            "reference.jpg",
        )
        self.assertEqual(packet["source_fingerprint"], fingerprint)

    def test_rejects_revision_or_decline_proposals(self):
        review = review_detail()
        for decision in ("request_customer_revision", "decline_request"):
            proposal = build_order_review_decision_proposal(review, decision, "staff:test")
            with self.assertRaisesRegex(OrderQuotePreparationError, "accept_for_quote_review"):
                build_order_quote_preparation(review, proposal)

    def test_rejects_authority_expansion(self):
        review = review_detail()
        proposal = accepted_proposal(review)
        proposal["effects"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderQuotePreparationError, "quote_authorized"):
            build_order_quote_preparation(review, proposal)

    def test_rejects_mismatched_correlation(self):
        review = review_detail()
        proposal = accepted_proposal(review)
        proposal["lifecycle_correlation_id"] = "order-request:different"
        with self.assertRaisesRegex(OrderQuotePreparationError, "correlation"):
            build_order_quote_preparation(review, proposal)

    def test_rejects_stale_review_state(self):
        review = review_detail()
        proposal = accepted_proposal(review)
        stale = copy.deepcopy(review)
        stale["review_state"] = "reviewed"
        with self.assertRaisesRegex(OrderQuotePreparationError, "pending_staff_review"):
            build_order_quote_preparation(stale, proposal)


if __name__ == "__main__":
    unittest.main()
