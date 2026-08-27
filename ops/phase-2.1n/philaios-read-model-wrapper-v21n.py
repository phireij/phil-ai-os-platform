#!/usr/bin/env python3
import json,subprocess

BASE='/opt/phil-ai-os/mission-control/read-model.py.pre-phase21n'

def load(path):
    p=subprocess.run(['python3',path],capture_output=True,text=True,timeout=30)
    if p.returncode!=0:
        raise SystemExit(p.stderr.strip() or f'{path} failed')
    return json.loads(p.stdout)

def classify(data):
    coord=data.get('coordinator') or {}
    registry=coord.get('agent_registry') or []
    hermes=next((a for a in registry if a.get('agent_id')=='hermes'),None)
    if not hermes or hermes.get('enabled') is not True or hermes.get('assignable') is not True or hermes.get('authority_ceiling')!='L3':
        return 'unassignable','registry_not_eligible'

    runtime=data.get('agent_runtime') or {}
    presence=(runtime.get('presence') or {}).get('logical_presence')
    if presence in {'stale','offline'}:
        return 'stale','logical_presence_not_fresh'
    if presence!='fresh':
        return 'indeterminate','logical_presence_unknown'

    workload=runtime.get('workload') or {}
    # Phase 2.1N deliberately requires explicit complete workload evidence.
    # The current 2.1M projection does not yet provide these fields, so this
    # fails closed instead of inferring idle/ready from missing state.
    if workload.get('evidence_complete') is not True:
        return 'indeterminate','workload_evidence_incomplete'
    count=workload.get('active_task_count')
    states=workload.get('active_states')
    if not isinstance(count,int) or count < 0 or not isinstance(states,list):
        return 'indeterminate','workload_evidence_invalid'
    if count>0:
        return 'busy','durable_active_workload_present'
    if count==0 and states==[]:
        return 'ready','durable_zero_active_workload_proven'
    return 'indeterminate','workload_evidence_conflicting'

def main():
    data=load(BASE)
    readiness,reason=classify(data)
    data['schema_version']='2.1n.v1'
    data['worker_readiness']={
        'schema_version':'2.1n.readiness.v1',
        'agent_id':'hermes',
        'task_class_scope':'general',
        'readiness':readiness,
        'reason_code':reason,
        'authority_effect':'none',
        'automatic_assignment':False,
        'automatic_retry':False,
        'automatic_reroute':False,
        'automatic_execution':False,
    }
    data.setdefault('governance',{})['worker_readiness_authority_effect']='none'
    print(json.dumps(data,sort_keys=True))

if __name__=='__main__':
    main()
