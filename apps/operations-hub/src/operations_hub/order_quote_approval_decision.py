from __future__ import annotations

import hashlib
import json
from typing import Any


SUPPORTED_QUOTE_APPROVAL_RECOMMENDATIONS = {
    "recommend_quote_approval",
    "request_quote_revision",
}


class OrderQuoteApprovalDecisionError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _bounded_text(value: Any, field: str, max_length: int, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise OrderQuoteApprovalDecisionError(f"{field} is required")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise OrderQuoteApprovalDecisionError(f"{field} exceeds {max_length} characters")
    return normalized


def build_order_quote_approval_decision_proposal(
    approval_request: dict[str, Any],
    *,
    recommendation: str,
    reviewer_ref: str,
    note: str = "",
) -> dict[str, Any]:
    """Build a deterministic recommendation proposal without deciding or authorizing the quote."""
    if not isinstance(approval_request, dict):
        raise OrderQuoteApprovalDecisionError("approval_request must be an object")
    if approval_request.get("schema") != "rubys-order-quote-approval-request" or approval_request.get("version") != 1:
        raise OrderQuoteApprovalDecisionError("unsupported quote approval request schema")
    if approval_request.get("state") != "approval_requested":
        raise OrderQuoteApprovalDecisionError("approval request must remain approval_requested")

    approval = approval_request.get("approval")
    if not isinstance(approval, dict) or approval.get("required") is not True:
        raise OrderQuoteApprovalDecisionError("approval request must remain approval-gated")
    if approval.get("decision") is not None:
        raise OrderQuoteApprovalDecisionError("approval decision must remain unset")
    if approval.get("approved_by") is not None or approval.get("approved_at") is not None:
        raise OrderQuoteApprovalDecisionError("approval metadata must remain unset")

    authority = approval_request.get("authority")
    if not isinstance(authority, dict):
        raise OrderQuoteApprovalDecisionError("approval request authority must be an object")
    for field, value in authority.items():
        if field == "approval_request_only":
            if value is not True:
                raise OrderQuoteApprovalDecisionError("approval request must remain approval_request_only")
        elif value is not False:
            raise OrderQuoteApprovalDecisionError(f"approval request authority {field} must remain false")

    pricing = approval_request.get("pricing")
    if not isinstance(pricing, dict):
        raise OrderQuoteApprovalDecisionError("approval request pricing must be an object")
    quote_amount = pricing.get("quote_amount")
    shipping_amount = pricing.get("shipping_amount")
    total_amount = pricing.get("total_amount")
    for value in (quote_amount, shipping_amount, total_amount):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise OrderQuoteApprovalDecisionError("approval request pricing must contain non-negative integer JPY amounts")
    if total_amount != quote_amount + shipping_amount:
        raise OrderQuoteApprovalDecisionError("approval request total_amount must reconcile")
    if pricing.get("currency") != "JPY" or pricing.get("customer_accepted") is not False:
        raise OrderQuoteApprovalDecisionError("approval request pricing state is invalid")

    if recommendation not in SUPPORTED_QUOTE_APPROVAL_RECOMMENDATIONS:
        raise OrderQuoteApprovalDecisionError("unsupported quote approval recommendation")

    request_id = _bounded_text(approval_request.get("approval_request_id"), "approval_request_id", 64)
    correlation_id = _bounded_text(approval_request.get("lifecycle_correlation_id"), "lifecycle_correlation_id", 64)
    reviewer = _bounded_text(reviewer_ref, "reviewer_ref", 120)
    review_note = _bounded_text(note, "note", 1000, required=False)

    source = {
        "approval_request_id": request_id,
        "lifecycle_correlation_id": correlation_id,
        "recommendation": recommendation,
        "reviewer_ref": reviewer,
        "note": review_note,
        "pricing": {
            "quote_amount": quote_amount,
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
            "currency": "JPY",
        },
    }
    fingerprint = hashlib.sha256(_canonical_json(source).encode("utf-8")).hexdigest()

    return {
        "schema": "rubys-order-quote-approval-decision-proposal",
        "version": 1,
        "state": "recommendation_only",
        "decision_proposal_id": f"quote-approval-proposal:{fingerprint[:24]}",
        "approval_request_id": request_id,
        "lifecycle_correlation_id": correlation_id,
        "source_draft_id": approval_request.get("source_draft_id"),
        "recommendation": recommendation,
        "reviewer_ref": reviewer,
        "note": review_note,
        "pricing": {
            "quote_amount": quote_amount,
            "shipping_amount": shipping_amount,
            "total_amount": total_amount,
            "currency": "JPY",
            "customer_accepted": False,
        },
        "effects": {
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "fulfillment_confirmed": False,
            "woo_commerce_mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "production_publish_authorized": False,
        },
        "mutation_authorized": False,
    }
