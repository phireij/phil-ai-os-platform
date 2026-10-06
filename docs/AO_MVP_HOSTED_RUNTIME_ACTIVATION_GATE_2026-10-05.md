# AO-MVP Hosted Runtime Activation Gate

Status: ACTIVATION NOT AUTHORIZED

This is the exact gate for moving the bounded AO-MVP orchestrator from repository-tested contracts to a continuously running external runtime.

## Required evidence — all must be GREEN
1. Approved runtime target and owner.
2. Exact immutable source revision and package/image digest.
3. Contract CI and supply-chain CI GREEN for that exact revision.
4. Persistent state volume survives service restart without state loss.
5. Concurrent-start test proves single-worker exclusion.
6. Crash/restart test proves expired-lease recovery without duplicate dispatch.
7. Corrupted-state test fails closed and performs no work.
8. Health/readiness reports NOT READY when any required invariant is absent.
9. Logs demonstrate secret/customer-data redaction.
10. Network egress is disabled by default or explicitly allowlisted.
11. A1 denylist remains enforced end-to-end.
12. Rollback drill stops runtime, disables dispatch, reduces effective autonomy to A0, and preserves evidence.
13. No production credentials are required for initial activation.
14. Activation approval is explicit and scoped only to this hosted A1 runtime.

## Activation scope
Even after this gate passes, activation authorizes only the hosted bounded A1 runtime. It does not authorize PR merge, production cutover, DNS, real orders, payments/refunds, live customer messaging, inventory/slot mutation, credential mutation, Twilio, KCFC production action, or authority self-widening.

## Fail condition
Any missing, stale, unknown, or failed required evidence means NOT READY and no activation.
