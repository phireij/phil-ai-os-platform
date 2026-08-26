# Phase 2.1 — Mission Control Capability & Gap Matrix

**Program:** Phil AI OS Platform  
**Date:** 2026-08-26  
**Status:** DISCOVERY COMPLETE / IMPLEMENTATION NOT AUTHORIZED  
**Basis:** Phase 1 closure records, Phase 1.19–1.27 validation workflows, and Phase 2.1 operating-model contract

## Executive finding

Mission Control does not need to be built from zero. Phase 1 already established substantial backend/control-plane primitives: authenticated Hermes reads, Mission Control snapshot, recent approvals/executions, approval request creation, review-link issuance, Telegram delivery, human approval, one-time approval consumption, replay rejection, execution audit linkage, monitoring, backup/self-heal, and an execution kill switch.

The principal Phase 2 gap is the **coherent operator control surface and canonical agent/task operating model**. Existing primitives must be consolidated without creating a second authority path around the Control API.

## Capability / gap matrix

| Required capability | Current evidence | Readiness | Phase 2.1 gap / action |
|---|---|---|---|
| Authenticated Hermes access | Hermes token mount and authenticated reads to snapshot, approvals and executions validated | GREEN | Preserve least-privilege credential boundary; do not expose raw token in UI |
| Mission Control safety snapshot | `/v1/mission-control/snapshot` is consumed by Hermes/monitoring | GREEN backend | Define operator-facing presentation and freshness/degraded-state semantics |
| Recent approval visibility | `/v1/approvals/recent` validated | GREEN backend | Add coherent operator queue, filtering, state/expiry/ownership presentation |
| Recent execution visibility | `/v1/execution/recent` validated | GREEN backend | Add task/approval/agent correlation and failure/result presentation |
| Approval request creation | Hermes Mission Control `request` command creates pending approval | GREEN | Preserve no-self-approval rule and exact request identity |
| Human review link | `/v1/approvals/link` issues review path/token; Telegram link delivery validated | GREEN | Integrate into primary operator workflow; protect token lifecycle |
| Human approve/deny | Approval API contract includes approve/deny and controlled approval flow was validated | GREEN backend | Surface explicit decision controls with reason/identity/time |
| Self-approval prevention | Hermes request activation verified `self_approval_capability=absent` | GREEN | Make this an invariant and negative test in future gates |
| Durable approval consumption | Consumed approval persisted with `consumed_by=hermes` | GREEN | Surface consumed state and immutable linkage |
| Replay protection | Reuse returns conflict/rejection before provider call | GREEN | Surface replay/rejection reason; retain fail-closed behavior |
| Execution audit linkage | Successful execution audit linked to approval ID | GREEN | Extend correlation to canonical task ID and agent identity |
| Execution governance | `general` only; Control API route; direct provider bypass prohibited | GREEN | No Phase 2 widening until separate activation gate |
| Kill switch | Governed execution kill switch exists and is available | GREEN backend | Add operator-visible status; design authenticated emergency-stop control separately |
| Monitoring | `phil-ai-os-monitor.service` active at final gate | GREEN | Surface health/degraded state in Mission Control without weakening monitor independence |
| Backup / self-heal | Scheduled backup and self-heal timers active | GREEN | Surface recovery readiness/status as read-only operational context |
| Agent identity | Source/requester fields exist, but no complete canonical agent registry/identity contract is evidenced | AMBER | Define stable agent ID, role, owner, authority level, status and credential binding |
| Task ownership | Approval/execution records exist but no canonical end-to-end task ownership model is evidenced | AMBER | Introduce canonical task ID/owner and correlation contract before orchestration |
| Task lifecycle | Pieces exist across approval/execution but no single task-state machine is evidenced | AMBER | Define canonical lifecycle and legal transitions |
| Agent/session status | No complete production contract evidenced for agent/session presence, heartbeat, workload or degraded state | AMBER | Define read model before any multi-agent runtime expansion |
| Operator interruption | Denial before execution and kill switch exist; per-running-task interruption is not evidenced | AMBER | Define semantics carefully; do not imply cancellation after irreversible provider/action boundary |
| Failure/stuck-task handling | Execution failure/audit primitives exist; unified stuck-task/retry policy not evidenced | AMBER | Define timeout, retry, ambiguity and escalation states before orchestration |
| Role/authority matrix | Initial L0–L4 ladder defined in Phase 2.1 contract | AMBER | Formalize per-role permissions and explicit non-authorities |
| Multi-agent handoff | Not established in Phase 1 | RED / NOT YET REQUIRED | Defer to Phase 2.2 after identity/task model is GREEN |
| Autonomous authority expansion | Explicitly prohibited without later gate | RED / INTENTIONALLY BLOCKED | Keep blocked |

## Canonical operating roles

### CEO / Human Operator
- Policy owner and final authority for material production expansion.
- May approve, deny, restrict, interrupt where technically safe, or engage emergency containment.
- Must have clear visibility into pending approvals, active/failed work, agent identity, and audit evidence.

### CTO Office
- Architecture/governance authority at L0–L2 by default.
- Inspects, analyzes, proposes, designs gates and validates evidence.
- Cannot silently grant itself or agents expanded production authority.

### Hermes
- Primary operational gateway/agent candidate.
- May observe and request work within its contract.
- L3 execution remains limited to explicitly governed production scope and approval policy.
- Cannot self-approve or bypass Control API/provider governance.

### Specialist Agents
- Not production-authorized by Phase 2.1.
- Each future agent requires explicit identity, owner, capabilities, non-authorities, credential scope, task classes and approval policy.
- No inherited privilege merely because Hermes delegates work.

### Mission Control
- Operator/control surface, not an independent authority source.
- Reads and writes only through governed Control API contracts.
- Must not hold a hidden bypass to providers, host shell, arbitrary filesystem mutation, or unrestricted agent execution.

## Canonical task lifecycle proposal

`RECEIVED -> CLASSIFIED -> ASSIGNED -> PLANNED -> POLICY_CHECK -> [APPROVAL_PENDING] -> AUTHORIZED -> EXECUTING -> {SUCCEEDED | FAILED | BLOCKED | CANCELLED} -> AUDITED -> CLOSED`

Additional terminal/exception states:

- `DENIED` — human/policy denial before execution.
- `EXPIRED` — approval/task authorization expired.
- `REJECTED` — validation mismatch, replay, allowlist, budget, health, or governance rejection.
- `AMBIGUOUS` — execution outcome cannot be safely determined; automatic retry prohibited unless idempotency is proven.
- `CONTAINED` — emergency control prevents further execution.

Rules:

1. Every production-capable task must have a stable task ID.
2. Every task must have an owner and originating agent/user identity.
3. Approval ID is linked to the exact governed execution unit when approval is required.
4. No transition from approval-pending/denied/expired/rejected directly to executing.
5. Execution outcome must produce durable audit evidence.
6. Retry is a new governed transition, not an invisible loop.
7. Agent-to-agent handoff must not increase authority.

## Initial approval / escalation matrix

| Action | Default authority | Human approval | Notes |
|---|---|---|---|
| Read Mission Control state | L0 | No, authenticated access only | Least privilege |
| Analyze / propose plan | L1 | No | No production mutation |
| Create approval request | L2 | No separate approval to request approval | Cannot execute by creating request |
| Approve/deny governed action | Human operator | Human decision | Agent self-approval prohibited |
| Execute current governed `general` action | L3 bounded | As required by active policy | Must route through Control API |
| Change execution allowlist | Policy/admin change | Explicit human gate | Separate validation/rollback required |
| Add specialist agent authority | Policy/admin change | Explicit human gate | Identity/capability contract required |
| Provider/model migration | Policy/admin change | Explicit human gate | Validation + rollback required |
| Emergency containment / kill switch | Human/operator control | Explicit operator action | Must be strongly authenticated/audited |
| L4 broad autonomous execution | Prohibited | Not authorizable implicitly | Requires future dedicated phase/gate |

## Smallest safe implementation increment

The next implementation should **not** be multi-agent orchestration or wider autonomy. The smallest safe increment is a **read-mostly Mission Control Operator Read Model** built on existing Control API state.

### Proposed Phase 2.1A scope

1. Define a canonical read-only Mission Control aggregate contract containing:
   - platform/control-plane health;
   - monitor/backup/self-heal status;
   - active production allowlist and kill-switch state;
   - recent approvals with state/expiry/requester;
   - recent executions with outcome and approval linkage;
   - known agent identity/status records (initially Hermes + CTO/human roles as declared records);
   - task correlation fields where already available.
2. Add stable `task_id` / `agent_id` schema only after read-only compatibility discovery confirms migration impact.
3. Validate that Mission Control cannot bypass Control API governance.
4. Produce a read-only operator page/API view before adding new mutation controls.
5. Keep existing Telegram approval flow operational during transition.

## Explicitly deferred

- persistent `routine` activation;
- specialist-agent production execution;
- multi-agent delegation/handoffs;
- autonomous retries;
- broad provider/model changes;
- arbitrary shell/filesystem/network authority;
- broad L4 autonomy;
- replacing independent monitoring/backup controls with UI-only logic.

## Rollback / containment boundary

Phase 2.1A should be additive and read-mostly. If the new read model/UI fails:

- existing Control API approval/execution paths remain authoritative;
- Telegram approval links remain available;
- Hermes existing Mission Control client remains available;
- monitoring and backup services remain independent;
- production execution allowlist remains `general` only;
- no provider migration is involved.

## CTO recommendation

**Proceed to Phase 2.1A — Mission Control Operator Read Model Contract & Read-Only Compatibility Discovery.**

Do not proceed directly to multi-agent orchestration. Establish canonical identity/task/read-model semantics first, then validate them without provider calls or production mutations.

`PHIL_AI_OS_PHASE_2_1_MISSION_CONTROL_GAP_MATRIX_COMPLETE`
