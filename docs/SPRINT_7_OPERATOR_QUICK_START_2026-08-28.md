# Sprint 7 — CEO / Operator Quick Start

Date: 2026-08-28
Status: OPERATIONAL GUIDE / DOES NOT GRANT PRODUCTION AUTHORITY

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
- production WooCommerce/KOMOJU/channel writes: **not authorized by Sprint 7 readiness work**;
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

Before production WooCommerce or KOMOJU activity:

- verified Ruby business/contact/policy data complete;
- phone number verified;
- no old test products/categories treated as authoritative;
- staging QA GREEN;
- SSL and checkout QA GREEN;
- production secret storage approved;
- rollback path ready;
- WooCommerce production gate explicitly approved;
- KOMOJU Test Mode validated before any Live Mode proposal;
- KOMOJU Live Mode separately approved before real payments.

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

- backup/restore readiness is not GREEN;
- verified business/contact/policy data is incomplete;
- production secret handling is not ready;
- credential/authority scans fail;
- replay/idempotency tests regress;
- rollback/disable path is unclear;
- payment/order/channel behavior differs from the approved expected flow;
- authority exceeds the recorded approval;
- the operator cannot confidently determine current state.

## 9. Launch acceptance

A GREEN engineering branch or merged PR means the software/readiness package passed its bounded gates. It does **not** mean live launch is authorized.

Live launch requires the remaining production gates and explicit CEO/CTO sign-off recorded in the Sprint 7 launch acceptance package.

`PHIL_AI_OS_SPRINT_7_OPERATOR_GUIDE_READY`
