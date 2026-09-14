from __future__ import annotations

from collections import defaultdict
from typing import Any


class MissionControlProjectionError(ValueError):
    pass


def _require_false(model: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    for field in fields:
        if model.get(field) is not False:
            raise MissionControlProjectionError(f"{label} {field} must remain false")


def _validated_count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MissionControlProjectionError(f"{label} must be a non-negative integer")
    return value


def _validated_count_map(value: Any, label: str) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MissionControlProjectionError(f"{label} must be an object")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key:
            raise MissionControlProjectionError(f"{label} keys must be non-empty strings")
        result[key] = _validated_count(count, f"{label}.{key}")
    return dict(sorted(result.items()))


def _attention_items(operations: dict[str, int], lifecycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, label, priority in (
        ("tasks_awaiting_approval", "Tasks awaiting approval", "high"),
        ("orders_pending_staff_review", "Orders pending staff review", "high"),
        ("quotes_pending_approval", "Quotes pending approval", "medium"),
        ("owner_review_pending_packets", "Owner review packets", "medium"),
    ):
        count = _validated_count(operations.get(key, 0), f"operations {key}")
        if count:
            items.append({"kind": key, "label": label, "count": count, "priority": priority})

    failure_count = sum(
        1
        for lifecycle in lifecycles
        if "failure" in str(lifecycle.get("latest_outcome", "")).lower()
        or "error" in str(lifecycle.get("latest_outcome", "")).lower()
    )
    if failure_count:
        items.append(
            {
                "kind": "simulated_lifecycle_failures",
                "label": "Simulated lifecycle failures",
                "count": failure_count,
                "priority": "high",
            }
        )
    return items


def build_mission_control_lifecycle_projection(
    operations_dashboard: dict[str, Any],
    automation_audit: dict[str, Any],
) -> dict[str, Any]:
    """Project bounded lifecycle/result status for read-only Mission Control consumption."""
    if not isinstance(operations_dashboard, dict) or operations_dashboard.get("status") != "read_only":
        raise MissionControlProjectionError("operations dashboard must remain read_only")
    _require_false(
        operations_dashboard,
        (
            "execution_authorized",
            "channel_reply_authorized",
            "quote_authorized",
            "customer_notification_authorized",
            "woo_commerce_mutation_authorized",
            "order_creation_authorized",
            "payment_execution_authorized",
            "sms_send_authorized",
            "inventory_mutation_authorized",
            "production_publish_authorized",
            "mutation_authorized",
        ),
        "operations dashboard",
    )

    if not isinstance(automation_audit, dict) or automation_audit.get("read_only") is not True:
        raise MissionControlProjectionError("automation audit must remain read_only")
    if automation_audit.get("authority_effect") != "none":
        raise MissionControlProjectionError("automation audit authority_effect must remain none")
    items = automation_audit.get("items")
    if not isinstance(items, list):
        raise MissionControlProjectionError("automation audit items must be a list")

    lifecycle_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            raise MissionControlProjectionError("automation audit item must be an object")
        for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized"):
            if item.get(field) is not False:
                raise MissionControlProjectionError(f"automation audit item {field} must remain false")
        if item.get("simulated") is not True or item.get("authority_effect") != "none":
            raise MissionControlProjectionError("automation audit item must remain simulated with no authority effect")
        lifecycle_id = item.get("lifecycle_correlation_id")
        sequence = item.get("sequence")
        stage = item.get("stage")
        outcome = item.get("outcome")
        if not isinstance(lifecycle_id, str) or not lifecycle_id:
            raise MissionControlProjectionError("automation lifecycle_correlation_id is required")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise MissionControlProjectionError("automation sequence must be a positive integer")
        if not isinstance(stage, str) or not stage or not isinstance(outcome, str) or not outcome:
            raise MissionControlProjectionError("automation stage and outcome are required")
        lifecycle_events[lifecycle_id].append(item)

    lifecycles = []
    for lifecycle_id, events in sorted(lifecycle_events.items()):
        ordered = sorted(events, key=lambda event: event["sequence"])
        latest = ordered[-1]
        lifecycles.append(
            {
                "lifecycle_correlation_id": lifecycle_id,
                "latest_sequence": latest["sequence"],
                "latest_stage": latest["stage"],
                "latest_outcome": latest["outcome"],
                "event_count": len(ordered),
                "simulated": True,
            }
        )

    task_model = operations_dashboard.get("tasks", {})
    if not isinstance(task_model, dict):
        raise MissionControlProjectionError("operations tasks must be an object")
    operations = {
        "channel_events": _validated_count(
            operations_dashboard.get("channels", {}).get("total_events", 0),
            "operations channel_events",
        ),
        "tasks": _validated_count(task_model.get("task_count", 0), "operations tasks"),
        "tasks_awaiting_approval": _validated_count(
            task_model.get("awaiting_approval", 0), "operations tasks_awaiting_approval"
        ),
        "tasks_ready_for_operator_review": _validated_count(
            task_model.get("ready_for_operator_review", 0), "operations tasks_ready_for_operator_review"
        ),
        "orders_pending_staff_review": _validated_count(
            operations_dashboard.get("orders", {}).get("pending_staff_review", 0),
            "operations orders_pending_staff_review",
        ),
        "quotes_pending_approval": _validated_count(
            operations_dashboard.get("quotes", {}).get("pending_approval", 0),
            "operations quotes_pending_approval",
        ),
        "owner_review_pending_packets": _validated_count(
            operations_dashboard.get("owner_review", {}).get("pending_packets", 0),
            "operations owner_review_pending_packets",
        ),
    }
    task_composition = {
        "duplicate_tasks": _validated_count(task_model.get("duplicate_tasks", 0), "tasks duplicate_tasks"),
        "by_source": _validated_count_map(task_model.get("source_counts", {}), "tasks source_counts"),
        "by_type": _validated_count_map(task_model.get("task_type_counts", {}), "tasks task_type_counts"),
        "read_only": True,
        "customer_payloads_exposed": False,
        "normalized_intent_exposed": False,
    }
    attention = _attention_items(operations, lifecycles)

    return {
        "schema": "phil-ai-os-mission-control-lifecycle-projection",
        "version": 3,
        "status": "read_only",
        "mission_control_mode": "read_only",
        "control_plane": {
            "autonomy_level": "A0",
            "execution_task_class": "general",
            "hermes_state": "idle",
            "specialists_enabled": False,
            "mission_control_write_enabled": False,
            "live_execution_enabled": False,
            "operator_decision_required_for_sensitive_actions": True,
        },
        "operations": operations,
        "task_composition": task_composition,
        "attention": {
            "count": sum(item["count"] for item in attention),
            "items": attention,
            "read_only": True,
        },
        "automation": {
            "total_audit_events": _validated_count(automation_audit.get("total_events", 0), "automation total_events"),
            "stage_counts": _validated_count_map(automation_audit.get("by_stage", {}), "automation by_stage"),
            "lifecycle_count": len(lifecycles),
            "lifecycles": lifecycles,
            "simulated_only": True,
        },
        "privacy": {
            "raw_customer_text_exposed": False,
            "custom_notes_exposed": False,
            "reference_image_names_exposed": False,
            "reply_draft_text_exposed": False,
        },
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "network_dispatch_authorized": False,
        "woo_commerce_mutation_authorized": False,
        "order_creation_authorized": False,
        "payment_execution_authorized": False,
        "sms_send_authorized": False,
        "inventory_mutation_authorized": False,
        "production_publish_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }
