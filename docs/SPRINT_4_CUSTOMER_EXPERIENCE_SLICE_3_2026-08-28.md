# Sprint 4 — Customer Experience Slice 3

Date: 2026-08-28
Status: GREEN

## Merchant direction

CEO confirmed **KOMOJU** as Ruby's intended payment merchant.

For the current architecture, the preferred integration boundary is the official KOMOJU WooCommerce plugin/account-sign-in flow rather than placing raw merchant credentials in Phil AI OS. Test-mode connection and any later live activation remain separately governed steps.

## Delivered

- multi-item checkout-intent contract with duplicate-SKU and quantity validation;
- deterministic cart pricing and JPY total composition;
- mixed-currency fail-closed behavior;
- inert KOMOJU provider profile with `connection_state=not_configured`;
- explicit `woocommerce_plugin` integration mode;
- non-authorizing payment-handoff intent contract;
- checkout/readiness identity matching before payment handoff preparation;
- readiness-GREEN requirement before a handoff can even be composed;
- `external_order_reference=null` while no WooCommerce order exists;
- hard-false order-creation, payment-execution and live-mode authority flags;
- KOMOJU/WooCommerce secret-pattern scans in the CX validator;
- offline cache coverage for the new cart/payment modules and provider fixture;
- CI assertion marker for the inert payment boundary.

## Validation

GitHub Actions pull-request run `33168460947` validated head `d2ef9126af5679ce22cd2a4db208673493e810b9`:

- JavaScript syntax: GREEN;
- **36/36 unit tests: GREEN**;
- CX fixture/PWA/accessibility/safety validation: GREEN;
- payment handoff contract: GREEN;
- loopback HTTP preview startup: GREEN;
- catalog/pickup/KOMOJU-provider/service-worker smoke: GREEN;
- teardown: GREEN.

Validation markers:

- `PHIL_AI_OS_SPRINT_4_CX_VALIDATION_GREEN`
- `PHIL_AI_OS_SPRINT_4_PAYMENT_HANDOFF_CONTRACT_GREEN`

## Payment authority boundary

This slice does **not**:

- connect a KOMOJU account;
- contain a KOMOJU account identifier, API key, secret, webhook token or live credential;
- enable KOMOJU Test Mode or Live Mode;
- create a WooCommerce order;
- execute or capture a payment;
- configure a production webhook;
- create payment authority inside Phil AI OS.

The prepared handoff is only an architecture/customer-flow intent. WooCommerce remains the intended order system and KOMOJU remains the intended payment provider through its WooCommerce integration.

## Later governed activation sequence

1. WooCommerce production/staging site readiness is separately approved.
2. Install/verify the official KOMOJU WooCommerce plugin.
3. Connect the merchant account through the plugin's account-sign-in flow.
4. Use KOMOJU Test Mode first and validate checkout/order/payment-status behavior.
5. Review rollback, security and operational evidence.
6. Obtain explicit CEO approval before Live Mode/payment production activation.

No raw KOMOJU credentials are required for the current Sprint 4 work.

`PHIL_AI_OS_SPRINT_4_CUSTOMER_EXPERIENCE_SLICE_3_GREEN`
