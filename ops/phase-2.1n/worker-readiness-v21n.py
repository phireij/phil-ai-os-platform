#!/usr/bin/env python3
import json,sys

ACTIVE_STATES={'ASSIGNED','RUNNING','APPROVAL_PENDING'}


def classify(x):
    registry=x.get('registry') or {}
    presence=x.get('presence')
    workload=x.get('workload')
    allowlist=x.get('execution_allowlist')

    if not registry or registry.get('enabled') is not True or registry.get('assignable') is not True or registry.get('authority_ceiling')!='L3':
        return 'unassignable'

    if presence in {'stale','offline'}:
        return 'stale'

    if presence != 'fresh':
        return 'indeterminate'

    if allowlist != ['general']:
        return 'indeterminate'

    if not isinstance(workload,dict):
        return 'indeterminate'
    if workload.get('evidence_complete') is not True:
        return 'indeterminate'

    states=workload.get('active_states')
    if not isinstance(states,list):
        return 'indeterminate'
    unknown=[s for s in states if s not in ACTIVE_STATES]
    if unknown:
        return 'indeterminate'
    if states:
        return 'busy'

    if workload.get('active_task_count')==0:
        return 'ready'
    return 'indeterminate'


def main():
    data=json.load(sys.stdin)
    result={
        'schema_version':'2.1n.readiness.v1',
        'readiness':classify(data),
        'authority_effect':'none',
        'automatic_assignment':False,
        'automatic_retry':False,
        'automatic_reroute':False,
        'automatic_execution':False,
    }
    print(json.dumps(result,separators=(',',':')))

if __name__=='__main__':
    main()
