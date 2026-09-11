from __future__ import annotations

import hashlib
import json
from typing import Any

ORDER_INTAKE_HANDOFF_SCHEMA = "rubys-order-intake-review-handoff"
ORDER_INTAKE_HANDOFF_VERSION = 1
ORDER_INTAKE_REQUEST_SCHEMA = "rubys-order-intake-request"
ORDER_INTAKE_REQUEST_VERSION = 1

SUPPORTED_FULFILLMENT = ("yamato", "ruby-car", "pickup")
SUPPORTED_CAKE_TYPES = ("basic", "custom")
SUPPORTED_YAMATO_WINDOWS = ("none", "08-12", "14-16", "16-18", "18-20", "19-21")
SUPPORTED_ADDONS = ("candles", "number-candle", "message-plaque")


class OrderIntakeHandoffError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise OrderIntakeHandoffError(f"{field} must be a string")
    if len(value) > max_length:
        raise OrderIntakeHandoffError(f"{field} exceeds {max_length} characters")
    return value


def _flag(value: Any, field: str, expected: bool) -> None:
    if value is not expected:
        raise OrderIntakeHandoffError(f"{field} must be {str(expected).lower()}")


def _validate_authority(authority: Any) -> None:
    if not isinstance(authority, dict):
        raise OrderIntakeHandoffError("authority must be an object")
    _flag(authority.get("staffReviewOnly"), "authority.staffReviewOnly", True)
    for field in (
        "fileContentPersisted",
        "fileUploadPerformed",
        "networkCallPerformed",
        "wooCommerceMutationAuthorized",
        "orderCreationAuthorized",
        "paymentExecutionAuthorized",
        "smsSendAuthorized",
        "inventoryMutationAuthorized",
        "productionPublishAuthorized",
    ):
        _flag(authority.get(field), f"authority.{field}", False)


def _validate_request_authority(authority: Any) -> None:
    if not isinstance(authority, dict):
        raise OrderIntakeHandoffError("request.authority must be an object")
    for field in (
        "fileContentPersisted",
        "fileUploadPerformed",
        "networkCallPerformed",
        "wooCommerceMutationAuthorized",
        "orderCreationAuthorized",
        "paymentExecutionAuthorized",
        "smsSendAuthorized",
        "inventoryMutationAuthorized",
        "productionPublishAuthorized",
    ):
        _flag(authority.get(field), f"request.authority.{field}", False)


def _normalize_reference_images(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise OrderIntakeHandoffError("request.customization.referenceImages must be an array")
    if len(value) > 8:
        raise OrderIntakeHandoffError("request.customization.referenceImages exceeds 8 items")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise OrderIntakeHandoffError(f"referenceImages[{index}] must be an object")
        if set(item) - {"name", "type"}:
            raise OrderIntakeHandoffError(f"referenceImages[{index}] contains forbidden file-content fields")
        normalized.append({
            "name": _text(item.get("name"), f"referenceImages[{index}].name", 160),
            "type": _text(item.get("type"), f"referenceImages[{index}].type", 80),
        })
    return normalized


def normalize_order_intake_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OrderIntakeHandoffError("handoff must be an object")
    if payload.get("schema") != ORDER_INTAKE_HANDOFF_SCHEMA:
        raise OrderIntakeHandoffError("unsupported handoff schema")
    if payload.get("version") != ORDER_INTAKE_HANDOFF_VERSION:
        raise OrderIntakeHandoffError("unsupported handoff version")
    if payload.get("state") != "prepared_for_staff_review":
        raise OrderIntakeHandoffError("handoff is not prepared for staff review")
    _validate_authority(payload.get("authority"))

    request = payload.get("request")
    if not isinstance(request, dict):
        raise OrderIntakeHandoffError("request must be an object")
    if request.get("schema") != ORDER_INTAKE_REQUEST_SCHEMA:
        raise OrderIntakeHandoffError("unsupported request schema")
    if request.get("version") != ORDER_INTAKE_REQUEST_VERSION:
        raise OrderIntakeHandoffError("unsupported request version")
    if request.get("state") != "review_only":
        raise OrderIntakeHandoffError("request must remain review_only")
    _validate_request_authority(request.get("authority"))

    pricing = request.get("pricing")
    if not isinstance(pricing, dict):
        raise OrderIntakeHandoffError("request.pricing must be an object")
    for field in ("quoteCalculated", "shippingFeeCalculated", "totalCalculated"):
        _flag(pricing.get(field), f"request.pricing.{field}", False)

    fulfillment = request.get("fulfillment")
    if not isinstance(fulfillment, dict):
        raise OrderIntakeHandoffError("request.fulfillment must be an object")
    method = fulfillment.get("method")
    if method not in SUPPORTED_FULFILLMENT:
        raise OrderIntakeHandoffError("unsupported fulfillment method")
    requested_date = _text(fulfillment.get("requestedDate"), "request.fulfillment.requestedDate", 10)
    pickup_time = _text(fulfillment.get("pickupTime"), "request.fulfillment.pickupTime", 5)
    yamato_window = fulfillment.get("yamatoWindow")
    if yamato_window not in SUPPORTED_YAMATO_WINDOWS:
        raise OrderIntakeHandoffError("unsupported Yamato window")
    _flag(fulfillment.get("routeOrFeeConfirmed"), "request.fulfillment.routeOrFeeConfirmed", False)
    _flag(fulfillment.get("fulfillmentConfirmed"), "request.fulfillment.fulfillmentConfirmed", False)
    if method != "pickup" and pickup_time:
        raise OrderIntakeHandoffError("pickupTime must be empty unless fulfillment is pickup")
    if method != "yamato" and yamato_window != "none":
        raise OrderIntakeHandoffError("yamatoWindow must be none unless fulfillment is yamato")

    customization = request.get("customization")
    if not isinstance(customization, dict):
        raise OrderIntakeHandoffError("request.customization must be an object")
    cake_type = customization.get("cakeType")
    if cake_type not in SUPPORTED_CAKE_TYPES:
        raise OrderIntakeHandoffError("unsupported cake type")
    custom_notes = _text(customization.get("customNotes"), "request.customization.customNotes", 4000)
    reference_images = _normalize_reference_images(customization.get("referenceImages"))
    if customization.get("referenceImageCount") != len(reference_images):
        raise OrderIntakeHandoffError("referenceImageCount does not match referenceImages")
    addons = customization.get("addons")
    if not isinstance(addons, list) or any(item not in SUPPORTED_ADDONS for item in addons):
        raise OrderIntakeHandoffError("unsupported add-on")
    addons = list(dict.fromkeys(addons))
    photo_topper = customization.get("photoTopper") is True
    edible_topper = customization.get("edibleTopper") is True
    icing_requested = customization.get("icingRequested") is True

    if cake_type == "basic" and (custom_notes or reference_images or photo_topper or edible_topper):
        raise OrderIntakeHandoffError("basic cake cannot carry custom-only fields")

    fingerprint = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    correlation_id = f"order-request:{fingerprint[:24]}"

    return {
        "source": "customer_experience_order_intake",
        "kind": "order_request",
        "normalized_intent": "staff_order_review",
        "review_required": True,
        "review_reason": "customer_order_request_requires_staff_confirmation",
        "review_state": "pending_staff_review",
        "approval_state": "not_evaluated",
        "lifecycle_correlation_id": correlation_id,
        "raw_handoff_fingerprint": fingerprint,
        "entities": {
            "fulfillment": {
                "method": method,
                "requested_date": requested_date,
                "pickup_time": pickup_time,
                "yamato_window": yamato_window,
                "route_or_fee_confirmed": False,
                "fulfillment_confirmed": False,
            },
            "customization": {
                "cake_type": cake_type,
                "custom_notes": custom_notes,
                "reference_images": reference_images,
                "reference_image_count": len(reference_images),
                "photo_topper": photo_topper,
                "edible_topper": edible_topper,
                "addons": addons,
                "icing_requested": icing_requested,
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
