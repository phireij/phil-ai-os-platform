#!/usr/bin/env python3
import sqlite3, sys

if len(sys.argv)!=2:
    raise SystemExit('usage: apply-lifecycle-ledger-migration.py DB_PATH')

c=sqlite3.connect(sys.argv[1])
try:
    assert c.execute('pragma quick_check').fetchone()[0]=='ok'
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
    c.commit()
    assert c.execute('pragma quick_check').fetchone()[0]=='ok'
finally:
    c.close()

print('lifecycle_ledger_migration=applied')
print('append_only_update_trigger=present')
print('append_only_delete_trigger=present')
print('PHIL_AI_OS_PHASE_2_1H_LEDGER_MIGRATION_APPLY_OK')
