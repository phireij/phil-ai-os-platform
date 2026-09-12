from __future__ import annotations

import hashlib
import json
from typing import Any


class ReplyDraftError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _required_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplyDraftError(f"{field} is required")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise ReplyDraftError(f"{field} exceeds {max_length} characters")
    return normalized


def build_reply_draft_proposal(
    task_candidate: dict[str, Any],
    draft_text: str,
    *,
    drafted_by: str = "hermes",
) -> dict[str, Any]:
    """Build a non-authorizing customer reply draft for explicit operator approval."""
    if not isinstance(task_candidate, dict):
        raise ReplyDraftError("task_candidate must be an object")
    if task_candidate.get("schema") != "phil-ai-os-operations-task-candidate" or task_candidate.get("version") != 1:
        raise ReplyDraftError("unsupported task candidate schema")
    if task_candidate.get("state") not in {"awaiting_approval", "ready_for_operator_review"}:
        raise ReplyDraftError("task candidate is not reviewable")

    authority = task_candidate.get("authority")
    if not isinstance(authority, dict) or authority.get("operator_review_only") is not True:
        raise ReplyDraftError("task candidate must remain operator_review_only")
    if authority.get("authority_effect") != "none":
        raise ReplyDraftError("task candidate authority_effect must remain none")
    for field, value in authority.items():
        if field in {"operator_review_only", "authority_effect"}:
            continue
        if value is not False:
            raise ReplyDraftError(f"task candidate authority {field} must remain false")

    task_id = _required_text(task_candidate.get("task_candidate_id"), "task_candidate_id", 64)
    correlation_id = _required_text(task_candidate.get("lifecycle_correlation_id"), "lifecycle_correlation_id", 64)
    source = _required_text(task_candidate.get("source"), "source", 40)
    external_event_id = _required_text(task_candidate.get("external_event_id"), "external_event_id", 160)
    task_type = _required_text(task_candidate.get("task_type"), "task_type", 80)
    normalized_intent = _required_text(task_candidate.get("normalized_intent"), "normalized_intent", 80)

    customer_context = task_candidate.get("customer_context")
    if not isinstance(customer_context, dict):
        raise ReplyDraftError("customer_context must be an object")
    locale = customer_context.get("locale")
    if locale not in {"en", "ja", "unknown"}:
        raise ReplyDraftError("unsupported reply locale")

    text = _required_text(draft_text, "draft_text", 4000)
    author = _required_text(drafted_by, "drafted_by", 80)
    if author not in {"hermes", "operator"}:
        raise ReplyDraftError("drafted_by must be hermes or operator")

    approval_required = task_candidate.get("approval_required") is True
    material = {
        "task_candidate_id": task_id,
        "lifecycle_correlation_id": correlation_id,
        "source": source,
        "external_event_id": external_event_id,
        "draft_text": text,
        "drafted_by": author,
    }
    fingerprint = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()

    return {
        "schema": "phil-ai-os-operations-reply-draft-proposal",
        "version": 1,
        "state": "awaiting_operator_approval",
        "reply_draft_id": f"ops-reply:{fingerprint[:24]}",
        "task_candidate_id": task_id,
        "lifecycle_correlation_id": correlation_id,
        "source": source,
        "external_event_id": external_event_id,
        "task_type": task_type,
        "normalized_intent": normalized_intent,
        "locale": locale,
        "draft_text": text,
        "drafted_by": author,
        "governance_approval_required": approval_required,
        "governance_approval_state": task_candidate.get("approval_state"),
        "operator_decision": None,
        "authority": {
            "draft_only": True,
            "operator_approval_required": True,
            "automatic_execution": False,
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "network_dispatch_authorized": False,
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
