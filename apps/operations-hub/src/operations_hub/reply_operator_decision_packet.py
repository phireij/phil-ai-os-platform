from __future__ import annotations

import hashlib
import json
from typing import Any

from .reply_draft import ReplyDraftError
from .reply_draft_decision import SUPPORTED_REPLY_DRAFT_RECOMMENDATIONS


class ReplyOperatorDecisionPacketError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_reply_operator_decision_packet(
    reply_draft: dict[str, Any],
    decision_proposal: dict[str, Any],
) -> dict[str, Any]:
    """Prepare an explicit operator-decision packet without deciding or dispatching the reply."""
    if not isinstance(reply_draft, dict) or not isinstance(decision_proposal, dict):
        raise ReplyOperatorDecisionPacketError("reply_draft and decision_proposal must be objects")
    if reply_draft.get("schema") != "phil-ai-os-operations-reply-draft-proposal" or reply_draft.get("version") != 1:
        raise ReplyOperatorDecisionPacketError("unsupported reply draft schema")
    if reply_draft.get("state") != "awaiting_operator_approval" or reply_draft.get("operator_decision") is not None:
        raise ReplyOperatorDecisionPacketError("reply draft must remain awaiting explicit operator approval")
    if reply_draft.get("governance_approval_required") is True:
        raise ReplyOperatorDecisionPacketError("reply draft remains blocked by governance approval")
    if reply_draft.get("governance_approval_state") != "not_required":
        raise ReplyOperatorDecisionPacketError("reply draft governance state is not operator-ready")

    authority = reply_draft.get("authority")
    if not isinstance(authority, dict) or authority.get("draft_only") is not True or authority.get("operator_approval_required") is not True:
        raise ReplyOperatorDecisionPacketError("reply draft must remain draft-only and operator-gated")
    if authority.get("authority_effect") != "none":
        raise ReplyOperatorDecisionPacketError("reply draft authority_effect must remain none")
    for field, value in authority.items():
        if field in {"draft_only", "operator_approval_required", "authority_effect"}:
            continue
        if value is not False:
            raise ReplyOperatorDecisionPacketError(f"reply draft authority {field} must remain false")

    if decision_proposal.get("schema") != "phil-ai-os-operations-reply-draft-decision-proposal" or decision_proposal.get("version") != 1:
        raise ReplyOperatorDecisionPacketError("unsupported decision proposal schema")
    if decision_proposal.get("state") != "recommendation_only":
        raise ReplyOperatorDecisionPacketError("decision proposal must remain recommendation_only")
    recommendation = decision_proposal.get("recommendation")
    if recommendation not in SUPPORTED_REPLY_DRAFT_RECOMMENDATIONS:
        raise ReplyOperatorDecisionPacketError("unsupported reply draft recommendation")
    effects = decision_proposal.get("effects")
    if not isinstance(effects, dict) or any(value is not False for value in effects.values()):
        raise ReplyOperatorDecisionPacketError("decision proposal effects must remain false")
    if decision_proposal.get("mutation_authorized") is not False:
        raise ReplyOperatorDecisionPacketError("decision proposal must remain non-authorizing")

    for field in ("reply_draft_id", "task_candidate_id", "lifecycle_correlation_id", "source"):
        if decision_proposal.get(field) != reply_draft.get(field):
            raise ReplyOperatorDecisionPacketError(f"decision proposal/reply draft {field} mismatch")

    material = {
        "reply_draft_id": reply_draft["reply_draft_id"],
        "decision_proposal_id": decision_proposal["decision_proposal_id"],
        "task_candidate_id": reply_draft["task_candidate_id"],
        "lifecycle_correlation_id": reply_draft["lifecycle_correlation_id"],
        "source": reply_draft["source"],
        "locale": reply_draft["locale"],
        "draft_text": reply_draft["draft_text"],
        "recommendation": recommendation,
    }
    fingerprint = hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()

    return {
        "schema": "phil-ai-os-operations-reply-operator-decision-packet",
        "version": 1,
        "state": "awaiting_explicit_operator_decision",
        "operator_decision_packet_id": f"ops-reply-operator:{fingerprint[:24]}",
        "reply_draft_id": reply_draft["reply_draft_id"],
        "decision_proposal_id": decision_proposal["decision_proposal_id"],
        "task_candidate_id": reply_draft["task_candidate_id"],
        "lifecycle_correlation_id": reply_draft["lifecycle_correlation_id"],
        "source": reply_draft["source"],
        "locale": reply_draft["locale"],
        "draft_text": reply_draft["draft_text"],
        "recommendation": recommendation,
        "operator_decision": None,
        "authority": {
            "operator_review_only": True,
            "operator_decision_required": True,
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
            "mutation_authorized": False,
            "authority_effect": "none",
        },
    }
