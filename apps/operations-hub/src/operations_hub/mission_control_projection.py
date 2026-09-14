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


def _project_recovery(recovery_read_model: dict[str, Any] | None) -> dict[str, Any]:
    if recovery_read_model is None:
        return {
            "plan_count": 0,
            "duplicate_plans": 0,
            "retry_simulation_count": 0,
            "stop_for_review_count": 0,
            "error_code_counts": {},
            "read_only": True,
            "automatic_retry": False,
            "retry_authorized": False,
            "automatic_rollback": False,
            "rollback_authorized": False,
            "execution_authorized": False,
            "mutation_authorized": False,
            "authority_effect": "none",
        }
    if not isinstance(recovery_read_model, dict) or recovery_read_model.get("status") != "read_only":
        raise MissionControlProjectionError("recovery read model must remain read_only")
    if recovery_read_model.get("authority_effect") != "none":
        raise MissionControlProjectionError("recovery authority_effect must remain none")
    _require_false(
        recovery_read_model,
        (
            "automatic_retry",
            "retry_authorized",
            "automatic_rollback",
            "rollback_authorized",
            "execution_authorized",
            "mutation_authorized",
        ),
        "recovery",
    )
    plan_count = _validated_count(recovery_read_model.get("plan_count", 0), "recovery plan_count")
    duplicate_plans = _validated_count(
        recovery_read_model.get("duplicate_plans", 0), "recovery duplicate_plans"
    )
    retry_simulation_count = _validated_count(
        recovery_read_model.get("retry_simulation_count", 0), "recovery retry_simulation_count"
    )
    stop_for_review_count = _validated_count(
        recovery_read_model.get("stop_for_review_count", 0), "recovery stop_for_review_count"
    )
    error_code_counts = _validated_count_map(
        recovery_read_model.get("error_code_counts", {}), "recovery error_code_counts"
    )
    if retry_simulation_count + stop_for_review_count != plan_count:
        raise MissionControlProjectionError("recovery action counts must match recovery plan_count")
    if sum(error_code_counts.values()) != plan_count:
        raise MissionControlProjectionError("recovery error_code_counts must match recovery plan_count")
    return {
        "plan_count": plan_count,
        "duplicate_plans": duplicate_plans,
        "retry_simulation_count": retry_simulation_count,
        "stop_for_review_count": stop_for_review_count,
        "error_code_counts": error_code_counts,
        "read_only": True,
        "automatic_retry": False,
        "retry_authorized": False,
        "automatic_rollback": False,
        "rollback_authorized": False,
        "execution_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }


def _project_approval(approval_read_model: dict[str, Any] | None) -> dict[str, Any]:
    if approval_read_model is None:
        return {
            "plan_count": 0,
            "decision_count": 0,
            "awaiting_decision": 0,
            "simulation_releasable": 0,
            "by_state": {},
            "read_only": True,
            "decision_ids_exposed": False,
            "plan_fingerprints_exposed": False,
            "automatic_execution": False,
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "mutation_authorized": False,
            "authority_effect": "none",
        }
    if not isinstance(approval_read_model, dict) or approval_read_model.get("status") != "read_only":
        raise MissionControlProjectionError("approval read model must remain read_only")
    if approval_read_model.get("authority_effect") != "none":
        raise MissionControlProjectionError("approval authority_effect must remain none")
    if approval_read_model.get("decision_ids_exposed") is not False:
        raise MissionControlProjectionError("approval decision identifiers must remain hidden")
    if approval_read_model.get("plan_fingerprints_exposed") is not False:
        raise MissionControlProjectionError("approval plan fingerprints must remain hidden")
    _require_false(
        approval_read_model,
        (
            "automatic_execution",
            "execution_authorized",
            "channel_reply_authorized",
            "mutation_authorized",
        ),
        "approval",
    )
    plan_count = _validated_count(approval_read_model.get("plan_count", 0), "approval plan_count")
    decision_count = _validated_count(approval_read_model.get("decision_count", 0), "approval decision_count")
    awaiting_decision = _validated_count(
        approval_read_model.get("awaiting_decision", 0), "approval awaiting_decision"
    )
    simulation_releasable = _validated_count(
        approval_read_model.get("simulation_releasable", 0), "approval simulation_releasable"
    )
    by_state = _validated_count_map(approval_read_model.get("by_state", {}), "approval by_state")
    if set(by_state) != {"required", "approved", "denied", "not_required"}:
        raise MissionControlProjectionError("approval by_state must contain each known state")
    if sum(by_state.values()) != plan_count:
        raise MissionControlProjectionError("approval plan_count must match approval by_state")
    if decision_count != by_state.get("approved", 0) + by_state.get("denied", 0):
        raise MissionControlProjectionError("approval decision_count must match approval by_state")
    if awaiting_decision != by_state.get("required", 0):
        raise MissionControlProjectionError("approval awaiting_decision must match approval by_state")
    if simulation_releasable != by_state.get("approved", 0) + by_state.get("not_required", 0):
        raise MissionControlProjectionError("approval simulation_releasable must match approval by_state")
    return {
        "plan_count": plan_count,
        "decision_count": decision_count,
        "awaiting_decision": awaiting_decision,
        "simulation_releasable": simulation_releasable,
        "by_state": by_state,
        "read_only": True,
        "decision_ids_exposed": False,
        "plan_fingerprints_exposed": False,
        "automatic_execution": False,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }


def _attention_items(
    operations: dict[str, int],
    lifecycles: list[dict[str, Any]],
    recovery: dict[str, Any],
    approval: dict[str, Any],
) -> list[dict[str, Any]]:
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

    awaiting_decision = approval["awaiting_decision"]
    if awaiting_decision:
        items.append(
            {
                "kind": "automation_approval_awaiting_decision",
                "label": "Automation approvals awaiting decision",
                "count": awaiting_decision,
                "priority": "high",
            }
        )

    stop_for_review = recovery["stop_for_review_count"]
    if stop_for_review:
        items.append(
            {
                "kind": "recovery_stop_for_review",
                "label": "Recovery items stopped for review",
                "count": stop_for_review,
                "priority": "high",
            }
        )

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
    recovery_read_model: dict[str, Any] | None = None,
    approval_read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project bounded lifecycle/result/recovery/approval status for read-only Mission Control consumption."""
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
    computed_stage_counts: dict[str, int] = defaultdict(int)
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
        computed_stage_counts[stage] += 1

    declared_total_events = _validated_count(
        automation_audit.get("total_events", 0), "automation total_events"
    )
    if declared_total_events != len(items):
        raise MissionControlProjectionError("automation total_events must match automation audit items")
    declared_stage_counts = _validated_count_map(
        automation_audit.get("by_stage", {}), "automation by_stage"
    )
    if declared_stage_counts != dict(sorted(computed_stage_counts.items())):
        raise MissionControlProjectionError("automation by_stage must match automation audit items")

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
    if operations["tasks_awaiting_approval"] + operations["tasks_ready_for_operator_review"] != operations["tasks"]:
        raise MissionControlProjectionError("operations task state counts must match operations tasks")
    if sum(task_composition["by_source"].values()) != operations["tasks"]:
        raise MissionControlProjectionError("tasks source_counts must match operations tasks")
    if sum(task_composition["by_type"].values()) != operations["tasks"]:
        raise MissionControlProjectionError("tasks task_type_counts must match operations tasks")
    recovery = _project_recovery(recovery_read_model)
    approval = _project_approval(approval_read_model)
    attention = _attention_items(operations, lifecycles, recovery, approval)

    return {
        "schema": "phil-ai-os-mission-control-lifecycle-projection",
        "version": 5,
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
        "approval": approval,
        "recovery": recovery,
        "attention": {
            "count": sum(item["count"] for item in attention),
            "items": attention,
            "read_only": True,
        },
        "automation": {
            "total_audit_events": declared_total_events,
            "stage_counts": declared_stage_counts,
            "lifecycle_count": len(lifecycles),
            "lifecycles": lifecycles,
            "simulated_only": True,
        },
        "privacy": {
            "raw_customer_text_exposed": False,
            "custom_notes_exposed": False,
            "reference_image_names_exposed": False,
            "reply_draft_text_exposed": False,
            "approval_decision_ids_exposed": False,
            "approval_plan_fingerprints_exposed": False,
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
