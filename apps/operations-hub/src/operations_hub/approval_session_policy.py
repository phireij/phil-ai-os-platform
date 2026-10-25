"""Inert approval-session freshness checks for a future trusted OIDC proxy.

This code never parses tokens or authenticates a browser. It accepts only
already-validated, server-side OIDC facts from a future trusted session service
and always returns a non-authorizing result while activation remains disabled.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone


class ApprovalSessionPolicyError(ValueError):
    """Raised when trusted session facts are malformed."""


@dataclass(frozen=True)
class ValidatedCEOPrincipal:
    issuer: str
    subject: str
    authenticated_at: datetime
    session_started_at: datetime
    last_activity_at: datetime


@dataclass(frozen=True)
class ApprovalSessionAssessment:
    principal_matches: bool
    session_current: bool
    reauthentication_current: bool
    required_auth_age_seconds: int | None
    activation_state: str = "design_only_inactive"
    approval_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


def assess_approval_session(
    principal: ValidatedCEOPrincipal,
    expected_issuer: str,
    expected_subject: str,
    risk_level: str,
    now: datetime,
) -> ApprovalSessionAssessment:
    """Evaluate only freshness/binding; never authorize an approval or action."""

    _validate(principal, expected_issuer, expected_subject, risk_level, now)
    required_age = {"R2": 900, "R3": 300}.get(risk_level)
    principal_matches = principal.issuer == expected_issuer and principal.subject == expected_subject
    session_current = (
        now - principal.session_started_at <= timedelta(hours=8)
        and now - principal.last_activity_at <= timedelta(minutes=30)
        and now >= principal.session_started_at
        and now >= principal.last_activity_at
    )
    reauthentication_current = (
        principal.authenticated_at <= now
        and (required_age is None or now - principal.authenticated_at <= timedelta(seconds=required_age))
    )
    return ApprovalSessionAssessment(principal_matches, session_current, reauthentication_current, required_age)


def _validate(principal: ValidatedCEOPrincipal, expected_issuer: str, expected_subject: str, risk_level: str, now: datetime) -> None:
    if not isinstance(principal, ValidatedCEOPrincipal):
        raise ApprovalSessionPolicyError("validated_principal_invalid")
    if not isinstance(expected_issuer, str) or expected_issuer != "https://accounts.google.com":
        raise ApprovalSessionPolicyError("expected_issuer_invalid")
    if not isinstance(expected_subject, str) or not expected_subject or len(expected_subject) > 255:
        raise ApprovalSessionPolicyError("expected_subject_invalid")
    if not isinstance(principal.issuer, str) or not principal.issuer or not isinstance(principal.subject, str) or not principal.subject:
        raise ApprovalSessionPolicyError("trusted_principal_identity_invalid")
    if risk_level not in {"R0", "R1", "R2", "R3", "R4"}:
        raise ApprovalSessionPolicyError("risk_level_invalid")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ApprovalSessionPolicyError("assessment_time_invalid")
    for value in (principal.authenticated_at, principal.session_started_at, principal.last_activity_at):
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ApprovalSessionPolicyError("trusted_session_time_invalid")
