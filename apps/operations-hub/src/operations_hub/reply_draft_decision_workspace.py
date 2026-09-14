from __future__ import annotations

from collections import Counter
from typing import Any

from .reply_draft_decision_register import ReplyDraftDecisionProposalRegister
from .reply_draft_register import ReplyDraftRegister


class ReplyDraftDecisionWorkspaceError(ValueError):
    pass


def build_reply_draft_decision_workspace(
    draft_register: ReplyDraftRegister,
    proposal_register: ReplyDraftDecisionProposalRegister,
) -> dict[str, Any]:
    """Correlate reply drafts with non-authorizing decision proposals for operator review."""
    if not isinstance(draft_register, ReplyDraftRegister):
        raise ReplyDraftDecisionWorkspaceError("draft_register must be a ReplyDraftRegister")
    if not isinstance(proposal_register, ReplyDraftDecisionProposalRegister):
        raise ReplyDraftDecisionWorkspaceError(
            "proposal_register must be a ReplyDraftDecisionProposalRegister"
        )

    drafts = draft_register.read_model()
    proposals = proposal_register.read_model()
    _assert_read_only(drafts, "draft_register")
    _assert_read_only(proposals, "proposal_register")

    draft_items = {item["reply_draft_id"]: item for item in drafts.get("items", [])}
    proposals_by_draft: dict[str, list[dict[str, Any]]] = {}
    for proposal in proposals.get("items", []):
        draft_id = proposal.get("reply_draft_id")
        draft = draft_items.get(draft_id)
        if draft is None:
            raise ReplyDraftDecisionWorkspaceError("decision proposal references an unknown reply draft")
        if proposal.get("task_candidate_id") != draft.get("task_candidate_id"):
            raise ReplyDraftDecisionWorkspaceError("decision proposal/reply draft task candidate mismatch")
        if proposal.get("lifecycle_correlation_id") != draft.get("lifecycle_correlation_id"):
            raise ReplyDraftDecisionWorkspaceError("decision proposal/reply draft correlation mismatch")
        if proposal.get("source") != draft.get("source"):
            raise ReplyDraftDecisionWorkspaceError("decision proposal/reply draft source mismatch")
        proposals_by_draft.setdefault(str(draft_id), []).append(proposal)

    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for draft_id, draft in draft_items.items():
        related = proposals_by_draft.get(draft_id, [])
        recommendations = sorted({item["recommendation"] for item in related})
        if len(recommendations) > 1:
            review_status = "conflicting_recommendations"
        elif len(recommendations) == 1:
            review_status = "recommendation_available"
        else:
            review_status = "awaiting_recommendation"
        status_counts[review_status] += 1
        rows.append(
            {
                "reply_draft_id": draft_id,
                "task_candidate_id": draft["task_candidate_id"],
                "lifecycle_correlation_id": draft["lifecycle_correlation_id"],
                "source": draft["source"],
                "locale": draft["locale"],
                "review_status": review_status,
                "recommendation_count": len(related),
                "recommendations": recommendations,
                "operator_decision_recorded": False,
                "reply_approved": False,
                "channel_reply_authorized": False,
            }
        )

    rows.sort(key=lambda item: item["reply_draft_id"])
    return {
        "status": "read_only",
        "workspace": "reply_draft_decision_review",
        "draft_count": len(rows),
        "awaiting_recommendation": status_counts.get("awaiting_recommendation", 0),
        "recommendation_available": status_counts.get("recommendation_available", 0),
        "conflicting_recommendations": status_counts.get("conflicting_recommendations", 0),
        "items": rows,
        "operator_decision_recorded": False,
        "reply_approved": False,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "network_dispatch_authorized": False,
        "mutation_authorized": False,
    }


def _assert_read_only(model: Any, label: str) -> None:
    if not isinstance(model, dict) or model.get("status") != "read_only":
        raise ReplyDraftDecisionWorkspaceError(f"{label} must remain read_only")
    for field in (
        "execution_authorized",
        "channel_reply_authorized",
        "network_dispatch_authorized",
        "mutation_authorized",
    ):
        if field in model and model.get(field) is not False:
            raise ReplyDraftDecisionWorkspaceError(f"{label} {field} must remain false")
