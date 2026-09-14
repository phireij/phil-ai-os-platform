from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from .task_extraction import TaskExtractionError


class TaskCandidateQueue:
    """Read-only in-memory queue for bounded channel-derived task candidates."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._duplicates = 0

    def ingest(self, candidate: dict[str, Any]) -> dict[str, Any]:
        _validate_candidate(candidate)
        task_id = candidate["task_candidate_id"]
        if task_id in self._tasks:
            if candidate != self._tasks[task_id]:
                raise TaskExtractionError("task candidate ID conflicts with existing content")
            self._duplicates += 1
            return {
                "accepted": False,
                "duplicate": True,
                "task_candidate_id": task_id,
                "mutation_authorized": False,
            }
        self._tasks[task_id] = copy.deepcopy(candidate)
        return {
            "accepted": True,
            "duplicate": False,
            "task_candidate_id": task_id,
            "mutation_authorized": False,
        }

    def read_model(self) -> dict[str, Any]:
        tasks = sorted(self._tasks.values(), key=lambda item: item["task_candidate_id"])
        task_type_counts = Counter(item["task_type"] for item in tasks)
        source_counts = Counter(item["source"] for item in tasks)
        state_counts = Counter(item["state"] for item in tasks)
        items = [
            {
                "task_candidate_id": item["task_candidate_id"],
                "lifecycle_correlation_id": item["lifecycle_correlation_id"],
                "source": item["source"],
                "task_type": item["task_type"],
                "normalized_intent": item["normalized_intent"],
                "risk_level": item["risk_level"],
                "state": item["state"],
                "approval_required": item["approval_required"],
                "approval_state": item["approval_state"],
                "mutation_authorized": False,
            }
            for item in tasks
        ]
        return {
            "status": "read_only",
            "queue": "channel_task_candidates",
            "task_count": len(tasks),
            "duplicate_tasks": self._duplicates,
            "awaiting_approval": state_counts.get("awaiting_approval", 0),
            "ready_for_operator_review": state_counts.get("ready_for_operator_review", 0),
            "task_type_counts": dict(sorted(task_type_counts.items())),
            "source_counts": dict(sorted(source_counts.items())),
            "items": items,
            "execution_authorized": False,
            "channel_reply_authorized": False,
            "mutation_authorized": False,
        }

    def task_detail(self, task_candidate_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_candidate_id)
        if task is None:
            return None
        return {
            "task_candidate_id": task["task_candidate_id"],
            "lifecycle_correlation_id": task["lifecycle_correlation_id"],
            "source": task["source"],
            "kind": task["kind"],
            "external_event_id": task["external_event_id"],
            "task_type": task["task_type"],
            "normalized_intent": task["normalized_intent"],
            "risk_level": task["risk_level"],
            "state": task["state"],
            "approval_required": task["approval_required"],
            "approval_state": task["approval_state"],
            "approval_reason": task.get("approval_reason"),
            "customer_context": copy.deepcopy(task["customer_context"]),
            "authority": copy.deepcopy(task["authority"]),
        }


def _validate_candidate(candidate: Any) -> None:
    if not isinstance(candidate, dict):
        raise TaskExtractionError("task candidate must be an object")
    if candidate.get("schema") != "phil-ai-os-operations-task-candidate" or candidate.get("version") != 1:
        raise TaskExtractionError("unsupported task candidate schema")
    if candidate.get("state") not in {"awaiting_approval", "ready_for_operator_review"}:
        raise TaskExtractionError("unsupported task candidate state")
    task_id = candidate.get("task_candidate_id")
    if not isinstance(task_id, str) or not task_id.startswith("ops-task:"):
        raise TaskExtractionError("invalid task_candidate_id")
    if not isinstance(candidate.get("lifecycle_correlation_id"), str) or not candidate["lifecycle_correlation_id"]:
        raise TaskExtractionError("task candidate lifecycle_correlation_id is required")

    approval_required = candidate.get("approval_required") is True
    expected_state = "awaiting_approval" if approval_required else "ready_for_operator_review"
    expected_approval = "required" if approval_required else "not_required"
    if candidate.get("state") != expected_state or candidate.get("approval_state") != expected_approval:
        raise TaskExtractionError("task candidate approval/state relationship is invalid")

    authority = candidate.get("authority")
    if not isinstance(authority, dict) or authority.get("operator_review_only") is not True:
        raise TaskExtractionError("task candidate must remain operator_review_only")
    if authority.get("authority_effect") != "none":
        raise TaskExtractionError("task candidate authority_effect must remain none")
    for field, value in authority.items():
        if field in {"operator_review_only", "authority_effect"}:
            continue
        if value is not False:
            raise TaskExtractionError(f"task candidate authority {field} must remain false")
