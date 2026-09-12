from __future__ import annotations

import hashlib
import json
from typing import Any


class TaskExtractionError(ValueError):
    pass


_TASK_TYPE_BY_INTENT = {
    "general_inquiry": "general_inquiry_task",
    "product_inquiry": "product_inquiry_task",
    "pickup_inquiry": "pickup_inquiry_task",
    "order_inquiry": "order_inquiry_task",
    "review_feedback": "public_review_task",
    "complaint": "customer_issue_task",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _required_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskExtractionError(f"{field} is required")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise TaskExtractionError(f"{field} exceeds {max_length} characters")
    return normalized


def build_task_candidate(event: dict[str, Any], governance: dict[str, Any]) -> dict[str, Any]:
    """Extract one bounded operator-review task candidate from a normalized channel event."""
    if not isinstance(event, dict) or not isinstance(governance, dict):
        raise TaskExtractionError("event and governance must be objects")
    if event.get("fixture_only") is not True:
        raise TaskExtractionError("bounded task extraction accepts fixture_only events")
    if event.get("mutation_authorized") is not False:
        raise TaskExtractionError("event must remain non-authorizing")

    for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if governance.get(field) is not False:
            raise TaskExtractionError(f"governance {field} must remain false")
    if governance.get("authority_effect") != "none":
        raise TaskExtractionError("governance authority_effect must remain none")

    correlation_id = _required_text(event.get("lifecycle_correlation_id"), "lifecycle_correlation_id", 64)
    if governance.get("lifecycle_correlation_id") != correlation_id:
        raise TaskExtractionError("event/governance correlation mismatch")

    intent = event.get("normalized_intent")
    if intent not in _TASK_TYPE_BY_INTENT:
        raise TaskExtractionError(f"unsupported normalized intent: {intent}")
    if governance.get("normalized_intent") != intent:
        raise TaskExtractionError("event/governance intent mismatch")

    source = _required_text(event.get("source"), "source", 40)
    kind = _required_text(event.get("kind"), "kind", 40)
    external_event_id = _required_text(event.get("external_event_id"), "external_event_id", 160)

    entities = event.get("entities")
    if not isinstance(entities, dict):
        raise TaskExtractionError("event entities must be an object")
    customer_text = _required_text(entities.get("text"), "entities.text", 4000)
    locale = entities.get("locale")
    if locale not in {"en", "ja", "unknown"}:
        raise TaskExtractionError("unsupported task locale")

    task_type = _TASK_TYPE_BY_INTENT[str(intent)]
    approval_required = governance.get("approval_required") is True
    approval_state = "required" if approval_required else "not_required"
    task_state = "awaiting_approval" if approval_required else "ready_for_operator_review"

    material = {
        "lifecycle_correlation_id": correlation_id,
        "source": source,
        "external_event_id": external_event_id,
        "task_type": task_type,
    }
    fingerprint = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()

    return {
        "schema": "phil-ai-os-operations-task-candidate",
        "version": 1,
        "state": task_state,
        "task_candidate_id": f"ops-task:{fingerprint[:24]}",
        "lifecycle_correlation_id": correlation_id,
        "source": source,
        "kind": kind,
        "external_event_id": external_event_id,
        "task_type": task_type,
        "normalized_intent": intent,
        "risk_level": governance.get("risk_level"),
        "approval_required": approval_required,
        "approval_state": approval_state,
        "approval_reason": governance.get("approval_reason") if approval_required else None,
        "customer_context": {
            "locale": locale,
            "text": customer_text,
        },
        "authority": {
            "operator_review_only": True,
            "automatic_execution": False,
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "woo_commerce_mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "production_publish_authorized": False,
            "mutation_authorized": False,
            "authority_effect": "none",
        },
    }
