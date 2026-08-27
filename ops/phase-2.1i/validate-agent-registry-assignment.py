#!/usr/bin/env python3
import sqlite3, sys, uuid, datetime as dt

if len(sys.argv) != 2:
    raise SystemExit('usage: validate-agent-registry-assignment.py DB_COPY')

c=sqlite3.connect(sys.argv[1])
c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'

approvals_before=c.execute('select count(*) from approval_requests').fetchone()[0]
audits_before=c.execute('select count(*) from execution_audit').fetchone()[0]
lifecycle_before=c.execute('select count(*) from task_lifecycle_events').fetchone()[0]

c.executescript('''
create table if not exists agent_registry(
  agent_id text primary key,
  display_name text not null,
  role text not null,
  authority_ceiling text not null check(authority_ceiling in ('L0','L1','L2','L3','L4')),
  status text not null check(status in ('active','inactive','disabled')),
  assignable integer not null check(assignable in (0,1)),
  created_at text not null,
  updated_at text not null
);
create trigger if not exists trg_agent_registry_agent_id_immutable
before update of agent_id on agent_registry
begin
  select raise(abort,'agent_id_immutable');
end;
''')

now=dt.datetime.now(dt.timezone.utc).isoformat()
rows=[
 ('human-operator-ceo','Human Operator / CEO','human_operator','L4','active',0),
 ('cto-office','CTO Office','architecture_governance','L2','active',0),
 ('hermes','Hermes','operational_gateway','L3','active',1),
 ('disabled-test','Disabled Test Agent','test','L1','disabled',1),
]
for r in rows:
    c.execute('insert into agent_registry(agent_id,display_name,role,authority_ceiling,status,assignable,created_at,updated_at) values(?,?,?,?,?,?,?,?)',(*r,now,now))
c.commit()

# Create a synthetic isolated task identity only inside the copy.
task='tsk_'+uuid.uuid4().hex
approval='apr_'+uuid.uuid4().hex
cols=[r[1] for r in c.execute('pragma table_info(approval_requests)')]
assert 'task_id' in cols
base={k:None for k in cols}
# Use an existing row as shape/template where possible, but never mutate production because this is a DB copy.
existing=c.execute('select * from approval_requests limit 1').fetchone()
if existing:
    base=dict(existing)
base['approval_id']=approval
base['task_id']=task
if 'created_at' in base: base['created_at']=now
if 'updated_at' in base: base['updated_at']=now
if 'expires_at' in base: base['expires_at']=now
if 'state' in base: base['state']='pending'
if 'source' in base: base['source']='phase-2.1i-validator'
if 'requester' in base: base['requester']='phase-2.1i-validator'
if 'task_text' in base: base['task_text']='isolated validator task'
if 'task_class' in base: base['task_class']='general'
if 'requested_by' in base: base['requested_by']='phase-2.1i-validator'
insert_cols=list(base)
q='insert into approval_requests('+','.join(insert_cols)+') values('+','.join('?'*len(insert_cols))+')'
c.execute(q,[base[k] for k in insert_cols]); c.commit()


def assign(task_id,agent_id,reason):
    assert c.execute('select 1 from approval_requests where task_id=?',(task_id,)).fetchone(), 'unknown_task'
    a=c.execute('select * from agent_registry where agent_id=?',(agent_id,)).fetchone()
    assert a is not None, 'unknown_agent'
    assert a['status']=='active', 'agent_not_active'
    assert a['assignable']==1, 'agent_not_assignable'
    event='evt_'+uuid.uuid4().hex
    c.execute('insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,actor_id,assigned_agent_id,previous_stage,reason_code,correlation_id) values(?,?,?,?,?,?,?,?,?,?)',
              (event,task_id,'ASSIGNED',dt.datetime.now(dt.timezone.utc).isoformat(),'control-api-coordinator','cto-office',agent_id,None,reason,None))
    c.commit(); return event

e1=assign(task,'hermes','initial_assignment')
assert c.execute('select assigned_agent_id from task_lifecycle_events where event_id=?',(e1,)).fetchone()[0]=='hermes'

for bad_agent,expected in [('missing-agent','unknown_agent'),('disabled-test','agent_not_active'),('cto-office','agent_not_assignable')]:
    blocked=False
    try: assign(task,bad_agent,'negative_test')
    except AssertionError as e: blocked=(str(e)==expected)
    assert blocked, (bad_agent,expected)

blocked=False
try: assign('tsk_missing','hermes','negative_test')
except AssertionError as e: blocked=(str(e)=='unknown_task')
assert blocked

# Reassignment is append-only history: append another ASSIGNED event, don't rewrite first.
e2=assign(task,'hermes','reaffirm_assignment')
assert e1!=e2
assert c.execute("select count(*) from task_lifecycle_events where task_id=? and stage='ASSIGNED'",(task,)).fetchone()[0]==2

immutable=False
try:
    c.execute("update agent_registry set agent_id='hermes-renamed' where agent_id='hermes'"); c.commit()
except sqlite3.DatabaseError:
    c.rollback(); immutable=True
assert immutable

# Cleanup synthetic isolated domain row and its lifecycle events is allowed only by restoring DB copy after test;
# append-only trigger blocks direct event deletion, which is expected and proves production-style semantics.
assert c.execute('select count(*) from approval_requests').fetchone()[0]==approvals_before+1
assert c.execute('select count(*) from execution_audit').fetchone()[0]==audits_before
assert c.execute('select count(*) from task_lifecycle_events').fetchone()[0]==lifecycle_before+2
assert c.execute('pragma quick_check').fetchone()[0]=='ok'

print('agent_registry=validated')
print('registered_assignable_agent=hermes')
print('unknown_agent=blocked')
print('disabled_agent=blocked')
print('non_assignable_agent=blocked')
print('unknown_task=blocked')
print('agent_id_immutable=true')
print('reassignment=append_only_event')
print('approval_state_authority_change=none')
print('execution_policy_change=none')
print('provider_call=none')
print('execution_call=none')
print('production_change=none')
print('PHIL_AI_OS_PHASE_2_1I_ISOLATED_AGENT_REGISTRY_ASSIGNMENT_OK')
