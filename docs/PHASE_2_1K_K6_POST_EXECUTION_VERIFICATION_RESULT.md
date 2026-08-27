# Phase 2.1K K6 — Post-Execution and Replay Verification Result

Status: **GREEN**

Date: 2026-08-27

## Production protections

Post-K5 read-only verification confirmed:

- Control API health: `ok`
- Control API readiness: `ok`
- safety monitor: active
- backup timer: active
- backup self-heal timer: active
- production execution allowlist: `general` only
- registered assignable agents: exactly one (`hermes`)
- Hermes authority ceiling: `L3`

No production change, approval mutation, execution call, or provider call occurred during K6.

## Durable approval/task/execution correlation

Exact identities remained correlated:

- Approval: `apr_7a3594fc61d1467593181d1ca7a2d502`
- Task: `tsk_e9694565de884bc9afa550d57db32426`
- Approval state: `approved`
- Task class: `general`
- Approval consumed by: `hermes`

Durable execution audit contained exactly two rows for the exact approval/task pair:

1. `success` — OpenAI / `gpt-5.6-terra`, primary route, compatibility pass, provider response present.
2. `approval_rejected` — replay attempt, with no provider/model/route/response identity.

Therefore:

- successful execution audits: `1`
- replay rejection audits: `1`
- provider response rows: `1`
- second provider call: **false**

Lifecycle correlation remained tied to the exact approval ID through `RECEIVED`, `CLASSIFIED`, `APPROVAL_PENDING`, and both `AUDITED` events.

## Expiry semantics clarification

The live source for `_approval_expire_if_needed` explicitly applies expiration only when an approval is still in `pending` state. Once a human decision moves it to `approved`, the pending-review expiration timestamp no longer invalidates the approved decision. The observed K5 consumption after the displayed `expires_at` is therefore consistent with the current designed approval-state semantics, not a bypass.

`PHIL_AI_OS_PHASE_2_1K_K6_POST_EXECUTION_VERIFICATION_GREEN`
