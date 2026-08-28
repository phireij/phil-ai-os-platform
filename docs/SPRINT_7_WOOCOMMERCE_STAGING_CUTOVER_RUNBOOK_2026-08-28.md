# Sprint 7 — Ruby WooCommerce Staging & Cutover Runbook

Date: 2026-08-28
Status: PREPARATION ONLY / CUTOVER NOT AUTHORIZED

## Architecture baseline

- Public customer domain remains `https://www.rubyscakedelights.shop/`.
- Future production storefront target: **WordPress + WooCommerce on Hostinger managed web hosting**.
- Phil AI OS remains on the **separate Hostinger VPS** as the control/intelligence plane.
- The current Hostinger Website Builder site is a **reference source only**, not the future commerce source of truth.

## Migration scope

Eligible for controlled field-by-field review and migration:

1. store information;
2. contact information;
3. policies.

Explicitly excluded:

- existing test products;
- existing test categories.

Every copied field must be verified before publication. The contact phone number is specifically unresolved and must not be published from the old site without verification.

## Preconditions before staging build

- [ ] Sprint 7 integrated regression GREEN;
- [ ] Sprint 7 security/recovery readiness GREEN;
- [ ] fresh backup/restore verification available for the control plane near cutover;
- [ ] Hostinger managed WordPress/WooCommerce staging target identified;
- [ ] verified Ruby Business Profile completed for store/contact/policy fields;
- [ ] phone number verified;
- [ ] production product/category source data approved independently of the old test catalog;
- [ ] secret-handling and rollback/abort plans accepted;
- [ ] no production WooCommerce credentials introduced yet unless separately authorized.

## Staging procedure

1. Create or prepare a WordPress + WooCommerce staging environment on Hostinger managed web hosting.
2. Confirm staging is not serving the public production domain to customers.
3. Apply WordPress/WooCommerce baseline configuration and required security/update settings.
4. Populate only verified store/contact/policy information from the controlled business profile.
5. Create the production category hierarchy from approved Ruby business data; do not import the existing test categories.
6. Create approved product records/media from verified Ruby product data; do not import the old test catalog.
7. Configure pickup/customer-flow requirements and bilingual fields where required.
8. Verify SSL/TLS and HTTPS behavior on staging.
9. Run storefront, cart, checkout-intent, pickup, bilingual, accessibility and mobile QA.
10. Validate WooCommerce API identity/reconciliation behavior in a non-production or separately approved staging context before any live production connection.
11. Configure KOMOJU only according to the separate KOMOJU runbook; Test Mode precedes any later Live Mode gate.
12. Record defects, blockers and acceptance evidence before proposing cutover.

## Cutover gate

Public-site/DNS/domain cutover must not begin until:

- all critical staging tests are GREEN;
- verified business data is complete;
- backup/rollback readiness is GREEN;
- production secret handling is approved;
- KOMOJU disposition for launch is explicitly decided;
- customer-facing policies are reviewed;
- the rollback path is understood and available;
- explicit CEO authorization is recorded for the production cutover scope.

## Controlled cutover sequence

Only after approval:

1. create/verify the final pre-cutover backup/snapshot or Hostinger-supported equivalent;
2. freeze avoidable storefront changes during the cutover window;
3. confirm SSL certificate/domain readiness;
4. perform the minimum Hostinger domain/site transition required to make the WooCommerce storefront public while retaining the same customer domain;
5. verify homepage/product/cart/checkout/pickup/policy/contact flows;
6. verify no old test products/categories are exposed;
7. verify monitoring and customer-impact signals;
8. keep production WooCommerce API writes disabled unless their separate activation gate is approved;
9. record launch evidence and operator sign-off.

## Abort / rollback

Abort if health, SSL, checkout, verified content, data integrity, customer-facing behavior or rollback readiness is uncertain.

Fallback must return the public storefront to the last known-good customer-facing state using the approved Hostinger/site/domain recovery path. Do not improvise a production DNS or site mutation outside the approved cutover scope.

## Explicit non-authorization

This runbook does not authorize DNS/site changes, production WooCommerce credentials, live API connectivity, live mutations, KOMOJU Live Mode, specialist activation, higher autonomy or Mission Control write authority.

`PHIL_AI_OS_SPRINT_7_WOOCOMMERCE_CUTOVER_RUNBOOK_READY_NOT_AUTHORIZED`
