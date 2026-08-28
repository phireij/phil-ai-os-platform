#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import uuid

AUTH = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
AUTONOMY = {"A0": 0, "A1": 1, "A2": 2, "A3": 3}
RISK_DEFAULT = {
    "R0": "allow_prepare",
    "R1": "require_human",
    "R2": "require_human",
    "R3": "escalate",
    "R4": "deny",
}


def _parse_time(value: str | None):
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def evaluate_policy(evidence: dict, now: dt.datetime | None = None) -> dict:
    """Pure deterministic policy evaluation. No I/O, mutation, approval consumption or execution."""
    now = now or dt.datetime.now(dt.timezone.utc)
    reasons: list[str] = []

    def result(decision: str, preconditions: bool = False):
        return {
            "policy_decision_id": "pdec_" + uuid.uuid5(
                uuid.NAMESPACE_URL,
                "|".join(str(evidence.get(k, "")) for k in (
                    "task_id", "task_class", "action_type", "subject_agent_id", "risk_tier"
                )),
            ).hex,
            "policy_version": "2.3-p3.v1",
            "evaluated_at": now.isoformat(),
            "task_id": evidence.get("task_id"),
            "task_class": evidence.get("task_class"),
            "action_type": evidence.get("action_type"),
            "subject_agent_id": evidence.get("subject_agent_id"),
            "subject_authority_ceiling": evidence.get("subject_authority_ceiling"),
            "risk_tier": evidence.get("risk_tier"),
            "required_authority": evidence.get("required_authority"),
            "configured_autonomy_ceiling": evidence.get("configured_autonomy_ceiling"),
            "requested_autonomy_level": evidence.get("requested_autonomy_level"),
            "human_approval_required": bool(evidence.get("human_approval_required")),
            "approval_id": (evidence.get("approval") or {}).get("approval_id"),
            "approval_state": (evidence.get("approval") or {}).get("state"),
            "approval_expires_at": (evidence.get("approval") or {}).get("expires_at"),
            "approval_consumption_required": bool(evidence.get("approval_consumption_required")),
            "scope_constraints": evidence.get("scope_constraints") or {},
            "evidence_refs": evidence.get("evidence_refs") or [],
            "decision": decision,
            "reason_codes": reasons.copy(),
            "execution_preconditions_satisfied": bool(preconditions),
            "authority_effect": "none",
        }

    # Required identity/evidence completeness.
    required = (
        "task_id", "task_class", "action_type", "subject_agent_id",
        "subject_authority_ceiling", "risk_tier", "required_authority",
        "configured_autonomy_ceiling", "requested_autonomy_level",
    )
    if not evidence.get("evidence_complete", False) or any(not evidence.get(k) for k in required):
        reasons.append("missing_or_incomplete_policy_evidence")
        return result("deny")

    risk = evidence.get("risk_tier")
    subject_auth = evidence.get("subject_authority_ceiling")
    required_auth = evidence.get("required_authority")
    configured_auto = evidence.get("configured_autonomy_ceiling")
    requested_auto = evidence.get("requested_autonomy_level")
    if risk not in RISK_DEFAULT or subject_auth not in AUTH or required_auth not in AUTH or configured_auto not in AUTONOMY or requested_auto not in AUTONOMY:
        reasons.append("unknown_policy_vocabulary")
        return result("deny")

    # Absolute deny boundaries.
    if evidence.get("direct_provider_bypass"):
        reasons.append("direct_provider_bypass_prohibited")
        return result("deny")
    if evidence.get("mission_control_mutation_as_authority"):
        reasons.append("mission_control_is_read_only")
        return result("deny")
    if evidence.get("readiness_as_permission"):
        reasons.append("readiness_is_not_permission")
        return result("deny")
    if evidence.get("authority_ceiling_as_permission"):
        reasons.append("authority_ceiling_is_not_grant")
        return result("deny")

    if AUTH[required_auth] > AUTH[subject_auth]:
        reasons.append("required_authority_exceeds_subject_ceiling")
        return result("escalate")

    if AUTONOMY[requested_auto] > AUTONOMY[configured_auto]:
        reasons.append("requested_autonomy_exceeds_configured_ceiling")
        return result("deny")

    requested_execution = bool(evidence.get("requested_execution"))
    requested_side_effect = bool(evidence.get("requested_side_effect")) or requested_execution

    if risk == "R4":
        reasons.append("risk_tier_prohibited")
        return result("deny")
    if risk == "R3":
        reasons.append("risk_tier_requires_governance_escalation")
        return result("escalate")
    if risk == "R0" and requested_side_effect:
        reasons.append("r0_cannot_authorize_side_effect")
        return result("deny")

    if requested_execution:
        if evidence.get("task_class") != "general":
            reasons.append("task_class_not_in_current_execution_allowlist")
            return result("deny")
        if evidence.get("kill_switch"):
            reasons.append("execution_kill_switch_active")
            return result("deny")
        if not evidence.get("control_api_boundary", False):
            reasons.append("control_api_execution_boundary_required")
            return result("deny")

    # Under current A0 policy, any side effect requires human approval.
    approval_required = bool(evidence.get("human_approval_required")) or requested_side_effect
    approval = evidence.get("approval") or {}
    if approval_required:
        if not approval:
            reasons.append("human_approval_required")
            return result("require_human")
        if approval.get("requester_id") and approval.get("decision_by") and approval.get("requester_id") == approval.get("decision_by"):
            reasons.append("self_approval_prohibited")
            return result("deny")
        state = approval.get("state")
        if state in {"denied", "expired"}:
            reasons.append("approval_not_usable_" + state)
            return result("deny")
        if approval.get("consumed"):
            reasons.append("approval_already_consumed_replay")
            return result("deny")
        if state != "approved":
            reasons.append("human_approval_required")
            return result("require_human")
        expiry = _parse_time(approval.get("expires_at"))
        if expiry is None or expiry <= now:
            reasons.append("approval_expired_or_missing_expiry")
            return result("deny")
        if not approval.get("scope_match", False):
            reasons.append("approval_scope_mismatch")
            return result("deny")

    if risk == "R0":
        reasons.append("read_only_preparation_allowed")
        return result("allow_prepare")

    if requested_execution:
        reasons.append("all_policy_preconditions_satisfied")
        return result("eligible_for_execution_boundary", preconditions=True)

    if requested_side_effect:
        reasons.append("human_authorized_side_effect_preconditions_satisfied")
        return result("eligible_for_execution_boundary", preconditions=True)

    reasons.append("preparation_only")
    return result("allow_prepare")
