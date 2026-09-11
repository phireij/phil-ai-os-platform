import unittest

from operations_hub.order_review import OrderReviewQueue


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
            "pricing": {"quoteCalculated": False, "shippingFeeCalculated": False, "totalCalculated": False},
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


class OrderReviewQueueTests(unittest.TestCase):
    def test_accepts_valid_handoff_into_read_only_staff_queue(self):
        queue = OrderReviewQueue()
        accepted = queue.ingest_handoff(handoff())
        self.assertIs(accepted["accepted"], True)
        self.assertIs(accepted["mutation_authorized"], False)
        model = queue.read_model()
        self.assertEqual(model["pending_review"], 1)
        self.assertEqual(model["items"][0]["fulfillment_method"], "pickup")
        self.assertEqual(model["items"][0]["reference_image_count"], 1)
        self.assertIs(model["items"][0]["has_custom_notes"], True)
        self.assertNotIn("custom_notes", model["items"][0])
        self.assertIs(model["mutation_authorized"], False)

    def test_duplicate_handoff_is_not_added_twice(self):
        queue = OrderReviewQueue()
        first = queue.ingest_handoff(handoff())
        second = queue.ingest_handoff(handoff())
        self.assertIs(first["accepted"], True)
        self.assertIs(second["duplicate"], True)
        model = queue.read_model()
        self.assertEqual(model["pending_review"], 1)
        self.assertEqual(model["duplicate_handoffs"], 1)

    def test_detail_keeps_bounded_review_data_and_no_authority(self):
        queue = OrderReviewQueue()
        accepted = queue.ingest_handoff(handoff())
        detail = queue.review_detail(accepted["lifecycle_correlation_id"])
        self.assertEqual(detail["entities"]["customization"]["custom_notes"], "Soft pink flowers")
        self.assertEqual(detail["entities"]["customization"]["reference_images"], [{"name": "reference.jpg", "type": "image/jpeg"}])
        self.assertIs(detail["authority"]["mutation_authorized"], False)
        self.assertIs(detail["authority"]["order_creation_authorized"], False)

    def test_invalid_authorizing_handoff_fails_before_queueing(self):
        queue = OrderReviewQueue()
        payload = handoff()
        payload["authority"]["paymentExecutionAuthorized"] = True
        with self.assertRaises(ValueError):
            queue.ingest_handoff(payload)
        self.assertEqual(queue.read_model()["pending_review"], 0)


if __name__ == "__main__":
    unittest.main()
