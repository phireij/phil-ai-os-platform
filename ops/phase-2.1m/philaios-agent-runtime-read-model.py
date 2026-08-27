#!/usr/bin/env python3
import datetime,json,pathlib,subprocess

CONTROL='phil-ai-os-core-control-api-1'
HEARTBEAT=pathlib.Path('/var/lib/phil-ai-os/agent-presence/hermes.json')
FRESH_SECONDS=120
STALE_SECONDS=300
TERMINAL={'SUCCEEDED','FAILED','BLOCKED','CANCELLED','DENIED','EXPIRED','REJECTED','AUDITED','CLOSED'}

def run(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    if p.returncode!=0:
        raise RuntimeError(p.stderr.strip() or 'command failed')
    return p.stdout.strip()

def db_snapshot():
    code=r'''import sqlite3,json
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True)
c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
agent=c.execute("select agent_id,display_name,role,authority_ceiling,enabled,assignable,created_at,source_component from agent_registry where agent_id='hermes'").fetchone()
latest={}
for r in c.execute("select task_id,stage,assigned_agent_id,occurred_at,event_id from task_lifecycle_events order by occurred_at,event_id").fetchall():
    latest[r['task_id']]=dict(r)
print(json.dumps({'agent':dict(agent) if agent else None,'latest':list(latest.values())},default=str))'''
    return json.loads(run(['docker','exec',CONTROL,'python3','-c',code]))

def runtime_status():
    names=run(['docker','ps','--format','{{.Names}}']).splitlines()
    hermes=next((n for n in names if n.startswith('hermes-agent-whow')),None)
    if not hermes:
        return {'container':'absent','running':False,'restart_count':None}
    running=run(['docker','inspect',hermes,'--format','{{.State.Running}}']).lower()=='true'
    restarts=int(run(['docker','inspect',hermes,'--format','{{.RestartCount}}']))
    return {'container':hermes,'running':running,'restart_count':restarts}

def heartbeat_status(now):
    if not HEARTBEAT.exists():
        return {'logical_presence':'unknown','heartbeat_age_seconds':None,'heartbeat':None}
    hb=json.loads(HEARTBEAT.read_text(encoding='utf-8'))
    observed=datetime.datetime.fromisoformat(hb['observed_at'].replace('Z','+00:00'))
    age=max(0,int((now-observed).total_seconds()))
    if age<=FRESH_SECONDS:
        state='fresh'
    elif age<=STALE_SECONDS:
        state='stale'
    else:
        state='offline'
    return {'logical_presence':state,'heartbeat_age_seconds':age,'heartbeat':hb}

def main():
    now=datetime.datetime.now(datetime.timezone.utc)
    db=db_snapshot()
    agent=db['agent']
    runtime=runtime_status()
    hb=heartbeat_status(now)
    latest=db['latest']
    active=[r for r in latest if r.get('assigned_agent_id')=='hermes' and r.get('stage') not in TERMINAL]
    by_stage={}
    for r in active:
        by_stage[r['stage']]=by_stage.get(r['stage'],0)+1
    out={
      'schema_version':'2.1m.v1',
      'status':'ok',
      'timestamp':now.isoformat(),
      'agent':agent,
      'runtime':runtime,
      'presence':hb,
      'workload':{
        'source':'durable_latest_task_lifecycle',
        'active_task_count':len(active),
        'active_by_stage':dict(sorted(by_stage.items())),
      },
      'governance':{
        'presence_authority_effect':'none',
        'automatic_retry':False,
        'automatic_reroute':False,
        'automatic_delegation':False,
        'automatic_execution':False,
      },
    }
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__':
    main()
