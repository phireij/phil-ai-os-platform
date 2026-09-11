import copy
import unittest

from operations_hub.order_intake import OrderIntakeHandoffError, normalize_order_intake_handoff


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
                "addons": ["candles", "message-plaque"],
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


class OrderIntakeHandoffTests(unittest.TestCase):
    def test_normalizes_review_only_order_request_for_staff_review(self):
        normalized = normalize_order_intake_handoff(handoff())
        self.assertEqual(normalized["source"], "customer_experience_order_intake")
        self.assertEqual(normalized["kind"], "order_request")
        self.assertIs(normalized["review_required"], True)
        self.assertEqual(normalized["review_state"], "pending_staff_review")
        self.assertEqual(normalized["approval_state"], "not_evaluated")
        self.assertEqual(normalized["entities"]["fulfillment"]["method"], "pickup")
        self.assertEqual(
            normalized["entities"]["customization"]["reference_images"],
            [{"name": "reference.jpg", "type": "image/jpeg"}],
        )
        self.assertIs(normalized["authority"]["mutation_authorized"], False)
        self.assertIs(normalized["authority"]["order_creation_authorized"], False)
        self.assertIs(normalized["authority"]["payment_execution_authorized"], False)

    def test_normalization_is_deterministic_for_same_handoff(self):
        first = normalize_order_intake_handoff(handoff())
        second = normalize_order_intake_handoff(handoff())
        self.assertEqual(first["raw_handoff_fingerprint"], second["raw_handoff_fingerprint"])
        self.assertEqual(first["lifecycle_correlation_id"], second["lifecycle_correlation_id"])

    def test_rejects_authority_expansion(self):
        payload = handoff()
        payload["authority"]["orderCreationAuthorized"] = True
        with self.assertRaisesRegex(OrderIntakeHandoffError, "orderCreationAuthorized"):
            normalize_order_intake_handoff(payload)

    def test_rejects_file_content_or_unbounded_reference_shape(self):
        payload = handoff()
        payload["request"]["customization"]["referenceImages"][0]["bytes"] = "private-file-content"
        with self.assertRaisesRegex(OrderIntakeHandoffError, "forbidden file-content"):
            normalize_order_intake_handoff(payload)

    def test_rejects_inconsistent_fulfillment_fields(self):
        payload = handoff()
        payload["request"]["fulfillment"]["method"] = "ruby-car"
        with self.assertRaisesRegex(OrderIntakeHandoffError, "pickupTime must be empty"):
            normalize_order_intake_handoff(payload)

    def test_basic_cake_cannot_smuggle_custom_only_fields(self):
        payload = handoff()
        customization = payload["request"]["customization"]
        customization["cakeType"] = "basic"
        with self.assertRaisesRegex(OrderIntakeHandoffError, "basic cake"):
            normalize_order_intake_handoff(payload)

    def test_rejects_non_review_only_request(self):
        payload = copy.deepcopy(handoff())
        payload["request"]["state"] = "ready_to_order"
        with self.assertRaisesRegex(OrderIntakeHandoffError, "review_only"):
            normalize_order_intake_handoff(payload)


if __name__ == "__main__":
    unittest.main()
