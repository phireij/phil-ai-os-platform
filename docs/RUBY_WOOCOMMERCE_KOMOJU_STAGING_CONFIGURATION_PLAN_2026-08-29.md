# Ruby's Cake Delights — WooCommerce + KOMOJU Staging Configuration Plan

Date: 2026-08-29  
Status: **READY FOR STAGING PREPARATION / NO PUBLIC CUTOVER / NO PAYMENT ACTIVATION AUTHORIZED**

## 1. Objective

Build and validate Ruby's replacement WordPress + WooCommerce storefront on Hostinger managed web hosting without changing the public Ruby domain and without enabling real payment authority.

The current public Hostinger Website Builder site remains the customer-facing production site until an explicit later cutover approval.

## 2. Prerequisites already complete

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

## 3. Current fulfillment baseline

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

These values are **legacy disclosure evidence**, not automatically approved WooCommerce shipping-zone configuration. Staging must verify whether the rates/service remain current and whether WooCommerce can represent them accurately before publication.

## 4. WooCommerce staging build sequence

### Stage A — hosting and platform

1. Create a Hostinger managed WordPress staging/non-public site.
2. Confirm it is not attached to the public Ruby production domain.
3. Install/update WordPress and WooCommerce using supported Hostinger/WordPress mechanisms.
4. Confirm HTTPS/SSL on staging.
5. Confirm admin access and WooCommerce health.
6. Record WordPress/WooCommerce versions and essential plugins.

### Stage B — controlled business content

1. Load verified business name, description, address, phone, email and social links.
2. Load approved Privacy Policy, Terms, Cancellation/Refund, Pickup/Order and Allergen content.
3. Load the reconciled Tokushoho draft as staging-only content.
4. Do not publish the Tokushoho page as final until payment/shipping/checkout values are synchronized and CEO approval is recorded.
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

## 5. KOMOJU staging preparation

### Official current integration model

Current KOMOJU documentation checked 2026-08-29 describes the WooCommerce flow as:

- install the **KOMOJU Payments** plugin;
- navigate to `WooCommerce → Settings → KOMOJU`;
- use **Sign into KOMOJU**;
- select the merchant account and **Test Mode** or **Live Mode**;
- enable payment methods individually;
- the sign-in flow automatically configures the secret key and webhooks.

Normal staging preparation therefore does not require manually collecting/pasting a KOMOJU API key.

Reference: `https://doc.komoju.com/docs/getting-started-with-woocommerce`

### Current authority boundary

The following remain false:

- KOMOJU Test Mode connection authorized: **false**;
- KOMOJU Test Mode connected: **false**;
- KOMOJU Live Mode authorized: **false**;
- payment execution authorized: **false**.

Installing the plugin in staging may be prepared as part of the technical build, but signing into the merchant account / connecting Test Mode is a separate controlled gate.

## 6. Payment-method reconciliation

The legacy Ruby legal page disclosed:

- Visa;
- Mastercard;
- JCB;
- American Express;
- Diners Club.

KOMOJU currently supports many Japan payment types globally. **Do not infer that every globally supported method is approved for Ruby.** KOMOJU states that merchants may only use payment methods approved for their account.

During the authorized Test Mode session:

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

## 7. Test Mode evidence required

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

## 8. Legal/checkout synchronization gate

Before Tokushoho publication approval, confirm the production candidate matches actual staging/approved launch configuration for:

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

## 9. Staging acceptance checklist

- [ ] Hostinger WordPress staging exists and is non-public.
- [ ] WordPress/WooCommerce healthy.
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

## 10. Next executable gate

**Create the Hostinger WordPress/WooCommerce staging environment without public-domain cutover or live-payment activation.**

Once staging exists, populate verified business/legal content, configure/test pickup and shipping, then seek separate authorization to connect KOMOJU Test Mode.

## 11. Explicit non-authorization

This plan does not authorize public site/DNS changes, production publication, KOMOJU Test Mode sign-in, KOMOJU Live Mode, real charges/refunds, production WooCommerce API mutation, or broader Phil AI OS authority.

`PHIL_AI_OS_RUBY_WOOCOMMERCE_KOMOJU_STAGING_PLAN_READY_NEXT_GATE_CREATE_STAGING`
