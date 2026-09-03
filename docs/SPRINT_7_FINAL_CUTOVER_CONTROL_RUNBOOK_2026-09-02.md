# Sprint 7 — Final Cutover Control Runbook

**Last reconciled:** 2026-09-03  
**Status:** **PREPARED / NOT AUTHORIZED TO EXECUTE YET**  
**Current executive position:** Sprint 3 remains current; this is future Sprint 7 launch preparation only.

## Objective

Make the eventual Ruby's Cake Delights WooCommerce public cutover a controlled verification-and-execution sequence, not an improvised launch-day design task.

## Phase A — Evidence freeze

Before any public change:

1. Confirm the approved final production catalog is frozen, versioned, and reconciled against a fresh read-only WooCommerce snapshot.
2. Confirm the 2026 Japan tax / Qualified Invoice decision remains GREEN: Ruby is treated as consumption-tax exempt, is not Qualified-Invoice registered, and WooCommerce tax remains disabled. No tax-table activation is required under the current decision.
3. Confirm final checkout, Tokushoho, payment methods, shipping fees and payment timing agree.
4. Confirm KOMOJU merchant Live eligibility and the exact production payment-method subset.
5. Confirm Air Mobile Order Quick Pickup production URL if that feature is part of launch.
6. Confirm SMS provider/account/sender readiness if SMS is part of launch.
7. Confirm `main` is covered by an approved branch-protection rule or repository ruleset before final public launch.
8. Capture current public-site and WooCommerce pre-production snapshots needed for rollback verification.

Any required item that is not explicitly GREEN keeps the launch decision at **NO-GO**.

## Phase B — Fresh recovery gate

Immediately before cutover, rerun the governed recovery validation and require:

- source SQLite `quick_check=ok`;
- isolated restored SQLite `quick_check=ok`;
- source/restored row counts match;
- backup timer active;
- backup monitor active;
- Control API healthy;
- rollback/abort path confirmed.

A previous recovery result is a baseline only and cannot substitute for this cutover-time check.

## Phase C — Final Go / No-Go

Review `ops/readiness/ruby-final-go-no-go-gate-2026-09-02.json` against current evidence. A GO requires every required launch gate to be explicitly reconciled GREEN and the final CEO Go/No-Go acceptance recorded.

Do not infer GO from:

- CEO scope approval alone;
- successful Test Mode payments;
- successful WooCommerce read-only authentication;
- current-head CI alone;
- the resolved tax decision alone;
- an earlier recovery run.

## Operator roles at cutover

| Role | Launch-day responsibility | Authority boundary |
|---|---|---|
| CEO | Final Go/No-Go acceptance and business decisions | Does not replace technical readiness gates |
| CTO office | Evidence reconciliation, sequence control, stop/rollback recommendation | No unapproved production side effects |
| Operator | Executes only the exact approved UI/command step | Must stop on any unexpected result |
| CI/readiness controls | Verify contracts, authority boundaries, recovery and acceptance evidence | Evidence only; never grants production authority |

One person may perform multiple roles, but the responsibilities and evidence must remain distinct.

## Phase D — Controlled activation order

Only after final GO, execute the approved activation plan in the smallest reversible sequence:

1. Freeze launch evidence and approved catalog version.
2. Apply only the explicitly approved WooCommerce production configuration/catalog step.
3. Verify storefront, inventory, shipping/pickup and approval-before-payment behavior before proceeding.
4. Activate only the approved KOMOJU Live payment-method subset, if its gate is GREEN.
5. Verify a bounded payment acceptance path before any broader customer exposure.
6. Enable SMS only if SMS is in launch scope and its provider/account/sender/handset gate is GREEN.
7. Perform public-domain/DNS cutover last, after the production storefront itself has passed acceptance.
8. Run the immediate post-cutover checklist before declaring launch complete.

Preserve separate verification points between production configuration/write steps, payment-mode activation, SMS activation and public-domain/DNS change. Do not batch unrelated irreversible changes.

The exact command/UI procedure for a production mutation must come from the then-current approved activation record; this runbook does not grant mutation authority by itself.

## Phase E — Immediate post-cutover acceptance

Verify, at minimum:

- public domain resolves to the intended production storefront;
- HTTPS/SSL is healthy;
- homepage, product, cart and checkout surfaces respond correctly;
- approved catalog/version is the one visible to customers;
- WooCommerce tax remains disabled while the exempt-business decision applies;
- shipping/pickup rules reflect the approved configuration;
- approval-before-payment behavior remains intact;
- payment methods match final legal disclosure;
- order/payment status transitions are correct;
- outbound customer notifications behave as approved;
- indexing/canonical/SEO state matches launch intent;
- no credential, authority, duplicate-order or duplicate-send regression occurred.

## Stop / rollback decision matrix

| Condition | Required response |
|---|---|
| A required gate is not GREEN before activation | **STOP / NO-GO.** Do not start the affected activation step. |
| Production configuration differs from the approved plan | **STOP.** Preserve evidence and revert the affected reversible change where approved. |
| Checkout, shipping/pickup or approval-before-payment fails | **STOP customer exposure.** Roll back the affected storefront/configuration step before proceeding. |
| KOMOJU Live payment acceptance fails or behaves unexpectedly | **STOP Live payment expansion.** Return to the approved safe payment state; do not repeatedly charge/test customers. |
| SMS sends unexpectedly, duplicates or fails identity/delivery verification | **DISABLE further sends.** Do not retry automatically. |
| DNS/public cutover produces incorrect origin, TLS or storefront behavior | **ROLL BACK DNS/public cutover** using the approved DNS rollback plan. |
| Recovery/backup evidence is stale or fails | **NO-GO / ABORT.** Re-establish recovery GREEN before any launch continuation. |
| Authority/credential boundary regresses | **ABORT.** Do not compensate with manual bypasses or expanded permissions. |

## Abort / rollback rule

If a mandatory verification fails, stop the affected activation sequence. Do not compensate with automatic retries, repeated customer sends, repeated real-payment attempts, temporary security bypasses or unapproved production mutations. Preserve the failure evidence, execute only the approved reversible rollback step, and re-enter through a new verified gate after remediation.

## Evidence to retain

For each launch step, retain enough evidence to answer:

- what exact version/configuration was approved;
- who approved the business decision;
- which technical gate was GREEN;
- what exact action was executed;
- what verification result followed;
- whether rollback was required;
- what final customer-facing state was accepted.

Do not retain raw credentials, payment secrets, personal tax-return files or unnecessary customer data in repository evidence.

## Governance

This document is preparation only. It does not change A0, `general`-only authority, enable specialists, grant Mission Control mutation authority, authorize automatic production execution, or turn a current NO-GO into GO.

`PHIL_AI_OS_SPRINT_7_FINAL_CUTOVER_RUNBOOK_PREPARED_FAIL_CLOSED`
