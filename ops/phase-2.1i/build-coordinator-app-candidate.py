#!/usr/bin/env python3
import pathlib, sys

if len(sys.argv)!=3:
    raise SystemExit('usage: build-coordinator-app-candidate.py INPUT_APP OUTPUT_APP')

src=pathlib.Path(sys.argv[1]).read_text()

if src.count('def lifecycle_event_insert(')!=1:
    raise SystemExit('expected lifecycle_event_insert exactly once')
if src.count('def approval_create(')!=1:
    raise SystemExit('expected approval_create exactly once')
if src.count('if path=="/v1/approvals/request":')!=1:
    raise SystemExit('expected approvals request route anchor exactly once')

helpers=r'''
def coordinator_task_terminal(conn, task_id):
    row=conn.execute("select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1",(task_id,)).fetchone()
    return bool(row and row[0] in {"SUCCEEDED","FAILED","DENIED","EXPIRED","CANCELLED","CLOSED"})

def coordinator_task_exists(conn, task_id):
    return conn.execute("select 1 from approval_requests where task_id=?",(task_id,)).fetchone() is not None

def coordinator_assign(task_id, agent_id, requested_by="control-api", reason_code=None):
    conn=db()
    try:
        if not coordinator_task_exists(conn,task_id):
            return 404,{"status":"task_not_found","task_id":task_id}
        if coordinator_task_terminal(conn,task_id):
            return 409,{"status":"task_terminal","task_id":task_id}
        agent=conn.execute("select agent_id,enabled,assignable from agent_registry where agent_id=?",(agent_id,)).fetchone()
        if not agent:
            return 404,{"status":"agent_not_found","agent_id":agent_id}
        if not bool(agent[1]) or not bool(agent[2]):
            return 409,{"status":"agent_not_assignable","agent_id":agent_id}
        prior=conn.execute("select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1",(task_id,)).fetchone()
        prior_stage=prior[0] if prior else None
        event_id=lifecycle_event_insert(conn,task_id,"ASSIGNED",actor_id=requested_by,assigned_agent_id=agent_id,previous_stage=prior_stage,reason_code=reason_code or "explicit_assignment",correlation_id=agent_id)
        conn.commit()
        return 200,{"assignment":{"task_id":task_id,"agent_id":agent_id,"event_id":event_id,"stage":"ASSIGNED"}}
    finally:
        conn.close()

def coordinator_plan(task_id, plan_kind="bounded", requested_by="control-api", supersedes_plan_ref=None):
    conn=db()
    try:
        if not coordinator_task_exists(conn,task_id):
            return 404,{"status":"task_not_found","task_id":task_id}
        if coordinator_task_terminal(conn,task_id):
            return 409,{"status":"task_terminal","task_id":task_id}
        if supersedes_plan_ref and not conn.execute("select 1 from task_plans where plan_ref=? and task_id=?",(supersedes_plan_ref,task_id)).fetchone():
            return 409,{"status":"invalid_supersedes_plan_ref","task_id":task_id}
        plan_ref="pln_"+uuid.uuid4().hex
        created_at=now_iso()
        conn.execute("insert into task_plans(plan_ref,task_id,created_at,created_by,plan_kind,status,supersedes_plan_ref) values(?,?,?,?,?,?,?)",(plan_ref,task_id,created_at,requested_by,plan_kind or "bounded","recorded",supersedes_plan_ref))
        prior=conn.execute("select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1",(task_id,)).fetchone()
        prior_stage=prior[0] if prior else None
        event_id=lifecycle_event_insert(conn,task_id,"PLANNED",actor_id=requested_by,previous_stage=prior_stage,reason_code="plan_recorded",correlation_id=plan_ref)
        conn.commit()
        return 201,{"plan":{"task_id":task_id,"plan_ref":plan_ref,"plan_kind":plan_kind or "bounded","event_id":event_id,"stage":"PLANNED","supersedes_plan_ref":supersedes_plan_ref}}
    finally:
        conn.close()

'''
src=src.replace('def approval_create(',helpers+'def approval_create(',1)

route_anchor='if path=="/v1/approvals/request":'
route_code=r'''if path=="/v1/tasks/assign":
            try:
                length=int(self.headers.get("Content-Length","0") or "0")
                raw=self.rfile.read(length) if length else b"{}"
                payload=json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(payload,dict): payload={}
            except Exception:
                payload={}
            code,body=coordinator_assign(str(payload.get("task_id") or ""),str(payload.get("agent_id") or ""),str(payload.get("requested_by") or "control-api"),str(payload.get("reason_code") or "") or None)
            self._json(code,body); return
        if path=="/v1/tasks/plan":
            try:
                length=int(self.headers.get("Content-Length","0") or "0")
                raw=self.rfile.read(length) if length else b"{}"
                payload=json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(payload,dict): payload={}
            except Exception:
                payload={}
            code,body=coordinator_plan(str(payload.get("task_id") or ""),str(payload.get("plan_kind") or "bounded"),str(payload.get("requested_by") or "control-api"),str(payload.get("supersedes_plan_ref") or "") or None)
            self._json(code,body); return
        '''+route_anchor
src=src.replace(route_anchor,route_code,1)

# Guardrail: both routes must be inside do_POST after the existing authorization gate.
d_start=src.index('    def do_POST(self):')
d_end=src.find('\n    def ',d_start+10)
if d_end<0: d_end=len(src)
block=src[d_start:d_end]
if block.count('/v1/tasks/assign')!=1 or block.count('/v1/tasks/plan')!=1:
    raise SystemExit('coordinator routes not scoped to do_POST')
if 'authorized(self.headers)' not in block:
    raise SystemExit('existing Control API authorization gate not found in do_POST')
if block.index('authorized(self.headers)') > block.index('/v1/tasks/assign'):
    raise SystemExit('coordinator route appears before authorization gate')

pathlib.Path(sys.argv[2]).write_text(src)
print('candidate_routes=/v1/tasks/assign,/v1/tasks/plan')
print('candidate_auth=existing_control_api_gate')
print('candidate_assignment=registry_authoritative')
print('candidate_plan_ref=server_generated')
print('candidate_execution_call=none')
print('candidate_provider_call=none')
print('candidate_authority_expansion=none')
print('PHIL_AI_OS_PHASE_2_1I_COORDINATOR_APP_CANDIDATE_BUILD_OK')
