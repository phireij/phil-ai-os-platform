import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub import (  # noqa: E402
    OperationsQueue,
    OrderQuoteApprovalDecisionProposalRegister,
    OrderQuoteApprovalRequestRegister,
    OrderQuoteOwnerDecisionPacketRegister,
    OrderReviewQueue,
    build_operations_dashboard,
    build_order_quote_approval_decision_proposal,
    build_order_quote_approval_request,
    build_order_quote_draft,
    build_order_quote_owner_decision_packet,
    build_order_quote_preparation,
    build_order_review_decision_proposal,
    normalize_channel_event,
)


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


def empty_sources():
    return (
        OperationsQueue(),
        OrderReviewQueue(),
        OrderQuoteApprovalRequestRegister(),
        OrderQuoteApprovalDecisionProposalRegister(),
        OrderQuoteOwnerDecisionPacketRegister(),
    )


class OperationsDashboardTests(unittest.TestCase):
    def test_empty_dashboard_is_read_only_and_non_authorizing(self):
        dashboard = build_operations_dashboard(*empty_sources())
        self.assertEqual("read_only", dashboard["status"])
        self.assertEqual(0, dashboard["channels"]["total_events"])
        self.assertEqual(0, dashboard["orders"]["pending_staff_review"])
        self.assertEqual(0, dashboard["quotes"]["pending_approval"])
        self.assertEqual(0, dashboard["owner_review"]["pending_packets"])
        self.assertFalse(dashboard["owner_review"]["owner_decision_pending"])
        for key, value in dashboard.items():
            if key.endswith("authorized"):
                self.assertIs(value, False, key)

    def test_dashboard_aggregates_channel_order_quote_and_owner_workload(self):
        channels, orders, approvals, recommendations, owner_packets = empty_sources()

        for source in ("facebook", "instagram", "telegram", "whatsapp", "google_business"):
            payload = json.loads((ROOT / "fixtures" / f"{source}.json").read_text(encoding="utf-8"))
            channels.ingest(normalize_channel_event(payload))

        order_handoff = handoff()
        accepted = orders.ingest_handoff(order_handoff)
        self.assertTrue(accepted["accepted"])
        review = orders.review_detail(accepted["lifecycle_correlation_id"])
        self.assertIsNotNone(review)

        review_proposal = build_order_review_decision_proposal(
            review,
            "accept_for_quote_review",
            "staff:dashboard-test",
        )
        preparation = build_order_quote_preparation(review, review_proposal)
        draft = build_order_quote_draft(
            preparation,
            quote_amount=5000,
            shipping_amount=0,
            total_amount=5000,
            prepared_by="staff:dashboard-test",
        )
        approval_request = build_order_quote_approval_request(
            draft,
            requested_by="staff:dashboard-test",
        )
        self.assertTrue(approvals.register(approval_request)["accepted"])

        recommendation = build_order_quote_approval_decision_proposal(
            approval_request,
            recommendation="recommend_quote_approval",
            reviewer_ref="staff:dashboard-test",
        )
        self.assertTrue(recommendations.register(recommendation)["accepted"])
        packet = build_order_quote_owner_decision_packet(
            approvals,
            recommendations,
            approval_request_id=approval_request["approval_request_id"],
        )
        self.assertTrue(owner_packets.register(packet)["accepted"])

        dashboard = build_operations_dashboard(
            channels,
            orders,
            approvals,
            recommendations,
            owner_packets,
        )
        self.assertEqual(5, dashboard["channels"]["total_events"])
        self.assertEqual(2, dashboard["channels"]["review_required"])
        self.assertEqual(1, dashboard["orders"]["pending_staff_review"])
        self.assertEqual(1, dashboard["quotes"]["pending_approval"])
        self.assertEqual(1, dashboard["quotes"]["recommendation_proposals"])
        self.assertEqual(1, dashboard["owner_review"]["pending_packets"])
        self.assertTrue(dashboard["owner_review"]["owner_decision_pending"])

        serialized = json.dumps(dashboard, ensure_ascii=False)
        self.assertNotIn("Soft pink flowers", serialized)
        self.assertNotIn("reference.jpg", serialized)
        self.assertNotIn("entities", serialized)

    def test_dashboard_does_not_expose_item_payloads(self):
        channels, orders, approvals, recommendations, owner_packets = empty_sources()
        payload = json.loads((ROOT / "fixtures" / "facebook.json").read_text(encoding="utf-8"))
        channels.ingest(normalize_channel_event(payload))
        dashboard = build_operations_dashboard(
            channels,
            orders,
            approvals,
            recommendations,
            owner_packets,
        )
        self.assertNotIn("items", dashboard["channels"])
        self.assertFalse(dashboard["privacy"]["raw_customer_text_exposed"])
        self.assertFalse(dashboard["privacy"]["custom_notes_exposed"])
        self.assertFalse(dashboard["privacy"]["reference_image_names_exposed"])


if __name__ == "__main__":
    unittest.main()
