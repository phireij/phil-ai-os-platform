import copy
import unittest

from operations_hub.order_quote_draft import OrderQuoteDraftError
from operations_hub.order_quote_register import OrderQuoteDraftRegister


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


class OrderQuoteDraftRegisterTests(unittest.TestCase):
    def test_registers_bounded_staff_quote_draft(self):
        register = OrderQuoteDraftRegister()
        result = register.register(draft())
        self.assertTrue(result["accepted"])
        self.assertFalse(result["mutation_authorized"])
        model = register.read_model()
        self.assertEqual(model["draft_count"], 1)
        self.assertEqual(model["items"][0]["total_amount"], 5800)
        self.assertEqual(model["items"][0]["currency"], "JPY")
        self.assertTrue(model["items"][0]["has_note"])
        self.assertNotIn("prepared_by", model["items"][0])
        self.assertNotIn("note", model["items"][0])
        self.assertFalse(model["quote_authorized"])
        self.assertFalse(model["order_creation_authorized"])

    def test_deduplicates_same_draft_id(self):
        register = OrderQuoteDraftRegister()
        register.register(draft())
        duplicate = register.register(draft())
        self.assertFalse(duplicate["accepted"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(register.read_model()["duplicate_drafts"], 1)

    def test_rejects_conflicting_content_for_existing_draft_id(self):
        register = OrderQuoteDraftRegister()
        register.register(draft())
        conflicting = copy.deepcopy(draft())
        conflicting["note"] = "Changed note under same ID"
        with self.assertRaisesRegex(OrderQuoteDraftError, "conflicts with existing draft content"):
            register.register(conflicting)
        self.assertEqual(register.read_model()["duplicate_drafts"], 0)

    def test_register_and_detail_isolate_nested_draft_state(self):
        register = OrderQuoteDraftRegister()
        payload = draft()
        register.register(payload)
        payload["request_context"]["customization"]["custom_notes"] = "caller mutated input"
        payload["pricing"]["quote_amount"] = 9999
        payload["authority"]["quote_authorized"] = True

        detail = register.draft_detail("quote-draft:0123456789abcdefghijklmn")
        self.assertEqual(detail["request_context"]["customization"]["custom_notes"], "Soft pink flowers")
        self.assertEqual(detail["pricing"]["quote_amount"], 5000)
        self.assertFalse(detail["authority"]["quote_authorized"])

        detail["request_context"]["customization"]["custom_notes"] = "caller mutated detail"
        detail["pricing"]["quote_amount"] = 8888
        detail["authority"]["quote_authorized"] = True
        reread = register.draft_detail("quote-draft:0123456789abcdefghijklmn")
        self.assertEqual(reread["request_context"]["customization"]["custom_notes"], "Soft pink flowers")
        self.assertEqual(reread["pricing"]["quote_amount"], 5000)
        self.assertFalse(reread["authority"]["quote_authorized"])

    def test_rejects_authority_expansion(self):
        payload = copy.deepcopy(draft())
        payload["authority"]["quote_authorized"] = True
        with self.assertRaisesRegex(OrderQuoteDraftError, "quote_authorized"):
            OrderQuoteDraftRegister().register(payload)

    def test_rejects_customer_acceptance(self):
        payload = copy.deepcopy(draft())
        payload["pricing"]["customer_accepted"] = True
        with self.assertRaisesRegex(OrderQuoteDraftError, "customer_accepted"):
            OrderQuoteDraftRegister().register(payload)

    def test_rejects_non_reconciling_total(self):
        payload = copy.deepcopy(draft())
        payload["pricing"]["total_amount"] = 6000
        with self.assertRaisesRegex(OrderQuoteDraftError, "must reconcile"):
            OrderQuoteDraftRegister().register(payload)

    def test_rejects_non_jpy_or_invalid_amounts(self):
        payload = copy.deepcopy(draft())
        payload["pricing"]["currency"] = "USD"
        with self.assertRaisesRegex(OrderQuoteDraftError, "currency must remain JPY"):
            OrderQuoteDraftRegister().register(payload)

        payload = copy.deepcopy(draft())
        payload["pricing"]["quote_amount"] = -1
        with self.assertRaisesRegex(OrderQuoteDraftError, "non-negative integer"):
            OrderQuoteDraftRegister().register(payload)

    def test_detail_keeps_bounded_context_without_granting_authority(self):
        register = OrderQuoteDraftRegister()
        register.register(draft())
        detail = register.draft_detail("quote-draft:0123456789abcdefghijklmn")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["request_context"]["customization"]["reference_images"][0]["name"], "reference.jpg")
        self.assertFalse(detail["authority"]["quote_authorized"])
        self.assertFalse(detail["authority"]["payment_execution_authorized"])


if __name__ == "__main__":
    unittest.main()
