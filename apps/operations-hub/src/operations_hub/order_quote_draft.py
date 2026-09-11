from __future__ import annotations

import hashlib
import json
from typing import Any


class OrderQuoteDraftError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _required_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrderQuoteDraftError(f"{field} is required")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise OrderQuoteDraftError(f"{field} exceeds {max_length} characters")
    return normalized


def _optional_text(value: Any, field: str, max_length: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise OrderQuoteDraftError(f"{field} must be a string")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise OrderQuoteDraftError(f"{field} exceeds {max_length} characters")
    return normalized


def _yen_amount(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrderQuoteDraftError(f"{field} must be an integer JPY amount")
    if value < 0:
        raise OrderQuoteDraftError(f"{field} must not be negative")
    if value > 10_000_000:
        raise OrderQuoteDraftError(f"{field} exceeds bounded quote amount")
    return value


def build_order_quote_draft(
    preparation: dict[str, Any],
    *,
    quote_amount: int,
    shipping_amount: int,
    total_amount: int,
    prepared_by: str,
    note: str = "",
) -> dict[str, Any]:
    """Build a deterministic staff-review-only quote draft without granting execution authority."""
    if not isinstance(preparation, dict):
        raise OrderQuoteDraftError("preparation must be an object")
    if preparation.get("schema") != "rubys-order-quote-preparation" or preparation.get("version") != 1:
        raise OrderQuoteDraftError("unsupported quote preparation schema")
    if preparation.get("state") != "prepared_for_quote_review":
        raise OrderQuoteDraftError("preparation must remain prepared_for_quote_review")

    authority = preparation.get("authority")
    if not isinstance(authority, dict) or authority.get("mutation_authorized") is not False:
        raise OrderQuoteDraftError("preparation must remain non-authorizing")
    for field, value in authority.items():
        if field == "quote_review_only":
            if value is not True:
                raise OrderQuoteDraftError("preparation must remain quote_review_only")
        elif value is not False:
            raise OrderQuoteDraftError(f"preparation authority {field} must remain false")

    correlation_id = _required_text(
        preparation.get("lifecycle_correlation_id"),
        "lifecycle_correlation_id",
        64,
    )
    preparation_id = _required_text(preparation.get("preparation_id"), "preparation_id", 64)
    source_fingerprint = _required_text(preparation.get("source_fingerprint"), "source_fingerprint", 128)

    amount = _yen_amount(quote_amount, "quote_amount")
    shipping = _yen_amount(shipping_amount, "shipping_amount")
    total = _yen_amount(total_amount, "total_amount")
    if total != amount + shipping:
        raise OrderQuoteDraftError("total_amount must equal quote_amount plus shipping_amount")

    staff_ref = _required_text(prepared_by, "prepared_by", 120)
    staff_note = _optional_text(note, "note", 1000)

    request_context = preparation.get("request_context")
    if not isinstance(request_context, dict):
        raise OrderQuoteDraftError("preparation request_context must be an object")

    draft_source = {
        "preparation_id": preparation_id,
        "source_fingerprint": source_fingerprint,
        "lifecycle_correlation_id": correlation_id,
        "quote_amount": amount,
        "shipping_amount": shipping,
        "total_amount": total,
        "currency": "JPY",
        "prepared_by": staff_ref,
        "note": staff_note,
    }
    draft_fingerprint = hashlib.sha256(_canonical_json(draft_source).encode("utf-8")).hexdigest()

    return {
        "schema": "rubys-order-quote-draft",
        "version": 1,
        "state": "draft_for_staff_review",
        "draft_id": f"quote-draft:{draft_fingerprint[:24]}",
        "lifecycle_correlation_id": correlation_id,
        "source_preparation_id": preparation_id,
        "source_fingerprint": source_fingerprint,
        "prepared_by": staff_ref,
        "note": staff_note,
        "request_context": request_context,
        "pricing": {
            "quote_amount": amount,
            "shipping_amount": shipping,
            "total_amount": total,
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
