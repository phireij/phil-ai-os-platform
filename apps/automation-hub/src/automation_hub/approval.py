from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ApprovalSimulationError(ValueError):
    pass


class ApprovalReplayError(ApprovalSimulationError):
    pass


@dataclass
class _ApprovalRecord:
    state: str
    decision_id: str | None = None


class ApprovalSimulationStore:
    def __init__(self) -> None:
        self._records: dict[str, _ApprovalRecord] = {}

    def register_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        _validate_plan_boundary(plan)
        plan_id = _require_plan_id(plan)
        state = "required" if plan.get("approval_required") is True else "not_required"
        current = self._records.get(plan_id)
        if current is None:
            self._records[plan_id] = _ApprovalRecord(state=state)
        elif current.state != state:
            raise ApprovalSimulationError("plan approval requirement changed after registration")
        return self.read(plan_id)

    def decide(self, plan_id: str, decision: str, decision_id: str) -> dict[str, Any]:
        if decision not in {"approve", "deny"}:
            raise ApprovalSimulationError("decision must be approve or deny")
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise ApprovalSimulationError("decision_id is required")
        record = self._records.get(plan_id)
        if record is None:
            raise ApprovalSimulationError("plan is not registered")
        if record.state == "not_required":
            raise ApprovalSimulationError("plan does not require approval")
        if record.state in {"approved", "denied"}:
            raise ApprovalReplayError("approval decision is one-time and already consumed")
        record.state = "approved" if decision == "approve" else "denied"
        record.decision_id = decision_id.strip()
        return self.read(plan_id)

    def release_for_simulation(self, plan: dict[str, Any]) -> dict[str, Any]:
        _validate_plan_boundary(plan)
        plan_id = _require_plan_id(plan)
        record = self._records.get(plan_id)
        if record is None:
            raise ApprovalSimulationError("plan is not registered")
        if record.state == "required":
            raise ApprovalSimulationError("approval is still required")
        if record.state == "denied":
            raise ApprovalSimulationError("approval was denied")
        if record.state not in {"approved", "not_required"}:
            raise ApprovalSimulationError("invalid approval state")
        return {
            "plan_id": plan_id,
            "approval_state": record.state,
            "simulation_release": True,
            "automatic_execution": False,
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "mutation_authorized": False,
            "authority_effect": "none",
        }

    def read(self, plan_id: str) -> dict[str, Any]:
        record = self._records.get(plan_id)
        if record is None:
            raise ApprovalSimulationError("plan is not registered")
        return {
            "plan_id": plan_id,
            "approval_state": record.state,
            "decision_id": record.decision_id,
            "authority_effect": "none",
            "execution_authorized": False,
        }


def _require_plan_id(plan: dict[str, Any]) -> str:
    plan_id = plan.get("plan_id")
    if not isinstance(plan_id, str) or not plan_id:
        raise ApprovalSimulationError("plan_id is required")
    return plan_id


def _validate_plan_boundary(plan: dict[str, Any]) -> None:
    if plan.get("authority_effect") != "none":
        raise ApprovalSimulationError("plan authority_effect must be none")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if plan.get(field) is not False:
            raise ApprovalSimulationError(f"plan {field} must remain false")
