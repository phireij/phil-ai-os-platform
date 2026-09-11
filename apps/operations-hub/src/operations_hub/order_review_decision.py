from __future__ import annotations

import hashlib
import json
from typing import Any

SUPPORTED_REVIEW_DECISIONS = (
    "accept_for_quote_review",
    "request_customer_revision",
    "decline_request",
)


class OrderReviewDecisionError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _required_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrderReviewDecisionError(f"{field} is required")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise OrderReviewDecisionError(f"{field} exceeds {max_length} characters")
    return normalized


def _optional_text(value: Any, field: str, max_length: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise OrderReviewDecisionError(f"{field} must be a string")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise OrderReviewDecisionError(f"{field} exceeds {max_length} characters")
    return normalized


def build_order_review_decision_proposal(
    review_detail: dict[str, Any],
    decision: str,
    reviewer_ref: str,
    note: str = "",
) -> dict[str, Any]:
    if not isinstance(review_detail, dict):
        raise OrderReviewDecisionError("review_detail must be an object")
    correlation_id = _required_text(
        review_detail.get("lifecycle_correlation_id"),
        "lifecycle_correlation_id",
        64,
    )
    if review_detail.get("review_state") != "pending_staff_review":
        raise OrderReviewDecisionError("review_state must remain pending_staff_review")
    authority = review_detail.get("authority")
    if not isinstance(authority, dict) or authority.get("mutation_authorized") is not False:
        raise OrderReviewDecisionError("review detail must remain non-authorizing")
    if decision not in SUPPORTED_REVIEW_DECISIONS:
        raise OrderReviewDecisionError("unsupported review decision")

    reviewer = _required_text(reviewer_ref, "reviewer_ref", 120)
    review_note = _optional_text(note, "note", 1000)
    source_fingerprint = hashlib.sha256(_canonical_json(review_detail).encode("utf-8")).hexdigest()
    proposal_id = hashlib.sha256(
        _canonical_json({
            "correlation_id": correlation_id,
            "decision": decision,
            "reviewer_ref": reviewer,
            "note": review_note,
            "source_fingerprint": source_fingerprint,
        }).encode("utf-8")
    ).hexdigest()

    return {
        "schema": "rubys-order-review-decision-proposal",
        "version": 1,
        "state": "proposal_only",
        "proposal_id": f"order-review:{proposal_id[:24]}",
        "lifecycle_correlation_id": correlation_id,
        "decision": decision,
        "reviewer_ref": reviewer,
        "note": review_note,
        "source_review_fingerprint": source_fingerprint,
        "effects": {
            "quote_authorized": False,
            "fulfillment_confirmed": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "woo_commerce_mutation_authorized": False,
            "production_publish_authorized": False,
        },
        "mutation_authorized": False,
    }
