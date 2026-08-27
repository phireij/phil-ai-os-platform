#!/usr/bin/env python3
import json,subprocess

BASE='/opt/phil-ai-os/mission-control/read-model.py.pre-phase21o'
CONTROL='phil-ai-os-core-control-api-1'
OPEN_STAGES={'RECEIVED','CLASSIFIED','APPROVAL_PENDING','ASSIGNED','PLANNED'}

def run(cmd,timeout=30):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if p.returncode!=0:
        raise RuntimeError(p.stderr.strip() or 'command failed')
    return p.stdout.strip()

def load_base():
    return json.loads(run(['python3',BASE]))

def workload_snapshot():
    code=r'''import sqlite3,json
c=sqlite3.connect('file:/app/state/control-plane.db?mode=ro',uri=True)
c.row_factory=sqlite3.Row
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
rows=[dict(r) for r in c.execute("select task_id,stage,assigned_agent_id,occurred_at,event_id from task_lifecycle_events order by occurred_at,event_id")]
by={}
for r in rows: by.setdefault(r['task_id'],[]).append(r)
active=[]; closed=[]; ind=[]
for tid,ev in sorted(by.items()):
    assigned=any(x.get('assigned_agent_id')=='hermes' for x in ev)
    if not assigned: continue
    latest=ev[-1]['stage']
    if latest in {'ASSIGNED','PLANNED'}:
        active.append({'task_id':tid,'stage':latest}); continue
    if latest=='AUDITED':
        approvals=[dict(r) for r in c.execute("select approval_id,consumed_at,consumed_by from approval_requests where task_id=? order by created_at",(tid,))]
        audits=[dict(r) for r in c.execute("select id,approval_id,response_id,outcome,detail from execution_audit where task_id=? order by occurred_at,id",(tid,))]
        success=[a for a in audits if a.get('outcome')=='success' and a.get('response_id')]
        rejection=[a for a in audits if a.get('outcome') in {'approval_rejected','rejected','failed','cancelled'}]
        same=(len({a.get('approval_id') for a in audits if a.get('approval_id')})==1)
        unique=(len(success)==1 and c.execute("select count(*) from execution_audit where response_id=?",(success[0]['response_id'],)).fetchone()[0]==1)
        consumed=(len(approvals)==1 and approvals[0].get('consumed_at') is not None and approvals[0].get('consumed_by') is not None)
        replay=False
        if len(audits)==2 and len(success)==1 and len(rejection)==1:
            d=(rejection[0].get('detail') or '').lower(); replay=('already_consumed' in d or 'replay' in d)
        if unique and same and consumed and replay:
            closed.append({'task_id':tid,'stage':'AUDITED','reason':'one_unique_success_plus_replay_rejection'}); continue
        if len(audits)==1 and len(success)==1 and unique and same and consumed:
            closed.append({'task_id':tid,'stage':'AUDITED','reason':'one_unique_success'}); continue
        ind.append({'task_id':tid,'stage':latest,'reason':'audited_closure_not_proven'}); continue
    if latest in OPEN_STAGES:
        active.append({'task_id':tid,'stage':latest}); continue
    ind.append({'task_id':tid,'stage':latest,'reason':'unknown_or_unsupported_terminal_evidence'})
print(json.dumps({'active':active,'closed':closed,'indeterminate':ind}))'''
    return json.loads(run(['docker','exec',CONTROL,'python3','-c',code]))

def main():
    data=load_base()
    snap=workload_snapshot()
    runtime=data.setdefault('agent_runtime',{})
    presence=(runtime.get('presence') or {}).get('logical_presence')
    ind=snap['indeterminate']; active=snap['active']
    runtime['workload']={
        'source':'durable_lifecycle_plus_execution_audit_correlation',
        'evidence_complete':len(ind)==0,
        'active_task_count':len(active) if not ind else None,
        'active_states':[x['stage'] for x in active] if not ind else None,
        'active_tasks':active if not ind else None,
        'closed_tasks':snap['closed'],
        'indeterminate_tasks':ind,
        'authority_effect':'none',
    }
    r=data.get('worker_readiness') or {}
    if presence in {'stale','offline'}:
        readiness,reason='stale','logical_presence_not_fresh'
    elif presence!='fresh':
        readiness,reason='indeterminate','logical_presence_unknown'
    elif ind:
        readiness,reason='indeterminate','workload_evidence_incomplete'
    elif active:
        readiness,reason='busy','durable_active_workload_present'
    else:
        readiness,reason='ready','durable_zero_active_workload_proven'
    r.update({'schema_version':'2.1o.readiness.v1','agent_id':'hermes','task_class_scope':'general','readiness':readiness,'reason_code':reason,'authority_effect':'none','automatic_assignment':False,'automatic_retry':False,'automatic_reroute':False,'automatic_execution':False})
    data['worker_readiness']=r
    data['schema_version']='2.1o.v1'
    data.setdefault('governance',{})['worker_readiness_authority_effect']='none'
    print(json.dumps(data,sort_keys=True))

if __name__=='__main__': main()
