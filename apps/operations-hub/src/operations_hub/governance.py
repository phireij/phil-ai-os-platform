from __future__ import annotations

from typing import Any


class GovernanceEvaluationError(ValueError):
    pass


_RISK_BY_INTENT = {
    "general_inquiry": "low",
    "product_inquiry": "low",
    "pickup_inquiry": "low",
    "order_inquiry": "medium",
    "review_feedback": "medium",
    "complaint": "high",
}


def evaluate_governance(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("mutation_authorized") is not False:
        raise GovernanceEvaluationError("operations event must remain non-authorizing")

    intent = event.get("normalized_intent")
    if intent not in _RISK_BY_INTENT:
        raise GovernanceEvaluationError(f"unsupported normalized intent: {intent}")

    correlation_id = event.get("lifecycle_correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id:
        raise GovernanceEvaluationError("lifecycle_correlation_id is required")

    review_required = event.get("review_required") is True
    approval_state = event.get("approval_state")
    if review_required and approval_state != "required":
        raise GovernanceEvaluationError("review-required event must have approval_state=required")

    risk_level = _RISK_BY_INTENT[intent]
    approval_required = review_required or risk_level == "high"
    reason = event.get("review_reason") if review_required else None
    if approval_required and not reason:
        reason = "risk_policy_requires_review"

    return {
        "source": event.get("source"),
        "external_event_id": event.get("external_event_id"),
        "normalized_intent": intent,
        "risk_level": risk_level,
        "human_review_required": approval_required,
        "approval_required": approval_required,
        "approval_reason": reason,
        "approval_state": "required" if approval_required else "not_required",
        "lifecycle_correlation_id": correlation_id,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }
