# Sprint 7 — KOMOJU Activation Runbook

Date: 2026-08-29
Status: PREPARATION ONLY / TEST MODE AND LIVE MODE NOT AUTHORIZED

## Current contract baseline

- payment provider: `komoju`;
- integration mode: `woocommerce_plugin`;
- current connection state: `not_configured`;
- order creation authority: false;
- payment execution authority: false;
- live mode authority: false.

## Intended architecture

Customer CX → WooCommerce order/checkout boundary → official KOMOJU Payments WooCommerce integration.

Phil AI OS may prepare and observe governed payment-handoff intent. This architecture does not give Phil AI OS direct payment authority.

## Current official WooCommerce connection model

Current KOMOJU WooCommerce documentation describes the supported setup as:

1. install the **KOMOJU Payments** WooCommerce plugin;
2. open `WooCommerce → Settings → KOMOJU`;
3. choose **Sign into KOMOJU**;
4. select the merchant account and connection mode;
5. use **Test Mode** for test payments or **Live Mode** only when the merchant account has been approved;
6. enable each approved payment method individually in WooCommerce.

The documented sign-in flow automatically configures the KOMOJU secret key and webhooks. Therefore the normal WooCommerce staging plan should **not request or paste manual API keys** unless a later verified integration requirement specifically requires them.

KOMOJU also warns not to use the deprecated legacy `Komoju` payment method. The supported plugin/payment-method configuration should be used instead.

Official reference checked 2026-08-29: `https://doc.komoju.com/docs/getting-started-with-woocommerce`

## Payment-method truth rule

The legacy Ruby Tokushoho page disclosed these card brands:

- Visa;
- Mastercard;
- JCB;
- American Express;
- Diners Club.

This is useful legacy customer-facing evidence, but it does **not** prove which payment methods are currently approved on Ruby's KOMOJU merchant account.

Current KOMOJU guidance states that merchants may only use payment methods that have completed the applicable review/approval. Before finalizing checkout or Tokushoho, the authorized operator must verify the actual merchant-available methods in the KOMOJU dashboard and enable only the intended subset in WooCommerce.

Official references checked 2026-08-29:

- `https://help.komoju.com/hc/en-us/articles/4747504478494-How-to-Check-the-Available-Payment-Methods-for-Your-Account`
- `https://doc.komoju.com/page/supported-payment-methods`

## Preconditions before any KOMOJU configuration

- [ ] WooCommerce staging environment is ready;
- [ ] checkout, pickup and shipping flow are GREEN without live payment execution;
- [ ] rollback/disable procedure exists;
- [ ] merchant/account access is available to the authorized operator;
- [ ] Test Mode integration scope is explicitly approved;
- [ ] actual merchant-available payment methods have been reviewed or are ready to be reviewed during the authorized Test Mode session;
- [ ] no Live Mode capability is introduced during Test Mode preparation;
- [ ] Tokushoho payment/shipping fields remain marked pending final configuration sync.

## Test Mode sequence

Only after a separate approval to configure Test Mode:

1. install/enable the supported **KOMOJU Payments** WooCommerce plugin in staging;
2. open `WooCommerce → Settings → KOMOJU` and use **Sign into KOMOJU**;
3. select Ruby's authorized KOMOJU merchant account and choose **Test Mode**;
4. confirm the plugin connection is Test Mode and not Live Mode;
5. verify the payment methods available to the merchant account and record the intended staging subset;
6. enable each intended payment method individually; do not enable the deprecated legacy `Komoju` method;
7. verify checkout renders only the intended payment options without real-charge authority;
8. run controlled test transactions using KOMOJU test facilities;
9. verify WooCommerce order-state transitions and KOMOJU test-state correlation;
10. verify duplicate/retry/callback behavior does not create duplicate order/payment effects;
11. verify failed/cancelled test payments produce the expected non-paid order state;
12. verify logs/audit records contain identifiers/statuses but no exposed secret material;
13. verify payment titles/descriptions and inline/redirect behavior are acceptable for customer UX;
14. document disable/recovery steps;
15. record Test Mode evidence before proposing Live Mode;
16. synchronize actual payment methods/timing into Tokushoho and checkout/legal content before publication approval.

## Current official payment-method context

KOMOJU currently documents multiple Japan payment types, including credit cards, convenience-store payments, Pay-Easy, PayPay, Merpay, Rakuten Pay, Paidy, bank transfer and others. Availability for Ruby must **not** be inferred from the global support list; use the merchant account's approved methods as the production source of truth.

Official reference checked 2026-08-29: `https://doc.komoju.com/page/supported-payment-methods`

## Live Mode gate

KOMOJU Live Mode is a separate production authorization boundary. Do not enable it unless all of the following are complete:

- Test Mode evidence GREEN;
- production WooCommerce storefront/cutover readiness GREEN;
- merchant Live Mode approval verified in KOMOJU;
- intended production payment-method subset verified;
- charge/refund/reconciliation ownership defined;
- customer-facing payment methods/timing and Tokushoho synchronized;
- shipping/checkout totals and legal disclosure synchronized;
- rollback/disable path tested or otherwise verified;
- explicit CEO approval recorded for Live Mode.

## First Live Mode principle

If later authorized, the first real-payment verification must be narrow, observable and reversible where possible. Confirm WooCommerce order state, KOMOJU payment state, amount, currency and fulfillment record immediately and stop if any state differs from the approved expected flow.

## Abort criteria

Stop configuration or disable the payment method if:

- the sign-in connection selects the wrong merchant account or mode;
- authentication/webhook behavior fails;
- a payment/order state cannot be reconciled;
- duplicate charge/order behavior appears;
- secrets are exposed in logs or configuration surfaces;
- the integration enters Live Mode unexpectedly;
- an unapproved payment method appears to customers;
- customer-facing checkout is materially degraded;
- checkout payment/shipping/legal text becomes inconsistent;
- the operator lacks a clear disable/recovery path.

## Explicit non-authorization

This runbook does not authorize KOMOJU Test Mode connection, Live Mode connection, real charges, refunds, payment execution, WooCommerce production order creation, production cutover, or broader Phil AI OS authority.

`PHIL_AI_OS_SPRINT_7_KOMOJU_RUNBOOK_READY_NOT_AUTHORIZED`
