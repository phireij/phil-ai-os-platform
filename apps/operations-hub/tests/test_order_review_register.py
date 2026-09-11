import copy
import unittest

from operations_hub.order_review_decision import (
    OrderReviewDecisionError,
    build_order_review_decision_proposal,
)
from operations_hub.order_review_register import OrderReviewProposalRegister


def review_detail():
    return {
        "lifecycle_correlation_id": "order-request:abc123",
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


class OrderReviewProposalRegisterTests(unittest.TestCase):
    def test_registers_valid_proposal_without_authority(self):
        detail = review_detail()
        proposal = build_order_review_decision_proposal(
            detail,
            "accept_for_quote_review",
            "staff:ruby",
            "Proceed to manual quote review.",
        )
        register = OrderReviewProposalRegister()
        result = register.register(proposal, detail)
        self.assertTrue(result["accepted"])
        self.assertFalse(result["duplicate"])
        self.assertFalse(result["mutation_authorized"])
        model = register.read_model()
        self.assertEqual(model["proposal_count"], 1)
        self.assertTrue(model["items"][0]["has_note"])
        self.assertNotIn("note", model["items"][0])

    def test_duplicate_proposal_is_deduplicated(self):
        detail = review_detail()
        proposal = build_order_review_decision_proposal(
            detail, "request_customer_revision", "staff:ruby", "Please clarify the design."
        )
        register = OrderReviewProposalRegister()
        first = register.register(proposal, detail)
        second = register.register(proposal, detail)
        self.assertTrue(first["accepted"])
        self.assertFalse(second["accepted"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(register.read_model()["duplicate_proposals"], 1)

    def test_rejects_source_fingerprint_mismatch(self):
        detail = review_detail()
        proposal = build_order_review_decision_proposal(
            detail, "decline_request", "staff:ruby", "Unable to fulfill."
        )
        changed = copy.deepcopy(detail)
        changed["entities"]["fulfillment"]["requested_date"] = "2026-09-15"
        with self.assertRaisesRegex(OrderReviewDecisionError, "fingerprint mismatch"):
            OrderReviewProposalRegister().register(proposal, changed)

    def test_rejects_effect_authority_expansion(self):
        detail = review_detail()
        proposal = build_order_review_decision_proposal(
            detail, "accept_for_quote_review", "staff:ruby"
        )
        proposal["effects"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderReviewDecisionError, "quote_authorized"):
            OrderReviewProposalRegister().register(proposal, detail)

    def test_rejects_stale_source_review(self):
        detail = review_detail()
        proposal = build_order_review_decision_proposal(
            detail, "accept_for_quote_review", "staff:ruby"
        )
        detail["review_state"] = "resolved"
        with self.assertRaisesRegex(OrderReviewDecisionError, "pending_staff_review"):
            OrderReviewProposalRegister().register(proposal, detail)

    def test_detail_remains_proposal_only(self):
        detail = review_detail()
        proposal = build_order_review_decision_proposal(
            detail, "request_customer_revision", "staff:ruby", "Need another reference image."
        )
        register = OrderReviewProposalRegister()
        register.register(proposal, detail)
        stored = register.proposal_detail(proposal["proposal_id"])
        self.assertEqual(stored["state"], "proposal_only")
        self.assertFalse(stored["mutation_authorized"])
        self.assertTrue(all(value is False for value in stored["effects"].values()))


if __name__ == "__main__":
    unittest.main()
