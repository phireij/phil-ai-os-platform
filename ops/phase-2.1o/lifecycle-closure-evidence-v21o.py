#!/usr/bin/env python3
import json
from collections import defaultdict

OPEN_STAGES = {'RECEIVED','CLASSIFIED','APPROVAL_PENDING','ASSIGNED','PLANNED'}
KNOWN_STAGES = OPEN_STAGES | {'AUDITED'}

def classify_task(task):
    events = task.get('events')
    if not isinstance(events, list) or not events:
        return {'classification':'closure_indeterminate','reason':'missing_lifecycle_evidence'}
    stages=[]
    for e in events:
        if not isinstance(e, dict) or not e.get('stage'):
            return {'classification':'closure_indeterminate','reason':'malformed_lifecycle_record'}
        stage=e['stage']
        if stage not in KNOWN_STAGES:
            return {'classification':'closure_indeterminate','reason':'unknown_lifecycle_stage'}
        stages.append(stage)
    latest=stages[-1]
    if latest in OPEN_STAGES:
        return {'classification':'open_proven','reason':'latest_stage_nonterminal','latest_stage':latest}

    # AUDITED is terminal only when a uniquely correlated established governed
    # execution outcome is explicitly supplied in durable isolated evidence.
    executions=task.get('execution_outcomes') or []
    task_id=task.get('task_id')
    valid=[]
    for x in executions:
        if not isinstance(x, dict):
            continue
        if x.get('task_id') != task_id:
            continue
        if x.get('governed') is not True:
            continue
        if x.get('outcome') not in {'succeeded','failed','cancelled','rejected'}:
            continue
        if not x.get('execution_id') or not x.get('audit_id'):
            continue
        valid.append((x.get('execution_id'),x.get('audit_id'),x.get('outcome')))
    uniq=set(valid)
    if len(uniq)==1 and len(valid)==1:
        return {'classification':'closed_proven','reason':'unique_governed_outcome_correlation','latest_stage':latest}
    if not valid:
        return {'classification':'closure_indeterminate','reason':'missing_governed_outcome_correlation','latest_stage':latest}
    return {'classification':'closure_indeterminate','reason':'ambiguous_or_replayed_correlation','latest_stage':latest}

def classify_worker(tasks, agent_id='hermes'):
    relevant=[]
    for t in tasks:
        assigned=t.get('assigned_agent_id')
        if assigned is not None and assigned != agent_id:
            continue
        relevant.append((t, classify_task(t)))
    ind=[r for _,r in relevant if r['classification']=='closure_indeterminate']
    open_rows=[(t,r) for t,r in relevant if r['classification']=='open_proven' and t.get('assigned_agent_id')==agent_id]
    return {
        'evidence_complete': not ind,
        'active_task_count': len(open_rows) if not ind else None,
        'active_states': [r.get('latest_stage') for _,r in open_rows] if not ind else None,
        'indeterminate_count': len(ind),
        'authority_effect':'none',
        'automatic_assignment':False,
        'automatic_retry':False,
        'automatic_reroute':False,
        'automatic_execution':False,
    }

def _task(task_id, stages, assigned='hermes', outcomes=None):
    return {'task_id':task_id,'assigned_agent_id':assigned,'events':[{'stage':s} for s in stages],'execution_outcomes':outcomes or []}

def selftest():
    cases={}
    cases['assigned_planned_unclosed']=classify_task(_task('t1',['RECEIVED','ASSIGNED','PLANNED']))
    assert cases['assigned_planned_unclosed']['classification']=='open_proven'

    good=[{'task_id':'t2','execution_id':'e2','audit_id':'a2','governed':True,'outcome':'succeeded'}]
    cases['correlated_audited']=classify_task(_task('t2',['RECEIVED','ASSIGNED','PLANNED','AUDITED'],outcomes=good))
    assert cases['correlated_audited']['classification']=='closed_proven'

    cases['audited_missing_correlation']=classify_task(_task('t3',['AUDITED']))
    assert cases['audited_missing_correlation']['classification']=='closure_indeterminate'

    replay=[
      {'task_id':'t4','execution_id':'e4','audit_id':'a4','governed':True,'outcome':'succeeded'},
      {'task_id':'t4','execution_id':'e4','audit_id':'a4','governed':True,'outcome':'succeeded'},
    ]
    cases['replayed_correlation']=classify_task(_task('t4',['AUDITED'],outcomes=replay))
    assert cases['replayed_correlation']['classification']=='closure_indeterminate'

    cross=[{'task_id':'other','execution_id':'e5','audit_id':'a5','governed':True,'outcome':'succeeded'}]
    cases['cross_task_correlation']=classify_task(_task('t5',['AUDITED'],outcomes=cross))
    assert cases['cross_task_correlation']['classification']=='closure_indeterminate'

    cases['unknown_stage']=classify_task(_task('t6',['RUNNING']))
    assert cases['unknown_stage']['classification']=='closure_indeterminate'

    w1=classify_worker([_task('t7',['ASSIGNED','PLANNED'])])
    assert w1['evidence_complete'] is True and w1['active_task_count']==1 and w1['active_states']==['PLANNED']

    w2=classify_worker([_task('t8',['AUDITED'])])
    assert w2['evidence_complete'] is False and w2['active_task_count'] is None

    w3=classify_worker([_task('t9',['AUDITED'],outcomes=[{'task_id':'t9','execution_id':'e9','audit_id':'a9','governed':True,'outcome':'succeeded'}])])
    assert w3['evidence_complete'] is True and w3['active_task_count']==0 and w3['active_states']==[]

    out={'schema_version':'2.1o.o2.v1','cases':cases,'worker_open':w1,'worker_indeterminate':w2,'worker_zero_active':w3}
    print(json.dumps(out,sort_keys=True))
    print('PHIL_AI_OS_PHASE_2_1O_O2_ISOLATED_LIFECYCLE_CLOSURE_VALIDATION_OK')

if __name__=='__main__':
    selftest()
