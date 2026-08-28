from __future__ import annotations

import hashlib
from typing import Any


class BoundaryRequestError(ValueError):
    pass


def _request_id(plan_id: str, correlation_id: str) -> str:
    material = f"{plan_id}|{correlation_id}|dry-run".encode("utf-8")
    return "dry-run:" + hashlib.sha256(material).hexdigest()[:24]


def build_dry_run_boundary_request(plan: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]:
    _validate_plan(plan)
    _validate_release(release)

    plan_id = plan.get("plan_id")
    correlation_id = plan.get("lifecycle_correlation_id")
    if release.get("plan_id") != plan_id:
        raise BoundaryRequestError("release/plan identity mismatch")
    if not isinstance(correlation_id, str) or not correlation_id:
        raise BoundaryRequestError("lifecycle_correlation_id is required")

    return {
        "request_id": _request_id(str(plan_id), correlation_id),
        "plan_id": plan_id,
        "lifecycle_correlation_id": correlation_id,
        "target": "execution_boundary",
        "operation": "preview_request",
        "mode": "dry_run",
        "task_class": "general",
        "assigned_agent": "hermes",
        "dry_run": True,
        "dispatch": False,
        "network_call": False,
        "automatic_execution": False,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }


def _validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("task_class") != "general" or plan.get("assigned_agent") != "hermes":
        raise BoundaryRequestError("plan routing is outside bounded baseline")
    if plan.get("specialist_enabled") is not False:
        raise BoundaryRequestError("specialists must remain disabled")
    if plan.get("authority_effect") != "none":
        raise BoundaryRequestError("plan authority_effect must remain none")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if plan.get(field) is not False:
            raise BoundaryRequestError(f"plan {field} must remain false")


def _validate_release(release: dict[str, Any]) -> None:
    if release.get("simulation_release") is not True:
        raise BoundaryRequestError("valid simulation release is required")
    if release.get("approval_state") not in {"approved", "not_required"}:
        raise BoundaryRequestError("approval state cannot release dry-run request")
    if release.get("authority_effect") != "none":
        raise BoundaryRequestError("release authority_effect must remain none")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if release.get(field) is not False:
            raise BoundaryRequestError(f"release {field} must remain false")
