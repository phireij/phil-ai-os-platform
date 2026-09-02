# Ruby WordPress/WooCommerce Pre-Production QA Milestone — 2026-09-02

**Program:** Phil AI OS Platform  
**Scope:** Ruby's Cake Delights operational pilot  
**Environment:** `https://darkgreen-wallaby-680439.hostingersite.com/`  
**Classification:** **PRE-PRODUCTION / A0 / LIVE CUTOVER NOT AUTHORIZED**

## Executive status

The separate Hostinger WordPress + WooCommerce environment now exists and has passed the bounded account-side configuration work performed to date. The existing public Hostinger Website Builder storefront at `rubyscakedelights.shop` remains outside this pre-production environment and no public cutover was authorized.

## Verified platform state

- WordPress **7.1**.
- WooCommerce **11.0.1** active.
- KOMOJU Japanese Payments **3.3.1** active.
- SG Order Approval for WooCommerce **2.2.1** active.
- Datery Delivery Date for WooCommerce **1.0.1** active.
- WP Mail SMTP **4.9.0** active.
- Store identity corrected to **Ruby's Cake Delights**.
- Store timezone corrected and verified as **Asia/Tokyo**.
- Currency verified as **JPY**.
- WooCommerce tax engine remains disabled pending separate Japan tax configuration review; this does not alter the CEO-confirmed business rule that catalog prices are intended to be tax-inclusive.

## Shipping and pickup

Verified shipping classes:

- `cool-60`
- `cool-80`
- `cool-100`
- `cool-120`

Verified Yamato Cool zones are present for:

- Chiba;
- Kanto excluding Chiba;
- South Tohoku + Shinetsu + Hokuriku + Chubu;
- North Tohoku + Kansai;
- Chugoku + Shikoku;
- Hokkaido + Kyushu;
- Okinawa;
- unsupported-islands handling.

Both customer-facing **Frozen / 冷凍** and **Chilled / 冷蔵** methods are present in the supported shipping zones. Prior checkout QA verified the class-based charge behavior and the corrected size-120 rates. Store pickup was also verified separately as a free customer option.

## Approval-before-payment flow

The current customer workflow is:

`Order submitted → Waiting for approval → Ruby confirms requested date → Pending payment → payment link issued → customer pays`

SG Order Approval is configured with:

- gateway enabled;
- title: **Submit Order for Confirmation / 注文確認を依頼**;
- inventory reduction on **order approval**, not on the initial request;
- customer messaging that no payment is taken before Ruby confirms the delivery/pickup request;
- approved-order messaging that payment links will be delivered by **email and SMS**.

A real isolated pre-production SG approval test confirmed the approved order becomes `pending`, `needs_payment=true`, and generates a WooCommerce order-payment URL.

## Delivery-date state

Datery is the active delivery-date plugin after the earlier Tyche Lite checkout conflict was isolated and Tyche was deactivated.

Persisted Datery settings verified on 2026-09-02:

- field label: **Preferred Delivery / Pickup Date / 希望配達・受取日**;
- required: **yes**;
- minimum lead: **2 days**;
- booking window: **30 days**;
- same-day cutoff: currently **blank**.

The old Tyche Lite option rows remain in the WordPress database but the plugin is inactive; these legacy rows are not the active delivery-date control surface.

## KOMOJU Test Mode

KOMOJU remains strictly pre-production/test-only.

Safe credential-prefix verification confirmed:

- secret key: `sk_test_*`;
- publishable key: `pk_test_*`;
- webhook secret: configured;
- `komoju_test_only=true`.

The legacy aggregate `komoju` gateway is disabled and the KOMOJU Credit Card gateway is enabled.

Prior controlled test transaction evidence already confirmed:

- test capture succeeded;
- WooCommerce order transitioned to Processing;
- refund succeeded;
- WooCommerce transitioned to Refunded;
- KOMOJU reflected Refunded.

**No `sk_live_*` or `pk_live_*` credential was activated. Live Mode remains prohibited without explicit CEO authorization.**

## Transactional email / SMTP

Authenticated SMTP is configured as:

- sender: **Ruby's Cake Delights <info@rubyscakedelights.shop>**;
- SPF: PASS;
- DKIM: PASS;
- DMARC: PASS.

End-to-end tests confirmed WordPress can send both a controlled diagnostic message and the actual SG approved-order payment-link email. Gmail classified both test messages as Spam despite authentication passing. Therefore email is retained but is not considered sufficient as the sole delivery channel for payment links.

## SMS payment-link fallback

PR #23 added and merged an A0-safe provider-neutral SMS payment-link scaffold to `main`:

- merged commit: `7026c0d84367bf13395f150454e70fec5a604337`;
- only approved `pending` payment-required orders are eligible;
- Japanese phone normalization;
- deterministic idempotency/duplicate suppression;
- payment URL redaction from general audit output;
- fail-closed provider errors;
- **no automatic retry**;
- default provider is disabled;
- no production SMS provider, credentials, sender identity or external send authority exists.

Production SMS activation remains a separate CEO gate.

## Legal/policy publication

The following approved bilingual/legal pages are now published in pre-production:

- **Privacy Policy / プライバシーポリシー**;
- **Terms & Conditions / 利用規約**;
- **特定商取引法に基づく表記 / Commerce Disclosure**;
- **Cancellation & Refund Policy / キャンセル・返金ポリシー**;
- **Pickup & Order Policy / 店頭受取・注文ポリシー**;
- **Allergen Information / アレルゲン情報**.

WordPress's privacy-page assignment is verified to point to the approved bilingual Privacy Policy page. The separate default WordPress draft titled only `Privacy Policy` was deliberately left untouched.

## Remaining blockers / next bounded work

1. Load only separately approved production catalog/category/media data; do not copy the old Website Builder test catalog.
2. Complete catalog/product-level shipping-class and chilled-eligibility assignment QA.
3. Review Japan tax display/calculation implementation while preserving the CEO-confirmed tax-inclusive price intent.
4. Prepare the **Air Mobile Order = Quick Pickup** link surface once its production URL is available; WooCommerce remains the advance-order/delivery platform.
5. Complete SMS provider comparison and keep live provider activation gated.
6. Perform fresh backup/restore and final legal/checkout synchronization near cutover.
7. Keep public-domain cutover, KOMOJU Live Mode/real payments, production SMS, production commerce writes, and higher autonomy under explicit CEO approval.

## Gate assessment

- Separate WordPress/WooCommerce environment: **GREEN**.
- Shipping foundation and prior shipping QA: **GREEN within pre-production scope**.
- Approval-before-payment flow: **GREEN**.
- Delivery-date checkout: **GREEN with current Datery rules documented**.
- KOMOJU Test Mode: **GREEN**.
- Test capture/refund: **GREEN**.
- SMTP authentication: **GREEN**.
- Email inbox placement: **NOT RELIABLE — SMS fallback required before production acceptance**.
- Legal/policy page publication: **GREEN**.
- SMS architecture/scaffold: **GREEN / external sending disabled**.
- Production cutover: **NOT AUTHORIZED**.
- KOMOJU Live Mode: **NOT AUTHORIZED**.

**Milestone classification: PRE-PRODUCTION CONFIGURATION GREEN / CATALOG + FINAL INTEGRATION QA NEXT / LIVE ACTIVATION GATED.**
