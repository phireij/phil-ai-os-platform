from __future__ import annotations

from typing import Any

from .order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from .order_quote_approval_decision_workspace import (
    OrderQuoteApprovalDecisionWorkspaceError,
    build_order_quote_approval_decision_workspace,
)
from .order_quote_approval_register import OrderQuoteApprovalRequestRegister
from .order_quote_owner_decision_register import OrderQuoteOwnerDecisionPacketRegister


class OrderQuoteOwnerDecisionWorkspaceError(ValueError):
    pass


def _require_read_only(model: Any, name: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise OrderQuoteOwnerDecisionWorkspaceError(f"{name} read model must be an object")
    if model.get("status") != "read_only" or model.get("mutation_authorized") is not False:
        raise OrderQuoteOwnerDecisionWorkspaceError(
            f"{name} read model must remain read_only and non-authorizing"
        )
    return model


def build_order_quote_owner_decision_workspace(
    approval_register: OrderQuoteApprovalRequestRegister,
    proposal_register: OrderQuoteApprovalDecisionProposalRegister,
    packet_register: OrderQuoteOwnerDecisionPacketRegister,
) -> dict[str, Any]:
    """Correlate owner-review packets with current recommendation evidence without deciding."""
    if not isinstance(approval_register, OrderQuoteApprovalRequestRegister):
        raise OrderQuoteOwnerDecisionWorkspaceError(
            "approval_register must be an OrderQuoteApprovalRequestRegister"
        )
    if not isinstance(proposal_register, OrderQuoteApprovalDecisionProposalRegister):
        raise OrderQuoteOwnerDecisionWorkspaceError(
            "proposal_register must be an OrderQuoteApprovalDecisionProposalRegister"
        )
    if not isinstance(packet_register, OrderQuoteOwnerDecisionPacketRegister):
        raise OrderQuoteOwnerDecisionWorkspaceError(
            "packet_register must be an OrderQuoteOwnerDecisionPacketRegister"
        )

    try:
        decision_workspace = build_order_quote_approval_decision_workspace(
            approval_register,
            proposal_register,
        )
    except OrderQuoteApprovalDecisionWorkspaceError as exc:
        raise OrderQuoteOwnerDecisionWorkspaceError(str(exc)) from exc

    decision_workspace = _require_read_only(decision_workspace, "decision_workspace")
    packet_model = _require_read_only(packet_register.read_model(), "packet_register")

    decision_rows: dict[str, dict[str, Any]] = {}
    for row in decision_workspace.get("items", []):
        request_id = row.get("approval_request_id")
        if not isinstance(request_id, str) or not request_id:
            raise OrderQuoteOwnerDecisionWorkspaceError(
                "decision workspace row is missing approval_request_id"
            )
        decision_rows[request_id] = row

    packets_by_request: dict[str, dict[str, Any]] = {}
    for packet in packet_model.get("items", []):
        request_id = packet.get("approval_request_id")
        if not isinstance(request_id, str) or not request_id:
            raise OrderQuoteOwnerDecisionWorkspaceError(
                "owner packet summary is missing approval_request_id"
            )
        if request_id in packets_by_request:
            raise OrderQuoteOwnerDecisionWorkspaceError(
                "owner packet register contains duplicate request summaries"
            )
        packets_by_request[request_id] = packet

    orphan_packets = sorted(
        request_id for request_id in packets_by_request if request_id not in decision_rows
    )
    if orphan_packets:
        raise OrderQuoteOwnerDecisionWorkspaceError(
            "owner packet register contains packets whose approval requests are absent"
        )

    items: list[dict[str, Any]] = []
    for request_id, row in decision_rows.items():
        packet_summary = packets_by_request.get(request_id)
        recommendation_status = row.get("recommendation_status")
        recommendations = row.get("recommendations")
        if not isinstance(recommendations, list):
            raise OrderQuoteOwnerDecisionWorkspaceError(
                "decision workspace recommendations must be a list"
            )

        if packet_summary is None:
            if recommendation_status == "recommendation_proposed":
                owner_review_status = "ready_for_owner_packet"
            elif recommendation_status == "recommendation_conflict":
                owner_review_status = "blocked_recommendation_conflict"
            else:
                owner_review_status = "awaiting_recommendation"
        else:
            if recommendation_status != "recommendation_proposed" or len(recommendations) != 1:
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet is stale because recommendation evidence is not singular"
                )
            packet_detail = packet_register.packet_detail(request_id)
            if not isinstance(packet_detail, dict):
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet detail is unavailable"
                )
            if packet_detail.get("state") != "awaiting_owner_decision":
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet must remain awaiting_owner_decision"
                )
            if packet_detail.get("lifecycle_correlation_id") != row.get("lifecycle_correlation_id"):
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet correlation does not match current approval evidence"
                )
            if packet_detail.get("source_draft_id") != row.get("source_draft_id"):
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet source draft does not match current approval evidence"
                )
            if packet_detail.get("recommendation") != recommendations[0]:
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet recommendation does not match current approval evidence"
                )

            pricing = packet_detail.get("pricing")
            if not isinstance(pricing, dict):
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet pricing detail is unavailable"
                )
            for field in ("quote_amount", "shipping_amount", "total_amount", "currency"):
                if pricing.get(field) != row.get(field):
                    raise OrderQuoteOwnerDecisionWorkspaceError(
                        f"owner packet {field} does not match current approval evidence"
                    )
            if pricing.get("customer_accepted") is not False:
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet customer_accepted must remain false"
                )

            source_proposals = packet_detail.get("decision_proposal_ids")
            current_proposals = row.get("decision_proposal_ids")
            if not isinstance(source_proposals, list) or not isinstance(current_proposals, list):
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet proposal evidence is unavailable"
                )
            if sorted(source_proposals) != sorted(current_proposals):
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner packet source proposals do not match current approval evidence"
                )

            owner_decision = packet_detail.get("owner_decision")
            if not isinstance(owner_decision, dict):
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner decision metadata is unavailable"
                )
            if owner_decision.get("decision") is not None:
                raise OrderQuoteOwnerDecisionWorkspaceError(
                    "owner decision must remain unset"
                )
            owner_review_status = "awaiting_owner_decision"

        items.append({
            "approval_request_id": request_id,
            "lifecycle_correlation_id": row.get("lifecycle_correlation_id"),
            "source_draft_id": row.get("source_draft_id"),
            "recommendation_status": recommendation_status,
            "recommendation": recommendations[0] if len(recommendations) == 1 else None,
            "quote_amount": row.get("quote_amount"),
            "shipping_amount": row.get("shipping_amount"),
            "total_amount": row.get("total_amount"),
            "currency": row.get("currency"),
            "owner_review_status": owner_review_status,
            "owner_decision": None,
            "approval_decided": False,
            "quote_authorized": False,
            "customer_notification_authorized": False,
            "mutation_authorized": False,
        })

    return {
        "status": "read_only",
        "workspace": "order_quote_owner_decision_review",
        "approval_request_count": len(items),
        "ready_for_owner_packet_count": sum(
            1 for item in items if item["owner_review_status"] == "ready_for_owner_packet"
        ),
        "awaiting_owner_decision_count": sum(
            1 for item in items if item["owner_review_status"] == "awaiting_owner_decision"
        ),
        "awaiting_recommendation_count": sum(
            1 for item in items if item["owner_review_status"] == "awaiting_recommendation"
        ),
        "blocked_recommendation_conflict_count": sum(
            1 for item in items if item["owner_review_status"] == "blocked_recommendation_conflict"
        ),
        "items": sorted(items, key=lambda item: item["approval_request_id"]),
        "owner_decision_pending": any(
            item["owner_review_status"] == "awaiting_owner_decision" for item in items
        ),
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
