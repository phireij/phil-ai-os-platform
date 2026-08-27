#!/usr/bin/env python3
import sqlite3, sys, uuid, datetime as dt

if len(sys.argv) != 2:
    raise SystemExit('usage: validate-lifecycle-ledger-migration.py DB_COPY')

path=sys.argv[1]
c=sqlite3.connect(path)
c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'

approval_before=c.execute('select count(*) from approval_requests').fetchone()[0]
audit_before=c.execute('select count(*) from execution_audit').fetchone()[0]
null_approval_before=c.execute('select count(*) from approval_requests where task_id is null').fetchone()[0]
null_audit_before=c.execute('select count(*) from execution_audit where task_id is null').fetchone()[0]

c.executescript('''
create table if not exists task_lifecycle_events(
  event_id text primary key,
  task_id text not null,
  stage text not null,
  occurred_at text not null,
  source_component text not null,
  actor_id text,
  assigned_agent_id text,
  previous_stage text,
  reason_code text,
  correlation_id text
);
create index if not exists idx_task_lifecycle_events_task_time
  on task_lifecycle_events(task_id, occurred_at, event_id);
create index if not exists idx_task_lifecycle_events_agent_time
  on task_lifecycle_events(assigned_agent_id, occurred_at);
create trigger if not exists trg_task_lifecycle_events_no_update
before update on task_lifecycle_events
begin
  select raise(abort,'task_lifecycle_events_append_only');
end;
create trigger if not exists trg_task_lifecycle_events_no_delete
before delete on task_lifecycle_events
begin
  select raise(abort,'task_lifecycle_events_append_only');
end;
''')

cols=[r[1] for r in c.execute('pragma table_info(task_lifecycle_events)')]
expected=['event_id','task_id','stage','occurred_at','source_component','actor_id','assigned_agent_id','previous_stage','reason_code','correlation_id']
assert cols==expected, cols

task='tsk_'+uuid.uuid4().hex
now=dt.datetime.now(dt.timezone.utc)
rows=[
 ('RECEIVED','control-api',None,None,None),
 ('CLASSIFIED','control-api',None,'RECEIVED','classification_finalized'),
 ('APPROVAL_PENDING','control-api',None,'CLASSIFIED','approval_created'),
 ('ASSIGNED','task-coordinator','hermes','APPROVAL_PENDING','explicit_assignment'),
]
ids=[]
for i,(stage,source,assigned,prev,reason) in enumerate(rows):
    event='evt_'+uuid.uuid4().hex
    ids.append(event)
    occurred=(now+dt.timedelta(microseconds=i)).isoformat()
    c.execute('insert into task_lifecycle_events(event_id,task_id,stage,occurred_at,source_component,actor_id,assigned_agent_id,previous_stage,reason_code,correlation_id) values(?,?,?,?,?,?,?,?,?,?)',
              (event,task,stage,occurred,source,None,assigned,prev,reason,None))
c.commit()

ledger=[dict(r) for r in c.execute('select * from task_lifecycle_events where task_id=? order by occurred_at,event_id',(task,))]
assert [x['stage'] for x in ledger]==['RECEIVED','CLASSIFIED','APPROVAL_PENDING','ASSIGNED']
assert ledger[-1]['assigned_agent_id']=='hermes'
assert all(x['task_id']==task for x in ledger)
assert len({x['event_id'] for x in ledger})==4

update_blocked=False
try:
    c.execute("update task_lifecycle_events set stage='CLOSED' where event_id=?",(ids[0],)); c.commit()
except sqlite3.DatabaseError:
    c.rollback(); update_blocked=True
assert update_blocked

delete_blocked=False
try:
    c.execute('delete from task_lifecycle_events where event_id=?',(ids[0],)); c.commit()
except sqlite3.DatabaseError:
    c.rollback(); delete_blocked=True
assert delete_blocked

assert c.execute('select count(*) from approval_requests').fetchone()[0]==approval_before
assert c.execute('select count(*) from execution_audit').fetchone()[0]==audit_before
assert c.execute('select count(*) from approval_requests where task_id is null').fetchone()[0]==null_approval_before
assert c.execute('select count(*) from execution_audit where task_id is null').fetchone()[0]==null_audit_before
assert c.execute('pragma quick_check').fetchone()[0]=='ok'

print('ledger_table=task_lifecycle_events')
print('ledger_columns='+','.join(cols))
print('synthetic_task_id_format=tsk_uuid4hex')
print('synthetic_event_id_format=evt_uuid4hex')
print('synthetic_event_count=4')
print('assignment_event=explicit_only')
print('append_only_update=blocked')
print('append_only_delete=blocked')
print('historical_null_task_ids_unchanged=true')
print('approval_rows_unchanged=true')
print('execution_rows_unchanged=true')
print('quick_check=ok')
print('PHIL_AI_OS_PHASE_2_1H_ISOLATED_LEDGER_MIGRATION_OK')
