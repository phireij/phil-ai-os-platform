# Ruby's Cake Delights — Checkout / Legal / Payment / Shipping Synchronization

Date: 2026-09-04  
Status: **IN PROGRESS — READ-ONLY SNAPSHOT GREEN / APPROVED SUBSET MISMATCH / REMEDIATION REQUIRED**

## Current production payment subset

CEO-approved initial KOMOJU launch subset:

- Visa / Mastercard
- JCB / American Express / Diners / Discover
- Konbini
- Merpay
- Paidy

Initial-launch exclusions:

- Bank Transfer — disabled
- Pay-easy — disabled
- PayPay — pending KOMOJU review
- Rakuten Pay — excluded

This selection does **not** authorize a real payment or WooCommerce mutation.

## Tax and shipping state

- Ruby's Cake Delights is treated as a 2026 consumption-tax-exempt business under the reviewed evidence.
- Qualified Invoice registration: not registered.
- WooCommerce tax route: disabled; no separate consumption-tax table write is required under the current decision.
- Production Yamato Cool shipping configuration and rates are already verified GREEN in the existing readiness record.

## Payment timing — what is already known

The legacy Tokushoho source says the legacy card methods were charged/confirmed when the order was placed. That wording must not be copied blindly to every KOMOJU method.

Official KOMOJU documentation confirms:

- Konbini is a deferred customer payment: a payment number/instruction is issued and the transaction waits for the customer to pay at the selected convenience store. The merchant-configurable default expiry is 3 days; Live Mode has its own expiry setting and must be checked directly before final legal wording.
- Paidy is completed immediately from the merchant transaction perspective when the transaction is created/captured; the customer's later Paidy billing relationship does not delay merchant payment completion.
- WooCommerce requires KOMOJU methods to be selected in the KOMOJU settings and then each resulting `KOMOJU - [payment method]` gateway must be enabled under WooCommerce payment settings before it appears on the site.

Official references reviewed:

- https://developer.woocommerce.com/docs/apis/rest-api/v3/payment-gateways/
- https://help.komoju.com/hc/ja/articles/4747504207390--WooCommerce-KOMOJU%E6%B1%BA%E6%B8%88%E3%82%92Live%E3%83%A2%E3%83%BC%E3%83%89-%E6%9C%AC%E7%95%AA%E7%92%B0%E5%A2%83-%E3%81%A7%E5%88%A9%E7%94%A8%E9%96%8B%E5%A7%8B%E3%81%99%E3%82%8B%E6%96%B9%E6%B3%95
- https://help.komoju.com/hc/en-us/articles/5201642509854--Paidy-Frequently-Asked-Questions-About-Payments

## Production GET-only snapshot result

Manual workflow run `33776964709` completed successfully on current `main` using the production read-only WooCommerce identity.

Safety evidence:

- network read-only: true
- mutation authorized: false
- payment execution authorized: false
- production publish authorized: false
- WooCommerce gateway `settings` values were not exported
- no customer/order/payment-token data was captured

The snapshot **cannot submit a payment** and cannot change gateway configuration.

Enabled gateways observed:

- `komoju_credit_card` — **KOMOJU Credit Card** — enabled
- `woa_gateway` — **Submit Order for Confirmation / 注文確認を依頼** — enabled

Disabled gateways observed:

- base `komoju` — disabled
- `bacs` / Direct bank transfer — disabled
- `cheque` — disabled
- `cod` — disabled

Not exposed in the WooCommerce gateway snapshot:

- Konbini
- Merpay
- Paidy
- Pay-easy
- PayPay
- Rakuten Pay

Therefore the approved initial subset does **not yet match** the WooCommerce checkout gateway configuration.

## Required WooCommerce/KOMOJU remediation

Per the official KOMOJU WooCommerce setup flow, the next configuration action is:

1. Open **WooCommerce → Settings → KOMOJU** and select the approved methods that are still missing: **Konbini, Merpay and Paidy**.
2. Save the KOMOJU settings.
3. Open **WooCommerce → Settings → Payments**.
4. Enable each resulting **KOMOJU - Konbini**, **KOMOJU - Merpay** and **KOMOJU - Paidy** gateway.
5. Keep Bank Transfer and Pay-easy disabled for the initial launch.
6. Do not enable PayPay while KOMOJU review remains pending.
7. Keep Rakuten Pay excluded.
8. Run the sanitized GET-only checkout snapshot again and require the approved subset to match before advancing the gate.

This configuration step is a production WooCommerce setting change. The repository does not mark it as performed and does not authorize real payment execution.

## Remaining synchronization evidence

- [x] Sanitized WooCommerce payment-gateway snapshot is GREEN.
- [ ] Enabled WooCommerce checkout methods exactly match the CEO-approved initial subset.
- [x] Bank Transfer is disabled for initial launch.
- [x] Pay-easy is not exposed in the current snapshot.
- [x] PayPay is not exposed while provider review is pending.
- [x] Rakuten Pay is not exposed.
- [ ] Add/enable Konbini, Merpay and Paidy in WooCommerce using the official KOMOJU two-step configuration.
- [ ] Rerun the read-only snapshot and verify the approved subset.
- [ ] KOMOJU Live Konbini expiry value is recorded.
- [ ] Customer-facing payment timing/deadline wording is finalized for every selected method.
- [ ] Tokushoho payment-method and payment-timing sections match the checkout behavior.
- [ ] Final order-confirmation screen correctly shows price, shipping, payment timing/deadline, fulfillment and cancellation information.

## Authority boundary

`mutation_authorized: false`  
`payment_execution_authorized: false`  
`production_publish_authorized: false`  
`automatic_production_execution_authorized: false`

`PHIL_AI_OS_RUBY_CHECKOUT_SNAPSHOT_GREEN_SUBSET_MISMATCH_FAIL_CLOSED`
