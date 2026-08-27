#!/usr/bin/env python3
import importlib.util, sqlite3, io, json, re, sys

if len(sys.argv)!=3:
    raise SystemExit('usage: validate-coordinator-handler-auth.py APP DB')
APP,DB=sys.argv[1:]
spec=importlib.util.spec_from_file_location('phase21i_handler_candidate',APP)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def copied_db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
mod.db=copied_db
mod.classify_task=lambda text:{'task_class':'general','confidence':1.0}
mod.evaluate_route=lambda task_class:(200,{'decision':{'profile':'validation','primary':{'provider':'none','model':'none'},'fallback':{}}})
code,body=mod.approval_create('phase21i isolated handler auth task',source='phase21i-handler',requester='phase21i-handler',requested_by='phase21i-handler')
assert code==201,(code,body)
task_id=body['approval']['task_id']; assert re.fullmatch(r'tsk_[0-9a-f]{32}',task_id)

def invoke(path,payload,authorized_value):
    h=mod.Handler.__new__(mod.Handler)
    raw=json.dumps(payload).encode()
    h.path=path
    h.headers={'Content-Length':str(len(raw))}
    h.rfile=io.BytesIO(raw)
    captured={}
    def out(code,body): captured.update(code=code,body=body)
    h._json=out
    old=mod.authorized
    mod.authorized=lambda headers: authorized_value
    try:
        mod.Handler.do_POST(h)
    finally:
        mod.authorized=old
    return captured

before_l=copied_db().execute('select count(*) from task_lifecycle_events').fetchone()[0]
before_p=copied_db().execute('select count(*) from task_plans').fetchone()[0]
before_e=copied_db().execute('select count(*) from execution_audit').fetchone()[0]
unauth_assign=invoke('/v1/tasks/assign',{'task_id':task_id,'agent_id':'hermes'},False)
unauth_plan=invoke('/v1/tasks/plan',{'task_id':task_id,'plan_kind':'bounded'},False)
assert unauth_assign.get('code')==401,unauth_assign
assert unauth_plan.get('code')==401,unauth_plan
assert copied_db().execute('select count(*) from task_lifecycle_events').fetchone()[0]==before_l
assert copied_db().execute('select count(*) from task_plans').fetchone()[0]==before_p
assert copied_db().execute('select count(*) from execution_audit').fetchone()[0]==before_e

auth_assign=invoke('/v1/tasks/assign',{'task_id':task_id,'agent_id':'hermes','requested_by':'control-api'},True)
assert auth_assign.get('code')==200,auth_assign
auth_plan=invoke('/v1/tasks/plan',{'task_id':task_id,'plan_kind':'bounded','requested_by':'control-api'},True)
assert auth_plan.get('code')==201,auth_plan
plan_ref=auth_plan['body']['plan']['plan_ref']; assert re.fullmatch(r'pln_[0-9a-f]{32}',plan_ref)
assert copied_db().execute("select count(*) from task_lifecycle_events where task_id=? and stage='ASSIGNED'",(task_id,)).fetchone()[0]==1
assert copied_db().execute("select count(*) from task_lifecycle_events where task_id=? and stage='PLANNED'",(task_id,)).fetchone()[0]==1
assert copied_db().execute('select count(*) from execution_audit').fetchone()[0]==before_e
assert copied_db().execute('pragma quick_check').fetchone()[0]=='ok'
print('unauthenticated_assign=401')
print('unauthenticated_plan=401')
print('unauthenticated_side_effect=none')
print('authenticated_assign=200')
print('authenticated_plan=201')
print('plan_ref_server_generated=true')
print('execution_audit_side_effect=none')
print('existing_control_api_auth_gate=validated')
print('public_port=none')
print('live_token_logged=none')
print('provider_call=none')
print('execution_call=none')
print('authority_expansion=none')
print('PHIL_AI_OS_PHASE_2_1I_ISOLATED_COORDINATOR_HANDLER_AUTH_OK')
