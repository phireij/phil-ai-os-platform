"""Pure, pre-activation policy evaluation for Mission Control automation.

This module deliberately has no network, database, queue, credential, provider,
or adapter dependency.  Its output is an auditable recommendation only; it
cannot create an approval, issue a lease, or authorize dispatch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import FrozenSet


class ApprovalGatedPolicyError(ValueError):
    """Raised when an assessment request is malformed."""


_FACTORS = frozenset(
    {
        "environment",
        "reversibility",
        "financial_or_customer_impact",
        "data_sensitivity",
        "breadth",
        "privilege",
        "external_visibility",
        "uncertainty",
    }
)
_RISK_LEVELS = frozenset({"R0", "R1", "R2", "R3", "R4"})


@dataclass(frozen=True)
class AssessmentRequest:
    """A bounded, content-free request for a risk recommendation."""

    environment: str
    requested_effect: str
    factors: FrozenSet[str]
    policy_version: str


@dataclass(frozen=True)
class PolicyDecision:
    """An inert decision suitable for persistence in the future audit ledger."""

    risk_level: str
    required_gate: str
    approval_ttl_minutes: int | None
    reasons: tuple[str, ...]
    policy_version: str
    activation_state: str = "design_only_inactive"
    automatic_execution: bool = False
    execution_authorized: bool = False
    mutation_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        """Return a JSON-safe, non-authorizing representation."""

        return asdict(self)


def assess(request: AssessmentRequest) -> PolicyDecision:
    """Classify risk conservatively and return a non-authorizing gate.

    Unknown factors, environments, and requested effects are R4. This makes the
    function safe to call before adapters or execution infrastructure exist.
    """

    _validate_request(request)
    reasons: list[str] = []
    factors = request.factors

    if request.environment not in {"sandbox", "internal", "staging", "production"}:
        return _decision("R4", "blocked", None, ("environment is unknown",), request.policy_version)
    if request.requested_effect not in {"observe", "reversible_internal", "operational_mutation", "external_or_customer", "restricted"}:
        return _decision("R4", "blocked", None, ("requested effect is unknown",), request.policy_version)
    if "uncertainty" in factors or request.requested_effect == "restricted":
        reasons.append("unknown or restricted scope requires a dedicated activation policy")
        return _decision("R4", "blocked", None, tuple(reasons), request.policy_version)
    if request.environment == "production" or request.requested_effect == "external_or_customer":
        reasons.append("production or external/customer impact requires typed CEO confirmation")
        return _decision("R3", "ceo_typed_confirmation", 15, tuple(reasons), request.policy_version)
    if request.requested_effect == "operational_mutation" or "privilege" in factors or "breadth" in factors:
        reasons.append("operational mutation, privilege, or breadth requires CEO reauthentication")
        return _decision("R2", "ceo_reauthenticate", 240, tuple(reasons), request.policy_version)
    if request.requested_effect == "reversible_internal":
        reasons.append("reversible internal action still requires CEO approval")
        return _decision("R1", "ceo_approval", 1440, tuple(reasons), request.policy_version)
    reasons.append("read-only observation is audit-only")
    return _decision("R0", "audit_only", None, tuple(reasons), request.policy_version)


def _decision(risk_level: str, required_gate: str, ttl: int | None, reasons: tuple[str, ...], policy_version: str) -> PolicyDecision:
    return PolicyDecision(risk_level, required_gate, ttl, reasons, policy_version)


def _validate_request(request: AssessmentRequest) -> None:
    if not isinstance(request, AssessmentRequest):
        raise ApprovalGatedPolicyError("assessment_request_invalid")
    if not isinstance(request.environment, str) or not request.environment:
        raise ApprovalGatedPolicyError("assessment_environment_invalid")
    if not isinstance(request.requested_effect, str) or not request.requested_effect:
        raise ApprovalGatedPolicyError("assessment_effect_invalid")
    if not isinstance(request.policy_version, str) or not request.policy_version or len(request.policy_version) > 100:
        raise ApprovalGatedPolicyError("assessment_policy_version_invalid")
    if not isinstance(request.factors, frozenset) or not request.factors <= _FACTORS:
        raise ApprovalGatedPolicyError("assessment_factors_invalid")
