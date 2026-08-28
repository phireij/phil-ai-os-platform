#!/usr/bin/env python3
"""Patch the live Control API source with the Phase 2.2 A6.7 inert handoff writer.

This patch is intentionally fail-closed:
- request cannot persist a handoff until authoritative required-authority evidence exists;
- acceptance requires target eligibility, authoritative ready state, unchanged authority/class evidence,
  and separately approved handoff authorization;
- no provider or execution route is invoked by these functions.
"""
from __future__ import annotations

import argparse
from pathlib import Path


MIGRATION_ANCHOR = "        # v0.19 approval-to-execution audit trace.\n"
FUNCTION_ANCHOR = 'def coordinator_assign(task_id, agent_id, requested_by="control-api", reason_code=None):\n'
ROUTE_ANCHOR = '        if path=="/v1/tasks/assign":\n'

MIGRATION = '''        # Phase 2.2 A6.7 additive inert handoff persistence.
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS task_handoffs(
            handoff_id TEXT PRIMARY KEY,
            handoff_version TEXT NOT NULL,
            task_id TEXT NOT NULL,
            source_agent_id TEXT NOT NULL,
            target_agent_id TEXT NOT NULL,
            task_class TEXT NOT NULL,
            required_authority TEXT NOT NULL,
            source_authority_ceiling TEXT NOT NULL,
            target_authority_ceiling TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            correlation_id TEXT NOT NULL UNIQUE,
            requested_by TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            handoff_approval_required INTEGER NOT NULL,
            handoff_approval_state TEXT NOT NULL,
            execution_approval_state TEXT,
            source_readiness TEXT,
            target_readiness TEXT,
            state TEXT NOT NULL,
            decided_by TEXT,
            decided_at TEXT,
            containment_reason TEXT,
            lifecycle_event_id TEXT UNIQUE
        );
        CREATE INDEX IF NOT EXISTS idx_task_handoffs_task_requested
          ON task_handoffs(task_id,requested_at,handoff_id);
        CREATE INDEX IF NOT EXISTS idx_task_handoffs_state_expires
          ON task_handoffs(state,expires_at);
        """)

'''

FUNCTIONS = r'''HANDOFF_TTL_SECONDS = 900


def _authority_rank(value):
    return {"L0":0,"L1":1,"L2":2,"L3":3,"L4":4}.get(str(value),-1)


def coordinator_current_owner(conn, task_id):
    row=conn.execute(
        "select assigned_agent_id from task_lifecycle_events "
        "where task_id=? and stage='ASSIGNED' and assigned_agent_id is not null "
        "order by occurred_at desc,event_id desc limit 1",
        (task_id,),
    ).fetchone()
    return row[0] if row else None


def coordinator_agent_readiness(conn, agent_id):
    row=conn.execute(
        "select enabled,assignable from agent_registry where agent_id=?",
        (agent_id,),
    ).fetchone()
    if not row:
        return "unknown"
    if not bool(row[0]) or not bool(row[1]):
        return "unassignable"
    # A6.7 does not infer readiness from registry alone. Multi-agent authenticated
    # presence + durable workload evidence is a later governed gate.
    return "indeterminate"


def coordinator_required_authority(conn, task_id, task_class):
    # Production does not yet expose authoritative required-authority evidence.
    # A6.7 MUST NOT invent a level from target identity, source identity, or task class.
    # A later governed gate may replace this with an authoritative policy source.
    return None


def coordinator_handoff_request(task_id, target_agent_id, reason_code, requested_by="control-api"):
    task_id=(task_id or "").strip()
    target_agent_id=(target_agent_id or "").strip()
    reason_code=(reason_code or "handoff_requested").strip()[:128]
    requested_by=(requested_by or "control-api").strip()[:128]
    if not task_id or not target_agent_id:
        return 400,{"status":"invalid_request","detail":"task_id and target_agent_id are required","timestamp":now_iso()}
    conn=db()
    try:
        if not coordinator_task_exists(conn,task_id):
            return 404,{"status":"task_not_found","task_id":task_id,"timestamp":now_iso()}
        if coordinator_task_terminal(conn,task_id):
            return 409,{"status":"task_terminal","task_id":task_id,"timestamp":now_iso()}
        source_agent_id=coordinator_current_owner(conn,task_id)
        if not source_agent_id:
            return 409,{"status":"source_owner_unknown","task_id":task_id,"timestamp":now_iso()}
        if source_agent_id==target_agent_id:
            return 409,{"status":"same_agent_handoff_forbidden","task_id":task_id,"timestamp":now_iso()}
        source=conn.execute(
            "select authority_ceiling from agent_registry where agent_id=?",
            (source_agent_id,),
        ).fetchone()
        target=conn.execute(
            "select authority_ceiling from agent_registry where agent_id=?",
            (target_agent_id,),
        ).fetchone()
        if not source:
            return 409,{"status":"source_agent_not_registered","agent_id":source_agent_id,"timestamp":now_iso()}
        if not target:
            return 404,{"status":"target_agent_not_found","agent_id":target_agent_id,"timestamp":now_iso()}
        task=conn.execute(
            "select task_class,state,consumed_at from approval_requests "
            "where task_id=? order by created_at desc limit 1",
            (task_id,),
        ).fetchone()
        if not task:
            return 409,{"status":"task_policy_evidence_missing","task_id":task_id,"timestamp":now_iso()}
        task_class=task[0]
        if task_class!='general' or EXECUTION_ALLOWED_TASK_CLASSES!={"general"}:
            return 409,{"status":"handoff_scope_not_allowed","task_class":task_class,"timestamp":now_iso()}
        required_authority=coordinator_required_authority(conn,task_id,task_class)
        if not required_authority:
            return 409,{"status":"required_authority_evidence_missing","task_id":task_id,"timestamp":now_iso()}
        if _authority_rank(source[0]) < _authority_rank(required_authority) or _authority_rank(target[0]) < _authority_rank(required_authority):
            return 409,{"status":"authority_ceiling_insufficient","required_authority":required_authority,"timestamp":now_iso()}
        handoff_id='hof_'+uuid.uuid4().hex
        correlation_id='hofcorr_'+uuid.uuid4().hex
        requested_at=now_iso()
        expires_at=(datetime.now(timezone.utc)+timedelta(seconds=HANDOFF_TTL_SECONDS)).isoformat()
        execution_state='consumed' if task[2] else str(task[1] or 'unknown')
        source_readiness=coordinator_agent_readiness(conn,source_agent_id)
        target_readiness=coordinator_agent_readiness(conn,target_agent_id)
        conn.execute("""insert into task_handoffs(
            handoff_id,handoff_version,task_id,source_agent_id,target_agent_id,task_class,required_authority,
            source_authority_ceiling,target_authority_ceiling,reason_code,correlation_id,requested_by,requested_at,expires_at,
            handoff_approval_required,handoff_approval_state,execution_approval_state,source_readiness,target_readiness,state)
            values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (handoff_id,'2.2-a6.7.v1',task_id,source_agent_id,target_agent_id,task_class,required_authority,
             source[0],target[0],reason_code,correlation_id,requested_by,requested_at,expires_at,
             1,'pending',execution_state,source_readiness,target_readiness,'requested'))
        conn.commit()
        return 201,{"status":"ok","handoff":{"handoff_id":handoff_id,"task_id":task_id,
            "source_agent_id":source_agent_id,"target_agent_id":target_agent_id,"state":"requested",
            "handoff_approval_required":True,"handoff_approval_state":"pending",
            "source_readiness":source_readiness,"target_readiness":target_readiness,
            "correlation_id":correlation_id,"expires_at":expires_at},"timestamp":now_iso()}
    finally:
        conn.close()


def coordinator_handoff_accept(handoff_id):
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
        if not source:
            conn.rollback()
            return 409,{"status":"source_agent_not_registered","timestamp":now_iso()}
        source_readiness=coordinator_agent_readiness(conn,d['source_agent_id'])
        target_readiness=coordinator_agent_readiness(conn,d['target_agent_id'])
        if source_readiness!='ready' or target_readiness!='ready':
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
        if bool(d['handoff_approval_required']) and d['handoff_approval_state']!='approved':
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
            "update task_handoffs set state='accepted',decided_by='control-api-authenticated',decided_at=?,"
            "lifecycle_event_id=?,source_readiness=?,target_readiness=? where handoff_id=? and state='requested'",
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


def coordinator_handoff_reject(handoff_id):
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
        if d['state']=='rejected':
            conn.rollback()
            return 200,{"status":"ok","handoff":d,"idempotent_replay":True,"timestamp":now_iso()}
        if d['state']!='requested':
            conn.rollback()
            return 409,{"status":"handoff_terminal","state":d['state'],"timestamp":now_iso()}
        now=now_iso()
        conn.execute(
            "update task_handoffs set state='rejected',decided_by='control-api-authenticated',decided_at=?,"
            "containment_reason='explicit_rejection' where handoff_id=? and state='requested'",
            (now,handoff_id),
        )
        conn.commit()
        out=dict(conn.execute("select * from task_handoffs where handoff_id=?",(handoff_id,)).fetchone())
        return 200,{"status":"ok","handoff":out,"timestamp":now_iso()}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


'''

ROUTES = r'''        if path=="/v1/tasks/handoff/request":
            try:
                length=int(self.headers.get("Content-Length","0") or "0")
                raw=self.rfile.read(min(length,4096)) if length else b"{}"
                payload=json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(payload,dict): payload={}
            except Exception:
                payload={}
            code,body=coordinator_handoff_request(
                str(payload.get("task_id") or ""),
                str(payload.get("target_agent_id") or ""),
                str(payload.get("reason_code") or "handoff_requested"),
                str(payload.get("requested_by") or "control-api"),
            )
            self._json(code,body); return
        if path=="/v1/tasks/handoff/accept":
            try:
                length=int(self.headers.get("Content-Length","0") or "0")
                raw=self.rfile.read(min(length,4096)) if length else b"{}"
                payload=json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(payload,dict): payload={}
            except Exception:
                payload={}
            code,body=coordinator_handoff_accept(str(payload.get("handoff_id") or ""))
            self._json(code,body); return
        if path=="/v1/tasks/handoff/reject":
            try:
                length=int(self.headers.get("Content-Length","0") or "0")
                raw=self.rfile.read(min(length,4096)) if length else b"{}"
                payload=json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(payload,dict): payload={}
            except Exception:
                payload={}
            code,body=coordinator_handoff_reject(str(payload.get("handoff_id") or ""))
            self._json(code,body); return
'''


def patch(text: str) -> str:
    if "Phase 2.2 A6.7 additive inert handoff persistence" in text:
        raise SystemExit("source already contains A6.7 patch")
    for anchor, label in (
        (MIGRATION_ANCHOR, "migration"),
        (FUNCTION_ANCHOR, "function"),
        (ROUTE_ANCHOR, "route"),
    ):
        count = text.count(anchor)
        if count != 1:
            raise SystemExit(f"expected exactly one {label} anchor, found {count}")
    text = text.replace(MIGRATION_ANCHOR, MIGRATION + MIGRATION_ANCHOR, 1)
    text = text.replace(FUNCTION_ANCHOR, FUNCTIONS + FUNCTION_ANCHOR, 1)
    text = text.replace(ROUTE_ANCHOR, ROUTES + ROUTE_ANCHOR, 1)
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--output")
    args = ap.parse_args()
    src = Path(args.source)
    out = Path(args.output) if args.output else src
    text = src.read_text(encoding="utf-8")
    out.write_text(patch(text), encoding="utf-8")


if __name__ == "__main__":
    main()
