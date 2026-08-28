#!/usr/bin/env python3
import datetime as dt
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('p3', Path('scripts/phase2_3_p3_isolated_policy_evaluator.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
NOW = dt.datetime(2026, 8, 28, 7, 20, tzinfo=dt.timezone.utc)
FUTURE = (NOW + dt.timedelta(minutes=10)).isoformat()


def base(**kw):
    d = {
        'task_id':'tsk_p3_case',
        'task_class':'general',
        'action_type':'bounded_action',
        'subject_agent_id':'hermes',
        'subject_authority_ceiling':'L3',
        'risk_tier':'R2',
        'required_authority':'L1',
        'configured_autonomy_ceiling':'A0',
        'requested_autonomy_level':'A0',
        'human_approval_required':True,
        'approval_consumption_required':True,
        'scope_constraints':{'task_id':'tsk_p3_case'},
        'evidence_refs':['isolated:test'],
        'evidence_complete':True,
        'requested_execution':False,
        'requested_side_effect':False,
        'kill_switch':False,
        'control_api_boundary':True,
        'direct_provider_bypass':False,
        'mission_control_mutation_as_authority':False,
        'readiness_as_permission':False,
        'authority_ceiling_as_permission':False,
    }
    d.update(kw)
    return d


def approved(**kw):
    a = {
        'approval_id':'apr_p3', 'state':'approved', 'expires_at':FUTURE,
        'consumed':False, 'scope_match':True,
        'requester_id':'hermes', 'decision_by':'human-operator-ceo'
    }
    a.update(kw); return a


def check(name, evidence, expected, preconditions=None):
    r = m.evaluate_policy(evidence, now=NOW)
    assert r['decision'] == expected, (name, r)
    assert r['authority_effect'] == 'none'
    if preconditions is not None:
        assert r['execution_preconditions_satisfied'] is preconditions, (name, r)
    print(f'{name}={expected}')
    return r

check('r0_observe', base(risk_tier='R0', human_approval_required=False), 'allow_prepare', False)
check('missing_evidence', base(evidence_complete=False), 'deny', False)
check('unknown_risk', base(risk_tier='RX'), 'deny', False)
check('authority_violation', base(subject_authority_ceiling='L1', required_authority='L3'), 'escalate', False)
check('autonomy_violation', base(requested_autonomy_level='A1'), 'deny', False)
check('direct_provider_bypass', base(direct_provider_bypass=True), 'deny', False)
check('mission_control_mutation', base(mission_control_mutation_as_authority=True), 'deny', False)
check('readiness_as_permission', base(readiness_as_permission=True), 'deny', False)
check('authority_as_permission', base(authority_ceiling_as_permission=True), 'deny', False)
check('r3_escalation', base(risk_tier='R3'), 'escalate', False)
check('r4_denial', base(risk_tier='R4'), 'deny', False)
check('r0_side_effect_denied', base(risk_tier='R0', requested_side_effect=True, human_approval_required=False), 'deny', False)
check('side_effect_no_approval', base(requested_side_effect=True), 'require_human', False)
check('self_approval', base(requested_side_effect=True, approval=approved(decision_by='hermes')), 'deny', False)
check('denied_approval', base(requested_side_effect=True, approval=approved(state='denied')), 'deny', False)
check('expired_state', base(requested_side_effect=True, approval=approved(state='expired')), 'deny', False)
check('consumed_replay', base(requested_side_effect=True, approval=approved(consumed=True)), 'deny', False)
check('pending_approval', base(requested_side_effect=True, approval=approved(state='pending')), 'require_human', False)
check('expired_timestamp', base(requested_side_effect=True, approval=approved(expires_at=(NOW-dt.timedelta(seconds=1)).isoformat())), 'deny', False)
check('scope_mismatch', base(requested_side_effect=True, approval=approved(scope_match=False)), 'deny', False)
check('routine_not_allowlisted', base(task_class='routine', requested_execution=True, approval=approved()), 'deny', False)
check('kill_switch', base(requested_execution=True, kill_switch=True, approval=approved()), 'deny', False)
check('control_api_boundary_missing', base(requested_execution=True, control_api_boundary=False, approval=approved()), 'deny', False)
check('valid_general_execution_policy_only', base(requested_execution=True, approval=approved()), 'eligible_for_execution_boundary', True)
check('valid_human_authorized_side_effect_policy_only', base(requested_side_effect=True, approval=approved()), 'eligible_for_execution_boundary', True)

# Purity/static capability proof.
raw = Path('scripts/phase2_3_p3_isolated_policy_evaluator.py').read_text(encoding='utf-8').lower()
for forbidden in ('sqlite3', 'urllib', 'requests', 'subprocess', 'socket', '/v1/execute', 'openai', 'anthropic', 'gemini', 'docker'):
    assert forbidden not in raw, forbidden
assert 'approval_consume' not in raw
assert 'authority_effect": "none"' in raw or '"authority_effect": "none"' in raw

print('policy_evaluator_io=false')
print('policy_evaluator_mutation=false')
print('policy_evaluator_approval_consumption=false')
print('provider_call=false')
print('production_change=none')
print('PHIL_AI_OS_PHASE_2_3_P3_ISOLATED_POLICY_EVALUATOR_OK')
