from __future__ import annotations

from collections import Counter
from typing import Any

from .reply_draft import ReplyDraftError


class ReplyDraftRegister:
    """Read-only register for bounded reply draft proposals awaiting operator approval."""

    def __init__(self) -> None:
        self._drafts: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def register(self, proposal: dict[str, Any]) -> dict[str, Any]:
        _validate_proposal(proposal)
        reply_draft_id = proposal["reply_draft_id"]
        if reply_draft_id in self._drafts:
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "reply_draft_id": reply_draft_id,
                "channel_reply_authorized": False,
            }
        self._drafts[reply_draft_id] = dict(proposal)
        return {
            "accepted": True,
            "duplicate": False,
            "reply_draft_id": reply_draft_id,
            "channel_reply_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        drafts = sorted(self._drafts.values(), key=lambda item: item["reply_draft_id"])
        source_counts = Counter(item["source"] for item in drafts)
        locale_counts = Counter(item["locale"] for item in drafts)
        return {
            "status": "read_only",
            "register": "reply_draft_proposals",
            "draft_count": len(drafts),
            "duplicate_drafts": self._duplicates,
            "awaiting_operator_approval": len(drafts),
            "source_counts": dict(sorted(source_counts.items())),
            "locale_counts": dict(sorted(locale_counts.items())),
            "items": [
                {
                    "reply_draft_id": item["reply_draft_id"],
                    "task_candidate_id": item["task_candidate_id"],
                    "lifecycle_correlation_id": item["lifecycle_correlation_id"],
                    "source": item["source"],
                    "task_type": item["task_type"],
                    "normalized_intent": item["normalized_intent"],
                    "locale": item["locale"],
                    "drafted_by": item["drafted_by"],
                    "governance_approval_required": item["governance_approval_required"],
                    "state": item["state"],
                    "channel_reply_authorized": False,
                    "mutation_authorized": False,
                }
                for item in drafts
            ],
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "network_dispatch_authorized": False,
            "mutation_authorized": False,
        }

    def detail(self, reply_draft_id: str) -> dict[str, Any] | None:
        draft = self._drafts.get(reply_draft_id)
        return dict(draft) if draft is not None else None


def _validate_proposal(proposal: Any) -> None:
    if not isinstance(proposal, dict):
        raise ReplyDraftError("reply draft proposal must be an object")
    if proposal.get("schema") != "phil-ai-os-operations-reply-draft-proposal" or proposal.get("version") != 1:
        raise ReplyDraftError("unsupported reply draft proposal schema")
    if proposal.get("state") != "awaiting_operator_approval":
        raise ReplyDraftError("reply draft proposal must await operator approval")
    if proposal.get("operator_decision") is not None:
        raise ReplyDraftError("reply draft proposal operator decision must remain unset")
    authority = proposal.get("authority")
    if not isinstance(authority, dict):
        raise ReplyDraftError("reply draft authority is required")
    if authority.get("draft_only") is not True or authority.get("operator_approval_required") is not True:
        raise ReplyDraftError("reply draft must remain draft-only and operator-gated")
    if authority.get("authority_effect") != "none":
        raise ReplyDraftError("reply draft authority_effect must remain none")
    for field, value in authority.items():
        if field in {"draft_only", "operator_approval_required", "authority_effect"}:
            continue
        if value is not False:
            raise ReplyDraftError(f"reply draft authority {field} must remain false")
