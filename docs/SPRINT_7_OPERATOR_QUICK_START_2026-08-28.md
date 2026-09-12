# Sprint 7 — CEO / Operator Quick Start

**Last reconciled:** 2026-09-12  
**Status:** OPERATIONAL GUIDE / TRAINING PREPARATION / DOES NOT GRANT PRODUCTION AUTHORITY  
**Current executive position:** Sprint 3 remains current and owner-gated; Sprint 4 is bounded parallel acceleration; Sprint 5–7 readiness is advanced but formal live activation remains separately gated.

## 1. Ten-second Mission Control check

When opening Mission Control, first answer four questions:

1. **Is the system healthy?**
2. **What work is active or queued?**
3. **What needs human attention or approval?**
4. **Is anything outside the authorized boundary?**

The prepared Mission Control lifecycle projection is **read-only**. It may summarize workload and simulated lifecycle/result status, but it must not be treated as write/execution authority. If any answer is unclear, treat that as an operational attention item before approving new sensitive work.

## 2. Current authority baseline

The Core V1 operating boundary remains:

- autonomy: **A0**;
- execution task class: **`general` only**;
- bounded routing agent: **Hermes**;
- specialists: **disabled for normal live execution**;
- Mission Control: **read-only**;
- automatic production execution: **disabled**;
- automatic customer reply/send: **disabled**;
- WooCommerce production read-only identity/connectivity: **GREEN**;
- WooCommerce production mutation/publication: **not authorized**;
- real KOMOJU payment execution: **not authorized**;
- production SMS send: **not authorized**;
- production inventory mutation: **not authorized**;
- live Google Routes calls: **not authorized**;
- public-domain/DNS cutover: **not authorized**;
- automatic production retry/rollback with side effects: **not authorized**.

A readiness artifact, GREEN CI result, owner scope approval, or simulation result does not by itself change this baseline.

## 3. Current roadmap position

Current operational interpretation of the executive roadmap:

- **Sprint 3 — WooCommerce Foundation:** CURRENT PRIMARY / owner-gated closure;
- **Sprint 4 — Customer Experience:** bounded parallel acceleration, foundation materially GREEN;
- **Sprint 5 — Operations Hub:** formal roadmap entry pending; substantial non-authorizing foundation prepared early;
- **Sprint 6 — Automation:** formal roadmap entry pending; substantial simulation readiness prepared early;
- **Sprint 7 — Launch:** future formal sprint; integrated readiness materially prepared early.

Historical Sprint 5/6 “formal closure” markers refer to bounded engineering workstream closure only. They are **not** executive-roadmap Sprint 5/6 completion records.

## 4. Approval handling

Before approving an action:

1. confirm the requested scope matches the displayed task/context;
2. confirm the target environment is explicit;
3. confirm the action does not silently expand task class, agent authority, customer/account scope or production mutation scope;
4. confirm any required rollback/disable path exists;
5. approve only the narrow action intended;
6. verify one-time approval consumption where applicable;
7. verify replay protection;
8. review audit/correlation evidence after the action or simulation.

If scope, recipient, target environment or authority is ambiguous, deny or stop and resolve the ambiguity first.

## 5. Catalog operator workflow

The preferred catalog handoff is now the owner worksheet round trip:

1. start from the generated owner-editable CSV;
2. keep parent/variation SKU relationships intact;
3. complete only factual/approved owner fields;
4. do not replace unknown facts with guesses;
5. return the edited worksheet for fail-closed intake review;
6. review every proposed change before it is accepted into the canonical catalog source;
7. provide fresh evidence for changes to source-backed facts such as price or existing English copy;
8. only after the catalog is complete and approved may a separate production-mutation gate be considered.

For the current working subset, Moist Chocolate Round Cake is modeled as one variable product with parent `RCD-MCH-RD` and sellable variation SKUs `RCD-MCH-RD-15` and `RCD-MCH-RD-21`. Fudgy Milky Bar and Cheezy Ensaymada remain simple products.

The worksheet intake reviewer is **non-authorizing**. It does not automatically write back to the catalog or WooCommerce.

## 6. Commerce / payment check

Current verified facts:

- Ruby business/contact profile: **GREEN**;
- 2026 Japan consumption-tax decision: **GREEN — exempt / not Qualified-Invoice registered**;
- WooCommerce tax: **disabled**;
- WooCommerce production read-only identity/connectivity: **GREEN**;
- final Initial Launch Catalog V1: **PENDING OWNER COMPLETION/APPROVAL**;
- KOMOJU Test Mode capture/refund: **GREEN**;
- KOMOJU merchant Live dashboard/readiness evidence: **GREEN**;
- approved production payment subset/configuration evidence: **GREEN**;
- Live Konbini expiry: **3 days — verified**;
- KOMOJU final live acceptance / real-money execution: **PENDING / NOT AUTHORIZED**;
- actual final WooCommerce confirmation-screen owner acceptance: **PENDING**.

Before any production catalog mutation or real-payment activity:

- confirm the final owner-approved catalog/version can be identified precisely;
- confirm no old builder/test products or synthetic fixtures are being treated as authoritative;
- confirm bilingual copy, media, fulfillment/package and shipping facts are complete;
- confirm tax/Qualified-Invoice status has not changed;
- reconcile against a fresh read-only Woo snapshot;
- confirm staging QA, SSL, checkout, shipping/pickup and approval-before-payment remain GREEN;
- confirm rollback/disable path and production secret handling are ready;
- confirm the actual final checkout/confirmation screen has the required evidence and owner acceptance;
- confirm every required mutation/payment gate is explicitly GREEN;
- never treat read-only credentials, Test Mode evidence, dashboard access or scope approval as production write/payment authority.

## 7. Operations Hub / channel check

Prepared non-authorizing capabilities include:

- five-channel normalization for Facebook, Instagram, Telegram, WhatsApp and Google Business fixtures;
- review-only task extraction and idempotent queueing;
- read-only workload dashboard;
- reply-draft proposals and review workspaces;
- recommendation-only decision proposals and decision packets;
- privacy-preserving Mission Control projection.

Before any real external channel activation:

- identify the exact approved business/app/bot identity;
- verify the provider's current integration capability and permissions;
- use least privilege;
- verify ingress authenticity/signatures where applicable;
- begin read-only/canary wherever possible;
- keep outbound replies/writes disabled until separately approved;
- verify idempotency/replay behavior;
- verify governance routing and escalation;
- verify the disable/revoke path;
- verify customer/privacy data handling;
- request a separate live reply/write gate if outbound actions are required.

Existing Telegram approval/notification infrastructure does not automatically grant Operations Hub Telegram reply authority.

## 8. Automation check

Prepared automation is simulation-only.

Before any future live automation activation, confirm:

- the task class remains explicitly allowed;
- the assigned agent is explicitly authorized;
- approval requirements are satisfied;
- the execution boundary is the approved Control API/integration boundary;
- the requested action is not merely a simulated/dry-run plan;
- idempotency and replay protection are GREEN;
- audit correlation is preserved end-to-end;
- failure/rollback behavior is known;
- no specialist, channel reply, commerce mutation, payment, SMS or inventory authority has been implicitly added.

A simulated success is evidence about orchestration logic, not authorization for live execution.

## 9. Incident handling

For an unexpected error or side effect:

1. stop the affected activation/workflow;
2. preserve safe evidence/log references;
3. disable the affected integration or write capability if needed;
4. verify current customer/order/payment/inventory state;
5. follow the rollback/abort matrix;
6. rotate/revoke credentials if exposure is suspected;
7. reconcile affected orders/messages/payments/records;
8. re-run the failed gate before resuming.

Do not broaden authority as a shortcut to recover from an incident.

## 10. Backup and recovery check

Phase 1 historically validated scheduled backup, monitoring and isolated restore. Before production cutover or significant production mutation:

- confirm a **launch-fresh** backup exists;
- confirm backup timer/monitor health;
- run/confirm database integrity checks where applicable;
- verify the isolated restore procedure near launch;
- confirm who owns the rollback decision;
- confirm the restore target and stop criteria.

Historical GREEN evidence is not a substitute for launch-time freshness.

## 11. Repository / deployment check

Before final public launch:

- confirm current-head required CI is GREEN;
- confirm `main` has an actually enforced branch-protection rule or repository ruleset;
- confirm required status checks match the approved policy;
- confirm production deployment/cutover runbooks are current;
- confirm no unresolved secret/credential scan issue exists;
- confirm preview/test deployment artifacts are not being mistaken for production deployment evidence.

The current linked GitHub integration cannot activate repository administration controls. The `main` ruleset gate therefore remains an external/admin launch dependency until it is actually enabled and verified.

## 12. Launch-day stop conditions

Stop or postpone the affected launch step if:

- any required launch gate is not explicitly GREEN;
- final catalog/version approval cannot be identified;
- actual final-screen acceptance is missing;
- backup/restore readiness is not launch-fresh;
- production secret handling is not ready;
- `main` lacks required protection/ruleset coverage;
- credential/authority scans fail;
- replay/idempotency tests regress;
- rollback/disable path is unclear;
- payment/order/channel behavior differs from the approved expected flow;
- Air Mobile URL or other required launch dependency is missing from the chosen launch scope;
- Twilio/SMS readiness is incomplete while SMS remains in launch scope;
- authority exceeds the recorded approval;
- the operator cannot confidently determine current state.

## 13. Pre-launch operator rehearsal checklist

Before final Go/No-Go, perform one bounded rehearsal with no production side effects:

- [ ] Open/read Mission Control status and identify current workload/approval items.
- [ ] Walk one sample task from intake → classification → governance → approval boundary → simulated plan → audit evidence.
- [ ] Verify a governance-sensitive sample stops at approval and cannot self-approve.
- [ ] Verify a simulated failure produces bounded recovery evidence without automatic side effects.
- [ ] Review the final catalog worksheet/intake-review process using a copy, not production catalog data.
- [ ] Review checkout/payment acceptance gates without executing a real payment.
- [ ] Locate the current cutover and rollback runbooks.
- [ ] Verify launch-fresh backup/restore check procedure is understood.
- [ ] Verify the repository-protection gate is either GREEN or explicitly blocks launch.
- [ ] Verify final CEO Go/No-Go and CTO sign-off locations/process.

Record rehearsal issues as blockers; do not work around them by expanding authority.

## 14. Launch acceptance

A GREEN engineering branch, merged PR, simulated workflow, readiness artifact or owner scope approval does **not** mean live launch is authorized.

Live launch requires every applicable production gate to be GREEN plus final CEO Go/No-Go and CTO sign-off recorded in the Sprint 7 launch-acceptance package.

Public-domain/DNS cutover is performed **last**, after the production storefront and all launch-scope components have passed their respective acceptance checks.

`PHIL_AI_OS_SPRINT_7_OPERATOR_GUIDE_READY`
