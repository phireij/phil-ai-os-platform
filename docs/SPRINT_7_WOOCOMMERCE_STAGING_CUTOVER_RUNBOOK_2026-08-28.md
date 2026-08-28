# Sprint 7 — Ruby WooCommerce Pre-Production & Cutover Runbook

Date: 2026-08-29
Status: PREPARATION ONLY / PARALLEL WORDPRESS PRE-PRODUCTION NEXT / CUTOVER NOT AUTHORIZED

## Architecture baseline

- Public customer domain remains `https://www.rubyscakedelights.shop/`.
- Current public storefront is **Hostinger Website Builder**.
- Future production storefront target: **WordPress + WooCommerce on Hostinger managed web hosting**.
- Phil AI OS remains on the **separate Hostinger VPS** as the control/intelligence plane.
- The current Website Builder site is a **reference source only**, not the future commerce source of truth.

## Hostinger environment rule

Current Hostinger guidance requires an existing WordPress installation to be detected before its native WordPress staging feature can be created, and the built-in staging feature requires an eligible hosting plan (Business web hosting or higher under the current guidance).

Because Ruby's current public site is Website Builder, the first WordPress environment must be a **parallel non-public WordPress/WooCommerce pre-production site**, not a direct native staging clone of the current public site.

The public domain must remain on the existing Website Builder site until explicit cutover authorization.

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

Therefore pre-production must support and test both intended fulfillment modes rather than assuming pickup-only operation. Legacy shipping rates are source evidence, not automatic production configuration: the actual WooCommerce shipping zones, fees, eligibility and tax treatment must be verified before launch.

## Preconditions before parallel WordPress build

- [x] Sprint 7 integrated regression baseline GREEN;
- [x] Sprint 7 security/recovery readiness package GREEN;
- [x] verified Ruby Business Profile completed;
- [x] phone number verified;
- [x] Tokushoho legacy source captured/reconciled;
- [ ] Hostinger managed WordPress hosting/site slot available for a separate non-public build;
- [ ] temporary domain/subdomain/non-production address selected without moving the Ruby public domain;
- [ ] approved production product/category source data available independently of the old test catalog;
- [ ] production shipping-zone/rate design verified against intended Yamato service;
- [ ] fresh backup/restore verification available near cutover;
- [ ] payment handling and rollback/abort plans accepted;
- [ ] no production WooCommerce/KOMOJU Live authority introduced.

## Parallel pre-production procedure

1. In Hostinger hPanel, create a **separate WordPress website** using the supported WordPress/CMS installation path.
2. Use a temporary domain/subdomain/non-production address and keep `rubyscakedelights.shop` attached to the existing Website Builder site.
3. Confirm WordPress is detected in Hostinger and record the hosting plan's native WordPress staging eligibility.
4. Install/activate WooCommerce.
5. Apply WordPress/WooCommerce baseline configuration and required security/update settings.
6. Populate only verified store/contact/policy information from the controlled Ruby Business Profile.
7. Add the reconciled Tokushoho working draft as **non-public pre-production content** for checkout/legal QA; do not treat it as publication-approved yet.
8. Create the production category hierarchy from separately approved Ruby business data; do not import the existing test categories.
9. Create approved product records/media from verified Ruby product data; do not import the old test catalog.
10. Configure store pickup and intended Yamato Cool delivery behavior.
11. Configure shipping zones/rates as a pre-production candidate, then reconcile them against the legacy disclosure and current business decision before publication.
12. Configure pickup/customer-flow requirements and bilingual fields where required.
13. Verify SSL/TLS and HTTPS behavior on the pre-production site.
14. Run storefront, product, cart, checkout-intent, pickup, shipping, bilingual, accessibility and mobile QA.
15. Validate WooCommerce API identity/reconciliation behavior in the non-production context before any live production connection.
16. Install/configure KOMOJU only according to the separate KOMOJU runbook. Test Mode precedes any later Live Mode gate.
17. After actual payment methods and payment timing are known, synchronize checkout wording and Tokushoho before seeking publication approval.
18. Record defects, blockers and acceptance evidence before proposing cutover.

## Native Hostinger WordPress staging after WordPress exists

After the parallel WordPress installation exists:

1. verify the Hostinger plan supports native WordPress staging;
2. if supported, use `Websites → Dashboard → WordPress → Staging` for WordPress-to-WordPress test copies as appropriate;
3. treat Hostinger's **Publish** action as a production-impacting action requiring the later cutover gate;
4. remember that publishing staging can replace live WordPress files/database, so it must never be used casually during the migration.

## Pre-production acceptance evidence

Pre-production can be marked GREEN only when all of the following are evidenced:

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
- KOMOJU disposition recorded for the pre-production scope;
- no production Live Mode/payment authority present.

## Cutover gate

Public-site/DNS/domain cutover must not begin until:

- all critical pre-production tests are GREEN;
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

This runbook does not authorize creating or purchasing a Hostinger hosting resource on the CEO's behalf, public DNS/site changes, production WooCommerce credentials, live API connectivity, live mutations, KOMOJU Test or Live Mode, real payments/refunds, specialist activation, higher autonomy or Mission Control write authority.

`PHIL_AI_OS_SPRINT_7_WOOCOMMERCE_CUTOVER_RUNBOOK_READY_NOT_AUTHORIZED`
