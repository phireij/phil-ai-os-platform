# Sprint 7 — KOMOJU Activation Runbook

Date: 2026-08-28
Status: PREPARATION ONLY / TEST MODE AND LIVE MODE NOT AUTHORIZED

## Current contract baseline

- payment provider: `komoju`;
- integration mode: `woocommerce_plugin`;
- current connection state: `not_configured`;
- order creation authority: false;
- payment execution authority: false;
- live mode authority: false.

## Intended architecture

Customer CX → WooCommerce order/checkout boundary → KOMOJU WooCommerce integration.

Phil AI OS may prepare and observe governed payment-handoff intent. This architecture does not give Phil AI OS direct payment authority.

## Preconditions before any KOMOJU configuration

- [ ] WooCommerce staging environment is ready;
- [ ] checkout and pickup flow is GREEN without live payment execution;
- [ ] secret-handling requirements are accepted;
- [ ] rollback/disable procedure exists;
- [ ] merchant/account access is available to the authorized operator;
- [ ] integration scope is approved;
- [ ] no Live Mode credential or capability is introduced during Test Mode preparation.

## Test Mode sequence

Only after a separate approval to configure Test Mode:

1. install/enable the supported KOMOJU WooCommerce integration in staging or the specifically approved non-live environment;
2. connect only the Test Mode account/configuration;
3. verify checkout renders the intended payment options without real-charge authority;
4. run controlled test transactions;
5. verify WooCommerce order-state transitions and KOMOJU test-state correlation;
6. verify duplicate/retry/callback behavior does not create duplicate order/payment effects;
7. verify failed/cancelled test payments produce the expected non-paid order state;
8. verify logs/audit records contain identifiers/statuses but no secret material;
9. document disable/recovery steps;
10. record Test Mode evidence before proposing Live Mode.

## Live Mode gate

KOMOJU Live Mode is a separate production authorization boundary. Do not enable it unless all of the following are complete:

- Test Mode evidence GREEN;
- production WooCommerce storefront/cutover readiness GREEN;
- merchant production account verified;
- production secret storage approved;
- charge/refund/reconciliation ownership defined;
- customer-facing payment/policy information reviewed;
- rollback/disable path tested or otherwise verified;
- explicit CEO approval recorded for Live Mode.

## First Live Mode principle

If later authorized, the first real-payment verification must be narrow, observable and reversible where possible. Confirm order/payment correlation immediately and stop if any state differs from the approved expected flow.

## Abort criteria

Stop configuration or disable the payment method if:

- authentication or callback verification fails;
- a payment/order state cannot be reconciled;
- duplicate charge/order behavior appears;
- secrets are exposed in logs or configuration surfaces;
- the integration enters Live Mode unexpectedly;
- customer-facing checkout is materially degraded;
- the operator lacks a clear disable/recovery path.

## Explicit non-authorization

This runbook does not authorize KOMOJU Test Mode connection, Live Mode connection, real charges, refunds, payment execution, WooCommerce production order creation, production credentials, or broader Phil AI OS authority.

`PHIL_AI_OS_SPRINT_7_KOMOJU_RUNBOOK_READY_NOT_AUTHORIZED`
