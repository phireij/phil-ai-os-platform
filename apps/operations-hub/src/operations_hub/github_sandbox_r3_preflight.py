"""Pure, runtime-inactive R3 preflight checks for the GitHub sandbox pilot.

The module has no credential, filesystem, network, queue, database, or dispatch
dependency. It validates evidence supplied by a future durable system and always
returns a blocked preview; it cannot issue an execution lease.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .github_sandbox_issue_pilot import GitHubSandboxIssuePilotRequest, preview_issue_dispatch


class GitHubSandboxR3PreflightError(ValueError):
    """Raised when any R3 pilot preflight evidence is missing or unsafe."""


_R3_TTL_SECONDS = 15 * 60
_CEO_REAUTH_MAX_AGE_SECONDS = 5 * 60
_REQUIRED_CONFIRMATION = "CREATE ONE LABELLED SANDBOX ISSUE in phireij/mission-control-github-sandbox"


@dataclass(frozen=True)
class R3PilotApprovalEvidence:
    approval_id: str
    plan_digest: str
    risk_level: str
    typed_confirmation: str
    ceo_reauthenticated_at_epoch: int
    approved_at_epoch: int
    expires_at_epoch: int
    revoked: bool
    consumed: bool


@dataclass(frozen=True)
class PilotLimitEvidence:
    issues_created_in_last_24_hours: int
    external_action_budget_usd: int
    reserved_external_action_budget_usd: int
    emergency_stop_active: bool


@dataclass(frozen=True)
class PilotIdempotencyEvidence:
    state: str


@dataclass(frozen=True)
class InertR3PreflightPreview:
    approval_id: str
    plan_digest: str
    state: str = "blocked"
    reason: str = "adapter_runtime_inactive"
    execution_lease_issued: bool = False
    credential_read_authorized: bool = False
    token_request_authorized: bool = False
    dispatch_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


def review_r3_preflight(
    request: GitHubSandboxIssuePilotRequest,
    approval: R3PilotApprovalEvidence,
    limits: PilotLimitEvidence,
    idempotency: PilotIdempotencyEvidence,
    now_epoch_seconds: int,
) -> InertR3PreflightPreview:
    """Validate all supplied R3 gate evidence and still fail closed at runtime."""

    preview_issue_dispatch(request)
    _validate_approval(request, approval, now_epoch_seconds)
    _validate_limits(limits)
    _validate_idempotency(idempotency)
    return InertR3PreflightPreview(approval_id=approval.approval_id, plan_digest=request.plan_digest)


def _validate_approval(request: GitHubSandboxIssuePilotRequest, approval: R3PilotApprovalEvidence, now: int) -> None:
    if not isinstance(approval, R3PilotApprovalEvidence):
        raise GitHubSandboxR3PreflightError("github_sandbox_approval_evidence_invalid")
    if not isinstance(now, int) or isinstance(now, bool) or now <= 0:
        raise GitHubSandboxR3PreflightError("github_sandbox_preflight_clock_invalid")
    if not isinstance(approval.approval_id, str) or not approval.approval_id:
        raise GitHubSandboxR3PreflightError("github_sandbox_approval_id_invalid")
    if approval.risk_level != "R3":
        raise GitHubSandboxR3PreflightError("github_sandbox_risk_not_r3")
    if approval.plan_digest != request.plan_digest:
        raise GitHubSandboxR3PreflightError("github_sandbox_plan_digest_mismatch")
    if approval.typed_confirmation != _REQUIRED_CONFIRMATION:
        raise GitHubSandboxR3PreflightError("github_sandbox_typed_confirmation_invalid")
    if approval.revoked:
        raise GitHubSandboxR3PreflightError("github_sandbox_approval_revoked")
    if approval.consumed:
        raise GitHubSandboxR3PreflightError("github_sandbox_approval_already_consumed")
    if approval.expires_at_epoch - approval.approved_at_epoch != _R3_TTL_SECONDS:
        raise GitHubSandboxR3PreflightError("github_sandbox_approval_ttl_invalid")
    if now > approval.expires_at_epoch:
        raise GitHubSandboxR3PreflightError("github_sandbox_approval_expired")
    if now - approval.ceo_reauthenticated_at_epoch > _CEO_REAUTH_MAX_AGE_SECONDS:
        raise GitHubSandboxR3PreflightError("github_sandbox_ceo_reauthentication_stale")


def _validate_limits(limits: PilotLimitEvidence) -> None:
    if not isinstance(limits, PilotLimitEvidence):
        raise GitHubSandboxR3PreflightError("github_sandbox_limit_evidence_invalid")
    if limits.emergency_stop_active:
        raise GitHubSandboxR3PreflightError("github_sandbox_emergency_stop_active")
    if limits.issues_created_in_last_24_hours != 0:
        raise GitHubSandboxR3PreflightError("github_sandbox_24_hour_limit_reached")
    if limits.external_action_budget_usd != 0 or limits.reserved_external_action_budget_usd != 0:
        raise GitHubSandboxR3PreflightError("github_sandbox_external_action_budget_invalid")


def _validate_idempotency(idempotency: PilotIdempotencyEvidence) -> None:
    if not isinstance(idempotency, PilotIdempotencyEvidence):
        raise GitHubSandboxR3PreflightError("github_sandbox_idempotency_evidence_invalid")
    if idempotency.state != "absent":
        raise GitHubSandboxR3PreflightError("github_sandbox_idempotency_not_clear")
