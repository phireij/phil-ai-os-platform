from __future__ import annotations

import hashlib
from typing import Any


class RecoveryPlanError(ValueError):
    pass


def build_recovery_plan(
    request: dict[str, Any],
    *,
    error_code: str,
    retryable: bool,
    attempt: int,
    max_attempts: int = 3,
    side_effect_observed: bool = False,
) -> dict[str, Any]:
    _validate_request(request)
    if not isinstance(error_code, str) or not error_code.strip():
        raise RecoveryPlanError("error_code is required")
    if attempt < 1 or max_attempts < 1 or attempt > max_attempts:
        raise RecoveryPlanError("invalid attempt bounds")
    if side_effect_observed:
        raise RecoveryPlanError("dry-run request cannot report a side effect")

    retry_planned = bool(retryable and attempt < max_attempts)
    next_action = "retry_simulation" if retry_planned else "stop_for_review"
    material = f"{request['request_id']}|{error_code}|{attempt}|{max_attempts}".encode("utf-8")
    recovery_id = "recovery:" + hashlib.sha256(material).hexdigest()[:24]

    return {
        "recovery_id": recovery_id,
        "request_id": request["request_id"],
        "lifecycle_correlation_id": request["lifecycle_correlation_id"],
        "error_code": error_code.strip(),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "retryable": bool(retryable),
        "retry_planned": retry_planned,
        "next_action": next_action,
        "automatic_retry": False,
        "retry_authorized": False,
        "rollback_required": False,
        "rollback_reason": "dry_run_no_side_effect",
        "automatic_rollback": False,
        "rollback_authorized": False,
        "execution_authorized": False,
        "mutation_authorized": False,
        "authority_effect": "none",
    }


def _validate_request(request: dict[str, Any]) -> None:
    if request.get("mode") != "dry_run" or request.get("dry_run") is not True:
        raise RecoveryPlanError("recovery planner accepts dry-run requests only")
    if request.get("dispatch") is not False or request.get("network_call") is not False:
        raise RecoveryPlanError("dry-run request must not dispatch or call network")
    if request.get("authority_effect") != "none":
        raise RecoveryPlanError("request authority_effect must remain none")
    for field in ("automatic_execution", "execution_authorized", "channel_reply_authorized", "mutation_authorized"):
        if request.get(field) is not False:
            raise RecoveryPlanError(f"request {field} must remain false")
    for field in ("request_id", "lifecycle_correlation_id"):
        if not isinstance(request.get(field), str) or not request[field]:
            raise RecoveryPlanError(f"{field} is required")
