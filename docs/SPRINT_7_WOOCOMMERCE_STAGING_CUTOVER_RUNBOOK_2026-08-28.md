# Sprint 7 — Ruby WooCommerce Pre-Production & Cutover Runbook

**Last reconciled:** 2026-09-03  
**Status:** **PRE-PRODUCTION GREEN / CUTOVER PREPARATION ONLY / PUBLIC CUTOVER NOT READY**  
**Current executive position:** Sprint 3 remains current; this is future Sprint 7 cutover preparation.

## Architecture baseline

- Public customer domain remains `https://www.rubyscakedelights.shop/` on the current Hostinger Website Builder site.
- WooCommerce pre-production origin is `https://darkgreen-wallaby-680439.hostingersite.com/`.
- Future public storefront target is the prepared WordPress + WooCommerce environment after all launch gates are GREEN.
- Phil AI OS remains on the separate Hostinger VPS as the control/intelligence plane.
- The current Website Builder site is a reference source only, not the future commerce source of truth.

## Current verified pre-production state

- [x] Parallel WordPress/WooCommerce pre-production environment exists.
- [x] WordPress and WooCommerce are healthy.
- [x] HTTPS/SSL is verified.
- [x] WooCommerce `wc/v3` surface is available.
- [x] Ruby Business Profile is complete — **15/15 resolved**.
- [x] Business phone is verified — **050-1785-0575**.
- [x] Required bilingual policy/legal pages are prepared/published in pre-production.
- [x] Tokushoho source is reconciled; final checkout/payment/shipping synchronization remains pending.
- [x] Store pickup and Yamato Cool shipping configuration are verified in pre-production.
- [x] Approval-before-payment and Datery behavior are verified.
- [x] KOMOJU Test Mode capture/refund is GREEN.
- [x] WooCommerce production read-only identity/connectivity is GREEN.
- [x] 2026 Japan tax decision is GREEN — **exempt / not Qualified-Invoice registered / WooCommerce tax disabled**.
- [ ] Final owner-approved production catalog is pending.
- [ ] KOMOJU Live acceptance and production payment-method subset are pending.
- [ ] Fresh near-cutover recovery check is pending.
- [ ] Main branch protection/repository ruleset is pending.
- [ ] Final public cutover plan and final Go/No-Go are pending.

## Migration scope

Eligible for controlled migration/configuration only after the relevant mutation gate is GREEN:

1. verified store information;
2. verified contact information;
3. approved customer/legal policies;
4. final owner-approved production catalog and media;
5. verified fulfillment assignments.

Explicitly excluded:

- old Website Builder test products/categories as authoritative data;
- repository fixtures/synthetic products as production data;
- any unapproved media/source record.

## Fulfillment and tax baseline

Pre-production supports:

- store pickup;
- Yamato Cool chilled/frozen shipping using the verified zones/classes/rates;
- approval-before-payment flow;
- Datery preferred delivery/pickup date behavior.

For 2026 under the reviewed current facts, Ruby is treated as a consumption-tax-exempt business and is not Qualified-Invoice registered. **WooCommerce tax remains disabled.** Do not create 8%/10% tax-table configuration while this decision applies.

If Ruby's tax/Invoice status changes, stop and re-open the tax gate before changing WooCommerce tax configuration.

## Catalog loading gate

Before any production catalog write:

1. freeze the final owner-approved catalog package;
2. confirm every product has approved bilingual names/content, unique SKU, price, category, primary media and fulfillment assignment;
3. confirm old builder/test/fixture sources are excluded;
4. capture a fresh GET-only production WooCommerce catalog snapshot;
5. run the side-effect-free catalog reconciliation planner and review `create / update / noop` intentions;
6. verify current legal/checkout/recovery prerequisites required by the production mutation gate;
7. obtain/record the then-required bounded mutation authorization before executing any write.

Read-only identity/connectivity does **not** authorize this step.

## KOMOJU gate

KOMOJU Test Mode is already GREEN. Live Mode remains separate.

Before any real payment exposure:

- merchant Live eligibility must be verified;
- merchant-side available payment methods must be confirmed;
- the exact production payment-method subset must be finalized;
- checkout/payment timing and Tokushoho must be synchronized;
- the final Go/No-Go and other applicable launch gates must be GREEN.

Do not infer Live readiness from successful Test Mode capture/refund or CEO scope approval alone.

## Pre-production acceptance evidence

The existing pre-production baseline is GREEN for:

- WordPress/WooCommerce health;
- HTTPS/SSL;
- store/contact/policy baseline;
- no authoritative migration from old test catalog;
- store pickup and Yamato Cool shipping;
- approval-before-payment and Datery;
- mobile/bilingual/accessibility CX foundation;
- KOMOJU Test Mode;
- WooCommerce production read-only identity/connectivity;
- Japan 2026 exempt/tax-disabled decision.

The final production catalog remains the only Sprint 3 owner-input gate.

## Public cutover gate

Public-site/DNS/domain cutover must not begin until every applicable launch gate is explicitly GREEN, including:

- final approved production catalog loaded and accepted through the authorized mutation path;
- fresh launch-time backup/restore verification;
- final checkout/Tokushoho/payment/shipping synchronization;
- production payment-method verification;
- KOMOJU Live acceptance if online payments are in launch scope;
- SMS production acceptance if SMS is in launch scope;
- Air Mobile Order Quick Pickup production URL if that feature is in launch scope;
- approved branch-protection rule or repository ruleset on `main`;
- rollback/abort path confirmed;
- public cutover plan confirmed;
- final CEO Go/No-Go and CTO sign-off.

The resolved Japan tax decision remains GREEN unless new facts supersede it.

## Controlled cutover sequence

Only after final GO:

1. create/verify the final pre-cutover backup/snapshot or Hostinger-supported equivalent;
2. freeze avoidable storefront/catalog changes during the cutover window;
3. confirm final approved catalog/version and current WooCommerce production state;
4. confirm SSL certificate/domain readiness;
5. verify production storefront, inventory, shipping/pickup and approval-before-payment behavior before DNS exposure;
6. verify only the approved payment/SMS integrations that are in launch scope;
7. perform the minimum Hostinger domain/DNS/site transition required to make the accepted WooCommerce storefront public while retaining the customer domain;
8. verify homepage/product/cart/checkout/pickup/shipping/policy/contact/payment flows;
9. verify no old test products/categories are exposed;
10. verify monitoring and customer-impact signals;
11. record launch evidence and operator sign-off.

**DNS/public cutover is last.** Do not use DNS as a way to test an unaccepted production storefront.

## Abort / rollback

Abort if health, SSL, checkout, shipping totals, payment state, verified content, data integrity, customer-facing behavior, repository protection, authority boundaries or rollback readiness is uncertain.

Fallback must return the public storefront to the last known-good customer-facing state using the approved Hostinger/site/domain recovery path. Do not improvise a production DNS/site mutation, expand permissions, repeatedly charge/test customers, or enable automatic customer-message retries to recover from an incident.

## Explicit non-authorization

This runbook does not authorize public DNS/site changes, production WooCommerce mutation, KOMOJU Live Mode, real payments/refunds, live SMS sending, specialist activation, higher autonomy, automatic production execution or Mission Control write authority. CEO scope approval is already recorded but remains subordinate to readiness gates.

`PHIL_AI_OS_SPRINT_7_WOOCOMMERCE_CUTOVER_RUNBOOK_READY_NOT_AUTHORIZED`
