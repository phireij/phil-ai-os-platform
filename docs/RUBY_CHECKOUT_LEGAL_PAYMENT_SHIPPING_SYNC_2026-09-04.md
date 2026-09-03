# Ruby's Cake Delights — Checkout / Legal / Payment / Shipping Synchronization

Date: 2026-09-04  
Status: **APPROVED KOMOJU SUBSET + CHECKOUT + LIVE KONBINI 3-DAY EXPIRY + PAYMENT-TIMING WORDING GREEN; PUBLICATION / FINAL SCREEN PENDING**

## Verified production payment subset

CEO-approved initial KOMOJU launch subset:

- Visa / Mastercard
- JCB / American Express / Diners / Discover
- Konbini
- Merpay
- Paidy

Initial-launch exclusions remain:

- Bank Transfer — disabled
- Pay-easy — not exposed
- PayPay — not exposed while provider review is pending
- Rakuten Pay — excluded / not exposed

This selection does **not** authorize a real payment or WooCommerce mutation.

## Fresh production GET-only verification

Workflow run `33776964709`, rerun attempt 2, completed successfully after the owner enabled the approved methods in WooCommerce.

Sanitized artifact: `9902650701`  
Captured at: `2026-09-03T16:27:24.175410Z`

Enabled gateway evidence:

- `komoju_credit_card` — Credit Card
- `komoju_konbini` — Konbini
- `komoju_merpay` — Merpay
- `komoju_paidy` — Paidy
- `woa_gateway` — Submit Order for Confirmation / 注文確認を依頼

Disabled gateway evidence:

- `bacs` — Direct bank transfer
- `cheque` — Check payments
- `cod` — Cash on delivery
- base `komoju` gateway — disabled

Pay-easy, PayPay and Rakuten Pay are not exposed in the sanitized WooCommerce gateway snapshot.

Therefore the approved initial KOMOJU payment subset now **matches the WooCommerce checkout configuration**.

The snapshot is network-read-only, exports no gateway settings/secrets, cannot submit a payment, cannot create an order, and cannot change WooCommerce configuration.

## Live Konbini expiry verification

- KOMOJU Live Konbini payment-expiry setting: **3 days — VERIFIED GREEN**.
- Evidence classification: owner-confirmed Live dashboard configuration evidence.
- The 3-day setting is configuration/timing evidence only; it does **not** prove or authorize a real Konbini payment, settlement, refund or capture.

## Payment timing / Tokushoho reconciliation

Customer-facing payment timing/deadline wording is now reconciled for every selected launch method in `docs/RUBY_PAYMENT_TIMING_TOKUSHOHO_RECONCILIATION_2026-09-04.md`.

- Credit card — payment procedure at order time; actual issuer billing/debit date depends on the card issuer.
- Konbini — pay by the exact KOMOJU deadline shown/notified after the order; current Live expiry setting is 3 days.
- Merpay — complete the Merpay app/QR payment flow at order time; payment completes when the Merpay flow confirms completion.
- Paidy — merchant-side transaction completes at order/transaction time while the customer pays Paidy later under Paidy's published billing schedule; current customer due date is the 27th under the documented methods.

Paidy's currently published customer-borne fees are also captured in the reconciliation companion so they can be shown consistently before order submission.

This closes the **payment-timing wording** evidence item only. It does not approve the final Tokushoho publication text and does not replace the final checkout/confirmation-screen review.

## Tax and shipping state

- 2026 consumption-tax status: exempt.
- Qualified Invoice registration: not registered.
- WooCommerce tax route: disabled.
- Production Yamato Cool shipping configuration and rates: verified GREEN.

## Remaining synchronization evidence

- [x] Approved KOMOJU payment subset finalized.
- [x] WooCommerce checkout configuration matches the approved subset.
- [x] Bank Transfer disabled.
- [x] Pay-easy not exposed.
- [x] PayPay not exposed while review is pending.
- [x] Rakuten Pay not exposed.
- [x] Tax route reconciled.
- [x] Shipping configuration/rates reconciled.
- [x] Actual **KOMOJU Live Konbini payment-expiry setting verified at 3 days**.
- [x] Customer-facing payment timing/deadline wording reconciled for all selected methods.
- [x] Tokushoho payment-method/payment-timing reconciliation record prepared.
- [ ] Apply reconciled payment wording to the final Tokushoho publication candidate and obtain required owner approval before publication.
- [ ] Review the final checkout/order-confirmation screen for price, shipping, payment timing/deadline, fulfillment and cancellation wording.

## Authority boundary

`mutation_authorized: false`  
`payment_execution_authorized: false`  
`production_publish_authorized: false`  
`automatic_production_execution_authorized: false`

Checkout configuration, Live Konbini expiry and payment-timing wording are GREEN, but **real payment execution remains blocked** and publication remains separately gated.

`PHIL_AI_OS_RUBY_CHECKOUT_PAYMENT_TIMING_GREEN_FINAL_SCREEN_AND_PUBLICATION_PENDING_FAIL_CLOSED`
