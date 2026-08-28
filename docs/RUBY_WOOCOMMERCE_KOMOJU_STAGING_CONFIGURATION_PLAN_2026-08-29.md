# Ruby's Cake Delights — WooCommerce + KOMOJU Pre-Production Configuration Plan

Date: 2026-08-29  
Status: **READY FOR PARALLEL PRE-PRODUCTION / NO PUBLIC CUTOVER / NO PAYMENT ACTIVATION AUTHORIZED**

## 1. Objective

Build and validate Ruby's replacement WordPress + WooCommerce storefront on Hostinger managed web hosting **in parallel with the existing Hostinger Website Builder site**, without changing the public Ruby domain and without enabling real payment authority.

The current public Hostinger Website Builder site remains the customer-facing production site until an explicit later cutover approval.

## 2. Hostinger environment model

Ruby's current public storefront is **Hostinger Website Builder**, not WordPress.

Current Hostinger guidance checked 2026-08-29 states that its native WordPress staging feature requires:

- an existing WordPress installation detected in hPanel; and
- a Business web-hosting plan or higher for the built-in staging feature.

Therefore the existing Website Builder site cannot be directly cloned into Hostinger's native WordPress staging feature as the first migration step.

### Correct first environment

Create a **separate non-public WordPress + WooCommerce pre-production site** on Hostinger using a temporary domain/subdomain or another non-production address available in the hosting account. Do **not** point `rubyscakedelights.shop` to it yet.

Once WordPress exists, verify the hosting plan's native staging eligibility. If available, Hostinger's WordPress staging feature can then be used for subsequent WordPress-to-WordPress testing/publish cycles.

Hostinger references checked 2026-08-29:

- `https://www.hostinger.com/support/2458059-how-to-create-a-website-in-hostinger/`
- `https://www.hostinger.com/support/5720286-how-to-create-a-wordpress-staging-environment-in-hostinger/`

## 3. Prerequisites already complete

- Verified Ruby Business Profile: **15/15 resolved**.
- Current business phone: **050-1785-0575**.
- Privacy Policy: approved.
- Terms & Conditions: approved.
- Cancellation/Refund Policy: approved.
- Pickup/Order Policy: approved.
- Allergen Disclaimer: approved.
- Existing 特定商取引法 source: captured and reconciled.
- Tokushoho publication candidate uses current email `info@rubyscakedelights.shop` and current phone.
- Existing builder test products/categories remain excluded from production migration.

## 4. Current fulfillment baseline

### Store pickup

Verified current business model supports store pickup at:

〒272-0034 千葉県市川市市川1丁目26-15 花亀ビル1階B号

Current pickup hours: Wednesday–Saturday, 14:00–20:00.

**Recheck required around mid-September 2026** because the business owner expects operating-hour changes.

### Shipping

The legacy legal disclosure confirms Yamato Transport Cool TA-Q-BIN delivery with the following currently published legacy rates:

- Kanto: ¥1,350 flat;
- other regions: ¥1,500–¥1,800;
- actual charge may vary by order and destination and is shown at checkout.

These values are **legacy disclosure evidence**, not automatically approved WooCommerce shipping-zone configuration. Pre-production must verify whether the rates/service remain current and whether WooCommerce can represent them accurately before publication.

## 5. WooCommerce pre-production build sequence

### Stage A — create the parallel Hostinger WordPress site

In hPanel, the authorized account owner should create a new website using WordPress/CMS installation while keeping the existing Ruby Website Builder site untouched.

Target requirements:

1. separate/non-public address for the WordPress build;
2. no DNS/domain cutover for `rubyscakedelights.shop`;
3. WordPress installed and detected in Hostinger;
4. WooCommerce installed/activated;
5. HTTPS/SSL available;
6. WordPress admin access confirmed;
7. WordPress/WooCommerce versions and essential plugins recorded;
8. Hostinger plan/native-staging eligibility recorded after WordPress exists.

Current Hostinger navigation reference for creating a CMS site: `Websites → Dashboard → Auto Installer` / WordPress, depending on the current hPanel flow.

### Stage B — controlled business content

1. Load verified business name, description, address, phone, email and social links.
2. Load approved Privacy Policy, Terms, Cancellation/Refund, Pickup/Order and Allergen content.
3. Load the reconciled Tokushoho draft as pre-production-only content.
4. Do not treat the Tokushoho page as publication-approved until payment/shipping/checkout values are synchronized and CEO approval is recorded.
5. Do not migrate the old builder test products/categories.

### Stage C — production catalog source

Create categories/products only from separately approved Ruby source data. For each item require at minimum:

- product name;
- category;
- price and tax treatment;
- product description;
- pickup/shipping eligibility;
- preparation/lead time where applicable;
- inventory/availability rule;
- product image/media;
- allergen/ingredient information where applicable.

The September 13 meal rollout is a verified business fact but does not itself authorize product records, prices, SKUs or inventory.

### Stage D — fulfillment

Configure and test:

1. **Local/store pickup** at the verified Ichikawa location.
2. **Yamato Cool shipping** candidate configuration based on current business decision and carrier/rate verification.
3. Shipping zones and exclusions.
4. Shipping fees and tax behavior.
5. Pickup versus shipping eligibility per product.
6. Address/checkout validation.
7. Order totals and customer-visible fee disclosure.
8. Mid-September operating-hours update before launch if the schedule has changed.

## 6. KOMOJU pre-production preparation

### Official current integration model

Current KOMOJU documentation checked 2026-08-29 describes the WooCommerce flow as:

- install the **KOMOJU Payments** plugin;
- navigate to `WooCommerce → Settings → KOMOJU`;
- use **Sign into KOMOJU**;
- select the merchant account and **Test Mode** or **Live Mode**;
- enable payment methods individually;
- the sign-in flow automatically configures the secret key and webhooks.

Normal WooCommerce preparation therefore does not require manually collecting/pasting a KOMOJU API key.

Reference: `https://doc.komoju.com/docs/getting-started-with-woocommerce`

### Current authority boundary

The following remain false:

- KOMOJU Test Mode connection authorized: **false**;
- KOMOJU Test Mode connected: **false**;
- KOMOJU Live Mode authorized: **false**;
- payment execution authorized: **false**.

Installing the plugin can be prepared in the non-public WordPress environment, but signing into Ruby's merchant account / connecting Test Mode is a separate controlled gate.

## 7. Payment-method reconciliation

The legacy Ruby legal page disclosed:

- Visa;
- Mastercard;
- JCB;
- American Express;
- Diners Club.

KOMOJU currently supports many Japan payment types globally. **Do not infer that every globally supported method is approved for Ruby.** KOMOJU states that merchants may only use payment methods approved for their account.

During the separately authorized Test Mode session:

1. verify Ruby's merchant account;
2. review merchant-available/approved payment methods;
3. choose the intended storefront subset;
4. enable only those methods individually in WooCommerce;
5. do not use the deprecated legacy `Komoju` WooCommerce payment method;
6. record payment timing/customer flow for each enabled method;
7. update Tokushoho and checkout text to match exactly.

References checked 2026-08-29:

- `https://help.komoju.com/hc/en-us/articles/4747504478494-How-to-Check-the-Available-Payment-Methods-for-Your-Account`
- `https://doc.komoju.com/page/supported-payment-methods`

## 8. Test Mode evidence required

After separate Test Mode authorization:

- correct Ruby merchant account connected;
- mode visibly confirmed as Test Mode;
- intended payment methods only;
- successful test order/payment correlation;
- failed/cancelled payment handling;
- pending/async payment handling if an async method is enabled;
- webhook/order-state synchronization;
- duplicate/retry behavior safe;
- no secret material in logs;
- payment titles/descriptions acceptable;
- inline versus redirect behavior reviewed;
- disable/disconnect path documented;
- no real charge capability.

## 9. Legal/checkout synchronization gate

Before Tokushoho publication approval, confirm the production candidate matches actual pre-production/approved launch configuration for:

- tax-inclusive prices;
- additional customer charges;
- Yamato shipping rates/regions;
- store pickup terms;
- actual enabled KOMOJU payment methods;
- payment timing/deadlines;
- delivery/pickup timing;
- cancellation/refund rules;
- defect/damage reporting;
- final order-confirmation screen disclosures.

## 10. Pre-production acceptance checklist

- [ ] Parallel Hostinger WordPress site exists and is not serving the Ruby public domain.
- [ ] WordPress/WooCommerce healthy.
- [ ] Hostinger native WordPress staging eligibility recorded after WordPress exists.
- [ ] HTTPS/SSL GREEN.
- [ ] Verified business/contact/policy content loaded.
- [ ] Old test products/categories absent.
- [ ] Approved catalog data loaded.
- [ ] Pickup flow GREEN.
- [ ] Shipping zones/rates verified and GREEN.
- [ ] Cart totals/fees/tax GREEN.
- [ ] Mobile/bilingual/accessibility QA GREEN.
- [ ] KOMOJU plugin disposition recorded.
- [ ] If separately authorized, KOMOJU Test Mode evidence GREEN.
- [ ] Tokushoho synchronized with actual launch configuration.
- [ ] Fresh launch-time backup/restore evidence available near cutover.
- [ ] Public domain/DNS unchanged.
- [ ] KOMOJU Live Mode remains OFF.

## 11. Next executable gate

**Create the parallel Hostinger WordPress + WooCommerce pre-production site while leaving `rubyscakedelights.shop` on the existing Website Builder site.**

Once the WordPress environment exists, populate verified business/legal content, configure/test pickup and shipping, verify native staging eligibility, and then seek separate authorization to connect KOMOJU Test Mode.

## 12. Explicit non-authorization

This plan does not authorize public site/DNS changes, production publication, KOMOJU Test Mode sign-in, KOMOJU Live Mode, real charges/refunds, production WooCommerce API mutation, or broader Phil AI OS authority.

`PHIL_AI_OS_RUBY_WOOCOMMERCE_KOMOJU_PREPRODUCTION_PLAN_READY_NEXT_GATE_CREATE_PARALLEL_WORDPRESS`
