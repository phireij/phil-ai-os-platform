# Phil AI OS Platform — Phase 2.3 P5 Inert Policy Ledger Activation Gate

**Phase:** 2.3 P5  
**Status:** PREPARED / PRODUCTION ACTIVATION NOT AUTHORIZED  
**Date:** 2026-08-28  
**Prerequisites:** P1–P4 GREEN

## Purpose

Activate only the minimum reusable policy-decision persistence and read-only visibility proven by P4, while keeping policy evaluation non-authoritative and disconnected from approval consumption and execution.

This is a production persistence/writer expansion and therefore requires explicit CEO authorization before activation.

## Authorized scope if approved

P5 may only:

1. add an append-only `policy_decisions` table;
2. add DB triggers that block UPDATE and DELETE;
3. enforce `authority_effect='none'` at the database boundary;
4. add an internal policy-decision persistence helper;
5. package the already isolated pure P3 evaluator for internal future use;
6. add a read-only Mission Control policy-decision projection;
7. validate the candidate against a copied production DB before deployment;
8. create prechange rollback snapshots;
9. atomically deploy the bounded candidate;
10. verify the new ledger is present and initially empty or contains only an explicitly defined non-authorizing validation record if separately justified by the activation script;
11. verify rollback readiness and all inherited governance invariants.

## P5 must NOT add

- `/v1/policy/evaluate` or another externally callable policy writer route;
- automatic policy evaluation on task intake;
- automatic approval or denial side effects;
- approval consumption;
- provider execution;
- `/v1/execute` behavior changes;
- `routine` or any new production execution class;
- autonomy above A0;
- specialist eligibility or credentials;
- automatic assignment/handoff/retry/reroute/delegation/execution;
- Mission Control mutation capability;
- authority-ceiling changes;
- provider/model/credential changes;
- direct provider bypass.

## Production invariants

After successful P5 activation:

- execution allowlist remains exactly `general`;
- autonomy ceiling remains A0;
- Hermes remains L3 enabled/assignable;
- `specialist-worker-01` remains L1 disabled/non-assignable and non-executing;
- Mission Control mutations remain HTTP 405;
- unauthenticated Control API mutation routes remain protected;
- approval semantics, expiry, one-time consumption and replay rejection remain unchanged;
- execution kill switch remains unchanged;
- monitoring, backup and backup self-heal remain active;
- no provider or execution call occurs during activation;
- policy decisions grant no authority;
- no automatic action is introduced.

## Persistence contract

The production `policy_decisions` ledger must be append-only and include at minimum:

- `policy_decision_id` primary key;
- `policy_version`;
- `evaluated_at`;
- `task_id`;
- `task_class`;
- `action_type`;
- `subject_agent_id`;
- `subject_authority_ceiling`;
- `risk_tier`;
- `required_authority`;
- `configured_autonomy_ceiling`;
- `requested_autonomy_level`;
- `human_approval_required`;
- optional approval identity/state/expiry evidence;
- `approval_consumption_required`;
- scope/evidence/reason snapshots;
- decision;
- execution-precondition state;
- `authority_effect='none'`;
- durable evidence hash.

Database triggers must reject UPDATE and DELETE.

## Rollback

Before mutation, snapshot:

- production database;
- Control API source/image/compose state;
- Mission Control read model.

Any failed post-mutation invariant requires automatic rollback to the exact P4 entry state.

## Success criteria

P5 is GREEN only if:

1. additive migration succeeds;
2. append-only enforcement is live;
3. policy decisions cannot grant authority;
4. Mission Control can read the ledger while remaining read-only;
5. all protected production state outside the approved schema/read-model increment is unchanged;
6. no approval is consumed;
7. no provider/execution call occurs;
8. current A0 and `general`-only boundaries remain intact;
9. rollback is armed and verified;
10. independent post-success verification passes.

## Explicit authorization required

Production activation requires the exact authorization:

`APPROVE_PHASE_2_3_P5`

Until that authorization is received, P5 remains prepared but blocked.

`PHIL_AI_OS_PHASE_2_3_P5_GATE_PREPARED`
