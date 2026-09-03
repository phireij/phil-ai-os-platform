# Sprint 7 — KOMOJU Activation Runbook

**Last reconciled:** 2026-09-03  
**Status:** **TEST MODE GREEN / LIVE SCOPE APPROVED / LIVE ACCEPTANCE PENDING FAIL-CLOSED**  
**Current executive position:** Sprint 3 remains current; this is future Sprint 7 payment-launch preparation.

## Current verified baseline

- payment provider: `komoju`;
- integration mode: `woocommerce_plugin` using the supported KOMOJU Payments WooCommerce plugin;
- WooCommerce pre-production environment: **GREEN**;
- current KOMOJU connection state: **Test Mode**;
- controlled Test Mode capture/refund: **GREEN**;
- order creation authority from Phil AI OS: false;
- real payment execution readiness: false;
- Live Mode readiness: false;
- CEO Live Mode **scope approval**: true;
- scope approval overrides readiness: false.

Customer CX → WooCommerce order/checkout boundary → official KOMOJU Payments WooCommerce integration.

Phil AI OS may prepare and observe governed payment-handoff intent. It does not receive direct payment authority from this architecture or from Test Mode success.

## Connection and secret handling

The supported WooCommerce connection uses the KOMOJU plugin sign-in/account-selection flow. The integration configures the required secret/webhook material through that supported flow.

Operational rules:

- do not ask the CEO to paste KOMOJU API secrets into chat or repository files;
- do not expose secrets in logs/readiness evidence;
- use only the intended Ruby merchant account and connection mode;
- do not use the deprecated legacy `Komoju` payment method;
- merchant/account-side availability is the production source of truth for payment methods.

## Test Mode — completed baseline

The following evidence is already GREEN in pre-production:

- [x] supported KOMOJU Payments plugin connected;
- [x] connection confirmed as **Test Mode**, not Live Mode;
- [x] checkout/payment handoff tested without real-charge authority;
- [x] controlled test capture completed successfully;
- [x] controlled test refund completed successfully;
- [x] WooCommerce payment/order-state behavior was observed successfully;
- [x] no Live Mode or real-payment authority was granted by the test;
- [x] Test Mode remains the safe current state.

Test Mode does **not** need to be repeated merely because this runbook was reconciled. Re-test only when a relevant plugin/configuration/payment-flow change makes fresh evidence necessary.

## Payment-method truth rule

Legacy Tokushoho/card-brand wording and KOMOJU's general list of supported payment methods are not sufficient to determine Ruby's production payment options.

Before Live activation, the authorized operator must verify in Ruby's actual merchant account:

1. whether the merchant is approved/eligible for Live Mode;
2. which payment methods are currently available/approved;
3. which exact subset Ruby wants enabled at launch;
4. that WooCommerce checkout exposes only that approved subset;
5. that Tokushoho/payment/shipping wording matches the actual launch configuration.

Do not infer merchant availability from KOMOJU's global supported-method documentation.

## Live Mode acceptance gate

CEO approval for the **scope** of KOMOJU Live Mode has already been recorded. It does not authorize activation until the readiness gate is GREEN.

Require all applicable items below before switching from Test Mode to Live Mode:

- [x] Test Mode capture/refund evidence GREEN;
- [x] WooCommerce pre-production baseline GREEN;
- [ ] final owner-approved production catalog ready and accepted;
- [ ] merchant Live Mode approval/eligibility verified in KOMOJU;
- [ ] merchant-available payment methods verified;
- [ ] exact production payment-method subset finalized;
- [ ] final checkout/Tokushoho/payment/shipping synchronization GREEN;
- [ ] charge/refund/reconciliation ownership confirmed;
- [ ] rollback/disable path verified for Live activation;
- [ ] fresh near-cutover recovery evidence GREEN when temporally required;
- [ ] `main` branch protection/repository ruleset GREEN before final public launch;
- [ ] final Go/No-Go and applicable sign-offs recorded.

Until those conditions are satisfied:

- current mode remains **Test Mode**;
- `real_payment_execution_ready=false`;
- no real customer charge/refund is authorized by readiness;
- no automatic Live activation or retry is allowed.

## First Live acceptance principle

After a future explicitly gated Live activation, the first real-payment acceptance must be narrow and observable. Verify immediately:

- intended merchant account;
- intended payment method;
- amount and JPY currency;
- WooCommerce order state;
- KOMOJU payment state;
- approval-before-payment behavior where applicable;
- customer-facing payment/legal wording;
- reconciliation/audit evidence.

Stop if any state differs from the accepted expected flow. Do not perform repeated real charges simply to diagnose an uncertain configuration.

## Abort / disable criteria

Stop Live activation or disable the affected payment method if:

- wrong merchant account or mode is selected;
- merchant Live eligibility cannot be verified;
- an unapproved payment method appears;
- authentication/webhook behavior fails;
- payment/order states cannot be reconciled;
- duplicate charge/order behavior appears;
- secrets are exposed;
- checkout/payment/shipping/Tokushoho wording becomes inconsistent;
- the operator lacks a clear disable/recovery path;
- any required launch/readiness gate regresses.

Return to the accepted safe state, preserve evidence, remediate, and re-enter through the appropriate gate. Do not broaden permissions or bypass readiness controls to recover.

## Explicit non-authorization

This runbook records Test Mode as already GREEN and Live **scope** as approved. It does not itself authorize Live Mode activation, real charges/refunds, production order creation, WooCommerce production mutation, SMS sending, DNS/public cutover, specialist activation, higher autonomy, automatic production execution, or Mission Control write authority.

`PHIL_AI_OS_SPRINT_7_KOMOJU_RUNBOOK_READY_NOT_AUTHORIZED`
