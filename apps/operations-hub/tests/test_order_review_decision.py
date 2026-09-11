import unittest

from operations_hub.order_review_decision import (
    OrderReviewDecisionError,
    build_order_review_decision_proposal,
)


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


class OrderReviewDecisionTests(unittest.TestCase):
    def test_builds_deterministic_non_authorizing_proposal(self):
        first = build_order_review_decision_proposal(
            review_detail(),
            "accept_for_quote_review",
            "staff:operator",
            "Review recipe and final quote.",
        )
        second = build_order_review_decision_proposal(
            review_detail(),
            "accept_for_quote_review",
            "staff:operator",
            "Review recipe and final quote.",
        )
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "proposal_only")
        self.assertEqual(first["mutation_authorized"], False)
        self.assertFalse(any(first["effects"].values()))

    def test_accept_for_quote_review_does_not_authorize_quote_or_order(self):
        proposal = build_order_review_decision_proposal(
            review_detail(), "accept_for_quote_review", "staff:operator"
        )
        self.assertFalse(proposal["effects"]["quote_authorized"])
        self.assertFalse(proposal["effects"]["fulfillment_confirmed"])
        self.assertFalse(proposal["effects"]["order_creation_authorized"])
        self.assertFalse(proposal["effects"]["payment_execution_authorized"])

    def test_requires_pending_review_state(self):
        detail = review_detail()
        detail["review_state"] = "reviewed"
        with self.assertRaisesRegex(OrderReviewDecisionError, "pending_staff_review"):
            build_order_review_decision_proposal(detail, "decline_request", "staff:operator")

    def test_rejects_authority_expansion(self):
        detail = review_detail()
        detail["authority"]["mutation_authorized"] = True
        with self.assertRaisesRegex(OrderReviewDecisionError, "non-authorizing"):
            build_order_review_decision_proposal(detail, "request_customer_revision", "staff:operator")

    def test_rejects_unknown_decision(self):
        with self.assertRaisesRegex(OrderReviewDecisionError, "unsupported review decision"):
            build_order_review_decision_proposal(review_detail(), "create_order", "staff:operator")

    def test_bounds_reviewer_and_note(self):
        with self.assertRaisesRegex(OrderReviewDecisionError, "reviewer_ref"):
            build_order_review_decision_proposal(review_detail(), "decline_request", "")
        with self.assertRaisesRegex(OrderReviewDecisionError, "note exceeds"):
            build_order_review_decision_proposal(
                review_detail(), "decline_request", "staff:operator", "x" * 1001
            )


if __name__ == "__main__":
    unittest.main()
