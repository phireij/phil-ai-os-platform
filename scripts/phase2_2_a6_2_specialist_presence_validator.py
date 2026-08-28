#!/usr/bin/env python3
from dataclasses import dataclass

FRESH=120
STALE=300

@dataclass(frozen=True)
class Registry:
    present: bool
    enabled: bool
    assignable: bool
    ceiling: str='L1'

@dataclass(frozen=True)
class Evidence:
    authenticated: bool
    claimed_agent_id: str|None
    authenticated_agent_id: str|None
    age_seconds: int|None
    runtime_running: bool|None
    workload_known: bool
    active_workload: int|None
    policy_general: bool


def presence(e: Evidence) -> str:
    if not e.authenticated:
        return 'unknown'
    if e.claimed_agent_id != 'specialist-worker-01':
        return 'unknown'
    if e.authenticated_agent_id != 'specialist-worker-01':
        return 'unknown'
    if e.age_seconds is None or e.age_seconds < 0:
        return 'unknown'
    if e.age_seconds <= FRESH:
        return 'fresh'
    if e.age_seconds <= STALE:
        return 'stale'
    return 'offline'


def readiness(r: Registry, e: Evidence) -> str:
    if not r.present or not r.enabled or not r.assignable:
        return 'unassignable'
    p=presence(e)
    if p in ('stale','offline'):
        return 'stale'
    if p != 'fresh' or not e.workload_known or e.active_workload is None or not e.policy_general:
        return 'indeterminate'
    if e.active_workload > 0:
        return 'busy'
    if e.active_workload == 0:
        return 'ready'
    return 'indeterminate'


def ev(**kw):
    base=dict(authenticated=True,claimed_agent_id='specialist-worker-01',authenticated_agent_id='specialist-worker-01',age_seconds=0,runtime_running=True,workload_known=True,active_workload=0,policy_general=True)
    base.update(kw)
    return Evidence(**base)


def main():
    assert presence(ev(age_seconds=0))=='fresh'
    assert presence(ev(age_seconds=120))=='fresh'
    assert presence(ev(age_seconds=121))=='stale'
    assert presence(ev(age_seconds=300))=='stale'
    assert presence(ev(age_seconds=301))=='offline'
    assert presence(ev(authenticated=False))=='unknown'
    print('freshness_thresholds=ok')

    locked=Registry(True,False,False)
    assert readiness(locked,ev())=='unassignable'
    assert readiness(Registry(True,True,False),ev())=='unassignable'
    print('registry_precedence=ok')

    assert presence(ev(authenticated=False,runtime_running=True))=='unknown'
    assert presence(ev(runtime_running=False,age_seconds=20))=='fresh'
    print('runtime_presence_separation=ok')

    assert presence(ev(authenticated_agent_id='hermes'))=='unknown'
    assert presence(ev(claimed_agent_id='hermes',authenticated_agent_id='hermes'))=='unknown'
    assert presence(ev(claimed_agent_id='specialist-worker-01',authenticated_agent_id='hermes'))=='unknown'
    print('identity_substitution_blocked=ok')

    eligible=Registry(True,True,True)
    assert readiness(eligible,ev(workload_known=False,active_workload=None))=='indeterminate'
    assert readiness(eligible,ev(workload_known=True,active_workload=0))=='ready'
    assert readiness(eligible,ev(workload_known=True,active_workload=1))=='busy'
    assert readiness(eligible,ev(policy_general=False))=='indeterminate'
    print('workload_and_policy_fail_closed=ok')

    for age in (0,150,400):
        e=ev(age_seconds=age)
        _=presence(e); _=readiness(locked,e)
    print('authority_effect=none')
    print('automatic_assignment=false')
    print('automatic_retry=false')
    print('automatic_reroute=false')
    print('automatic_delegation=false')
    print('automatic_execution=false')
    print('approval_effect=none')
    print('provider_effect=none')
    print('production_change=none')
    print('PHIL_AI_OS_PHASE_2_2_A6_2_SPECIALIST_PRESENCE_CONTRACT_OK')

if __name__=='__main__':
    main()
