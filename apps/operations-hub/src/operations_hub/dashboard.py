from __future__ import annotations

from typing import Any

from .order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from .order_quote_approval_register import OrderQuoteApprovalRequestRegister
from .order_quote_owner_decision_register import OrderQuoteOwnerDecisionPacketRegister
from .order_review import OrderReviewQueue
from .queue import OperationsQueue
from .task_queue import TaskCandidateQueue


class OperationsDashboardError(ValueError):
    pass


def _read_only(model: Any, label: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise OperationsDashboardError(f"{label} read model must be an object")
    if model.get("status") != "read_only":
        raise OperationsDashboardError(f"{label} read model must remain read_only")
    if model.get("mutation_authorized") is not False:
        raise OperationsDashboardError(f"{label} read model must remain non-authorizing")
    return model


def build_operations_dashboard(
    channel_queue: OperationsQueue,
    order_review_queue: OrderReviewQueue,
    approval_register: OrderQuoteApprovalRequestRegister,
    recommendation_register: OrderQuoteApprovalDecisionProposalRegister,
    owner_packet_register: OrderQuoteOwnerDecisionPacketRegister,
    task_queue: TaskCandidateQueue | None = None,
) -> dict[str, Any]:
    """Aggregate bounded Operations Hub workload without exposing customer payloads or granting authority."""
    if not isinstance(channel_queue, OperationsQueue):
        raise OperationsDashboardError("channel_queue must be an OperationsQueue")
    if not isinstance(order_review_queue, OrderReviewQueue):
        raise OperationsDashboardError("order_review_queue must be an OrderReviewQueue")
    if not isinstance(approval_register, OrderQuoteApprovalRequestRegister):
        raise OperationsDashboardError("approval_register must be an OrderQuoteApprovalRequestRegister")
    if not isinstance(recommendation_register, OrderQuoteApprovalDecisionProposalRegister):
        raise OperationsDashboardError(
            "recommendation_register must be an OrderQuoteApprovalDecisionProposalRegister"
        )
    if not isinstance(owner_packet_register, OrderQuoteOwnerDecisionPacketRegister):
        raise OperationsDashboardError(
            "owner_packet_register must be an OrderQuoteOwnerDecisionPacketRegister"
        )
    if task_queue is not None and not isinstance(task_queue, TaskCandidateQueue):
        raise OperationsDashboardError("task_queue must be a TaskCandidateQueue or None")

    channels = _read_only(channel_queue.read_model(), "channel_queue")
    orders = _read_only(order_review_queue.read_model(), "order_review_queue")
    approvals = _read_only(approval_register.read_model(), "approval_register")
    recommendations = _read_only(
        recommendation_register.read_model(), "recommendation_register"
    )
    owner_packets = _read_only(owner_packet_register.read_model(), "owner_packet_register")
    tasks = (
        _read_only(task_queue.read_model(), "task_queue")
        if task_queue is not None
        else {
            "task_count": 0,
            "duplicate_tasks": 0,
            "awaiting_approval": 0,
            "ready_for_operator_review": 0,
            "task_type_counts": {},
            "source_counts": {},
        }
    )

    return {
        "status": "read_only",
        "dashboard": "operations_hub_workload",
        "channels": {
            "total_events": channels.get("total_events", 0),
            "duplicate_events": channels.get("duplicate_events", 0),
            "review_required": channels.get("review_required", 0),
            "standard_queue": channels.get("standard_queue", 0),
            "source_counts": dict(channels.get("source_counts", {})),
            "intent_counts": dict(channels.get("intent_counts", {})),
        },
        "tasks": {
            "task_count": tasks.get("task_count", 0),
            "duplicate_tasks": tasks.get("duplicate_tasks", 0),
            "awaiting_approval": tasks.get("awaiting_approval", 0),
            "ready_for_operator_review": tasks.get("ready_for_operator_review", 0),
            "task_type_counts": dict(tasks.get("task_type_counts", {})),
            "source_counts": dict(tasks.get("source_counts", {})),
        },
        "orders": {
            "pending_staff_review": orders.get("pending_review", 0),
            "duplicate_handoffs": orders.get("duplicate_handoffs", 0),
        },
        "quotes": {
            "pending_approval": approvals.get("pending_approval_count", 0),
            "duplicate_approval_requests": approvals.get("duplicate_requests", 0),
            "recommendation_proposals": recommendations.get("proposal_count", 0),
            "duplicate_recommendations": recommendations.get("duplicate_proposals", 0),
        },
        "owner_review": {
            "pending_packets": owner_packets.get("packet_count", 0),
            "duplicate_packets": owner_packets.get("duplicate_packets", 0),
            "owner_decision_pending": owner_packets.get("owner_decision_pending") is True,
        },
        "privacy": {
            "raw_customer_text_exposed": False,
            "custom_notes_exposed": False,
            "reference_image_names_exposed": False,
        },
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "quote_authorized": False,
        "customer_notification_authorized": False,
        "woo_commerce_mutation_authorized": False,
        "order_creation_authorized": False,
        "payment_execution_authorized": False,
        "sms_send_authorized": False,
        "inventory_mutation_authorized": False,
        "production_publish_authorized": False,
        "mutation_authorized": False,
    }
