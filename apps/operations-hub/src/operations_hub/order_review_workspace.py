from __future__ import annotations

from typing import Any

from .order_review import OrderReviewQueue
from .order_review_register import OrderReviewProposalRegister


class OrderReviewWorkspaceError(ValueError):
    pass


def _require_read_only(model: Any, name: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise OrderReviewWorkspaceError(f"{name} read model must be an object")
    if model.get("status") != "read_only" or model.get("mutation_authorized") is not False:
        raise OrderReviewWorkspaceError(f"{name} read model must remain read_only and non-authorizing")
    return model


def build_order_review_workspace(
    review_queue: OrderReviewQueue,
    proposal_register: OrderReviewProposalRegister,
) -> dict[str, Any]:
    if not isinstance(review_queue, OrderReviewQueue):
        raise OrderReviewWorkspaceError("review_queue must be an OrderReviewQueue")
    if not isinstance(proposal_register, OrderReviewProposalRegister):
        raise OrderReviewWorkspaceError("proposal_register must be an OrderReviewProposalRegister")

    queue_model = _require_read_only(review_queue.read_model(), "review_queue")
    proposal_model = _require_read_only(proposal_register.read_model(), "proposal_register")

    proposals_by_correlation: dict[str, list[dict[str, Any]]] = {}
    for proposal in proposal_model.get("items", []):
        correlation_id = proposal.get("lifecycle_correlation_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise OrderReviewWorkspaceError("proposal is missing lifecycle_correlation_id")
        proposals_by_correlation.setdefault(correlation_id, []).append(proposal)

    rows: list[dict[str, Any]] = []
    queue_correlation_ids: set[str] = set()
    for item in queue_model.get("items", []):
        correlation_id = item.get("lifecycle_correlation_id")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise OrderReviewWorkspaceError("review item is missing lifecycle_correlation_id")
        queue_correlation_ids.add(correlation_id)
        proposals = proposals_by_correlation.get(correlation_id, [])
        rows.append({
            "lifecycle_correlation_id": correlation_id,
            "review_state": item.get("review_state"),
            "review_reason": item.get("review_reason"),
            "fulfillment_method": item.get("fulfillment_method"),
            "requested_date": item.get("requested_date"),
            "cake_type": item.get("cake_type"),
            "reference_image_count": item.get("reference_image_count"),
            "has_custom_notes": item.get("has_custom_notes") is True,
            "proposal_count": len(proposals),
            "proposal_decisions": sorted({proposal["decision"] for proposal in proposals}),
            "has_review_proposal": bool(proposals),
            "mutation_authorized": False,
        })

    orphan_proposals = sorted(
        correlation_id
        for correlation_id in proposals_by_correlation
        if correlation_id not in queue_correlation_ids
    )
    if orphan_proposals:
        raise OrderReviewWorkspaceError("proposal register contains source reviews absent from the review queue")

    pending_without_proposal = sum(1 for row in rows if not row["has_review_proposal"])
    return {
        "status": "read_only",
        "workspace": "order_intake_staff_review",
        "pending_review": len(rows),
        "proposal_count": proposal_model.get("proposal_count", 0),
        "pending_without_proposal": pending_without_proposal,
        "items": sorted(rows, key=lambda item: item["lifecycle_correlation_id"]),
        "mutation_authorized": False,
        "order_creation_authorized": False,
        "payment_execution_authorized": False,
        "sms_send_authorized": False,
        "inventory_mutation_authorized": False,
        "production_publish_authorized": False,
    }
