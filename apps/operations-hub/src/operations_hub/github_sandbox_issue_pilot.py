"""Pure, inactive request validation for the GitHub sandbox issue pilot.

This module deliberately has no credential input, HTTP client, subprocess,
filesystem, environment, or GitHub SDK dependency.  It validates only the
single proposed action's immutable scope and always returns a blocked preview.
It cannot request an installation token or create an issue.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping


class GitHubSandboxIssuePilotError(ValueError):
    """Raised when a requested sandbox pilot action exceeds the fixed scope."""


_TARGET_REPOSITORY = "phireij/mission-control-github-sandbox"
_PERMITTED_OPERATION = "create_labelled_issue"
_REQUIRED_LABEL = "mission-control-sandbox-pilot"
_PLAN_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_REQUEST_FIELDS = frozenset({"target_repository", "operation", "label", "approval_id", "plan_digest"})
_FORBIDDEN_FIELDS = frozenset({"private_key", "installation_token", "authorization_header", "webhook_secret"})


@dataclass(frozen=True)
class GitHubSandboxIssuePilotRequest:
    """Content-free request shape for an eventual, separately activated pilot."""

    target_repository: str
    operation: str
    label: str
    approval_id: str
    plan_digest: str


@dataclass(frozen=True)
class InertGitHubSandboxDispatchPreview:
    """A JSON-safe result that proves no dispatch or network action occurred."""

    target_repository: str
    operation: str
    label: str
    approval_id: str
    plan_digest: str
    state: str = "blocked"
    reason: str = "adapter_runtime_inactive"
    network_authorized: bool = False
    token_request_authorized: bool = False
    dispatch_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


def request_from_record(record: Mapping[str, Any]) -> GitHubSandboxIssuePilotRequest:
    """Parse an exact, credential-free request record and reject all extras."""

    if not isinstance(record, Mapping):
        raise GitHubSandboxIssuePilotError("github_sandbox_request_invalid")
    fields = set(record)
    if fields & _FORBIDDEN_FIELDS:
        raise GitHubSandboxIssuePilotError("github_sandbox_credential_field_forbidden")
    if fields != _REQUEST_FIELDS:
        raise GitHubSandboxIssuePilotError("github_sandbox_request_fields_invalid")
    return GitHubSandboxIssuePilotRequest(**dict(record))


def preview_issue_dispatch(request: GitHubSandboxIssuePilotRequest) -> InertGitHubSandboxDispatchPreview:
    """Validate fixed scope and return a fail-closed, non-dispatching preview."""

    _validate_request(request)
    return InertGitHubSandboxDispatchPreview(
        target_repository=request.target_repository,
        operation=request.operation,
        label=request.label,
        approval_id=request.approval_id,
        plan_digest=request.plan_digest,
    )


def _validate_request(request: GitHubSandboxIssuePilotRequest) -> None:
    if not isinstance(request, GitHubSandboxIssuePilotRequest):
        raise GitHubSandboxIssuePilotError("github_sandbox_request_invalid")
    if request.target_repository != _TARGET_REPOSITORY:
        raise GitHubSandboxIssuePilotError("github_sandbox_target_not_allowlisted")
    if request.operation != _PERMITTED_OPERATION:
        raise GitHubSandboxIssuePilotError("github_sandbox_operation_not_allowlisted")
    if request.label != _REQUIRED_LABEL:
        raise GitHubSandboxIssuePilotError("github_sandbox_label_not_allowlisted")
    if not isinstance(request.approval_id, str) or not request.approval_id or len(request.approval_id) > 200:
        raise GitHubSandboxIssuePilotError("github_sandbox_approval_invalid")
    if not isinstance(request.plan_digest, str) or not _PLAN_DIGEST_PATTERN.fullmatch(request.plan_digest):
        raise GitHubSandboxIssuePilotError("github_sandbox_plan_digest_invalid")
