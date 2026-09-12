from __future__ import annotations

from collections import Counter
from typing import Any

from .reply_draft import ReplyDraftError
from .reply_draft_register import ReplyDraftRegister
from .task_queue import TaskCandidateQueue


class ReplyDraftWorkspaceError(ValueError):
    pass


def build_reply_draft_workspace(
    task_queue: TaskCandidateQueue,
    draft_register: ReplyDraftRegister,
) -> dict[str, Any]:
    """Build a read-only operator review workspace for reply drafts without granting send authority."""
    if not isinstance(task_queue, TaskCandidateQueue):
        raise ReplyDraftWorkspaceError("task_queue must be a TaskCandidateQueue")
    if not isinstance(draft_register, ReplyDraftRegister):
        raise ReplyDraftWorkspaceError("draft_register must be a ReplyDraftRegister")

    tasks = task_queue.read_model()
    drafts = draft_register.read_model()
    _assert_read_only(tasks, "task_queue")
    _assert_read_only(drafts, "draft_register")

    task_items = {item["task_candidate_id"]: item for item in tasks.get("items", [])}
    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for item in drafts.get("items", []):
        task_id = item.get("task_candidate_id")
        task = task_items.get(task_id)
        if task is None:
            raise ReplyDraftWorkspaceError("reply draft references an unknown task candidate")
        if item.get("lifecycle_correlation_id") != task.get("lifecycle_correlation_id"):
            raise ReplyDraftWorkspaceError("reply draft/task lifecycle correlation mismatch")
        if item.get("source") != task.get("source"):
            raise ReplyDraftWorkspaceError("reply draft/task source mismatch")
        if item.get("state") != "awaiting_operator_approval":
            raise ReplyDraftWorkspaceError("reply draft must remain awaiting_operator_approval")

        governance_required = item.get("governance_approval_required") is True
        if governance_required != (task.get("approval_required") is True):
            raise ReplyDraftWorkspaceError("reply draft/task governance approval mismatch")

        review_status = (
            "blocked_by_governance_approval"
            if governance_required
            else "ready_for_operator_approval"
        )
        status_counts[review_status] += 1
        rows.append(
            {
                "reply_draft_id": item["reply_draft_id"],
                "task_candidate_id": task_id,
                "lifecycle_correlation_id": item["lifecycle_correlation_id"],
                "source": item["source"],
                "task_type": item["task_type"],
                "locale": item["locale"],
                "drafted_by": item["drafted_by"],
                "review_status": review_status,
                "operator_approval_required": True,
                "channel_reply_authorized": False,
            }
        )

    return {
        "status": "read_only",
        "workspace": "reply_draft_review",
        "draft_count": len(rows),
        "ready_for_operator_approval": status_counts.get("ready_for_operator_approval", 0),
        "blocked_by_governance_approval": status_counts.get("blocked_by_governance_approval", 0),
        "items": rows,
        "execution_authorized": False,
        "channel_reply_authorized": False,
        "network_dispatch_authorized": False,
        "mutation_authorized": False,
    }


def _assert_read_only(model: Any, label: str) -> None:
    if not isinstance(model, dict) or model.get("status") != "read_only":
        raise ReplyDraftWorkspaceError(f"{label} must remain read_only")
    for field in (
        "execution_authorized",
        "channel_reply_authorized",
        "network_dispatch_authorized",
        "mutation_authorized",
    ):
        if field in model and model.get(field) is not False:
            raise ReplyDraftWorkspaceError(f"{label} {field} must remain false")
