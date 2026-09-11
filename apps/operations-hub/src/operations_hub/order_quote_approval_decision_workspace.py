from __future__ import annotations

from typing import Any

from .order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from .order_quote_approval_register import OrderQuoteApprovalRequestRegister


class OrderQuoteApprovalDecisionWorkspaceError(ValueError):
    pass


def _require_read_only(model: Any, name: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise OrderQuoteApprovalDecisionWorkspaceError(f"{name} read model must be an object")
    if model.get("status") != "read_only" or model.get("mutation_authorized") is not False:
        raise OrderQuoteApprovalDecisionWorkspaceError(
            f"{name} read model must remain read_only and non-authorizing"
        )
    return model


def build_order_quote_approval_decision_workspace(
    approval_register: OrderQuoteApprovalRequestRegister,
    proposal_register: OrderQuoteApprovalDecisionProposalRegister,
) -> dict[str, Any]:
    """Correlate pending quote approvals with recommendation-only proposals."""
    if not isinstance(approval_register, OrderQuoteApprovalRequestRegister):
        raise OrderQuoteApprovalDecisionWorkspaceError(
            "approval_register must be an OrderQuoteApprovalRequestRegister"
        )
    if not isinstance(proposal_register, OrderQuoteApprovalDecisionProposalRegister):
        raise OrderQuoteApprovalDecisionWorkspaceError(
            "proposal_register must be an OrderQuoteApprovalDecisionProposalRegister"
        )

    approval_model = _require_read_only(approval_register.read_model(), "approval_register")
    proposal_model = _require_read_only(proposal_register.read_model(), "proposal_register")

    approvals_by_id: dict[str, dict[str, Any]] = {}
    for request in approval_model.get("items", []):
        request_id = request.get("approval_request_id")
        if not isinstance(request_id, str) or not request_id:
            raise OrderQuoteApprovalDecisionWorkspaceError(
                "approval request is missing approval_request_id"
            )
        approvals_by_id[request_id] = request

    proposals_by_request: dict[str, list[dict[str, Any]]] = {}
    for proposal in proposal_model.get("items", []):
        request_id = proposal.get("approval_request_id")
        if not isinstance(request_id, str) or not request_id:
            raise OrderQuoteApprovalDecisionWorkspaceError(
                "decision proposal is missing approval_request_id"
            )
        proposals_by_request.setdefault(request_id, []).append(proposal)

    orphan_request_ids = sorted(
        request_id
        for request_id in proposals_by_request
        if request_id not in approvals_by_id
    )
    if orphan_request_ids:
        raise OrderQuoteApprovalDecisionWorkspaceError(
            "decision proposal register contains proposals whose approval requests are absent"
        )

    rows: list[dict[str, Any]] = []
    for request_id, request in approvals_by_id.items():
        proposals = proposals_by_request.get(request_id, [])
        request_detail = approval_register.request_detail(request_id)
        if not isinstance(request_detail, dict):
            raise OrderQuoteApprovalDecisionWorkspaceError(
                "approval request detail is unavailable"
            )
        request_pricing = request_detail.get("pricing")
        if not isinstance(request_pricing, dict):
            raise OrderQuoteApprovalDecisionWorkspaceError(
                "approval request detail pricing is unavailable"
            )

        correlation_id = request.get("lifecycle_correlation_id")
        recommendations: list[str] = []
        proposal_ids: list[str] = []
        for proposal in proposals:
            if proposal.get("lifecycle_correlation_id") != correlation_id:
                raise OrderQuoteApprovalDecisionWorkspaceError(
                    "decision proposal correlation does not match approval request"
                )
            if proposal.get("total_amount") != request.get("total_amount"):
                raise OrderQuoteApprovalDecisionWorkspaceError(
                    "decision proposal total_amount does not match approval request"
                )
            if proposal.get("currency") != request.get("currency"):
                raise OrderQuoteApprovalDecisionWorkspaceError(
                    "decision proposal currency does not match approval request"
                )

            proposal_id = proposal.get("decision_proposal_id")
            proposal_detail = proposal_register.proposal_detail(proposal_id)
            if not isinstance(proposal_detail, dict):
                raise OrderQuoteApprovalDecisionWorkspaceError(
                    "decision proposal detail is unavailable"
                )
            proposal_pricing = proposal_detail.get("pricing")
            if not isinstance(proposal_pricing, dict):
                raise OrderQuoteApprovalDecisionWorkspaceError(
                    "decision proposal detail pricing is unavailable"
                )
            for field in ("quote_amount", "shipping_amount", "total_amount", "currency"):
                if proposal_pricing.get(field) != request_pricing.get(field):
                    raise OrderQuoteApprovalDecisionWorkspaceError(
                        f"decision proposal {field} does not match approval request"
                    )
            if proposal_pricing.get("customer_accepted") is not False:
                raise OrderQuoteApprovalDecisionWorkspaceError(
                    "decision proposal customer_accepted must remain false"
                )

            proposal_ids.append(proposal_id)
            recommendations.append(proposal["recommendation"])

        unique_recommendations = sorted(set(recommendations))
        if not proposals:
            recommendation_status = "recommendation_not_proposed"
        elif len(unique_recommendations) == 1:
            recommendation_status = "recommendation_proposed"
        else:
            recommendation_status = "recommendation_conflict"

        rows.append({
            "approval_request_id": request_id,
            "lifecycle_correlation_id": correlation_id,
            "source_draft_id": request.get("source_draft_id"),
            "approval_state": request.get("state"),
            "quote_amount": request.get("quote_amount"),
            "shipping_amount": request.get("shipping_amount"),
            "total_amount": request.get("total_amount"),
            "currency": request.get("currency"),
            "proposal_count": len(proposals),
            "decision_proposal_ids": sorted(proposal_ids),
            "recommendations": unique_recommendations,
            "recommendation_status": recommendation_status,
            "decision": None,
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "mutation_authorized": False,
        })

    return {
        "status": "read_only",
        "workspace": "order_quote_approval_decision_review",
        "approval_request_count": len(rows),
        "awaiting_recommendation_count": sum(
            1 for row in rows if row["recommendation_status"] == "recommendation_not_proposed"
        ),
        "recommendation_ready_count": sum(
            1 for row in rows if row["recommendation_status"] == "recommendation_proposed"
        ),
        "recommendation_conflict_count": sum(
            1 for row in rows if row["recommendation_status"] == "recommendation_conflict"
        ),
        "items": sorted(rows, key=lambda item: item["approval_request_id"]),
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
    }
