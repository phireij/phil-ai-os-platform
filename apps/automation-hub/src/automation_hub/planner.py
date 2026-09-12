from __future__ import annotations

import hashlib
from typing import Any


class AutomationPlanError(ValueError):
    pass


def _stable_plan_id(correlation_id: str, intent: str, approval_required: bool) -> str:
    material = f"{correlation_id}|{intent}|{int(approval_required)}".encode("utf-8")
    return "auto-plan:" + hashlib.sha256(material).hexdigest()[:24]


def _build_plan(
    *,
    correlation_id: str,
    source: Any,
    intent: Any,
    risk_level: Any,
    approval_required: bool,
    approval_state: Any,
    observation_step: str,
    governance_step: str,
) -> dict[str, Any]:
    state = "blocked_pending_approval" if approval_required else "ready_for_simulation"
    steps = [
        {"name": observation_step, "system": "operations_hub", "mode": "read_only"},
        {"name": governance_step, "system": "control_plane_contract", "mode": "simulation"},
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
        "source": source,
        "normalized_intent": intent,
        "risk_level": risk_level,
        "approval_required": approval_required,
        "approval_state": approval_state,
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
    return _build_plan(
        correlation_id=correlation_id,
        source=event.get("source"),
        intent=intent,
        risk_level=governance.get("risk_level"),
        approval_required=approval_required,
        approval_state=governance.get("approval_state"),
        observation_step="observe_event",
        governance_step="evaluate_governance",
    )


def build_task_automation_plan(task_candidate: dict[str, Any]) -> dict[str, Any]:
    """Route an extracted Operations Hub task into the existing simulation-only automation boundary."""
    if not isinstance(task_candidate, dict):
        raise AutomationPlanError("task candidate must be an object")
    if task_candidate.get("schema") != "phil-ai-os-operations-task-candidate" or task_candidate.get("version") != 1:
        raise AutomationPlanError("unsupported task candidate schema")

    authority = task_candidate.get("authority")
    if not isinstance(authority, dict) or authority.get("operator_review_only") is not True:
        raise AutomationPlanError("task candidate must remain operator_review_only")
    if authority.get("authority_effect") != "none":
        raise AutomationPlanError("task candidate authority_effect must remain none")
    for field, value in authority.items():
        if field in {"operator_review_only", "authority_effect"}:
            continue
        if value is not False:
            raise AutomationPlanError(f"task candidate authority {field} must remain false")

    correlation_id = task_candidate.get("lifecycle_correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id:
        raise AutomationPlanError("task candidate lifecycle_correlation_id is required")
    source = task_candidate.get("source")
    if not isinstance(source, str) or not source:
        raise AutomationPlanError("task candidate source is required")
    intent = task_candidate.get("normalized_intent")
    if not isinstance(intent, str) or not intent:
        raise AutomationPlanError("task candidate normalized_intent is required")
    risk_level = task_candidate.get("risk_level")
    if risk_level not in {"low", "medium", "high"}:
        raise AutomationPlanError("task candidate risk_level is invalid")

    approval_required = task_candidate.get("approval_required") is True
    approval_state = task_candidate.get("approval_state")
    expected_approval_state = "required" if approval_required else "not_required"
    expected_task_state = "awaiting_approval" if approval_required else "ready_for_operator_review"
    if approval_state != expected_approval_state:
        raise AutomationPlanError("task candidate approval state is inconsistent")
    if task_candidate.get("state") != expected_task_state:
        raise AutomationPlanError("task candidate task state is inconsistent")

    return _build_plan(
        correlation_id=correlation_id,
        source=source,
        intent=intent,
        risk_level=risk_level,
        approval_required=approval_required,
        approval_state=approval_state,
        observation_step="observe_task_candidate",
        governance_step="validate_task_governance",
    )
