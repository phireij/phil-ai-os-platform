from __future__ import annotations

import hashlib
from typing import Any


class AutomationPlanError(ValueError):
    pass


def _stable_plan_id(correlation_id: str, intent: str, approval_required: bool) -> str:
    material = f"{correlation_id}|{intent}|{int(approval_required)}".encode("utf-8")
    return "auto-plan:" + hashlib.sha256(material).hexdigest()[:24]


def build_automation_plan(event: dict[str, Any], governance: dict[str, Any]) -> dict[str, Any]:
    for field in ("mutation_authorized",):
        if event.get(field) is not False:
            raise AutomationPlanError(f"event {field} must remain false")
    for field in ("execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if governance.get(field) is not False:
            raise AutomationPlanError(f"governance {field} must remain false")
    if governance.get("authority_effect") != "none":
        raise AutomationPlanError("governance authority_effect must be none")

    correlation_id = event.get("lifecycle_correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id:
        raise AutomationPlanError("lifecycle_correlation_id is required")
    if governance.get("lifecycle_correlation_id") != correlation_id:
        raise AutomationPlanError("event/governance correlation mismatch")

    intent = event.get("normalized_intent")
    if governance.get("normalized_intent") != intent:
        raise AutomationPlanError("event/governance intent mismatch")

    approval_required = governance.get("approval_required") is True
    state = "blocked_pending_approval" if approval_required else "ready_for_simulation"

    steps = [
        {"name": "observe_event", "system": "operations_hub", "mode": "read_only"},
        {"name": "evaluate_governance", "system": "control_plane_contract", "mode": "simulation"},
    ]
    if approval_required:
        steps.append({"name": "wait_for_human_approval", "system": "approval_surface", "mode": "simulation"})
    else:
        steps.append({"name": "policy_clear_for_simulation", "system": "control_plane_contract", "mode": "simulation"})
    steps.extend(
        [
            {"name": "route_general", "system": "hermes", "mode": "simulation"},
            {"name": "preview_execution_boundary", "system": "execution_boundary", "mode": "simulation"},
            {"name": "preview_result_audit", "system": "mission_control", "mode": "read_only"},
        ]
    )

    return {
        "plan_id": _stable_plan_id(correlation_id, str(intent), approval_required),
        "lifecycle_correlation_id": correlation_id,
        "source": event.get("source"),
        "normalized_intent": intent,
        "risk_level": governance.get("risk_level"),
        "approval_required": approval_required,
        "approval_state": governance.get("approval_state"),
        "plan_state": state,
        "task_class": "general",
        "assigned_agent": "hermes",
        "specialist_enabled": False,
        "automatic_execution": False,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
        "steps": steps,
    }
