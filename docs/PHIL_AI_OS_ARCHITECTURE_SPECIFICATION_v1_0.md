# Phil AI OS Platform — Architecture Specification v1.0

**Version:** 1.0  
**Freeze date:** 2026-08-28  
**Status:** **FROZEN BASELINE**  
**Owner:** CEO / CTO Office

## 1. Architectural objective

Phil AI OS Platform is a governed AI-native operating platform in which orchestration, policy, approval, execution, observability, audit, recovery and business integrations remain separated by explicit authority boundaries.

The design principle is:

**Parallel development + serialized governed activation.**

## 2. Core topology

### Hermes / Lead Orchestration
Hermes receives/decomposes work, coordinates tasks and may hand work to registered agents within established authority. Hermes does not bypass the Control API, approval contract or Execution Boundary for production side effects.

### Control API
The Control API is the central operational system of record and governance boundary for:

- system/runtime metadata;
- agent registry and authority state;
- routing/policy state;
- approvals;
- task lifecycle/handoff evidence;
- execution audit;
- usage evidence;
- policy-decision evidence.

### Durable control-plane database
Core V1 uses the durable SQLite control-plane database managed behind the Control API as the canonical operational datastore. It is protected by scheduled backup, monitoring, self-heal, verified restore and rollback procedures.

### Execution Boundary
The Execution Boundary is the sole authorized production side-effect surface. Provider/system calls must not bypass its governance and audit controls.

### Approval Boundary
Human approval is a first-class control. Approval expiry, one-time consumption, replay protection and durable linkage to execution remain required where policy demands approval.

### Mission Control
Mission Control is the operator/read-model surface. At the v1.0 architecture freeze it is observational/read-only unless a separately authorized production gate introduces bounded mutation authority.

Its V1 UX North Star is rapid situational awareness through:

- Executive View — health, work, attention, risk;
- Operations View — tasks, agents, handoffs, lifecycle;
- Governance View — autonomy, policy, approvals, authority and audit.

A CEO/operator should be able to determine within approximately 10 seconds whether the system is healthy, what it is doing, what needs attention and whether anything is outside authorized boundaries.

## 3. Multi-agent model

The platform supports durable multi-agent identity and handoff while retaining centralized governance.

Accepted Sprint 2 exit state:

- Hermes: L3, enabled/assignable within established scope;
- `specialist-worker-01`: L1, disabled/non-assignable for normal production execution;
- production autonomy ceiling: **A0**;
- execution task-class allowlist: **`general` only**.

Specialist enablement and any authority expansion require a separate production gate.

## 4. Policy architecture

Phase 2.3 establishes:

- risk-tier/policy decision contract;
- pure/inert evaluator packaging for internal use;
- durable append-only `policy_decisions` ledger;
- `authority_effect` constrained to `none` at the current gate;
- read-only policy visibility.

No reusable external policy writer/evaluate API route is authorized at this freeze. Policy state must not silently create production authority.

## 5. Reliability and recovery

The architecture requires:

- health/readiness monitoring;
- durable audit evidence;
- scheduled backups;
- backup freshness monitoring;
- backup self-heal;
- isolated restore validation;
- rollback snapshot before controlled production change;
- fail-closed behavior when required identity, secret, policy or approval state is unavailable.

## 6. Business integration rule

WooCommerce, customer-experience channels, Operations Hub channels and future business systems must enter through explicit contracts and governed integration boundaries.

No external business integration receives implied authority from being connected. Credentials, live connectivity, production identities and mutation scopes require explicit controlled activation.

## 7. Data-system rule

The Control API remains the authority layer even if additional datastores or reporting systems are later introduced. A secondary datastore must not silently become a competing system of record.

Supabase is not part of the Core V1 critical path at this architecture freeze; its disposition is recorded separately.

## 8. V1 governance invariants

The following may not be bypassed for schedule compression:

1. human approval where policy requires it;
2. Execution Boundary for side effects;
3. durable audit/lifecycle evidence;
4. rollback preparation for controlled activation;
5. security/credential boundaries;
6. data integrity and backup/recovery controls;
7. explicit authorization for new production identity or authority.

## 9. Change control

Architecture Specification v1.0 is the accepted Sprint 2 baseline. Changes that expand production identity, authority, execution classes, autonomous action, writable Mission Control behavior, or canonical datastore authority require an explicit architecture/governance decision and corresponding roadmap update.

`PHIL_AI_OS_ARCHITECTURE_V1_0_FROZEN`
