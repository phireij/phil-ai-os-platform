from __future__ import annotations

from typing import Any

from .order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from .order_quote_approval_decision_workspace import (
    OrderQuoteApprovalDecisionWorkspaceError,
    build_order_quote_approval_decision_workspace,
)
from .order_quote_approval_register import OrderQuoteApprovalRequestRegister


class OrderQuoteOwnerDecisionPacketError(ValueError):
    pass


def build_order_quote_owner_decision_packet(
    approval_register: OrderQuoteApprovalRequestRegister,
    proposal_register: OrderQuoteApprovalDecisionProposalRegister,
    *,
    approval_request_id: str,
) -> dict[str, Any]:
    """Prepare one recommendation-ready quote packet without making the owner decision."""
    if not isinstance(approval_request_id, str) or not approval_request_id.strip():
        raise OrderQuoteOwnerDecisionPacketError("approval_request_id is required")

    try:
        workspace = build_order_quote_approval_decision_workspace(
            approval_register,
            proposal_register,
        )
    except OrderQuoteApprovalDecisionWorkspaceError as exc:
        raise OrderQuoteOwnerDecisionPacketError(str(exc)) from exc

    if workspace.get("status") != "read_only" or workspace.get("mutation_authorized") is not False:
        raise OrderQuoteOwnerDecisionPacketError("decision workspace must remain read_only and non-authorizing")
    for field in (
        "approval_decided",
        "quote_authorized",
        "customer_notification_authorized",
        "fulfillment_confirmed",
        "woo_commerce_mutation_authorized",
        "order_creation_authorized",
        "payment_execution_authorized",
        "sms_send_authorized",
        "inventory_mutation_authorized",
        "production_publish_authorized",
        "mutation_authorized",
    ):
        if workspace.get(field) is not False:
            raise OrderQuoteOwnerDecisionPacketError(f"decision workspace {field} must remain false")

    target = None
    normalized_id = approval_request_id.strip()
    for item in workspace.get("items", []):
        if item.get("approval_request_id") == normalized_id:
            target = item
            break
    if not isinstance(target, dict):
        raise OrderQuoteOwnerDecisionPacketError("approval request is not present in the decision workspace")
    if target.get("recommendation_status") != "recommendation_proposed":
        raise OrderQuoteOwnerDecisionPacketError(
            "approval request must have exactly one bounded recommendation before owner review"
        )

    recommendations = target.get("recommendations")
    proposal_ids = target.get("decision_proposal_ids")
    if not isinstance(recommendations, list) or len(recommendations) != 1:
        raise OrderQuoteOwnerDecisionPacketError("owner packet requires exactly one recommendation")
    if not isinstance(proposal_ids, list) or not proposal_ids:
        raise OrderQuoteOwnerDecisionPacketError("owner packet requires at least one source proposal")
    if target.get("decision") is not None or target.get("approval_decided") is not False:
        raise OrderQuoteOwnerDecisionPacketError("approval decision must remain unset")

    recommendation = recommendations[0]
    if recommendation not in {"recommend_quote_approval", "request_quote_revision"}:
        raise OrderQuoteOwnerDecisionPacketError("unsupported quote approval recommendation")

    return {
        "schema": "rubys-order-quote-owner-decision-packet",
        "version": 1,
        "state": "awaiting_owner_decision",
        "approval_request_id": normalized_id,
        "lifecycle_correlation_id": target.get("lifecycle_correlation_id"),
        "source_draft_id": target.get("source_draft_id"),
        "decision_proposal_ids": list(proposal_ids),
        "recommendation": recommendation,
        "pricing": {
            "quote_amount": target.get("quote_amount"),
            "shipping_amount": target.get("shipping_amount"),
            "total_amount": target.get("total_amount"),
            "currency": target.get("currency"),
            "customer_accepted": False,
        },
        "owner_decision": {
            "required": True,
            "decision": None,
            "decided_by": None,
            "decided_at": None,
        },
        "authority": {
            "owner_review_only": True,
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "fulfillment_confirmed": False,
            "woo_commerce_mutation_authorized": False,
            "order_creation_authorized": False,
            "payment_execution_authorized": False,
            "sms_send_authorized": False,
            "inventory_mutation_authorized": False,
            "production_publish_authorized": False,
            "mutation_authorized": False,
        },
    }
