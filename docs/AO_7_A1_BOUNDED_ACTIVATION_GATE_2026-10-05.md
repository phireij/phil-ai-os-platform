# AO-7 / A1 Bounded Activation Gate

Status: CEO PRE-AUTHORIZED; PRECONDITIONS NOT YET SATISFIED  
Authority effect of this document: none until every activation precondition validates.

## CEO decision

On 2026-10-05 the CEO approved A1 activation in advance. This approval authorizes activation only for the bounded A1 matrix below after the threat-model, rollback, fail-closed, exact-head CI, and activation-evidence gates are GREEN. It does not waive a gate.

## A1 allowlist

A1 MAY autonomously perform only:
- repository inspection and verified status reconciliation;
- deterministic tests, static analysis, and documentation;
- development-branch code preparation;
- CI execution and failure investigation;
- draft pull-request preparation and updates;
- read-only staging/repository evidence collection where credentials and existing policy permit it.

## A1 denylist — remains separately approval-gated

A1 MUST NOT:
- merge a pull request or bypass branch protection;
- publish/cut over production or change DNS;
- create real customer orders or execute payments/refunds;
- send live customer SMS/email/social/channel replies;
- mutate production inventory, slots, customer data, or credentials/secrets;
- enable Twilio or other deferred live providers;
- activate KCFC production actions/connectors/mass messaging;
- widen agent authority, enable an unapproved specialist execution runtime, or modify this matrix autonomously.

## Threat model

Activation must fail closed against:
1. stale or missing evidence being promoted to GREEN;
2. dependency bypass;
3. replay/duplicate work dispatch;
4. selector choosing a denied task class;
5. task metadata attempting to self-authorize;
6. approval state being inferred from prose instead of durable evidence;
7. CI failure or unknown exact-head state;
8. branch-protection absence being treated as merge permission;
9. adapter failure being treated as success;
10. cross-project authority leakage between Phil AI OS, Ruby, and KCFC.

## Activation preconditions

All must be evidenced:
- A0 queue/selector contracts GREEN;
- exact A1 authority matrix is machine-readable and validator-enforced;
- selector is deterministic, dependency-aware, allowlist-only, and cannot execute;
- bounded dispatcher has replay protection and denylist enforcement;
- rollback disables A1 and returns to A0 without production mutation;
- fail-closed tests cover the threat model;
- exact-head CI and supply-chain policy GREEN;
- activation record names the exact commit and CEO approval date.

Until then, effective autonomy remains A0.

## Rollback

Rollback is logical and fail-closed: set effective autonomy ceiling to A0, disable A1 dispatch, preserve evidence/ledger history, and perform no compensating production mutation. Any uncertain state is treated as A0.

## Production boundary

A1 is an engineering autonomy level, not production-operation authorization. Production/live side effects remain separately gated.
