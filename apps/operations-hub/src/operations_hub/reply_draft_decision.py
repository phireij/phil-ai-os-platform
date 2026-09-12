from __future__ import annotations

import hashlib
import json
from typing import Any


SUPPORTED_REPLY_DRAFT_RECOMMENDATIONS = {
    "recommend_future_dispatch",
    "request_reply_revision",
    "reject_reply_draft",
}


class ReplyDraftDecisionError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _bounded_text(value: Any, field: str, max_length: int, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ReplyDraftDecisionError(f"{field} is required")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise ReplyDraftDecisionError(f"{field} exceeds {max_length} characters")
    return normalized


def build_reply_draft_decision_proposal(
    reply_draft: dict[str, Any],
    *,
    recommendation: str,
    reviewer_ref: str,
    note: str = "",
) -> dict[str, Any]:
    """Build a non-authorizing operator recommendation for a reply draft.

    This deliberately does not approve or dispatch a customer reply. Drafts that still
    require governance approval remain blocked from operator decision proposals.
    """
    if not isinstance(reply_draft, dict):
        raise ReplyDraftDecisionError("reply_draft must be an object")
    if reply_draft.get("schema") != "phil-ai-os-operations-reply-draft-proposal" or reply_draft.get("version") != 1:
        raise ReplyDraftDecisionError("unsupported reply draft schema")
    if reply_draft.get("state") != "awaiting_operator_approval":
        raise ReplyDraftDecisionError("reply draft must remain awaiting_operator_approval")
    if reply_draft.get("operator_decision") is not None:
        raise ReplyDraftDecisionError("reply draft operator decision must remain unset")
    if reply_draft.get("governance_approval_required") is True:
        raise ReplyDraftDecisionError("reply draft remains blocked by governance approval")
    if reply_draft.get("governance_approval_state") != "not_required":
        raise ReplyDraftDecisionError("reply draft governance state is not operator-ready")

    authority = reply_draft.get("authority")
    if not isinstance(authority, dict):
        raise ReplyDraftDecisionError("reply draft authority must be an object")
    if authority.get("draft_only") is not True or authority.get("operator_approval_required") is not True:
        raise ReplyDraftDecisionError("reply draft must remain draft-only and operator-gated")
    if authority.get("authority_effect") != "none":
        raise ReplyDraftDecisionError("reply draft authority_effect must remain none")
    for field, value in authority.items():
        if field in {"draft_only", "operator_approval_required", "authority_effect"}:
            continue
        if value is not False:
            raise ReplyDraftDecisionError(f"reply draft authority {field} must remain false")

    if recommendation not in SUPPORTED_REPLY_DRAFT_RECOMMENDATIONS:
        raise ReplyDraftDecisionError("unsupported reply draft recommendation")

    reply_draft_id = _bounded_text(reply_draft.get("reply_draft_id"), "reply_draft_id", 64)
    task_candidate_id = _bounded_text(reply_draft.get("task_candidate_id"), "task_candidate_id", 64)
    correlation_id = _bounded_text(reply_draft.get("lifecycle_correlation_id"), "lifecycle_correlation_id", 64)
    source = _bounded_text(reply_draft.get("source"), "source", 40)
    reviewer = _bounded_text(reviewer_ref, "reviewer_ref", 120)
    review_note = _bounded_text(note, "note", 1000, required=False)

    material = {
        "reply_draft_id": reply_draft_id,
        "task_candidate_id": task_candidate_id,
        "lifecycle_correlation_id": correlation_id,
        "source": source,
        "recommendation": recommendation,
        "reviewer_ref": reviewer,
        "note": review_note,
    }
    fingerprint = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()

    return {
        "schema": "phil-ai-os-operations-reply-draft-decision-proposal",
        "version": 1,
        "state": "recommendation_only",
        "decision_proposal_id": f"ops-reply-decision:{fingerprint[:24]}",
        "reply_draft_id": reply_draft_id,
        "task_candidate_id": task_candidate_id,
        "lifecycle_correlation_id": correlation_id,
        "source": source,
        "recommendation": recommendation,
        "reviewer_ref": reviewer,
        "note": review_note,
        "effects": {
            "operator_decision_recorded": False,
            "reply_approved": False,
            "channel_reply_authorized": False,
            "network_dispatch_authorized": False,
            "execution_authorized": False,
            "woo_commerce_mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "production_publish_authorized": False,
        },
        "mutation_authorized": False,
    }
