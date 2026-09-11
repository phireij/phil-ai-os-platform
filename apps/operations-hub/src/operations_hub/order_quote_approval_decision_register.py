from __future__ import annotations

from typing import Any

from .order_quote_approval_decision import (
    OrderQuoteApprovalDecisionError,
    SUPPORTED_QUOTE_APPROVAL_RECOMMENDATIONS,
)


class OrderQuoteApprovalDecisionProposalRegister:
    """Read-only in-memory register for bounded quote approval recommendation proposals."""

    def __init__(self) -> None:
        self._proposals: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def register(self, proposal: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(proposal, dict):
            raise OrderQuoteApprovalDecisionError("decision proposal must be an object")
        if proposal.get("schema") != "rubys-order-quote-approval-decision-proposal" or proposal.get("version") != 1:
            raise OrderQuoteApprovalDecisionError("unsupported quote approval decision proposal schema")
        if proposal.get("state") != "recommendation_only":
            raise OrderQuoteApprovalDecisionError("decision proposal must remain recommendation_only")
        if proposal.get("recommendation") not in SUPPORTED_QUOTE_APPROVAL_RECOMMENDATIONS:
            raise OrderQuoteApprovalDecisionError("unsupported quote approval recommendation")
        if proposal.get("mutation_authorized") is not False:
            raise OrderQuoteApprovalDecisionError("decision proposal must remain non-authorizing")

        effects = proposal.get("effects")
        if not isinstance(effects, dict):
            raise OrderQuoteApprovalDecisionError("decision proposal effects must be an object")
        if not effects or any(value is not False for value in effects.values()):
            raise OrderQuoteApprovalDecisionError("decision proposal effects must remain false")

        proposal_id = proposal.get("decision_proposal_id")
        request_id = proposal.get("approval_request_id")
        correlation_id = proposal.get("lifecycle_correlation_id")
        if not isinstance(proposal_id, str) or not proposal_id.startswith("quote-approval-proposal:"):
            raise OrderQuoteApprovalDecisionError("invalid decision_proposal_id")
        if not isinstance(request_id, str) or not request_id.startswith("quote-approval:"):
            raise OrderQuoteApprovalDecisionError("invalid approval_request_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise OrderQuoteApprovalDecisionError("decision proposal is missing lifecycle_correlation_id")

        pricing = proposal.get("pricing")
        if not isinstance(pricing, dict):
            raise OrderQuoteApprovalDecisionError("decision proposal pricing must be an object")
        quote_amount = pricing.get("quote_amount")
        shipping_amount = pricing.get("shipping_amount")
        total_amount = pricing.get("total_amount")
        for value in (quote_amount, shipping_amount, total_amount):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OrderQuoteApprovalDecisionError("decision proposal pricing must contain non-negative integer JPY amounts")
        if total_amount != quote_amount + shipping_amount:
            raise OrderQuoteApprovalDecisionError("decision proposal total_amount must reconcile")
        if pricing.get("currency") != "JPY" or pricing.get("customer_accepted") is not False:
            raise OrderQuoteApprovalDecisionError("decision proposal pricing state is invalid")

        if proposal_id in self._proposals:
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "decision_proposal_id": proposal_id,
                "approval_request_id": request_id,
                "mutation_authorized": False,
            }

        self._proposals[proposal_id] = dict(proposal)
        return {
            "accepted": True,
            "duplicate": False,
            "decision_proposal_id": proposal_id,
            "approval_request_id": request_id,
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        items = []
        for proposal in sorted(self._proposals.values(), key=lambda item: item["decision_proposal_id"]):
            pricing = proposal["pricing"]
            items.append({
                "decision_proposal_id": proposal["decision_proposal_id"],
                "approval_request_id": proposal["approval_request_id"],
                "lifecycle_correlation_id": proposal["lifecycle_correlation_id"],
                "recommendation": proposal["recommendation"],
                "total_amount": pricing["total_amount"],
                "currency": pricing["currency"],
                "has_note": bool(proposal.get("note")),
                "approval_decided": False,
                "quote_authorized": False,
                "mutation_authorized": False,
            })
        return {
            "status": "read_only",
            "register": "order_quote_approval_decision_proposals",
            "proposal_count": len(items),
            "duplicate_proposals": self._duplicates,
            "items": items,
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "mutation_authorized": False,
        }

    def proposal_detail(self, decision_proposal_id: str) -> dict[str, Any] | None:
        proposal = self._proposals.get(decision_proposal_id)
        if proposal is None:
            return None
        return dict(proposal)
