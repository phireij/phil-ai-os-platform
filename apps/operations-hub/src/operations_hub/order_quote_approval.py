from __future__ import annotations

import hashlib
import json
from typing import Any

from .order_quote_draft import OrderQuoteDraftError


class OrderQuoteApprovalRequestError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _required_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrderQuoteApprovalRequestError(f"{field} is required")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise OrderQuoteApprovalRequestError(f"{field} exceeds {max_length} characters")
    return normalized


def _optional_text(value: Any, field: str, max_length: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise OrderQuoteApprovalRequestError(f"{field} must be a string")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise OrderQuoteApprovalRequestError(f"{field} exceeds {max_length} characters")
    return normalized


def build_order_quote_approval_request(
    draft: dict[str, Any],
    *,
    requested_by: str,
    reason: str = "",
) -> dict[str, Any]:
    """Prepare an approval-gated quote request without granting quote or send authority."""
    if not isinstance(draft, dict):
        raise OrderQuoteApprovalRequestError("draft must be an object")
    if draft.get("schema") != "rubys-order-quote-draft" or draft.get("version") != 1:
        raise OrderQuoteApprovalRequestError("unsupported quote draft schema")
    if draft.get("state") != "draft_for_staff_review":
        raise OrderQuoteApprovalRequestError("draft must remain draft_for_staff_review")

    authority = draft.get("authority")
    if not isinstance(authority, dict):
        raise OrderQuoteApprovalRequestError("draft authority must be an object")
    for field, value in authority.items():
        if field == "staff_review_only":
            if value is not True:
                raise OrderQuoteApprovalRequestError("draft must remain staff_review_only")
        elif value is not False:
            raise OrderQuoteApprovalRequestError(f"draft authority {field} must remain false")

    pricing = draft.get("pricing")
    if not isinstance(pricing, dict):
        raise OrderQuoteApprovalRequestError("draft pricing must be an object")
    quote_amount = pricing.get("quote_amount")
    shipping_amount = pricing.get("shipping_amount")
    total_amount = pricing.get("total_amount")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (quote_amount, shipping_amount, total_amount)):
        raise OrderQuoteApprovalRequestError("draft pricing must contain non-negative integer JPY amounts")
    if total_amount != quote_amount + shipping_amount:
        raise OrderQuoteApprovalRequestError("draft total_amount must reconcile")
    if pricing.get("currency") != "JPY":
        raise OrderQuoteApprovalRequestError("draft currency must remain JPY")
    if pricing.get("customer_accepted") is not False:
        raise OrderQuoteApprovalRequestError("draft customer_accepted must remain false")

    draft_id = _required_text(draft.get("draft_id"), "draft_id", 64)
    correlation_id = _required_text(draft.get("lifecycle_correlation_id"), "lifecycle_correlation_id", 64)
    requester = _required_text(requested_by, "requested_by", 120)
    request_reason = _optional_text(reason, "reason", 1000)

    fingerprint_source = {
        "draft_id": draft_id,
        "lifecycle_correlation_id": correlation_id,
        "pricing": {
            "quote_amount": quote_amount,
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
            "currency": "JPY",
        },
        "requested_by": requester,
        "reason": request_reason,
    }
    fingerprint = hashlib.sha256(_canonical_json(fingerprint_source).encode("utf-8")).hexdigest()

    return {
        "schema": "rubys-order-quote-approval-request",
        "version": 1,
        "state": "approval_requested",
        "approval_request_id": f"quote-approval:{fingerprint[:24]}",
        "lifecycle_correlation_id": correlation_id,
        "source_draft_id": draft_id,
        "requested_by": requester,
        "reason": request_reason,
        "pricing": {
            "quote_amount": quote_amount,
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
            "currency": "JPY",
            "customer_accepted": False,
        },
        "approval": {
            "required": True,
            "decision": None,
            "approved_by": None,
            "approved_at": None,
        },
        "authority": {
            "approval_request_only": True,
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
