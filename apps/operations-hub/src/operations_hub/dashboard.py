from __future__ import annotations

from collections import Counter
from typing import Any

from .order_quote_approval_decision_register import OrderQuoteApprovalDecisionProposalRegister
from .order_quote_approval_register import OrderQuoteApprovalRequestRegister
from .order_quote_owner_decision_register import OrderQuoteOwnerDecisionPacketRegister
from .order_review import OrderReviewQueue
from .queue import OperationsQueue
from .task_queue import TaskCandidateQueue


class OperationsDashboardError(ValueError):
    pass


def _require_non_authorizing(record: dict[str, Any], label: str) -> None:
    for field, value in record.items():
        if field.endswith("_authorized") and value is not False:
            raise OperationsDashboardError(f"{label} {field} must remain false")


def _read_only(model: Any, label: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise OperationsDashboardError(f"{label} read model must be an object")
    if model.get("status") != "read_only":
        raise OperationsDashboardError(f"{label} read model must remain read_only")
    _require_non_authorizing(model, f"{label} read model")
    items = model.get("items")
    if items is not None:
        if not isinstance(items, list):
            raise OperationsDashboardError(f"{label} read model items must be a list")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise OperationsDashboardError(f"{label} read model item[{index}] must be an object")
            _require_non_authorizing(item, f"{label} read model item[{index}]")
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


def _item_string_counts(items: list[dict[str, Any]], field: str, label: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for index, item in enumerate(items):
        value = item.get(field)
        if not isinstance(value, str) or not value:
            raise OperationsDashboardError(f"{label} item[{index}] {field} must be a non-empty string")
        counts[value] += 1
    return dict(sorted(counts.items()))


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

    channel_items = _validated_items(channels.get("items"), "channel")
    channel_total_events = _validated_count(channels.get("total_events", 0), "channel total_events")
    channel_duplicate_events = _validated_count(channels.get("duplicate_events", 0), "channel duplicate_events")
    channel_review_required = _validated_count(channels.get("review_required", 0), "channel review_required")
    channel_standard_queue = _validated_count(channels.get("standard_queue", 0), "channel standard_queue")
    channel_source_counts = _validated_count_map(channels.get("source_counts", {}), "channel source_counts")
    channel_intent_counts = _validated_count_map(channels.get("intent_counts", {}), "channel intent_counts")
    if channel_total_events != len(channel_items):
        raise OperationsDashboardError("channel total_events must match channel items")
    if channel_review_required + channel_standard_queue != channel_total_events:
        raise OperationsDashboardError("channel queue counts must match channel total_events")
    if sum(channel_source_counts.values()) != channel_total_events:
        raise OperationsDashboardError("channel source_counts must match channel total_events")
    if sum(channel_intent_counts.values()) != channel_total_events:
        raise OperationsDashboardError("channel intent_counts must match channel total_events")
    computed_channel_sources = _item_string_counts(channel_items, "source", "channel")
    computed_channel_intents = _item_string_counts(channel_items, "normalized_intent", "channel")
    computed_review_required = 0
    for index, item in enumerate(channel_items):
        review_required = item.get("review_required")
        if not isinstance(review_required, bool):
            raise OperationsDashboardError(f"channel item[{index}] review_required must be boolean")
        if review_required:
            computed_review_required += 1
    if channel_source_counts != computed_channel_sources:
        raise OperationsDashboardError("channel source_counts must match channel items")
    if channel_intent_counts != computed_channel_intents:
        raise OperationsDashboardError("channel intent_counts must match channel items")
    if channel_review_required != computed_review_required:
        raise OperationsDashboardError("channel review_required must match channel items")
    if channel_standard_queue != len(channel_items) - computed_review_required:
        raise OperationsDashboardError("channel standard_queue must match channel items")

    task_count = _validated_count(tasks.get("task_count", 0), "task task_count")
    task_duplicate_tasks = _validated_count(tasks.get("duplicate_tasks", 0), "task duplicate_tasks")
    task_awaiting_approval = _validated_count(tasks.get("awaiting_approval", 0), "task awaiting_approval")
    task_ready_for_operator_review = _validated_count(
        tasks.get("ready_for_operator_review", 0), "task ready_for_operator_review"
    )
    task_type_counts = _validated_count_map(tasks.get("task_type_counts", {}), "task task_type_counts")
    task_source_counts = _validated_count_map(tasks.get("source_counts", {}), "task source_counts")
    if task_awaiting_approval + task_ready_for_operator_review != task_count:
        raise OperationsDashboardError("task state counts must match task task_count")
    if sum(task_type_counts.values()) != task_count:
        raise OperationsDashboardError("task task_type_counts must match task task_count")
    if sum(task_source_counts.values()) != task_count:
        raise OperationsDashboardError("task source_counts must match task task_count")
    if task_queue is not None:
        task_items = _validated_items(tasks.get("items"), "task")
        if task_count != len(task_items):
            raise OperationsDashboardError("task task_count must match task items")
        computed_task_sources = _item_string_counts(task_items, "source", "task")
        computed_task_types = _item_string_counts(task_items, "task_type", "task")
        computed_task_states = _item_string_counts(task_items, "state", "task")
        if set(computed_task_states) - {"awaiting_approval", "ready_for_operator_review"}:
            raise OperationsDashboardError("task items contain unsupported states")
        if task_source_counts != computed_task_sources:
            raise OperationsDashboardError("task source_counts must match task items")
        if task_type_counts != computed_task_types:
            raise OperationsDashboardError("task task_type_counts must match task items")
        if task_awaiting_approval != computed_task_states.get("awaiting_approval", 0):
            raise OperationsDashboardError("task awaiting_approval must match task items")
        if task_ready_for_operator_review != computed_task_states.get("ready_for_operator_review", 0):
            raise OperationsDashboardError("task ready_for_operator_review must match task items")

    order_items = _validated_items(orders.get("items"), "order review")
    order_pending_review = _validated_count(orders.get("pending_review", 0), "order pending_review")
    order_duplicate_handoffs = _validated_count(orders.get("duplicate_handoffs", 0), "order duplicate_handoffs")
    if order_pending_review != len(order_items):
        raise OperationsDashboardError("order pending_review must match order review items")
    for index, item in enumerate(order_items):
        if item.get("review_state") != "pending_staff_review":
            raise OperationsDashboardError(
                f"order review item[{index}] review_state must remain pending_staff_review"
            )

    approval_items = _validated_items(approvals.get("items"), "approval")
    pending_approval_count = _validated_count(
        approvals.get("pending_approval_count", 0), "approval pending_approval_count"
    )
    duplicate_approval_requests = _validated_count(
        approvals.get("duplicate_requests", 0), "approval duplicate_requests"
    )
    if pending_approval_count != len(approval_items):
        raise OperationsDashboardError("approval pending_approval_count must match approval items")
    for index, item in enumerate(approval_items):
        if item.get("state") != "approval_requested":
            raise OperationsDashboardError(
                f"approval item[{index}] state must remain approval_requested"
            )
        if item.get("decision") is not None:
            raise OperationsDashboardError(
                f"approval item[{index}] decision must remain unset"
            )

    recommendation_items = _validated_items(recommendations.get("items"), "recommendation")
    recommendation_proposal_count = _validated_count(
        recommendations.get("proposal_count", 0), "recommendation proposal_count"
    )
    duplicate_recommendations = _validated_count(
        recommendations.get("duplicate_proposals", 0), "recommendation duplicate_proposals"
    )
    if recommendation_proposal_count != len(recommendation_items):
        raise OperationsDashboardError("recommendation proposal_count must match recommendation items")
    for index, item in enumerate(recommendation_items):
        if item.get("approval_decided") is not False:
            raise OperationsDashboardError(
                f"recommendation item[{index}] approval_decided must remain false"
            )

    owner_packet_items = _validated_items(owner_packets.get("items"), "owner packet")
    owner_packet_count = _validated_count(owner_packets.get("packet_count", 0), "owner packet_count")
    duplicate_owner_packets = _validated_count(owner_packets.get("duplicate_packets", 0), "owner duplicate_packets")
    if owner_packet_count != len(owner_packet_items):
        raise OperationsDashboardError("owner packet_count must match owner packet items")
    owner_decision_pending = owner_packets.get("owner_decision_pending")
    if owner_decision_pending is not bool(owner_packet_items):
        raise OperationsDashboardError("owner_decision_pending must match owner packet items")
    for index, item in enumerate(owner_packet_items):
        if item.get("owner_decision_required") is not True:
            raise OperationsDashboardError(
                f"owner packet item[{index}] owner_decision_required must remain true"
            )
        if item.get("owner_decision") is not None:
            raise OperationsDashboardError(
                f"owner packet item[{index}] owner_decision must remain unset"
            )

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
            "task_count": task_count,
            "duplicate_tasks": task_duplicate_tasks,
            "awaiting_approval": task_awaiting_approval,
            "ready_for_operator_review": task_ready_for_operator_review,
            "task_type_counts": task_type_counts,
            "source_counts": task_source_counts,
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
