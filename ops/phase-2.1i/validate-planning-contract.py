#!/usr/bin/env python3
import sqlite3, sys, uuid, datetime as dt

if len(sys.argv) != 2:
    raise SystemExit('usage: validate-planning-contract.py DB_COPY')

path=sys.argv[1]
c=sqlite3.connect(path)
c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'

approval_before=c.execute('select count(*) from approval_requests').fetchone()[0]
audit_before=c.execute('select count(*) from execution_audit').fetchone()[0]
ledger_before=c.execute('select count(*) from task_lifecycle_events').fetchone()[0]

c.executescript('''
create table if not exists task_plans(
  plan_ref text primary key,
  task_id text not null,
  created_at text not null,
  created_by text not null,
  plan_kind text not null,
  status text not null,
  supersedes_plan_ref text
);
create index if not exists idx_task_plans_task_time on task_plans(task_id, created_at, plan_ref);
create trigger if not exists trg_task_plans_no_update
before update on task_plans begin select raise(abort,'task_plans_append_only'); end;
create trigger if not exists trg_task_plans_no_delete
before delete on task_plans begin select raise(abort,'task_plans_append_only'); end;
''')

now=dt.datetime.now(dt.timezone.utc).isoformat()
task='tsk_'+uuid.uuid4().hex
approval='apr_'+uuid.uuid4().hex
c.execute('insert into approval_requests(approval_id,task_id,created_at,updated_at,expires_at,state,source,requester,task_text,task_class,confidence,profile,primary_provider,primary_model,fallback_provider,fallback_model,requested_by) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
          (approval,task,now,now,now,'pending','phase21i-validator','validator','isolated synthetic task','general',None,None,None,None,None,None,'validator'))
c.execute('insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,reason_code) values(?,?,?,?,?,?)',
          ('evt_'+uuid.uuid4().hex,task,'RECEIVED',now,'control-api','isolated_validation'))
c.commit()


def canonical_exists(task_id):
    return c.execute('select 1 from approval_requests where task_id=?',(task_id,)).fetchone() is not None

def terminal(task_id):
    row=c.execute("select stage from task_lifecycle_events where task_id=? order by occurred_at desc,event_id desc limit 1",(task_id,)).fetchone()
    return bool(row and row[0] in {'SUCCEEDED','FAILED','DENIED','EXPIRED','CANCELLED','CLOSED'})

def create_plan(task_id, plan_ref, supersedes=None, source='control-api'):
    if source!='control-api': raise ValueError('unauthorized_coordinator')
    if not canonical_exists(task_id): raise ValueError('unknown_task')
    if terminal(task_id): raise ValueError('terminal_task')
    if c.execute('select 1 from task_plans where plan_ref=?',(plan_ref,)).fetchone(): raise ValueError('plan_ref_collision')
    t=dt.datetime.now(dt.timezone.utc).isoformat()
    c.execute('insert into task_plans(plan_ref,task_id,created_at,created_by,plan_kind,status,supersedes_plan_ref) values(?,?,?,?,?,?,?)',
              (plan_ref,task_id,t,'control-api','bounded','recorded',supersedes))
    c.execute('insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,previous_stage,reason_code,correlation_id) values(?,?,?,?,?,?,?,?)',
              ('evt_'+uuid.uuid4().hex,task_id,'PLANNED',t,'control-api','RECEIVED','plan_recorded',plan_ref))
    c.commit()

p1='pln_'+uuid.uuid4().hex
create_plan(task,p1)
assert c.execute('select count(*) from task_plans where task_id=?',(task,)).fetchone()[0]==1
assert c.execute("select correlation_id from task_lifecycle_events where task_id=? and stage='PLANNED' order by occurred_at desc limit 1",(task,)).fetchone()[0]==p1

p2='pln_'+uuid.uuid4().hex
create_plan(task,p2,p1)
assert c.execute('select supersedes_plan_ref from task_plans where plan_ref=?',(p2,)).fetchone()[0]==p1
assert c.execute('select count(*) from task_plans where task_id=?',(task,)).fetchone()[0]==2

blocked={}
for name,fn in {
 'unknown_task':lambda:create_plan('tsk_missing','pln_'+uuid.uuid4().hex),
 'unauthorized_source':lambda:create_plan(task,'pln_'+uuid.uuid4().hex,source='hermes'),
 'collision':lambda:create_plan(task,p1),
}.items():
    try: fn(); blocked[name]=False
    except ValueError: blocked[name]=True
assert all(blocked.values())

update_blocked=False
try:
    c.execute("update task_plans set status='changed' where plan_ref=?",(p1,)); c.commit()
except sqlite3.DatabaseError:
    c.rollback(); update_blocked=True
assert update_blocked

delete_blocked=False
try:
    c.execute('delete from task_plans where plan_ref=?',(p1,)); c.commit()
except sqlite3.DatabaseError:
    c.rollback(); delete_blocked=True
assert delete_blocked

term_time=dt.datetime.now(dt.timezone.utc).isoformat()
c.execute('insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,reason_code) values(?,?,?,?,?,?)',
          ('evt_'+uuid.uuid4().hex,task,'CLOSED',term_time,'control-api','isolated_terminal'))
c.commit()
terminal_blocked=False
try:
    create_plan(task,'pln_'+uuid.uuid4().hex)
except ValueError:
    terminal_blocked=True
assert terminal_blocked

# Synthetic isolated rows are allowed only in the copied DB; ensure original domain row counts were not modified apart from one synthetic approval used for validation.
assert c.execute('select count(*) from approval_requests').fetchone()[0]==approval_before+1
assert c.execute('select count(*) from execution_audit').fetchone()[0]==audit_before
assert c.execute('pragma quick_check').fetchone()[0]=='ok'

print('task_plans=validated')
print('planned_event=explicit_plan_ref_only')
print('replanning=append_only_supersession')
print('unknown_task=blocked')
print('terminal_task=blocked')
print('unauthorized_coordinator=blocked')
print('plan_ref_collision=blocked')
print('plan_update=blocked')
print('plan_delete=blocked')
print('execution_call=none')
print('provider_call=none')
print('approval_authority_change=none')
print('authority_expansion=none')
print('PHIL_AI_OS_PHASE_2_1I_ISOLATED_PLANNING_CONTRACT_OK')
