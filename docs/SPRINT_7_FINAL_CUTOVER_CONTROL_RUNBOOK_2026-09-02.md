# Sprint 7 — Final Cutover Control Runbook

**Date:** 2026-09-02  
**Status:** **PREPARED / NOT AUTHORIZED TO EXECUTE YET**

## Objective

Make the eventual Ruby's Cake Delights WooCommerce public cutover a controlled verification-and-execution sequence, not an improvised launch-day design task.

## Phase A — Evidence freeze

Before any public change:

1. Confirm the approved final production catalog is frozen and versioned.
2. Confirm Japan tax / Qualified Invoice evidence has been reviewed and the resulting WooCommerce tax configuration is explicitly documented.
3. Confirm final checkout, Tokushoho, payment methods, shipping fees and payment timing agree.
4. Confirm KOMOJU merchant Live eligibility and the exact production payment-method subset.
5. Confirm Air Mobile Order Quick Pickup production URL if that feature is part of launch.
6. Confirm SMS provider/account/sender readiness if SMS is part of launch.
7. Capture current public-site and WooCommerce pre-production snapshots needed for rollback verification.

Any missing item keeps the launch decision at **NO-GO**.

## Phase B — Fresh recovery gate

Immediately before cutover, rerun the governed recovery validation and require:

- source SQLite `quick_check=ok`;
- isolated restored SQLite `quick_check=ok`;
- source/restored row counts match;
- backup timer active;
- backup monitor active;
- Control API healthy;
- rollback/abort path confirmed.

A Sep 2 recovery result is a baseline only and cannot substitute for this cutover-time check.

## Phase C — Final Go / No-Go

Review `ops/readiness/ruby-final-go-no-go-gate-2026-09-02.json` against current evidence. A GO requires every required launch gate to be explicitly reconciled GREEN and the final CEO Go/No-Go acceptance recorded.

Do not infer GO from:

- CEO scope approval alone;
- successful Test Mode payments;
- successful WooCommerce read-only authentication;
- current-head CI alone;
- an earlier recovery run.

## Phase D — Controlled activation order

Only after final GO, execute the approved activation plan in the smallest reversible sequence. Preserve separate verification points between any production configuration/write step, payment-mode activation and public-domain/DNS change. Do not batch unrelated irreversible changes.

The exact command/UI procedure for a production mutation must come from the then-current approved activation record; this runbook does not grant mutation authority by itself.

## Phase E — Immediate post-cutover acceptance

Verify, at minimum:

- public domain resolves to the intended production storefront;
- HTTPS/SSL is healthy;
- homepage, product, cart and checkout surfaces respond correctly;
- shipping/pickup rules reflect the approved configuration;
- approval-before-payment behavior remains intact;
- payment methods match final legal disclosure;
- order/payment status transitions are correct;
- outbound customer notifications behave as approved;
- indexing/canonical/SEO state matches launch intent;
- no credential, authority or duplicate-send regression occurred.

## Abort / rollback rule

If a mandatory verification fails, stop the affected activation sequence. Do not compensate with automatic retries, repeated customer sends or unapproved production mutations. Follow the approved rollback/abort record and re-enter through a new verified gate after remediation.

## Governance

This document is preparation only. It does not change A0, `general`-only authority, enable specialists, grant Mission Control mutation authority, authorize automatic production execution, or turn a current NO-GO into GO.

`PHIL_AI_OS_SPRINT_7_FINAL_CUTOVER_RUNBOOK_PREPARED_FAIL_CLOSED`
