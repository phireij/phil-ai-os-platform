from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class AutomationAuditError(ValueError):
    pass


@dataclass(frozen=True)
class AutomationAuditEvent:
    sequence: int
    lifecycle_correlation_id: str
    plan_id: str
    stage: str
    outcome: str
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "lifecycle_correlation_id": self.lifecycle_correlation_id,
            "plan_id": self.plan_id,
            "request_id": self.request_id,
            "stage": self.stage,
            "outcome": self.outcome,
            "simulated": True,
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "mutation_authorized": False,
            "authority_effect": "none",
        }


class InMemoryAutomationAudit:
    def __init__(self) -> None:
        self._events: list[AutomationAuditEvent] = []

    def record_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        _validate_plan(plan)
        outcome = "approval_required" if plan.get("approval_required") is True else "simulation_ready"
        return self._append(plan, "plan_created", outcome)

    def record_approval(self, plan: dict[str, Any], approval_state: str) -> dict[str, Any]:
        _validate_plan(plan)
        if approval_state not in {"approved", "denied", "not_required"}:
            raise AutomationAuditError("unsupported approval state")
        return self._append(plan, "approval_evaluated", approval_state)

    def record_boundary_request(self, plan: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        _validate_plan(plan)
        _validate_request(plan, request)
        return self._append(plan, "boundary_preview", "dry_run_created", request_id=request["request_id"])

    def record_simulated_result(self, plan: dict[str, Any], request: dict[str, Any], outcome: str = "simulated_success") -> dict[str, Any]:
        _validate_plan(plan)
        _validate_request(plan, request)
        if outcome not in {"simulated_success", "simulated_failure"}:
            raise AutomationAuditError("unsupported simulated outcome")
        return self._append(plan, "result_preview", outcome, request_id=request["request_id"])

    def read_model(self) -> dict[str, Any]:
        items = [event.to_dict() for event in self._events]
        by_stage: dict[str, int] = {}
        for item in items:
            by_stage[item["stage"]] = by_stage.get(item["stage"], 0) + 1
        return {
            "total_events": len(items),
            "by_stage": by_stage,
            "items": items,
            "read_only": True,
            "authority_effect": "none",
        }

    def _append(self, plan: dict[str, Any], stage: str, outcome: str, request_id: str | None = None) -> dict[str, Any]:
        event = AutomationAuditEvent(
            sequence=len(self._events) + 1,
            lifecycle_correlation_id=plan["lifecycle_correlation_id"],
            plan_id=plan["plan_id"],
            request_id=request_id,
            stage=stage,
            outcome=outcome,
        )
        self._events.append(event)
        return event.to_dict()


def _validate_plan(plan: dict[str, Any]) -> None:
    if plan.get("authority_effect") != "none":
        raise AutomationAuditError("plan authority_effect must remain none")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if plan.get(field) is not False:
            raise AutomationAuditError(f"plan {field} must remain false")
    for field in ("plan_id", "lifecycle_correlation_id"):
        if not isinstance(plan.get(field), str) or not plan[field]:
            raise AutomationAuditError(f"{field} is required")


def _validate_request(plan: dict[str, Any], request: dict[str, Any]) -> None:
    if request.get("plan_id") != plan.get("plan_id") or request.get("lifecycle_correlation_id") != plan.get("lifecycle_correlation_id"):
        raise AutomationAuditError("request does not match plan")
    if request.get("mode") != "dry_run" or request.get("dry_run") is not True:
        raise AutomationAuditError("only dry-run requests may be audited here")
    if request.get("dispatch") is not False or request.get("network_call") is not False:
        raise AutomationAuditError("request may not dispatch or call network")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if request.get(field) is not False:
            raise AutomationAuditError(f"request {field} must remain false")
