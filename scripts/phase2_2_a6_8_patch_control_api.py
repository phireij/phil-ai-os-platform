#!/usr/bin/env python3
"""Patch A6.7 Control API with the canary-scoped A6.8 authority/readiness bridge.

The extension is intentionally narrow:
- only root-controlled runtime-state evidence for APPROVE_PHASE_2_2_A6_8 can supply L1;
- only the exact canary task/source/target/correlation may project readiness;
- human handoff authorization is bound to the exact returned handoff id/correlation;
- execution approval is observed but never changed;
- all non-canary tasks remain fail-closed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

EXPECTED_BASE_SHA = "faa727987e087e2540fec7be0c9d709f7cc57dd51ddc767a3d8b39e0a6474b55"
START = "def coordinator_agent_readiness(conn, agent_id):\n"
END = "def coordinator_handoff_request(task_id, target_agent_id, reason_code, requested_by=\"control-api\"):\n"
ACCEPT_START = "def coordinator_handoff_accept(handoff_id):\n"
ACCEPT_END = "def coordinator_handoff_reject(handoff_id):\n"

A68_BRIDGE = r'''A68_AUTHORIZATION = "APPROVE_PHASE_2_2_A6_8"
A68_POLICY_PATH = RUNTIME_STATE_DIR / "phase2_2_a6_8_canary_policy.json"
A68_READINESS_PATH = RUNTIME_STATE_DIR / "phase2_2_a6_8_canary_readiness.json"


def _a68_json(path):
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else None
    except Exception:
        return None


def _a68_valid_future(value):
    try:
        return datetime.now(timezone.utc) < _iso_to_dt(str(value))
    except Exception:
        return False


def _a68_policy(conn, task_id, task_class, handoff=None):
    p=_a68_json(A68_POLICY_PATH)
    if not p:
        return None
    if p.get("schema_version")!="2.2-a6.8.v1":
        return None
    if p.get("authorization")!=A68_AUTHORIZATION or p.get("authorized_by")!="CEO":
        return None
    if p.get("task_id")!=task_id or p.get("task_class")!=task_class or task_class!="general":
        return None
    if p.get("required_authority")!="L1":
        return None
    if p.get("source_agent_id")!="hermes" or p.get("target_agent_id")!="specialist-worker-01":
        return None
    if not isinstance(p.get("canary_correlation_id"),str) or not p.get("canary_correlation_id"):
        return None
    if not _a68_valid_future(p.get("expires_at")):
        return None
    if coordinator_current_owner(conn,task_id)!="hermes":
        return None
    if handoff is not None:
        if p.get("handoff_authorized") is not True:
            return None
        if p.get("handoff_id")!=handoff.get("handoff_id"):
            return None
        if p.get("handoff_correlation_id")!=handoff.get("correlation_id"):
            return None
        if handoff.get("task_id")!=task_id:
            return None
        if handoff.get("source_agent_id")!="hermes" or handoff.get("target_agent_id")!="specialist-worker-01":
            return None
        if handoff.get("required_authority")!="L1":
            return None
    return p


def coordinator_agent_readiness(conn, agent_id, task_id=None):
    row=conn.execute(
        "select authority_ceiling,enabled,assignable from agent_registry where agent_id=?",
        (agent_id,),
    ).fetchone()
    if not row:
        return "unknown"
    if not bool(row[1]) or not bool(row[2]):
        return "unassignable"
    if not task_id:
        return "indeterminate"
    task=conn.execute(
        "select task_class from approval_requests where task_id=? order by created_at desc limit 1",
        (task_id,),
    ).fetchone()
    if not task:
        return "indeterminate"
    p=_a68_policy(conn,task_id,task[0])
    if not p:
        return "indeterminate"
    r=_a68_json(A68_READINESS_PATH)
    if not r:
        return "indeterminate"
    if r.get("schema_version")!="2.2-a6.8.v1" or r.get("authorization")!=A68_AUTHORIZATION:
        return "indeterminate"
    if r.get("task_id")!=task_id or r.get("source_agent_id")!="hermes" or r.get("target_agent_id")!="specialist-worker-01":
        return "indeterminate"
    if r.get("canary_correlation_id")!=p.get("canary_correlation_id"):
        return "indeterminate"
    try:
        generated=_iso_to_dt(str(r.get("generated_at")))
        age=(datetime.now(timezone.utc)-generated).total_seconds()
    except Exception:
        return "indeterminate"
    if age < -5 or age > 120 or not _a68_valid_future(r.get("expires_at")):
        return "stale"
    if agent_id=="hermes":
        if r.get("source_presence_authenticated") is True and coordinator_current_owner(conn,task_id)=="hermes":
            return "busy"
        return "indeterminate"
    if agent_id=="specialist-worker-01":
        if row[0]!="L1" or r.get("target_presence_signature_verified") is not True:
            return "indeterminate"
        if int(r.get("specialist_prior_assignment_refs",-1))!=0:
            return "busy"
        refs=conn.execute(
            "select count(*) from task_lifecycle_events where stage='ASSIGNED' and assigned_agent_id='specialist-worker-01'"
        ).fetchone()[0]
        return "ready" if int(refs)==0 else "busy"
    return "indeterminate"


def coordinator_required_authority(conn, task_id, task_class):
    p=_a68_policy(conn,task_id,task_class)
    return p.get("required_authority") if p else None


def coordinator_handoff_authorized(conn, handoff):
    task=conn.execute(
        "select task_class from approval_requests where task_id=? order by created_at desc limit 1",
        (handoff.get("task_id"),),
    ).fetchone()
    if not task:
        return False
    return _a68_policy(conn,handoff.get("task_id"),task[0],handoff=handoff) is not None


'''

A68_ACCEPT = r'''def coordinator_handoff_accept(handoff_id):
    handoff_id=(handoff_id or "").strip()
    if not handoff_id:
        return 400,{"status":"invalid_request","detail":"handoff_id is required","timestamp":now_iso()}
    conn=db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute("select * from task_handoffs where handoff_id=?",(handoff_id,)).fetchone()
        if not row:
            conn.rollback()
            return 404,{"status":"handoff_not_found","handoff_id":handoff_id,"timestamp":now_iso()}
        d=dict(row)
        if d['state']=='accepted':
            conn.rollback()
            return 200,{"status":"ok","handoff":d,"idempotent_replay":True,"timestamp":now_iso()}
        if d['state']!='requested':
            conn.rollback()
            return 409,{"status":"handoff_not_requestable","state":d['state'],"timestamp":now_iso()}
        if datetime.now(timezone.utc) >= _iso_to_dt(d['expires_at']):
            now=now_iso()
            conn.execute(
                "update task_handoffs set state='expired',decided_by='control-api-authenticated',"
                "decided_at=?,containment_reason='expired' where handoff_id=? and state='requested'",
                (now,handoff_id),
            )
            conn.commit()
            return 409,{"status":"handoff_expired","handoff_id":handoff_id,"timestamp":now_iso()}
        current_owner=coordinator_current_owner(conn,d['task_id'])
        if current_owner!=d['source_agent_id']:
            conn.execute(
                "update task_handoffs set state='contained',decided_by='control-api-authenticated',"
                "decided_at=?,containment_reason='source_owner_changed' where handoff_id=? and state='requested'",
                (now_iso(),handoff_id),
            )
            conn.commit()
            return 409,{"status":"handoff_contained","reason":"source_owner_changed","timestamp":now_iso()}
        target=conn.execute(
            "select authority_ceiling,enabled,assignable from agent_registry where agent_id=?",
            (d['target_agent_id'],),
        ).fetchone()
        source=conn.execute(
            "select authority_ceiling,enabled,assignable from agent_registry where agent_id=?",
            (d['source_agent_id'],),
        ).fetchone()
        if not target or not bool(target[1]) or not bool(target[2]):
            conn.rollback()
            return 409,{"status":"target_not_assignable","target_agent_id":d['target_agent_id'],"timestamp":now_iso()}
        if not source or not bool(source[1]) or not bool(source[2]):
            conn.rollback()
            return 409,{"status":"source_not_assignable","timestamp":now_iso()}
        source_readiness=coordinator_agent_readiness(conn,d['source_agent_id'],d['task_id'])
        target_readiness=coordinator_agent_readiness(conn,d['target_agent_id'],d['task_id'])
        if source_readiness not in {'busy','ready'} or target_readiness!='ready':
            conn.rollback()
            return 409,{"status":"handoff_readiness_not_ready","source_readiness":source_readiness,
                        "target_readiness":target_readiness,"timestamp":now_iso()}
        task=conn.execute(
            "select task_class,state,consumed_at from approval_requests where task_id=? order by created_at desc limit 1",
            (d['task_id'],),
        ).fetchone()
        if not task or task[0]!=d['task_class'] or task[0]!='general' or EXECUTION_ALLOWED_TASK_CLASSES!={"general"}:
            conn.rollback()
            return 409,{"status":"handoff_task_class_conflict","timestamp":now_iso()}
        required_authority=coordinator_required_authority(conn,d['task_id'],task[0])
        if not required_authority or required_authority!=d['required_authority']:
            conn.rollback()
            return 409,{"status":"required_authority_evidence_missing_or_changed","timestamp":now_iso()}
        if source[0]!=d['source_authority_ceiling'] or target[0]!=d['target_authority_ceiling']:
            conn.rollback()
            return 409,{"status":"handoff_authority_evidence_changed","timestamp":now_iso()}
        if _authority_rank(source[0]) < _authority_rank(d['required_authority']) or _authority_rank(target[0]) < _authority_rank(d['required_authority']):
            conn.rollback()
            return 409,{"status":"handoff_authority_insufficient","timestamp":now_iso()}
        current_execution_state='consumed' if task[2] else str(task[1] or 'unknown')
        if current_execution_state!=str(d.get('execution_approval_state') or 'unknown'):
            conn.rollback()
            return 409,{"status":"execution_approval_state_changed","timestamp":now_iso()}
        if bool(d['handoff_approval_required']) and not coordinator_handoff_authorized(conn,d):
            conn.rollback()
            return 409,{"status":"handoff_approval_required","handoff_approval_state":d['handoff_approval_state'],"timestamp":now_iso()}
        latest=conn.execute(
            "select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1",
            (d['task_id'],),
        ).fetchone()
        prior_stage=latest[0] if latest else None
        event_id=lifecycle_event_insert(
            conn,d['task_id'],'ASSIGNED',source_component='control-api-handoff',
            actor_id='control-api-authenticated',assigned_agent_id=d['target_agent_id'],
            previous_stage=prior_stage,reason_code='handoff_accepted',correlation_id=d['correlation_id'],
        )
        updated=conn.execute(
            "update task_handoffs set state='accepted',handoff_approval_state='approved',"
            "decided_by='control-api-authenticated',decided_at=?,lifecycle_event_id=?,"
            "source_readiness=?,target_readiness=? where handoff_id=? and state='requested'",
            (now_iso(),event_id,source_readiness,target_readiness,handoff_id),
        )
        if updated.rowcount!=1:
            raise RuntimeError('handoff_accept_transition_conflict')
        conn.commit()
        out=dict(conn.execute("select * from task_handoffs where handoff_id=?",(handoff_id,)).fetchone())
        return 200,{"status":"ok","handoff":out,"timestamp":now_iso()}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


'''


def replace_block(text: str, start: str, end: str, replacement: str) -> str:
    a=text.find(start)
    if a < 0:
        raise SystemExit(f"missing start anchor: {start}")
    b=text.find(end,a)
    if b < 0:
        raise SystemExit(f"missing end anchor: {end}")
    return text[:a] + replacement + text[b:]


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("path")
    args=ap.parse_args()
    p=Path(args.path)
    text=p.read_text(encoding="utf-8")
    if "A68_AUTHORIZATION" in text:
        raise SystemExit("A6.8 patch already present")
    if START not in text or ACCEPT_START not in text:
        raise SystemExit("A6.7 handoff anchors missing")
    text=replace_block(text,START,END,A68_BRIDGE)
    text=text.replace("coordinator_agent_readiness(conn,source_agent_id)","coordinator_agent_readiness(conn,source_agent_id,task_id)")
    text=text.replace("coordinator_agent_readiness(conn,target_agent_id)","coordinator_agent_readiness(conn,target_agent_id,task_id)")
    text=text.replace("(handoff_id,'2.2-a6.7.v1',task_id", "(handoff_id,'2.2-a6.8.v1',task_id",1)
    text=replace_block(text,ACCEPT_START,ACCEPT_END,A68_ACCEPT)
    p.write_text(text,encoding="utf-8")
    print("PHIL_AI_OS_PHASE_2_2_A6_8_PATCH_OK")


if __name__=="__main__":
    main()
