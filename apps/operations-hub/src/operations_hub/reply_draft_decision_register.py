from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from .reply_draft_decision import (
    SUPPORTED_REPLY_DRAFT_RECOMMENDATIONS,
    ReplyDraftDecisionError,
)


class ReplyDraftDecisionProposalRegister:
    """Read-only register for non-authorizing reply-draft decision proposals."""

    def __init__(self) -> None:
        self._proposals: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def register(self, proposal: dict[str, Any]) -> dict[str, Any]:
        _validate_proposal(proposal)
        proposal_id = proposal["decision_proposal_id"]
        if proposal_id in self._proposals:
            if proposal != self._proposals[proposal_id]:
                raise ReplyDraftDecisionError("decision_proposal_id conflicts with existing proposal content")
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "decision_proposal_id": proposal_id,
                "channel_reply_authorized": False,
            }
        self._proposals[proposal_id] = copy.deepcopy(proposal)
        return {
            "accepted": True,
            "duplicate": False,
            "decision_proposal_id": proposal_id,
            "channel_reply_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        proposals = sorted(self._proposals.values(), key=lambda item: item["decision_proposal_id"])
        recommendation_counts = Counter(item["recommendation"] for item in proposals)
        source_counts = Counter(item["source"] for item in proposals)
        return {
            "status": "read_only",
            "register": "reply_draft_decision_proposals",
            "proposal_count": len(proposals),
            "duplicate_proposals": self._duplicates,
            "recommendation_counts": dict(sorted(recommendation_counts.items())),
            "source_counts": dict(sorted(source_counts.items())),
            "items": [
                {
                    "decision_proposal_id": item["decision_proposal_id"],
                    "reply_draft_id": item["reply_draft_id"],
                    "task_candidate_id": item["task_candidate_id"],
                    "lifecycle_correlation_id": item["lifecycle_correlation_id"],
                    "source": item["source"],
                    "recommendation": item["recommendation"],
                    "has_note": bool(item.get("note")),
                    "state": item["state"],
                    "channel_reply_authorized": False,
                    "mutation_authorized": False,
                }
                for item in proposals
            ],
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "network_dispatch_authorized": False,
            "mutation_authorized": False,
        }

    def proposal_detail(self, decision_proposal_id: str) -> dict[str, Any] | None:
        proposal = self._proposals.get(decision_proposal_id)
        return copy.deepcopy(proposal) if proposal is not None else None


def _validate_proposal(proposal: Any) -> None:
    if not isinstance(proposal, dict):
        raise ReplyDraftDecisionError("reply draft decision proposal must be an object")
    if proposal.get("schema") != "phil-ai-os-operations-reply-draft-decision-proposal" or proposal.get("version") != 1:
        raise ReplyDraftDecisionError("unsupported reply draft decision proposal schema")
    if proposal.get("state") != "recommendation_only":
        raise ReplyDraftDecisionError("reply draft decision proposal must remain recommendation_only")
    if proposal.get("recommendation") not in SUPPORTED_REPLY_DRAFT_RECOMMENDATIONS:
        raise ReplyDraftDecisionError("unsupported reply draft recommendation")
    proposal_id = proposal.get("decision_proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id.startswith("ops-reply-decision:"):
        raise ReplyDraftDecisionError("invalid decision_proposal_id")
    effects = proposal.get("effects")
    if not isinstance(effects, dict) or any(value is not False for value in effects.values()):
        raise ReplyDraftDecisionError("reply draft decision proposal effects must remain false")
    if proposal.get("mutation_authorized") is not False:
        raise ReplyDraftDecisionError("reply draft decision proposal must remain non-authorizing")
