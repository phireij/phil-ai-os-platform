#!/usr/bin/env python3
import json
from pathlib import Path

P = Path('policy/phase2_3_p2_risk_policy_contract.json')
d = json.loads(P.read_text(encoding='utf-8'))

assert d['schema_version'] == '2.3-p2.v1'
assert d['authority_effect'] == 'none'
cp = d['current_production']
assert cp['autonomy_ceiling'] == 'A0'
assert cp['execution_allowed_task_classes'] == ['general']
assert cp['mission_control_authority'] == 'read_only_observer'
assert cp['self_approval_allowed'] is False
assert cp['direct_provider_bypass_allowed'] is False
assert cp['automatic_task_class_expansion'] is False
assert cp['automatic_autonomy_expansion'] is False

expected_tiers = {
    'R0': 'allow_prepare',
    'R1': 'require_human',
    'R2': 'require_human',
    'R3': 'escalate',
    'R4': 'deny',
}
assert set(d['risk_tiers']) == set(expected_tiers)
for tier, decision in expected_tiers.items():
    assert d['risk_tiers'][tier]['default_decision'] == decision

assert list(d['autonomy_levels']) == ['A0','A1','A2','A3']
assert 'not_authorized' in d['autonomy_levels']['A1']
assert 'not_authorized' in d['autonomy_levels']['A2']
assert 'not_authorized' in d['autonomy_levels']['A3']

allowed = set(d['allowed_decisions'])
assert allowed == {
    'allow_prepare','require_human','eligible_for_execution_boundary','escalate','deny'
}
required = set(d['decision_object_required_fields'])
for field in (
    'policy_decision_id','policy_version','task_id','task_class','subject_agent_id',
    'subject_authority_ceiling','risk_tier','required_authority',
    'configured_autonomy_ceiling','requested_autonomy_level','human_approval_required',
    'approval_consumption_required','evidence_refs','decision','reason_codes',
    'execution_preconditions_satisfied','authority_effect'
):
    assert field in required, field

inv = d['invariants']
assert inv['risk_authority_autonomy_are_separate'] is True
assert inv['authority_ceiling_is_never_grant'] is True
assert inv['readiness_is_never_permission'] is True
assert inv['policy_evaluation_can_execute'] is False
assert inv['policy_evaluation_can_consume_approval'] is False
assert inv['human_approval_required_for_current_side_effects'] is True
assert inv['approval_is_expiring'] is True
assert inv['execution_approval_is_one_time'] is True
assert inv['replay_rejected_before_second_provider_call'] is True
assert inv['kill_switch_preserved'] is True
assert inv['control_api_execution_boundary_required'] is True
assert inv['missing_or_conflicting_evidence_fails_closed'] is True
assert inv['handoff_authorization_is_execution_approval'] is False

cases = {x['name']: x for x in d['static_cases']}
checks = {
    'r0_observe':'allow_prepare',
    'r1_side_effect_current_a0':'require_human',
    'r2_execution_unapproved':'require_human',
    'r3_sensitive':'escalate',
    'r4_prohibited':'deny',
    'routine_execution_not_allowlisted':'deny',
    'self_approval':'deny',
    'expired_approval':'deny',
    'consumed_approval_replay':'deny',
    'kill_switch_active_execution':'deny',
    'authority_ceiling_violation':'escalate_or_deny',
    'missing_policy_evidence':'deny_or_escalate',
}
for name, expected in checks.items():
    assert cases[name]['expected'] == expected, name

# Static non-capability proof: contract contains no production mutation or execution grant.
raw = P.read_text(encoding='utf-8').lower()
for forbidden in (
    'autonomous_execution_allowed": true',
    'self_approval_allowed": true',
    'direct_provider_bypass_allowed": true',
    'automatic_task_class_expansion": true',
    'automatic_autonomy_expansion": true',
):
    assert forbidden not in raw, forbidden

print('schema=2.3-p2.v1')
print('current_autonomy_ceiling=A0')
print('execution_allowlist=general_only')
print('risk_tiers=R0_R1_R2_R3_R4')
print('human_approval_current_side_effects=required')
print('self_approval=denied')
print('replay=denied')
print('kill_switch=preserved')
print('policy_evaluation_execution_capability=false')
print('authority_effect=none')
print('PHIL_AI_OS_PHASE_2_3_P2_CONTRACT_VALIDATION_OK')
