# Sprint 7 — Production Rollback & Abort Matrix

Date: 2026-08-28
Status: PREPARATION ONLY / NO PRODUCTION ACTIVATION AUTHORIZED

## Purpose

Define fail-closed abort triggers, accountable owners, verification checks and reversible fallbacks for future production changes.

| Production change | Abort trigger | Primary owner | Verification before continue | Reversible fallback |
|---|---|---|---|---|
| WordPress/WooCommerce cutover | health/HTTP failure, broken checkout, failed data-integrity check, unexpected customer-impacting regression | CTO / deployment operator | storefront health, SSL, admin access, catalog/checkout smoke, backup/restore readiness | stop cutover and restore prior known-good hosting/site state or DNS target per approved runbook |
| WooCommerce API activation | auth failure, duplicate/replay anomaly, stale inventory conflict, unexpected write, audit linkage failure | CTO / Commerce | least-privilege identity, read test, narrow mutation trial only if explicitly authorized, audit correlation, rollback snapshot | disable integration credentials/transport and restore affected record/state from approved snapshot/process |
| KOMOJU Test Mode | plugin/account integration failure, callback mismatch, unexpected order/payment state | CTO / Commerce | test transaction flow, order-state correlation, no Live Mode, no unintended charge | disable payment method/integration and revert to non-live checkout state |
| KOMOJU Live Mode | any unexpected real payment behavior, callback/auth failure, reconciliation mismatch | CEO + CTO | explicit Live Mode approval, verified test evidence, merchant controls, rollback/disable path | disable Live Mode/payment method, revoke/rotate affected credential if needed, reconcile affected orders/payments |
| External channel read/webhook activation | signature/auth failure, duplicate storm, malformed-event rate, unexpected account scope | CTO / Operations | signed event verification, idempotency, read-only ingestion, rate/error monitoring | disable webhook/token/app integration and return channel to disconnected state |
| External channel outbound reply/write | unauthorized reply, wrong recipient/thread, policy/approval bypass, duplicate send | CEO + CTO | explicit reply/write approval, one narrow canary, audit/correlation proof, kill switch | disable write scope/token capability immediately and revert to read-only/manual handling |
| Mission Control mutation authority | unauthorized state change, role/permission mismatch, audit gap | CEO + CTO | explicit authority decision, role tests, audit proof, rollback snapshot | revoke mutation permission and return Mission Control to read-only |
| Specialist/new execution-class activation | task routed outside approved scope, confidence/policy mismatch, bypass or audit failure | CEO + CTO | explicit scope approval, policy tests, canary task, kill switch | disable specialist/class and restore `general` + Hermes-only baseline |

## Global abort criteria

Abort the affected activation step immediately if any of the following occurs:

- required backup/restore verification is not GREEN;
- production secret handling prerequisites are incomplete;
- authority or credential scan fails;
- replay/idempotency regression appears;
- audit/correlation evidence is missing;
- rollback path cannot be executed or verified;
- scope exceeds the recorded approval;
- customer/payment/account side effects differ from the approved canary;
- the operator cannot determine system state confidently.

## Rollback governance

- Production rollback is **not automatic** under the current baseline.
- The operator must preserve evidence before rollback when doing so does not increase risk.
- A rollback must not expand authority beyond the original activation scope.
- After rollback, verify health, audit trail, credential state, affected records and customer/payment reconciliation as applicable.
- Re-entry requires the failed gate to be corrected and re-validated.

This matrix prepares rollback/abort governance only; it does not authorize any production activation or rollback execution.

`PHIL_AI_OS_SPRINT_7_ROLLBACK_ABORT_MATRIX_READY_NOT_AUTHORIZED`
