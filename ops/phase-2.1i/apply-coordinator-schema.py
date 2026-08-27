#!/usr/bin/env python3
import sqlite3, sys, datetime as dt

if len(sys.argv)!=2:
    raise SystemExit('usage: apply-coordinator-schema.py DB_COPY')

path=sys.argv[1]
c=sqlite3.connect(path)
try:
    assert c.execute('pragma quick_check').fetchone()[0]=='ok'
    c.executescript('''
    create table if not exists agent_registry(
      agent_id text primary key,
      display_name text not null,
      role text not null,
      authority_ceiling text not null,
      enabled integer not null check(enabled in (0,1)),
      assignable integer not null check(assignable in (0,1)),
      created_at text not null,
      source_component text not null
    );
    create trigger if not exists trg_agent_registry_id_immutable
    before update of agent_id on agent_registry begin select raise(abort,'agent_id_immutable'); end;
    create table if not exists task_plans(
      plan_ref text primary key,
      task_id text not null,
      created_at text not null,
      created_by text not null,
      plan_kind text not null,
      status text not null,
      supersedes_plan_ref text
    );
    create index if not exists idx_task_plans_task_time on task_plans(task_id,created_at,plan_ref);
    create trigger if not exists trg_task_plans_no_update
    before update on task_plans begin select raise(abort,'task_plans_append_only'); end;
    create trigger if not exists trg_task_plans_no_delete
    before delete on task_plans begin select raise(abort,'task_plans_append_only'); end;
    ''')
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    c.execute('insert or ignore into agent_registry(agent_id,display_name,role,authority_ceiling,enabled,assignable,created_at,source_component) values(?,?,?,?,?,?,?,?)',
              ('hermes','Hermes','operational_worker','L3',1,1,now,'control-api'))
    c.commit()
    assert c.execute('pragma quick_check').fetchone()[0]=='ok'
    print('agent_registry=ready')
    print('seed_agent=hermes')
    print('task_plans=ready')
    print('authority_expansion=none')
    print('PHIL_AI_OS_PHASE_2_1I_COORDINATOR_SCHEMA_COPY_OK')
finally:
    c.close()
