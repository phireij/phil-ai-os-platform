#!/usr/bin/env python3
"""Fail-closed Phase 2.3 P5 Control API patch.

Adds only:
- append-only policy_decisions schema with authority_effect='none';
- the isolated pure P3 evaluator as an internal helper;
- an internal persistence helper.

No external route, execution hook, approval hook, provider call, task-class change,
or authority expansion is added by this patch.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MIGRATION_ANCHOR = "        # v0.19 approval-to-execution audit trace.\n"
FUNCTION_ANCHOR = 'def coordinator_assign(task_id, agent_id, requested_by="control-api", reason_code=None):\n'
MARKER = "Phase 2.3 P5 append-only inert policy decision ledger"

MIGRATION = '''        # Phase 2.3 P5 append-only inert policy decision ledger.
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS policy_decisions(
          policy_decision_id TEXT PRIMARY KEY,
          policy_version TEXT NOT NULL,
          evaluated_at TEXT NOT NULL,
          task_id TEXT NOT NULL,
          task_class TEXT NOT NULL,
          action_type TEXT NOT NULL,
          subject_agent_id TEXT NOT NULL,
          subject_authority_ceiling TEXT NOT NULL,
          risk_tier TEXT NOT NULL,
          required_authority TEXT NOT NULL,
          configured_autonomy_ceiling TEXT NOT NULL,
          requested_autonomy_level TEXT NOT NULL,
          human_approval_required INTEGER NOT NULL,
          approval_id TEXT,
          approval_state TEXT,
          approval_expires_at TEXT,
          approval_consumption_required INTEGER NOT NULL,
          scope_constraints_json TEXT NOT NULL,
          evidence_refs_json TEXT NOT NULL,
          decision TEXT NOT NULL,
          reason_codes_json TEXT NOT NULL,
          execution_preconditions_satisfied INTEGER NOT NULL,
          authority_effect TEXT NOT NULL CHECK(authority_effect='none'),
          evidence_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_policy_decisions_task_time
          ON policy_decisions(task_id,evaluated_at);
        CREATE INDEX IF NOT EXISTS idx_policy_decisions_approval_time
          ON policy_decisions(approval_id,evaluated_at) WHERE approval_id IS NOT NULL;
        CREATE TRIGGER IF NOT EXISTS policy_decisions_no_update
          BEFORE UPDATE ON policy_decisions BEGIN
            SELECT RAISE(ABORT,'policy_decisions_append_only');
          END;
        CREATE TRIGGER IF NOT EXISTS policy_decisions_no_delete
          BEFORE DELETE ON policy_decisions BEGIN
            SELECT RAISE(ABORT,'policy_decisions_append_only');
          END;
        """)

'''

FUNCTIONS = r'''P23_POLICY_AUTH = {"L1":1,"L2":2,"L3":3,"L4":4}
P23_POLICY_AUTONOMY = {"A0":0,"A1":1,"A2":2,"A3":3}
P23_POLICY_RISK_DEFAULT = {
    "R0":"allow_prepare","R1":"require_human","R2":"require_human",
    "R3":"escalate","R4":"deny",
}


def _p23_policy_parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z","+00:00"))


def policy_evaluate_pure(evidence, now=None):
    """Pure P3 evaluator packaged for future internal use; no I/O or authority effect."""
    now=now or datetime.now(timezone.utc)
    reasons=[]
    def result(decision,preconditions=False):
        return {
            "policy_decision_id":"pdec_"+uuid.uuid5(
                uuid.NAMESPACE_URL,
                "|".join(str(evidence.get(k,"")) for k in (
                    "task_id","task_class","action_type","subject_agent_id","risk_tier"
                )),
            ).hex,
            "policy_version":"2.3-p3.v1",
            "evaluated_at":now.isoformat(),
            "task_id":evidence.get("task_id"),
            "task_class":evidence.get("task_class"),
            "action_type":evidence.get("action_type"),
            "subject_agent_id":evidence.get("subject_agent_id"),
            "subject_authority_ceiling":evidence.get("subject_authority_ceiling"),
            "risk_tier":evidence.get("risk_tier"),
            "required_authority":evidence.get("required_authority"),
            "configured_autonomy_ceiling":evidence.get("configured_autonomy_ceiling"),
            "requested_autonomy_level":evidence.get("requested_autonomy_level"),
            "human_approval_required":bool(evidence.get("human_approval_required")),
            "approval_id":(evidence.get("approval") or {}).get("approval_id"),
            "approval_state":(evidence.get("approval") or {}).get("state"),
            "approval_expires_at":(evidence.get("approval") or {}).get("expires_at"),
            "approval_consumption_required":bool(evidence.get("approval_consumption_required")),
            "scope_constraints":evidence.get("scope_constraints") or {},
            "evidence_refs":evidence.get("evidence_refs") or [],
            "decision":decision,
            "reason_codes":reasons.copy(),
            "execution_preconditions_satisfied":bool(preconditions),
            "authority_effect":"none",
        }

    required=(
        "task_id","task_class","action_type","subject_agent_id","subject_authority_ceiling",
        "risk_tier","required_authority","configured_autonomy_ceiling","requested_autonomy_level",
    )
    if not evidence.get("evidence_complete",False) or any(not evidence.get(k) for k in required):
        reasons.append("missing_or_incomplete_policy_evidence"); return result("deny")
    risk=evidence.get("risk_tier"); subject_auth=evidence.get("subject_authority_ceiling")
    required_auth=evidence.get("required_authority"); configured_auto=evidence.get("configured_autonomy_ceiling")
    requested_auto=evidence.get("requested_autonomy_level")
    if risk not in P23_POLICY_RISK_DEFAULT or subject_auth not in P23_POLICY_AUTH or required_auth not in P23_POLICY_AUTH or configured_auto not in P23_POLICY_AUTONOMY or requested_auto not in P23_POLICY_AUTONOMY:
        reasons.append("unknown_policy_vocabulary"); return result("deny")
    if evidence.get("direct_provider_bypass"):
        reasons.append("direct_provider_bypass_prohibited"); return result("deny")
    if evidence.get("mission_control_mutation_as_authority"):
        reasons.append("mission_control_is_read_only"); return result("deny")
    if evidence.get("readiness_as_permission"):
        reasons.append("readiness_is_not_permission"); return result("deny")
    if evidence.get("authority_ceiling_as_permission"):
        reasons.append("authority_ceiling_is_not_grant"); return result("deny")
    if P23_POLICY_AUTH[required_auth] > P23_POLICY_AUTH[subject_auth]:
        reasons.append("required_authority_exceeds_subject_ceiling"); return result("escalate")
    if P23_POLICY_AUTONOMY[requested_auto] > P23_POLICY_AUTONOMY[configured_auto]:
        reasons.append("requested_autonomy_exceeds_configured_ceiling"); return result("deny")
    requested_execution=bool(evidence.get("requested_execution"))
    requested_side_effect=bool(evidence.get("requested_side_effect")) or requested_execution
    if risk=="R4": reasons.append("risk_tier_prohibited"); return result("deny")
    if risk=="R3": reasons.append("risk_tier_requires_governance_escalation"); return result("escalate")
    if risk=="R0" and requested_side_effect:
        reasons.append("r0_cannot_authorize_side_effect"); return result("deny")
    if requested_execution:
        if evidence.get("task_class")!="general":
            reasons.append("task_class_not_in_current_execution_allowlist"); return result("deny")
        if evidence.get("kill_switch"):
            reasons.append("execution_kill_switch_active"); return result("deny")
        if not evidence.get("control_api_boundary",False):
            reasons.append("control_api_execution_boundary_required"); return result("deny")
    approval_required=bool(evidence.get("human_approval_required")) or requested_side_effect
    approval=evidence.get("approval") or {}
    if approval_required:
        if not approval:
            reasons.append("human_approval_required"); return result("require_human")
        if approval.get("requester_id") and approval.get("decision_by") and approval.get("requester_id")==approval.get("decision_by"):
            reasons.append("self_approval_prohibited"); return result("deny")
        state=approval.get("state")
        if state in {"denied","expired"}:
            reasons.append("approval_not_usable_"+state); return result("deny")
        if approval.get("consumed"):
            reasons.append("approval_already_consumed_replay"); return result("deny")
        if state!="approved":
            reasons.append("human_approval_required"); return result("require_human")
        expiry=_p23_policy_parse_time(approval.get("expires_at"))
        if expiry is None or expiry<=now:
            reasons.append("approval_expired_or_missing_expiry"); return result("deny")
        if not approval.get("scope_match",False):
            reasons.append("approval_scope_mismatch"); return result("deny")
    if risk=="R0": reasons.append("read_only_preparation_allowed"); return result("allow_prepare")
    if requested_execution:
        reasons.append("all_policy_preconditions_satisfied"); return result("eligible_for_execution_boundary",True)
    if requested_side_effect:
        reasons.append("human_authorized_side_effect_preconditions_satisfied"); return result("eligible_for_execution_boundary",True)
    reasons.append("preparation_only"); return result("allow_prepare")


def policy_decision_persist(decision_obj):
    """Internal append-only persistence helper. It does not grant or consume authority."""
    if not isinstance(decision_obj,dict) or decision_obj.get("authority_effect")!="none":
        raise ValueError("policy_decision_authority_effect_must_be_none")
    required=(
        "policy_decision_id","policy_version","evaluated_at","task_id","task_class","action_type",
        "subject_agent_id","subject_authority_ceiling","risk_tier","required_authority",
        "configured_autonomy_ceiling","requested_autonomy_level","decision",
    )
    if any(not decision_obj.get(k) for k in required):
        raise ValueError("policy_decision_required_field_missing")
    canonical=json.dumps(decision_obj,sort_keys=True,separators=(",",":"),default=str)
    evidence_hash="sha256:"+hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    conn=db()
    try:
        conn.execute("""insert into policy_decisions(
          policy_decision_id,policy_version,evaluated_at,task_id,task_class,action_type,subject_agent_id,
          subject_authority_ceiling,risk_tier,required_authority,configured_autonomy_ceiling,requested_autonomy_level,
          human_approval_required,approval_id,approval_state,approval_expires_at,approval_consumption_required,
          scope_constraints_json,evidence_refs_json,decision,reason_codes_json,execution_preconditions_satisfied,
          authority_effect,evidence_hash
        ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
          decision_obj["policy_decision_id"],decision_obj["policy_version"],decision_obj["evaluated_at"],
          decision_obj["task_id"],decision_obj["task_class"],decision_obj["action_type"],decision_obj["subject_agent_id"],
          decision_obj["subject_authority_ceiling"],decision_obj["risk_tier"],decision_obj["required_authority"],
          decision_obj["configured_autonomy_ceiling"],decision_obj["requested_autonomy_level"],
          1 if decision_obj.get("human_approval_required") else 0,decision_obj.get("approval_id"),
          decision_obj.get("approval_state"),decision_obj.get("approval_expires_at"),
          1 if decision_obj.get("approval_consumption_required") else 0,
          json.dumps(decision_obj.get("scope_constraints") or {},sort_keys=True,separators=(",",":")),
          json.dumps(decision_obj.get("evidence_refs") or [],sort_keys=True,separators=(",",":")),
          decision_obj["decision"],
          json.dumps(decision_obj.get("reason_codes") or [],sort_keys=True,separators=(",",":")),
          1 if decision_obj.get("execution_preconditions_satisfied") else 0,"none",evidence_hash,
        ))
        conn.commit()
        return {"policy_decision_id":decision_obj["policy_decision_id"],"evidence_hash":evidence_hash,"authority_effect":"none"}
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


'''


def patch(text: str) -> str:
    if MARKER in text:
        raise SystemExit("source already contains P5 patch")
    for anchor,label in ((MIGRATION_ANCHOR,"migration"),(FUNCTION_ANCHOR,"function")):
        count=text.count(anchor)
        if count!=1:
            raise SystemExit(f"expected exactly one {label} anchor, found {count}")
    if '/v1/policy/evaluate' in text:
        raise SystemExit("unexpected policy writer route already present")
    text=text.replace(MIGRATION_ANCHOR,MIGRATION+MIGRATION_ANCHOR,1)
    text=text.replace(FUNCTION_ANCHOR,FUNCTIONS+FUNCTION_ANCHOR,1)
    return text


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("source"); ap.add_argument("--output")
    args=ap.parse_args(); src=Path(args.source); out=Path(args.output) if args.output else src
    out.write_text(patch(src.read_text(encoding="utf-8")),encoding="utf-8")


if __name__=="__main__":
    main()
