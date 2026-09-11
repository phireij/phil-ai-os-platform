import copy

import pytest

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


def test_normalizes_review_only_order_request_for_staff_review():
    normalized = normalize_order_intake_handoff(handoff())
    assert normalized["source"] == "customer_experience_order_intake"
    assert normalized["kind"] == "order_request"
    assert normalized["review_required"] is True
    assert normalized["review_state"] == "pending_staff_review"
    assert normalized["approval_state"] == "not_evaluated"
    assert normalized["entities"]["fulfillment"]["method"] == "pickup"
    assert normalized["entities"]["customization"]["reference_images"] == [
        {"name": "reference.jpg", "type": "image/jpeg"}
    ]
    assert normalized["authority"]["mutation_authorized"] is False
    assert normalized["authority"]["order_creation_authorized"] is False
    assert normalized["authority"]["payment_execution_authorized"] is False


def test_normalization_is_deterministic_for_same_handoff():
    first = normalize_order_intake_handoff(handoff())
    second = normalize_order_intake_handoff(handoff())
    assert first["raw_handoff_fingerprint"] == second["raw_handoff_fingerprint"]
    assert first["lifecycle_correlation_id"] == second["lifecycle_correlation_id"]


def test_rejects_authority_expansion():
    payload = handoff()
    payload["authority"]["orderCreationAuthorized"] = True
    with pytest.raises(OrderIntakeHandoffError, match="orderCreationAuthorized"):
        normalize_order_intake_handoff(payload)


def test_rejects_file_content_or_unbounded_reference_shape():
    payload = handoff()
    payload["request"]["customization"]["referenceImages"][0]["bytes"] = "private-file-content"
    with pytest.raises(OrderIntakeHandoffError, match="forbidden file-content"):
        normalize_order_intake_handoff(payload)


def test_rejects_inconsistent_fulfillment_fields():
    payload = handoff()
    payload["request"]["fulfillment"]["method"] = "ruby-car"
    with pytest.raises(OrderIntakeHandoffError, match="pickupTime must be empty"):
        normalize_order_intake_handoff(payload)


def test_basic_cake_cannot_smuggle_custom_only_fields():
    payload = handoff()
    customization = payload["request"]["customization"]
    customization["cakeType"] = "basic"
    with pytest.raises(OrderIntakeHandoffError, match="basic cake"):
        normalize_order_intake_handoff(payload)


def test_rejects_non_review_only_request():
    payload = copy.deepcopy(handoff())
    payload["request"]["state"] = "ready_to_order"
    with pytest.raises(OrderIntakeHandoffError, match="review_only"):
        normalize_order_intake_handoff(payload)
