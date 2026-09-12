from __future__ import annotations

from collections import defaultdict
from typing import Any


class MissionControlProjectionError(ValueError):
    pass


def _require_false(model: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    for field in fields:
        if model.get(field) is not False:
            raise MissionControlProjectionError(f"{label} {field} must remain false")


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

    return {
        "schema": "phil-ai-os-mission-control-lifecycle-projection",
        "version": 1,
        "status": "read_only",
        "mission_control_mode": "read_only",
        "operations": {
            "channel_events": operations_dashboard.get("channels", {}).get("total_events", 0),
            "tasks": operations_dashboard.get("tasks", {}).get("task_count", 0),
            "tasks_awaiting_approval": operations_dashboard.get("tasks", {}).get("awaiting_approval", 0),
            "orders_pending_staff_review": operations_dashboard.get("orders", {}).get("pending_staff_review", 0),
            "quotes_pending_approval": operations_dashboard.get("quotes", {}).get("pending_approval", 0),
            "owner_review_pending_packets": operations_dashboard.get("owner_review", {}).get("pending_packets", 0),
        },
        "automation": {
            "total_audit_events": automation_audit.get("total_events", 0),
            "stage_counts": dict(automation_audit.get("by_stage", {})),
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
