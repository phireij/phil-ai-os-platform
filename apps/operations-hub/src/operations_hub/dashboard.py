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
    for field, value in model.items():
        if field.endswith("_authorized") and value is not False:
            raise OperationsDashboardError(f"{label} read model {field} must remain false")
    return model


def _validated_count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OperationsDashboardError(f"{label} must be a non-negative integer")
    return value


def _validated_count_map(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise OperationsDashboardError(f"{label} must be an object")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key:
            raise OperationsDashboardError(f"{label} keys must be non-empty strings")
        result[key] = _validated_count(count, f"{label}.{key}")
    return dict(sorted(result.items()))


def _validated_items(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise OperationsDashboardError(f"{label} items must be a list")
    if any(not isinstance(item, dict) for item in value):
        raise OperationsDashboardError(f"{label} items must contain objects")
    return value


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

    channel_total_events = _validated_count(channels.get("total_events", 0), "channel total_events")
    channel_duplicate_events = _validated_count(channels.get("duplicate_events", 0), "channel duplicate_events")
    channel_review_required = _validated_count(channels.get("review_required", 0), "channel review_required")
    channel_standard_queue = _validated_count(channels.get("standard_queue", 0), "channel standard_queue")
    channel_source_counts = _validated_count_map(channels.get("source_counts", {}), "channel source_counts")
    channel_intent_counts = _validated_count_map(channels.get("intent_counts", {}), "channel intent_counts")
    if channel_review_required + channel_standard_queue != channel_total_events:
        raise OperationsDashboardError("channel queue counts must match channel total_events")
    if sum(channel_source_counts.values()) != channel_total_events:
        raise OperationsDashboardError("channel source_counts must match channel total_events")
    if sum(channel_intent_counts.values()) != channel_total_events:
        raise OperationsDashboardError("channel intent_counts must match channel total_events")

    order_items = _validated_items(orders.get("items"), "order review")
    order_pending_review = _validated_count(orders.get("pending_review", 0), "order pending_review")
    order_duplicate_handoffs = _validated_count(orders.get("duplicate_handoffs", 0), "order duplicate_handoffs")
    if order_pending_review != len(order_items):
        raise OperationsDashboardError("order pending_review must match order review items")

    approval_items = _validated_items(approvals.get("items"), "approval")
    pending_approval_count = _validated_count(
        approvals.get("pending_approval_count", 0), "approval pending_approval_count"
    )
    duplicate_approval_requests = _validated_count(
        approvals.get("duplicate_requests", 0), "approval duplicate_requests"
    )
    if pending_approval_count != len(approval_items):
        raise OperationsDashboardError("approval pending_approval_count must match approval items")

    recommendation_items = _validated_items(recommendations.get("items"), "recommendation")
    recommendation_proposal_count = _validated_count(
        recommendations.get("proposal_count", 0), "recommendation proposal_count"
    )
    duplicate_recommendations = _validated_count(
        recommendations.get("duplicate_proposals", 0), "recommendation duplicate_proposals"
    )
    if recommendation_proposal_count != len(recommendation_items):
        raise OperationsDashboardError("recommendation proposal_count must match recommendation items")

    owner_packet_items = _validated_items(owner_packets.get("items"), "owner packet")
    owner_packet_count = _validated_count(owner_packets.get("packet_count", 0), "owner packet_count")
    duplicate_owner_packets = _validated_count(owner_packets.get("duplicate_packets", 0), "owner duplicate_packets")
    if owner_packet_count != len(owner_packet_items):
        raise OperationsDashboardError("owner packet_count must match owner packet items")
    owner_decision_pending = owner_packets.get("owner_decision_pending")
    if owner_decision_pending is not bool(owner_packet_items):
        raise OperationsDashboardError("owner_decision_pending must match owner packet items")

    return {
        "status": "read_only",
        "dashboard": "operations_hub_workload",
        "channels": {
            "total_events": channel_total_events,
            "duplicate_events": channel_duplicate_events,
            "review_required": channel_review_required,
            "standard_queue": channel_standard_queue,
            "source_counts": channel_source_counts,
            "intent_counts": channel_intent_counts,
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
            "pending_staff_review": order_pending_review,
            "duplicate_handoffs": order_duplicate_handoffs,
        },
        "quotes": {
            "pending_approval": pending_approval_count,
            "duplicate_approval_requests": duplicate_approval_requests,
            "recommendation_proposals": recommendation_proposal_count,
            "duplicate_recommendations": duplicate_recommendations,
        },
        "owner_review": {
            "pending_packets": owner_packet_count,
            "duplicate_packets": duplicate_owner_packets,
            "owner_decision_pending": owner_decision_pending,
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
