# Ruby's Cake Delights — Final Checkout / Order-Confirmation Screen Review Checklist

**Date:** 2026-09-04  
**Status:** **STATIC COMPLIANCE CHECKLIST READY — ACTUAL FINAL SCREEN REVIEW PENDING**  
**Scope:** Bounded Sprint 4 Customer Experience readiness while Sprint 3 remains the current primary sprint.

## Purpose

This checklist defines what must be visible and reviewable immediately before a customer submits the final WooCommerce order. It is based on the current Ruby checkout/payment/shipping/legal readiness state and Japan Consumer Affairs Agency final-confirmation requirements already reconciled by the project.

Preparing and validating this checklist is side-effect-free. It must not submit an order, execute or simulate a real Live payment, publish the storefront, or mutate production configuration.

## A. Order contents and quantity

- [ ] Each product is clearly identified.
- [ ] Quantity for each product is visible.
- [ ] Selected size/variant/options that affect the order are visible.
- [ ] Pickup vs delivery choice is visible.
- [ ] Customer can return to correct product, quantity, options or fulfillment information before final submission.

## B. Selling price, total and customer-borne fees

- [ ] Product selling price is visible for each line item.
- [ ] Order subtotal is visible.
- [ ] Shipping fee is visible where delivery is selected.
- [ ] Current Yamato Cool rate resolves consistently with verified configuration: Kanto ¥1,350; other supported regions ¥1,500–¥1,800.
- [ ] Final amount payable to Ruby's Cake Delights is clearly visible before submission.
- [ ] No separate WooCommerce consumption-tax amount is added under the current verified 2026 consumption-tax-exempt posture.
- [ ] The screen does not represent Ruby's Cake Delights as a Qualified Invoice issuer.
- [ ] Any payment-provider fee that is not part of the merchant-collected total is clearly distinguished where applicable; for Paidy, customer-side fees depend on the Paidy payment method and are handled by Paidy.

## C. Payment method and timing/deadline

Only the approved initial production subset may be offered:

- [ ] Credit cards — Visa / Mastercard / JCB / American Express / Diners Club / Discover.
- [ ] Konbini.
- [ ] Merpay.
- [ ] Paidy.
- [ ] Bank Transfer is not offered.
- [ ] Pay-easy is not offered.
- [ ] PayPay is not offered while provider review remains pending.
- [ ] Rakuten Pay is not offered.

Required timing/deadline information:

- [ ] Credit card: processing occurs during order placement; issuer billing/debit timing may differ.
- [ ] Konbini: the transaction-specific payment deadline is clearly presented or made available through the KOMOJU flow/instructions.
- [ ] Konbini: current verified Live expiry configuration is 3 days.
- [ ] Konbini: where a transaction-specific deadline exists, that exact deadline controls over generic wording.
- [ ] Merpay: customer is informed that payment is completed through the KOMOJU/Merpay flow before order confirmation.
- [ ] Paidy: customer is informed of Paidy authorization/processing at order placement and the customer billing schedule already reconciled in the payment-timing record.

## D. Fulfillment / delivery / pickup timing

- [ ] Delivery or pickup method is clearly visible.
- [ ] For delivery, selected/confirmed delivery timing is visible where applicable.
- [ ] Normal dispatch expectation of 2–5 days after order confirmation and required payment completion is not contradicted.
- [ ] For payment methods requiring later customer payment, fulfillment wording does not imply preparation/shipment occurs before required payment completion unless explicitly intended.
- [ ] Store pickup date/time is visible for pickup orders.
- [ ] Current pickup availability is not represented more broadly than the verified Wednesday–Saturday 14:00–20:00 state before the planned mid-September recheck.

## E. Cancellation, changes and returns

Unless a product/order explicitly has separately disclosed conditions:

- [ ] 48+ hours before scheduled pickup/shipment: full-refund eligibility is visible or directly accessible from the final screen.
- [ ] 24–<48 hours: 50% cancellation fee is visible or directly accessible.
- [ ] <24 hours / same-day / no-show: 100% cancellation fee is visible or directly accessible.
- [ ] Any custom/large/seasonal/event-specific earlier deadline is clearly disclosed before submission.
- [ ] Perishable-food change-of-mind return restriction is visible or directly accessible.
- [ ] Defect/damage/wrong-item claim route is visible or directly accessible, including the 24-hour shipped-order contact window.

## F. Final-action clarity and correction path

- [ ] Final submission control clearly communicates that activating it places/submits the order.
- [ ] The button/control is not visually or linguistically misleading about the fact that an order will be submitted.
- [ ] Required transaction terms can be reviewed together before the final action.
- [ ] Customer can correct entered information or return to an earlier step before final submission.
- [ ] Japanese customer-facing content is complete for the required legal/transaction terms.
- [ ] English support content, where exposed, does not contradict the Japanese production terms.

## G. Evidence required to mark the actual screen GREEN

The actual final-screen gate may become GREEN only after safe evidence is captured from the final WooCommerce checkout/order-confirmation implementation showing the items above. The evidence review must remain non-transactional where possible.

Acceptable evidence may include:

- a read-only rendered checkout/final-confirmation screen review using a non-submitted cart/session;
- screenshots or sanitized DOM/content captures that do not contain payment credentials or sensitive customer information;
- configuration/template evidence sufficient to prove required wording and controls;
- a controlled non-Live test flow if rendering cannot otherwise be proven, provided it does not constitute a real Live payment or production order.

The following are **not** required or authorized merely to satisfy this checklist:

- a real Live payment;
- a real production charge/capture/refund;
- publishing the Tokushoho candidate;
- public-domain/DNS cutover;
- enabling automatic production execution.

## Current review state

- Static checklist/specification: **GREEN / READY**.
- Tokushoho publication candidate: **READY, NOT APPROVED**.
- Actual final WooCommerce confirmation screen reviewed against this checklist: **FALSE / PENDING**.
- Checkout legal synchronization complete: **FALSE / PENDING ACTUAL SCREEN + APPROVAL**.
- Real payment execution authorized: **FALSE**.
- Production publishing authorized: **FALSE**.

`static_confirmation_screen_checklist_ready: true`  
`actual_final_confirmation_screen_reviewed: false`  
`tokushoho_publication_approved: false`  
`payment_execution_authorized: false`  
`production_publish_authorized: false`

`PHIL_AI_OS_RUBY_FINAL_CONFIRMATION_SCREEN_STATIC_CHECKLIST_READY_ACTUAL_REVIEW_PENDING_FAIL_CLOSED`
