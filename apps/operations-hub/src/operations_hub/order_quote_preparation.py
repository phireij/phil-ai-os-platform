from __future__ import annotations

import hashlib
import json
from typing import Any

from .order_review_decision import OrderReviewDecisionError


class OrderQuotePreparationError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_order_quote_preparation(
    review_detail: dict[str, Any],
    proposal_detail: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic, non-authorizing packet for future quote review."""
    if not isinstance(review_detail, dict):
        raise OrderQuotePreparationError("review_detail must be an object")
    if not isinstance(proposal_detail, dict):
        raise OrderQuotePreparationError("proposal_detail must be an object")

    correlation_id = review_detail.get("lifecycle_correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id:
        raise OrderQuotePreparationError("review_detail is missing lifecycle_correlation_id")
    if review_detail.get("review_state") != "pending_staff_review":
        raise OrderQuotePreparationError("review must remain pending_staff_review")

    review_authority = review_detail.get("authority")
    if not isinstance(review_authority, dict) or review_authority.get("mutation_authorized") is not False:
        raise OrderQuotePreparationError("review must remain non-authorizing")

    if proposal_detail.get("lifecycle_correlation_id") != correlation_id:
        raise OrderQuotePreparationError("proposal correlation does not match review")
    if proposal_detail.get("state") != "proposal_only":
        raise OrderQuotePreparationError("proposal must remain proposal_only")
    if proposal_detail.get("decision") != "accept_for_quote_review":
        raise OrderQuotePreparationError("quote preparation requires accept_for_quote_review")
    if proposal_detail.get("mutation_authorized") is not False:
        raise OrderQuotePreparationError("proposal must remain non-authorizing")

    effects = proposal_detail.get("effects")
    if not isinstance(effects, dict):
        raise OrderQuotePreparationError("proposal effects must be an object")
    for field, value in effects.items():
        if value is not False:
            raise OrderQuotePreparationError(f"proposal effect {field} must remain false")

    entities = review_detail.get("entities")
    if not isinstance(entities, dict):
        raise OrderQuotePreparationError("review entities must be an object")
    fulfillment = entities.get("fulfillment")
    customization = entities.get("customization")
    if not isinstance(fulfillment, dict) or not isinstance(customization, dict):
        raise OrderQuotePreparationError("review entities are incomplete")

    source_fingerprint = hashlib.sha256(
        _canonical_json({"review": review_detail, "proposal": proposal_detail}).encode("utf-8")
    ).hexdigest()

    return {
        "schema": "rubys-order-quote-preparation",
        "version": 1,
        "state": "prepared_for_quote_review",
        "preparation_id": f"quote-prep:{source_fingerprint[:24]}",
        "lifecycle_correlation_id": correlation_id,
        "source_proposal_id": proposal_detail.get("proposal_id"),
        "source_fingerprint": source_fingerprint,
        "request_context": {
            "fulfillment": {
                "method": fulfillment.get("method"),
                "requested_date": fulfillment.get("requested_date"),
                "pickup_time": fulfillment.get("pickup_time"),
                "yamato_window": fulfillment.get("yamato_window"),
                "route_or_fee_confirmed": False,
                "fulfillment_confirmed": False,
            },
            "customization": {
                "cake_type": customization.get("cake_type"),
                "custom_notes": customization.get("custom_notes", ""),
                "reference_images": list(customization.get("reference_images", [])),
                "reference_image_count": customization.get("reference_image_count", 0),
                "photo_topper": customization.get("photo_topper") is True,
                "edible_topper": customization.get("edible_topper") is True,
                "addons": list(customization.get("addons", [])),
                "icing_requested": customization.get("icing_requested") is True,
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
