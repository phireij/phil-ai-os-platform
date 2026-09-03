# Sprint 7 — CEO / Operator Quick Start

**Last reconciled:** 2026-09-03  
**Status:** OPERATIONAL GUIDE / DOES NOT GRANT PRODUCTION AUTHORITY  
**Current executive position:** Sprint 3 remains current; this guide is future launch preparation.

## 1. Ten-second Mission Control check

When opening Mission Control, first answer four questions:

1. **Is the system healthy?**
2. **What work is active or queued?**
3. **What needs human attention or approval?**
4. **Is anything outside the authorized boundary?**

If any answer is unclear, treat that as an operational attention item before approving new sensitive work.

## 2. Current authority baseline

The default Core V1 operating boundary remains:

- autonomy: **A0**;
- execution task class: **`general` only**;
- bounded routing agent: **Hermes**;
- specialists: **disabled**;
- Mission Control: **read-only** unless separately authorized;
- CEO production scope approval: **recorded**, but does not override readiness gates;
- WooCommerce production read-only identity/connectivity: **GREEN**;
- WooCommerce production mutation: **not ready / fail-closed**;
- KOMOJU Live, live SMS and public-domain/DNS execution: **not ready / separately gated**;
- automatic production retry/rollback: **not authorized**.

## 3. Approval handling

Before approving an action:

1. confirm the requested scope matches the displayed task/context;
2. confirm the action does not silently expand task class, agent authority, customer/account scope or production mutation scope;
3. confirm any required rollback/disable path exists;
4. approve only the narrow action intended;
5. verify the approval is consumed once and not replayed;
6. review audit/correlation evidence after the action or simulation.

If scope, recipient, target environment or authority is ambiguous, deny or stop and resolve the ambiguity first.

## 4. Incident handling

For an unexpected error or side effect:

1. stop the affected activation or workflow;
2. preserve useful evidence/log references where safe;
3. disable the affected integration or write capability if needed;
4. verify current system/customer/payment state;
5. follow the rollback/abort matrix;
6. rotate/revoke credentials if exposure is suspected;
7. reconcile affected orders/messages/payments/records as applicable;
8. re-run the failed gate before resuming.

Do not broaden authority as a shortcut to recover from an incident.

## 5. Backup and recovery check

Phase 1.17 historically validated scheduled backup, integrity monitoring and isolated restore. Before production cutover or significant production mutation:

- confirm a fresh backup exists;
- confirm the backup timer/monitor is healthy;
- run/confirm SQLite integrity checks where applicable;
- verify the isolated restore procedure near launch;
- know who owns the rollback decision.

Historical GREEN evidence is not a substitute for launch-time freshness.

## 6. Commerce / payment check

Current verified facts:

- Ruby business/contact profile: **GREEN**;
- 2026 Japan consumption-tax decision: **GREEN — exempt / not Qualified-Invoice registered**;
- WooCommerce tax: **disabled** under the current decision;
- WooCommerce production read-only identity/connectivity: **GREEN**;
- final production catalog: **PENDING — only remaining Sprint 3 owner-input gate**;
- KOMOJU Test Mode capture/refund: **GREEN**;
- KOMOJU Live acceptance: **PENDING**.

Before any production mutation or real-payment activity:

- confirm the final owner-approved catalog is frozen and reconciled against a fresh read-only Woo snapshot;
- confirm no old builder/test products or fixtures are treated as authoritative;
- confirm the tax decision has not changed; if it has, stop and re-open the tax gate;
- confirm staging QA, SSL, checkout, shipping/pickup and approval-before-payment remain GREEN;
- confirm production secret handling and rollback path are ready;
- confirm every required mutation/live-payment gate is explicitly GREEN;
- do not treat read-only credentials, scope approval or Test Mode evidence as write/payment authority.

## 7. External channel check

Before activating Facebook, Instagram, Telegram, WhatsApp or Google Business:

- verify the platform's current supported integration capability and permissions;
- identify the exact approved business/app/bot identity;
- use least privilege;
- validate ingress authenticity;
- keep outbound replies/writes disabled during initial read-only canary;
- verify idempotency/replay and governance routing;
- verify the disable/revoke path;
- request a separate write/reply gate if outbound actions are needed.

Existing Telegram approval/notification infrastructure does not automatically grant Operations Hub Telegram authority.

## 8. Launch-day stop conditions

Stop or postpone the affected launch step if:

- any required launch gate is not explicitly GREEN;
- backup/restore readiness is not launch-fresh;
- the final approved catalog/version cannot be identified;
- tax/Invoice status no longer matches the recorded exempt/not-registered decision;
- production secret handling is not ready;
- `main` lacks the required approved branch-protection rule or repository ruleset;
- credential/authority scans fail;
- replay/idempotency tests regress;
- rollback/disable path is unclear;
- payment/order/channel behavior differs from the approved expected flow;
- authority exceeds the recorded approval;
- the operator cannot confidently determine current state.

## 9. Launch acceptance

A GREEN engineering branch or merged PR means the software/readiness package passed its bounded gates. It does **not** mean live launch is authorized.

Live launch requires every applicable production gate to be GREEN plus final CEO Go/No-Go and CTO sign-off recorded in the Sprint 7 launch acceptance package.

The public-domain/DNS cutover is performed **last**, after the production storefront and other launch components have passed their respective acceptance checks.

`PHIL_AI_OS_SPRINT_7_OPERATOR_GUIDE_READY`
