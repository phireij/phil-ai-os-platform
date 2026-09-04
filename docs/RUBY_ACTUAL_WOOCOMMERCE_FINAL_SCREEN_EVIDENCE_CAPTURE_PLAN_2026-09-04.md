# Ruby's Cake Delights — Actual WooCommerce Final Confirmation Screen Evidence Capture Plan

**Date:** 4 September 2026  
**Status:** CONTRACT/CAPTURE PLAN READY — ACTUAL SCREEN REVIEW PENDING  
**Environment:** WooCommerce preproduction only  
**Authority:** no order creation, no payment execution, no production publishing, no catalog mutation, no DNS cutover

## Purpose

Capture enough sanitized evidence from the **actual WooCommerce preproduction final checkout/confirmation screen** to review the customer-facing legal/payment/fulfillment presentation without submitting an order or executing a payment.

The isolated Sprint 4 confirmation preview is already GREEN, but it does **not** satisfy this actual-screen gate.

## Evidence contract

The evidence must conform to:

`contracts/cx/final-confirmation-screen-evidence.schema.json`

Pending evidence is staged in:

`ops/readiness/ruby-actual-woocommerce-final-confirmation-screen-evidence.template.json`

## Safe capture procedure

1. Use the existing Ruby WooCommerce **preproduction** site only.
2. Use synthetic QA customer details only. Never use a real customer name, address, email, phone number, order number, payment token or provider credential.
3. Prepare a representative cart that allows the real WooCommerce checkout UI to render. This step may use ordinary preproduction browser/session state, but it must not create an order or payment.
4. Reach the final review state immediately before the final order-submission action.
5. **Do not click** `Place order`, `注文する`, or any equivalent order-submission/payment action.
6. Capture sanitized evidence showing the relevant customer-facing fields. Redact any accidental PII, cookies/session IDs, credentials, API keys, tokens, internal account identifiers or sensitive provider data before retention.
7. Record artifact references and SHA-256 hashes in the evidence JSON. Do not embed sensitive screenshots or secrets in the readiness record itself.
8. Mark an observation true only when the actual WooCommerce screen visibly proves it.
9. Keep `evidence_complete=false` and `actual_final_confirmation_screen_reviewed=false` until every required observation is evidenced and the validator is updated for the completed evidence instance.

## Required screen observations

The actual screen must make the following reviewable before submission:

- product name, quantity and applicable options;
- subtotal, shipping and final total;
- selected payment method;
- payment timing/deadline information;
- fulfillment timing;
- cancellation/return terms or a clear linked route;
- a correction/edit path before submission;
- an unambiguous final action label;
- Tokushoho disclosure or a clear linked route;
- tax presentation consistent with the current 2026 exempt-business posture;
- when Konbini is selected, wording reconciled to the verified **3-day** expiry, while the exact transaction deadline shown by the payment flow remains controlling.

## Evidence hygiene

Permitted evidence:

- sanitized screenshot artifact references;
- SHA-256 hashes;
- structured boolean observations;
- short review notes with no personal or secret data.

Prohibited evidence:

- real customer personal data;
- WooCommerce/KOMOJU credentials or keys;
- browser cookies/session identifiers;
- raw payment tokens;
- order submission evidence;
- real payment/capture/refund evidence;
- any production mutation introduced merely to satisfy this review.

## Acceptance boundary

This contract enables a safe actual-screen review but does not itself make the gate GREEN.

Current required state remains:

- `evidence_complete: false`
- `actual_final_confirmation_screen_reviewed: false`
- `order_creation_authorized: false`
- `payment_execution_authorized: false`
- `production_publish_authorized: false`

**Marker:** `PHIL_AI_OS_RUBY_ACTUAL_WOOCOMMERCE_FINAL_SCREEN_EVIDENCE_CONTRACT_READY_REVIEW_PENDING_FAIL_CLOSED`
