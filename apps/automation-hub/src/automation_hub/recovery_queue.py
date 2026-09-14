from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any

from .recovery import RecoveryPlanError


class RecoveryPlanQueue:
    """Read-only in-memory register for bounded dry-run recovery plans."""

    def __init__(self) -> None:
        self._plans: dict[str, dict[str, Any]] = {}
        self._fingerprints: dict[str, str] = {}
        self._duplicates = 0

    def ingest(self, plan: dict[str, Any]) -> dict[str, Any]:
        _validate_plan(plan)
        recovery_id = plan["recovery_id"]
        fingerprint = _plan_fingerprint(plan)
        if recovery_id in self._plans:
            if self._fingerprints.get(recovery_id) != fingerprint:
                raise RecoveryPlanError("recovery plan content changed for existing recovery_id")
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "recovery_id": recovery_id,
                "execution_authorized": False,
                "retry_authorized": False,
                "rollback_authorized": False,
                "mutation_authorized": False,
            }
        self._plans[recovery_id] = dict(plan)
        self._fingerprints[recovery_id] = fingerprint
        return {
            "accepted": True,
            "duplicate": False,
            "recovery_id": recovery_id,
            "execution_authorized": False,
            "retry_authorized": False,
            "rollback_authorized": False,
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        plans = sorted(self._plans.values(), key=lambda item: item["recovery_id"])
        action_counts = Counter(item["next_action"] for item in plans)
        error_counts = Counter(item["error_code"] for item in plans)
        items = [
            {
                "recovery_id": item["recovery_id"],
                "lifecycle_correlation_id": item["lifecycle_correlation_id"],
                "error_code": item["error_code"],
                "attempt": item["attempt"],
                "max_attempts": item["max_attempts"],
                "retryable": item["retryable"],
                "retry_planned": item["retry_planned"],
                "next_action": item["next_action"],
                "automatic_retry": False,
                "retry_authorized": False,
                "rollback_required": False,
                "automatic_rollback": False,
                "rollback_authorized": False,
                "execution_authorized": False,
                "mutation_authorized": False,
                "authority_effect": "none",
            }
            for item in plans
        ]
        return {
            "status": "read_only",
            "queue": "automation_recovery_review",
            "plan_count": len(plans),
            "duplicate_plans": self._duplicates,
            "retry_simulation_count": action_counts.get("retry_simulation", 0),
            "stop_for_review_count": action_counts.get("stop_for_review", 0),
            "error_code_counts": dict(sorted(error_counts.items())),
            "items": items,
            "plan_fingerprints_exposed": False,
            "automatic_retry": False,
            "retry_authorized": False,
            "automatic_rollback": False,
            "rollback_authorized": False,
            "execution_authorized": False,
            "mutation_authorized": False,
            "authority_effect": "none",
        }


def _plan_fingerprint(plan: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RecoveryPlanError("recovery plan must be JSON-serializable") from exc
    return hashlib.sha256(encoded).hexdigest()


def _validate_plan(plan: Any) -> None:
    if not isinstance(plan, dict):
        raise RecoveryPlanError("recovery plan must be an object")
    for field in ("recovery_id", "lifecycle_correlation_id", "error_code", "next_action"):
        if not isinstance(plan.get(field), str) or not plan[field]:
            raise RecoveryPlanError(f"recovery plan {field} is required")
    if not plan["recovery_id"].startswith("recovery:"):
        raise RecoveryPlanError("invalid recovery_id")
    if plan["next_action"] not in {"retry_simulation", "stop_for_review"}:
        raise RecoveryPlanError("unsupported recovery next_action")
    for field in ("attempt", "max_attempts"):
        value = plan.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RecoveryPlanError(f"recovery plan {field} must be a positive integer")
    if plan["attempt"] > plan["max_attempts"]:
        raise RecoveryPlanError("recovery plan attempt exceeds max_attempts")
    expected_retry = bool(plan.get("retryable") is True and plan["attempt"] < plan["max_attempts"])
    if plan.get("retry_planned") is not expected_retry:
        raise RecoveryPlanError("recovery plan retry state is inconsistent")
    expected_action = "retry_simulation" if expected_retry else "stop_for_review"
    if plan["next_action"] != expected_action:
        raise RecoveryPlanError("recovery plan next_action is inconsistent")
    if plan.get("rollback_required") is not False or plan.get("rollback_reason") != "dry_run_no_side_effect":
        raise RecoveryPlanError("recovery plan rollback boundary invalid")
    for field in (
        "automatic_retry",
        "retry_authorized",
        "automatic_rollback",
        "rollback_authorized",
        "execution_authorized",
        "mutation_authorized",
    ):
        if plan.get(field) is not False:
            raise RecoveryPlanError(f"recovery plan {field} must remain false")
    if plan.get("authority_effect") != "none":
        raise RecoveryPlanError("recovery plan authority_effect must remain none")
