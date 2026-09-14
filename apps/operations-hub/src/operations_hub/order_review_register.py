from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .order_review_decision import SUPPORTED_REVIEW_DECISIONS, OrderReviewDecisionError


class OrderReviewProposalRegister:
    """Read-only, in-memory register for non-authorizing staff review proposals."""

    def __init__(self) -> None:
        self._proposals: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def register(self, proposal: dict[str, Any], review_detail: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(proposal, dict):
            raise OrderReviewDecisionError("proposal must be an object")
        if not isinstance(review_detail, dict):
            raise OrderReviewDecisionError("review_detail must be an object")
        if proposal.get("schema") != "rubys-order-review-decision-proposal" or proposal.get("version") != 1:
            raise OrderReviewDecisionError("unsupported order review proposal schema")
        if proposal.get("state") != "proposal_only":
            raise OrderReviewDecisionError("proposal must remain proposal_only")
        if proposal.get("mutation_authorized") is not False:
            raise OrderReviewDecisionError("proposal must remain non-authorizing")
        if proposal.get("decision") not in SUPPORTED_REVIEW_DECISIONS:
            raise OrderReviewDecisionError("unsupported review decision")
        if review_detail.get("review_state") != "pending_staff_review":
            raise OrderReviewDecisionError("source review must remain pending_staff_review")
        authority = review_detail.get("authority")
        if not isinstance(authority, dict) or authority.get("mutation_authorized") is not False:
            raise OrderReviewDecisionError("source review must remain non-authorizing")
        if proposal.get("lifecycle_correlation_id") != review_detail.get("lifecycle_correlation_id"):
            raise OrderReviewDecisionError("proposal correlation does not match source review")

        expected_fingerprint = hashlib.sha256(
            self._canonical_json(review_detail).encode("utf-8")
        ).hexdigest()
        if proposal.get("source_review_fingerprint") != expected_fingerprint:
            raise OrderReviewDecisionError("proposal source review fingerprint mismatch")

        effects = proposal.get("effects")
        if not isinstance(effects, dict):
            raise OrderReviewDecisionError("proposal effects must be an object")
        expected_effects = (
            "quote_authorized",
            "fulfillment_confirmed",
            "order_creation_authorized",
            "payment_execution_authorized",
            "sms_send_authorized",
            "inventory_mutation_authorized",
            "woo_commerce_mutation_authorized",
            "production_publish_authorized",
        )
        for field in expected_effects:
            if effects.get(field) is not False:
                raise OrderReviewDecisionError(f"proposal effect {field} must remain false")

        proposal_id = proposal.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id.startswith("order-review:"):
            raise OrderReviewDecisionError("invalid proposal_id")
        if proposal_id in self._proposals:
            if proposal != self._proposals[proposal_id]:
                raise OrderReviewDecisionError("proposal_id conflicts with existing proposal content")
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "proposal_id": proposal_id,
                "mutation_authorized": False,
            }

        self._proposals[proposal_id] = copy.deepcopy(proposal)
        return {
            "accepted": True,
            "duplicate": False,
            "proposal_id": proposal_id,
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        items = [
            {
                "proposal_id": proposal["proposal_id"],
                "lifecycle_correlation_id": proposal["lifecycle_correlation_id"],
                "decision": proposal["decision"],
                "reviewer_ref": proposal["reviewer_ref"],
                "has_note": bool(proposal.get("note")),
                "state": proposal["state"],
                "mutation_authorized": False,
            }
            for proposal in sorted(self._proposals.values(), key=lambda item: item["proposal_id"])
        ]
        return {
            "status": "read_only",
            "register": "order_review_decision_proposals",
            "proposal_count": len(items),
            "duplicate_proposals": self._duplicates,
            "items": items,
            "mutation_authorized": False,
        }

    def proposal_detail(self, proposal_id: str) -> dict[str, Any] | None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return None
        return {
            "proposal_id": proposal["proposal_id"],
            "lifecycle_correlation_id": proposal["lifecycle_correlation_id"],
            "decision": proposal["decision"],
            "reviewer_ref": proposal["reviewer_ref"],
            "note": proposal.get("note", ""),
            "state": proposal["state"],
            "effects": copy.deepcopy(proposal["effects"]),
            "mutation_authorized": False,
        }
