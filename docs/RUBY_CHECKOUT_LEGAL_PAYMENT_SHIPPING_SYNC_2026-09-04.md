# Ruby's Cake Delights — Checkout / Legal / Payment / Shipping Synchronization

Date: 2026-09-04  
Status: **IN PROGRESS — PAYMENT SUBSET / TAX / SHIPPING RECONCILED; CHECKOUT CONFIGURATION STILL FAIL-CLOSED**

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
- The selected payment methods are supported by KOMOJU in Japan, but actual Ruby checkout exposure must still be verified against WooCommerce.

Official references reviewed:

- https://developer.woocommerce.com/docs/apis/rest-api/v3/payment-gateways/
- https://ja.doc.komoju.com/page/supported-payment-methods
- https://help.komoju.com/hc/ja/articles/4747480397982
- https://help.komoju.com/hc/en-us/articles/5201642509854--Paidy-Frequently-Asked-Questions-About-Payments

## Safe WooCommerce verification prepared

A manual production **GET-only** workflow now captures `/wp-json/wc/v3/payment_gateways` using the existing read-only production identity.

The artifact intentionally retains only:

- gateway ID;
- customer-facing title;
- enabled status;
- display order;
- method title; and
- method-support capability names.

The WooCommerce `settings` object is discarded because it may contain credentials, webhook values, account identifiers or other sensitive configuration.

The workflow:

- cannot create an order;
- cannot submit a payment;
- cannot enable/disable a gateway;
- cannot update WooCommerce;
- cannot publish the storefront;
- requires an explicit manual read-only confirmation; and
- retains the sanitized artifact for one day only.

Workflow: `.github/workflows/commerce-woocommerce-production-readonly-checkout-snapshot.yml`

## Remaining synchronization evidence

The gate remains PENDING until all of the following are verified:

- [ ] Sanitized WooCommerce payment-gateway snapshot is GREEN.
- [ ] Enabled WooCommerce checkout methods exactly match the CEO-approved initial subset.
- [ ] Bank Transfer and Pay-easy are absent/disabled for initial launch.
- [ ] PayPay is not exposed while provider review is pending.
- [ ] Rakuten Pay is not exposed.
- [ ] KOMOJU Live Konbini expiry value is recorded.
- [ ] Customer-facing payment timing/deadline wording is finalized for every selected method.
- [ ] Tokushoho payment-method and payment-timing sections match the checkout behavior.
- [ ] Final order-confirmation screen correctly shows price, shipping, payment timing/deadline, fulfillment and cancellation information.

## Authority boundary

`mutation_authorized: false`  
`payment_execution_authorized: false`  
`production_publish_authorized: false`  
`automatic_production_execution_authorized: false`

`PHIL_AI_OS_RUBY_CHECKOUT_LEGAL_PAYMENT_SYNC_PREPARED_FAIL_CLOSED`
