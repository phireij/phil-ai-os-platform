import copy
import unittest

from operations_hub.order_quote_approval import build_order_quote_approval_request
from operations_hub.order_quote_approval_register import OrderQuoteApprovalRequestRegister
from operations_hub.order_quote_approval_workspace import (
    OrderQuoteApprovalWorkspaceError,
    build_order_quote_approval_workspace,
)
from operations_hub.order_quote_draft import build_order_quote_draft
from operations_hub.order_quote_preparation import build_order_quote_preparation
from operations_hub.order_quote_register import OrderQuoteDraftRegister


def review_detail():
    return {
        "lifecycle_correlation_id": "order-request:0123456789abcdefghijklmn",
        "review_state": "pending_staff_review",
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
        "authority": {"mutation_authorized": False},
    }


def proposal_detail():
    return {
        "proposal_id": "order-review:0123456789abcdefghijklmn",
        "lifecycle_correlation_id": "order-request:0123456789abcdefghijklmn",
        "state": "proposal_only",
        "decision": "accept_for_quote_review",
        "effects": {
            "quote_authorized": False,
            "fulfillment_confirmed": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "woo_commerce_mutation_authorized": False,
            "production_publish_authorized": False,
        },
        "mutation_authorized": False,
    }


def draft():
    preparation = build_order_quote_preparation(review_detail(), proposal_detail())
    return build_order_quote_draft(
        preparation,
        quote_amount=5000,
        shipping_amount=800,
        total_amount=5800,
        prepared_by="staff:ruby",
        note="Review before sharing",
    )


class OrderQuoteApprovalWorkspaceTests(unittest.TestCase):
    def test_marks_draft_as_awaiting_approval_request(self):
        drafts = OrderQuoteDraftRegister()
        approvals = OrderQuoteApprovalRequestRegister()
        drafts.register(draft())
        workspace = build_order_quote_approval_workspace(drafts, approvals)
        self.assertEqual(workspace["draft_count"], 1)
        self.assertEqual(workspace["pending_approval_count"], 0)
        self.assertEqual(workspace["awaiting_approval_request_count"], 1)
        self.assertEqual(workspace["items"][0]["approval_status"], "approval_not_requested")
        self.assertIsNone(workspace["items"][0]["decision"])
        self.assertFalse(workspace["quote_authorized"])
        self.assertFalse(workspace["customer_notification_authorized"])

    def test_correlates_pending_approval_request_without_authorizing_quote(self):
        drafts = OrderQuoteDraftRegister()
        approvals = OrderQuoteApprovalRequestRegister()
        source_draft = draft()
        drafts.register(source_draft)
        request = build_order_quote_approval_request(
            source_draft,
            requested_by="staff:ruby",
            reason="Owner review required",
        )
        approvals.register(request)
        workspace = build_order_quote_approval_workspace(drafts, approvals)
        row = workspace["items"][0]
        self.assertEqual(row["approval_status"], "approval_requested")
        self.assertEqual(row["approval_request_count"], 1)
        self.assertEqual(row["approval_request_ids"], [request["approval_request_id"]])
        self.assertEqual(row["total_amount"], 5800)
        self.assertIsNone(row["decision"])
        self.assertFalse(row["quote_authorized"])
        self.assertFalse(row["customer_notification_authorized"])
        self.assertNotIn("requested_by", row)
        self.assertNotIn("reason", row)

    def test_output_is_deterministic(self):
        drafts = OrderQuoteDraftRegister()
        approvals = OrderQuoteApprovalRequestRegister()
        source_draft = draft()
        drafts.register(source_draft)
        approvals.register(
            build_order_quote_approval_request(source_draft, requested_by="staff:ruby")
        )
        first = build_order_quote_approval_workspace(drafts, approvals)
        second = build_order_quote_approval_workspace(drafts, approvals)
        self.assertEqual(first, second)

    def test_rejects_orphan_approval_request(self):
        drafts = OrderQuoteDraftRegister()
        approvals = OrderQuoteApprovalRequestRegister()
        source_draft = draft()
        approvals.register(
            build_order_quote_approval_request(source_draft, requested_by="staff:ruby")
        )
        with self.assertRaisesRegex(OrderQuoteApprovalWorkspaceError, "source drafts are absent"):
            build_order_quote_approval_workspace(drafts, approvals)

    def test_rejects_mismatched_pricing(self):
        drafts = OrderQuoteDraftRegister()
        approvals = OrderQuoteApprovalRequestRegister()
        source_draft = draft()
        drafts.register(source_draft)
        request = build_order_quote_approval_request(source_draft, requested_by="staff:ruby")
        approvals.register(request)
        approvals._requests[request["approval_request_id"]]["pricing"] = copy.deepcopy(request["pricing"])
        approvals._requests[request["approval_request_id"]]["pricing"]["total_amount"] = 5900
        with self.assertRaisesRegex(OrderQuoteApprovalWorkspaceError, "total_amount does not match"):
            build_order_quote_approval_workspace(drafts, approvals)

    def test_rejects_wrong_component_types(self):
        with self.assertRaisesRegex(OrderQuoteApprovalWorkspaceError, "draft_register"):
            build_order_quote_approval_workspace({}, OrderQuoteApprovalRequestRegister())
        with self.assertRaisesRegex(OrderQuoteApprovalWorkspaceError, "approval_register"):
            build_order_quote_approval_workspace(OrderQuoteDraftRegister(), {})


if __name__ == "__main__":
    unittest.main()
