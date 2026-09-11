import copy
import unittest

from operations_hub.order_quote_draft import OrderQuoteDraftError, build_order_quote_draft


def preparation():
    return {
        "schema": "rubys-order-quote-preparation",
        "version": 1,
        "state": "prepared_for_quote_review",
        "preparation_id": "quote-prep:0123456789abcdefghijklmn",
        "lifecycle_correlation_id": "order-request:0123456789abcdefghijklmn",
        "source_proposal_id": "order-review:0123456789abcdefghijklmn",
        "source_fingerprint": "a" * 64,
        "request_context": {
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
        "pricing": {
            "quote_amount": None,
            "shipping_amount": None,
            "total_amount": None,
            "currency": None,
            "quote_calculated": False,
            "shipping_fee_calculated": False,
            "total_calculated": False,
        },
        "authority": {
            "quote_review_only": True,
            "quote_authorized": False,
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


class OrderQuoteDraftTests(unittest.TestCase):
    def test_builds_staff_review_only_jpy_quote_draft(self):
        draft = build_order_quote_draft(
            preparation(),
            quote_amount=5000,
            shipping_amount=0,
            total_amount=5000,
            prepared_by="staff:ruby",
            note="Review before sharing with customer",
        )
        self.assertEqual(draft["state"], "draft_for_staff_review")
        self.assertEqual(draft["pricing"]["currency"], "JPY")
        self.assertEqual(draft["pricing"]["total_amount"], 5000)
        self.assertTrue(draft["pricing"]["quote_calculated"])
        self.assertFalse(draft["pricing"]["customer_accepted"])
        self.assertFalse(draft["authority"]["quote_authorized"])
        self.assertFalse(draft["authority"]["customer_notification_authorized"])
        self.assertFalse(draft["authority"]["order_creation_authorized"])
        self.assertFalse(draft["authority"]["payment_execution_authorized"])

    def test_is_deterministic_for_same_inputs(self):
        first = build_order_quote_draft(
            preparation(), quote_amount=5000, shipping_amount=800, total_amount=5800, prepared_by="staff:ruby"
        )
        second = build_order_quote_draft(
            preparation(), quote_amount=5000, shipping_amount=800, total_amount=5800, prepared_by="staff:ruby"
        )
        self.assertEqual(first["draft_id"], second["draft_id"])

    def test_rejects_total_that_does_not_reconcile(self):
        with self.assertRaisesRegex(OrderQuoteDraftError, "total_amount must equal"):
            build_order_quote_draft(
                preparation(), quote_amount=5000, shipping_amount=800, total_amount=6000, prepared_by="staff:ruby"
            )

    def test_rejects_non_integer_or_negative_yen_amounts(self):
        with self.assertRaisesRegex(OrderQuoteDraftError, "integer JPY"):
            build_order_quote_draft(
                preparation(), quote_amount=5000.5, shipping_amount=0, total_amount=5000, prepared_by="staff:ruby"
            )
        with self.assertRaisesRegex(OrderQuoteDraftError, "must not be negative"):
            build_order_quote_draft(
                preparation(), quote_amount=5000, shipping_amount=-1, total_amount=4999, prepared_by="staff:ruby"
            )

    def test_rejects_preparation_authority_expansion(self):
        payload = copy.deepcopy(preparation())
        payload["authority"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderQuoteDraftError, "quote_authorized"):
            build_order_quote_draft(
                payload, quote_amount=5000, shipping_amount=0, total_amount=5000, prepared_by="staff:ruby"
            )

    def test_rejects_stale_or_wrong_preparation_state(self):
        payload = copy.deepcopy(preparation())
        payload["state"] = "quote_authorized"
        with self.assertRaisesRegex(OrderQuoteDraftError, "prepared_for_quote_review"):
            build_order_quote_draft(
                payload, quote_amount=5000, shipping_amount=0, total_amount=5000, prepared_by="staff:ruby"
            )

    def test_bounds_staff_metadata(self):
        with self.assertRaisesRegex(OrderQuoteDraftError, "prepared_by exceeds"):
            build_order_quote_draft(
                preparation(), quote_amount=5000, shipping_amount=0, total_amount=5000, prepared_by="x" * 121
            )
        with self.assertRaisesRegex(OrderQuoteDraftError, "note exceeds"):
            build_order_quote_draft(
                preparation(), quote_amount=5000, shipping_amount=0, total_amount=5000, prepared_by="staff:ruby", note="x" * 1001
            )


if __name__ == "__main__":
    unittest.main()
