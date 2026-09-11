import unittest

from operations_hub.order_review import OrderReviewQueue
from operations_hub.order_review_decision import build_order_review_decision_proposal
from operations_hub.order_review_register import OrderReviewProposalRegister
from operations_hub.order_review_workspace import OrderReviewWorkspaceError, build_order_review_workspace


def handoff():
    return {
        "schema": "rubys-order-intake-review-handoff",
        "version": 1,
        "state": "prepared_for_staff_review",
        "request": {
            "schema": "rubys-order-intake-request",
            "version": 1,
            "state": "review_only",
            "fulfillment": {
                "method": "pickup",
                "requestedDate": "2026-09-14",
                "pickupTime": "15:30",
                "yamatoWindow": "none",
                "routeOrFeeConfirmed": False,
                "fulfillmentConfirmed": False,
            },
            "customization": {
                "cakeType": "custom",
                "customNotes": "Soft pink flowers",
                "referenceImages": [{"name": "reference.jpg", "type": "image/jpeg"}],
                "referenceImageCount": 1,
                "photoTopper": True,
                "edibleTopper": False,
                "addons": ["candles"],
                "icingRequested": True,
            },
            "pricing": {
                "quoteCalculated": False,
                "shippingFeeCalculated": False,
                "totalCalculated": False,
            },
            "authority": {
                "fileContentPersisted": False,
                "fileUploadPerformed": False,
                "networkCallPerformed": False,
                "wooCommerceMutationAuthorized": False,
                "orderCreationAuthorized": False,
                "paymentExecutionAuthorized": False,
                "smsSendAuthorized": False,
                "inventoryMutationAuthorized": False,
                "productionPublishAuthorized": False,
            },
        },
        "authority": {
            "staffReviewOnly": True,
            "fileContentPersisted": False,
            "fileUploadPerformed": False,
            "networkCallPerformed": False,
            "wooCommerceMutationAuthorized": False,
            "orderCreationAuthorized": False,
            "paymentExecutionAuthorized": False,
            "smsSendAuthorized": False,
            "inventoryMutationAuthorized": False,
            "productionPublishAuthorized": False,
        },
    }


class OrderReviewWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.queue = OrderReviewQueue()
        self.register = OrderReviewProposalRegister()
        accepted = self.queue.ingest_handoff(handoff())
        self.correlation_id = accepted["lifecycle_correlation_id"]

    def test_workspace_marks_pending_item_without_proposal(self):
        model = build_order_review_workspace(self.queue, self.register)
        self.assertEqual(model["pending_review"], 1)
        self.assertEqual(model["proposal_count"], 0)
        self.assertEqual(model["pending_without_proposal"], 1)
        self.assertFalse(model["items"][0]["has_review_proposal"])
        self.assertFalse(model["mutation_authorized"])
        self.assertFalse(model["order_creation_authorized"])
        self.assertFalse(model["payment_execution_authorized"])

    def test_workspace_correlates_registered_proposal_without_exposing_note(self):
        detail = self.queue.review_detail(self.correlation_id)
        proposal = build_order_review_decision_proposal(
            detail,
            "accept_for_quote_review",
            "staff:ruby",
            "Internal review note",
        )
        self.register.register(proposal, detail)
        model = build_order_review_workspace(self.queue, self.register)
        item = model["items"][0]
        self.assertTrue(item["has_review_proposal"])
        self.assertEqual(item["proposal_count"], 1)
        self.assertEqual(item["proposal_decisions"], ["accept_for_quote_review"])
        self.assertEqual(model["pending_without_proposal"], 0)
        self.assertNotIn("note", item)
        self.assertNotIn("reviewer_ref", item)

    def test_workspace_is_deterministic(self):
        first = build_order_review_workspace(self.queue, self.register)
        second = build_order_review_workspace(self.queue, self.register)
        self.assertEqual(first, second)

    def test_workspace_rejects_orphan_proposal(self):
        detail = self.queue.review_detail(self.correlation_id)
        proposal = build_order_review_decision_proposal(
            detail,
            "request_customer_revision",
            "staff:ruby",
        )
        self.register.register(proposal, detail)
        empty_queue = OrderReviewQueue()
        with self.assertRaisesRegex(OrderReviewWorkspaceError, "absent from the review queue"):
            build_order_review_workspace(empty_queue, self.register)

    def test_workspace_rejects_wrong_component_types(self):
        with self.assertRaisesRegex(OrderReviewWorkspaceError, "OrderReviewQueue"):
            build_order_review_workspace(object(), self.register)
        with self.assertRaisesRegex(OrderReviewWorkspaceError, "OrderReviewProposalRegister"):
            build_order_review_workspace(self.queue, object())


if __name__ == "__main__":
    unittest.main()
