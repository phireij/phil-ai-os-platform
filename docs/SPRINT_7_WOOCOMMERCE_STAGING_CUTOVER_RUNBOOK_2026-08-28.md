# Sprint 7 — Ruby WooCommerce Staging & Cutover Runbook

Date: 2026-08-29
Status: PREPARATION ONLY / STAGING NEXT / CUTOVER NOT AUTHORIZED

## Architecture baseline

- Public customer domain remains `https://www.rubyscakedelights.shop/`.
- Future production storefront target: **WordPress + WooCommerce on Hostinger managed web hosting**.
- Phil AI OS remains on the **separate Hostinger VPS** as the control/intelligence plane.
- The current Hostinger Website Builder site is a **reference source only**, not the future commerce source of truth.

## Migration scope

Eligible for controlled migration:

1. verified store information;
2. verified contact information;
3. approved customer/legal policies.

Explicitly excluded:

- existing test products;
- existing test categories.

Current verified prerequisites:

- [x] Verified Ruby Business Profile complete — **15/15 resolved**;
- [x] business phone verified — **050-1785-0575**;
- [x] Privacy Policy and Terms approved;
- [x] Cancellation/Refund, Pickup/Order and Allergen policies approved;
- [x] existing 特定商取引法 disclosure source captured and reconciled into a working draft;
- [ ] final Tokushoho publication approval pending checkout/payment/shipping synchronization.

## Fulfillment baseline

The legacy disclosure confirms **Yamato Transport Cool TA-Q-BIN delivery** and legacy shipping rates:

- Kanto: ¥1,350 flat;
- other regions: ¥1,500–¥1,800, subject to order/destination variation.

The verified business profile also supports **store pickup**.

Therefore staging must support and test both intended fulfillment modes rather than assuming pickup-only operation. Legacy shipping rates are source evidence, not automatic production configuration: the actual WooCommerce shipping zones, fees, eligibility and tax treatment must be verified before launch.

## Preconditions before staging build

- [x] Sprint 7 integrated regression baseline GREEN;
- [x] Sprint 7 security/recovery readiness package GREEN;
- [x] verified Ruby Business Profile completed;
- [x] phone number verified;
- [x] Tokushoho legacy source captured/reconciled;
- [ ] Hostinger managed WordPress/WooCommerce staging target created/identified;
- [ ] approved production product/category source data available independently of the old test catalog;
- [ ] production shipping-zone/rate design verified against intended Yamato service;
- [ ] fresh backup/restore verification available near cutover;
- [ ] secret/payment handling and rollback/abort plans accepted;
- [ ] no production WooCommerce/KOMOJU Live authority introduced.

## Staging procedure

1. Create or prepare a WordPress + WooCommerce staging environment on Hostinger managed web hosting.
2. Confirm staging is not serving the public production domain to customers.
3. Apply WordPress/WooCommerce baseline configuration and required security/update settings.
4. Populate only verified store/contact/policy information from the controlled Ruby Business Profile.
5. Add the reconciled Tokushoho working draft as **non-public staging content** for checkout/legal QA; do not treat it as publication-approved yet.
6. Create the production category hierarchy from separately approved Ruby business data; do not import the existing test categories.
7. Create approved product records/media from verified Ruby product data; do not import the old test catalog.
8. Configure store pickup and intended Yamato Cool delivery behavior.
9. Configure shipping zones/rates as a staging candidate, then reconcile them against the legacy disclosure and current business decision before publication.
10. Configure pickup/customer-flow requirements and bilingual fields where required.
11. Verify SSL/TLS and HTTPS behavior on staging.
12. Run storefront, product, cart, checkout-intent, pickup, shipping, bilingual, accessibility and mobile QA.
13. Validate WooCommerce API identity/reconciliation behavior in the non-production staging context before any live production connection.
14. Install/configure KOMOJU only according to the separate KOMOJU runbook. Test Mode precedes any later Live Mode gate.
15. After actual payment methods and payment timing are known, synchronize checkout wording and Tokushoho before seeking publication approval.
16. Record defects, blockers and acceptance evidence before proposing cutover.

## Staging acceptance evidence

Staging can be marked GREEN only when all of the following are evidenced:

- WordPress/WooCommerce health and admin access;
- WooCommerce active;
- HTTPS/SSL valid;
- verified business/contact/legal data displayed correctly;
- no old test catalog exposed;
- approved product/category source loaded;
- store pickup works as intended;
- intended Yamato shipping zones/rates work as intended;
- cart/checkout totals correctly include applicable shipping/fees/tax;
- mobile/bilingual/accessibility smoke GREEN;
- KOMOJU disposition recorded for the staging scope;
- no production Live Mode/payment authority present.

## Cutover gate

Public-site/DNS/domain cutover must not begin until:

- all critical staging tests are GREEN;
- fresh backup/rollback readiness is GREEN;
- production shipping configuration/rates are verified;
- KOMOJU Test Mode evidence is GREEN if online payment is in launch scope;
- actual production payment methods/timing are synchronized with Tokushoho and checkout;
- Tokushoho publication wording is approved;
- customer-facing policies have passed implementation review;
- rollback path is understood and available;
- explicit CEO authorization is recorded for the production cutover scope.

## Controlled cutover sequence

Only after approval:

1. create/verify the final pre-cutover backup/snapshot or Hostinger-supported equivalent;
2. freeze avoidable storefront changes during the cutover window;
3. confirm SSL certificate/domain readiness;
4. perform the minimum Hostinger domain/site transition required to make the WooCommerce storefront public while retaining the same customer domain;
5. verify homepage/product/cart/checkout/pickup/shipping/policy/contact flows;
6. verify no old test products/categories are exposed;
7. verify monitoring and customer-impact signals;
8. keep production WooCommerce API writes and KOMOJU Live Mode disabled unless their separate activation gates are approved;
9. record launch evidence and operator sign-off.

## Abort / rollback

Abort if health, SSL, checkout, shipping totals, payment state, verified content, data integrity, customer-facing behavior or rollback readiness is uncertain.

Fallback must return the public storefront to the last known-good customer-facing state using the approved Hostinger/site/domain recovery path. Do not improvise a production DNS or site mutation outside the approved cutover scope.

## Explicit non-authorization

This runbook does not authorize staging creation if that action itself requires a separate account-side approval, DNS/site changes, production WooCommerce credentials, live API connectivity, live mutations, KOMOJU Test or Live Mode, real payments/refunds, specialist activation, higher autonomy or Mission Control write authority.

`PHIL_AI_OS_SPRINT_7_WOOCOMMERCE_CUTOVER_RUNBOOK_READY_NOT_AUTHORIZED`
