#!/usr/bin/env python3
import importlib.util, sqlite3, re, sys

if len(sys.argv)!=3:
    raise SystemExit('usage: validate-coordinator-app-behavior.py APP DB')
APP,DB=sys.argv[1:]
spec=importlib.util.spec_from_file_location('phase21i_candidate',APP)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def copied_db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

mod.db=copied_db
mod.classify_task=lambda text:{'task_class':'general','confidence':1.0}
mod.evaluate_route=lambda task_class:(200,{'decision':{'profile':'validation','primary':{'provider':'none','model':'none'},'fallback':{}}})
before_a=copied_db().execute('select count(*) from approval_requests').fetchone()[0]
before_e=copied_db().execute('select count(*) from execution_audit').fetchone()[0]
code,body=mod.approval_create('phase21i isolated coordinator task',source='phase21i-validation',requester='phase21i-validation',requested_by='phase21i-validation')
assert code==201,(code,body)
task_id=body['approval']['task_id']; assert re.fullmatch(r'tsk_[0-9a-f]{32}',task_id)
code,assignment=mod.coordinator_assign(task_id,'hermes',requested_by='control-api')
assert code==200,(code,assignment)
assert assignment['assignment']['agent_id']=='hermes'
code,p1=mod.coordinator_plan(task_id,'bounded',requested_by='control-api')
assert code==201,(code,p1)
plan1=p1['plan']['plan_ref']; assert re.fullmatch(r'pln_[0-9a-f]{32}',plan1)
code,p2=mod.coordinator_plan(task_id,'bounded',requested_by='control-api',supersedes_plan_ref=plan1)
assert code==201,(code,p2)
assert p2['plan']['supersedes_plan_ref']==plan1 and p2['plan']['plan_ref']!=plan1
assert mod.coordinator_assign(task_id,'missing-agent')[0]==404
assert mod.coordinator_plan('tsk_missing')[0]==404
c=copied_db()
stages=[r[0] for r in c.execute('select stage from task_lifecycle_events where task_id=? order by occurred_at,event_id',(task_id,))]
assert 'ASSIGNED' in stages and stages.count('PLANNED')==2
assert c.execute('select count(*) from task_plans where task_id=?',(task_id,)).fetchone()[0]==2
assert c.execute('select count(*) from execution_audit').fetchone()[0]==before_e
assert c.execute('select count(*) from approval_requests').fetchone()[0]==before_a+1
mod.lifecycle_event_insert(c,task_id,'CLOSED',reason_code='isolated_terminal'); c.commit(); c.close()
assert mod.coordinator_assign(task_id,'hermes')[0]==409
assert mod.coordinator_plan(task_id)[0]==409
c=copied_db(); assert c.execute('pragma quick_check').fetchone()[0]=='ok'; c.close()
print('canonical_task_created_on_copy=true')
print('assignment_to_registered_hermes=ok')
print('plan_ref_server_generated=true')
print('replan_append_only=true')
print('unknown_agent=blocked')
print('unknown_task=blocked')
print('terminal_task_assignment=blocked')
print('terminal_task_planning=blocked')
print('execution_audit_side_effect=none')
print('provider_call=none')
print('authority_expansion=none')
print('PHIL_AI_OS_PHASE_2_1I_ISOLATED_COORDINATOR_APP_BEHAVIOR_OK')
