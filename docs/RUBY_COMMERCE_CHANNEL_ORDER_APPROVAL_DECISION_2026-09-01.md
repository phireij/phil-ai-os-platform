# Ruby's Cake Delights — Commerce Channel & Order Approval Decision

**Date:** 2026-09-01  
**Status:** CEO APPROVED DESIGN / PRE-PRODUCTION IMPLEMENTATION AUTHORIZED  
**Scope:** Ruby storefront channel separation, order-date approval, deferred card payment, SMS fallback, and Yamato COD design.

## 1. Approved commerce-channel split

CEO approved the following operating model for the current launch:

- **Airレジ + Airペイ + Air Mobile Order:** physical-store POS and **Quick Pickup / ready-stock pickup** channel.
- **WooCommerce:** Ruby's full e-commerce channel for advance orders, made-to-order/custom products, scheduled pickup, Yamato Cool delivery, and other workflows requiring Ruby confirmation.
- WooCommerce should prominently link customers to **Air Mobile Order** for ready-stock / quick store pickup rather than independently duplicating the same pickup inventory in both systems.
- Products that legitimately need Woo fulfillment (for example shippable frozen products) may also exist in WooCommerce, but inventory duplication must not be treated as synchronized until a safe integration is proven.

### Post-development research requirement

After the current Phil AI OS / Ruby storefront development is completed, investigate whether **Airレジ / Air Mobile Order inventory and order synchronization with WooCommerce can be automated safely**. Do not assume an API or synchronization capability until current Air service interfaces, terms, operational conflict handling, idempotency, reconciliation, and failure recovery are verified.

## 2. Approved WooCommerce order workflow

For advance/scheduled WooCommerce orders, card payment should **not** be captured immediately when the customer first requests an order date.

Approved flow:

1. Customer selects a preferred pickup/delivery date.
2. Customer submits an order request.
3. No credit-card charge is taken at request submission.
4. Ruby reviews product/date/capacity feasibility.
5. If accepted, Ruby approves the requested date/order.
6. For card-payment customers, WooCommerce generates the secure order-payment URL and sends the payment request.
7. The same payment request should be delivered through **email + SMS** so the process does not depend on the customer finding an email in Primary/Promotions/Spam.
8. The customer completes payment through **KOMOJU**.
9. Only after successful payment is the card order considered paid/confirmed for production.
10. If the requested date cannot be accepted, Ruby contacts the customer to propose an alternate date or cancel the request without requiring a refund because no card capture occurred.

Target lifecycle:

`Requested → Availability Review → Date Approved → Awaiting Payment → Paid → Preparing → Ready/Shipped → Completed`

For Yamato COD:

`Requested → Availability Review → Date Approved / COD Confirmed → Preparing → Shipped → Completed`

## 3. Notification design

For approved card orders:

- Email payment link: required.
- SMS payment link: required fallback channel.
- Customer mobile number: required for Woo advance-order workflow unless a later approved exception is introduced.
- Order-request confirmation page must clearly state that no payment has been taken yet and that Ruby will send a payment link after date/availability approval.
- Reminder/escalation logic should be implemented so approved-but-unpaid orders do not consume production capacity indefinitely.
- Exact reminder cadence and reservation expiry window remain configurable and must be finalized before production publication.

## 4. Yamato Cash on Delivery

Ruby has Yamato Cash on Delivery / 宅急便コレクト capability approved operationally.

WooCommerce should support COD as an alternative payment preference for eligible Yamato delivery orders.

COD design requirements:

- COD must be available only for eligible Yamato delivery methods, not store pickup unless separately approved.
- The customer-facing COD fee should use Yamato's current official tier rather than a flat historical ¥500 surcharge.
- The fee calculation must account for Yamato's rule that the collection amount includes the COD fee itself.
- COD amount/fee limits, eligible services, and exact current rates must be verified against current Yamato official material at implementation/launch QA.

## 5. Current pre-production evidence as of 2026-09-01

Verified manually in the temporary Hostinger WordPress/WooCommerce pre-production site:

- WordPress + WooCommerce + HTTPS operational.
- Store Pickup configured.
- Yamato Cool Frozen and Chilled configured.
- Shipping classes: Cool 60 / 80 / 100 / 120.
- Japan regional shipping zones tested with representative addresses.
- Unsupported Yamato Cool island zone added before Kanto matching.
- KOMOJU official WooCommerce integration connected in **Test Mode**.
- KOMOJU Credit Card test checkout completed successfully with 3DS.
- WooCommerce Order #41 captured ¥1,165 in KOMOJU Test Mode.
- Full ¥1,165 refund succeeded through WooCommerce → KOMOJU.
- Temporary QA product removed after shipping/payment QA.
- KOMOJU Live Mode remains unauthorized and disconnected from production use.

## 6. Customer-policy synchronization required

The current WordPress draft Privacy/Terms/Commerce Disclosure content was prepared before this deferred-payment decision and must be revised before publication so it does not state that card payment is always captured when the initial order request is placed.

Policy updates required before production publication:

- order request vs accepted order distinction;
- preferred date subject to Ruby confirmation;
- card payment requested only after approval;
- payment-link delivery by email and SMS;
- payment deadline/reservation expiry once finalized;
- Yamato COD payment option and COD fee schedule;
- Air Mobile Order quick-pickup channel disclosure/link where appropriate;
- shipping/date availability and unsupported-region behavior.

`production_publish_authorized: false`  
`komoju_live_authorized: false`  
`air_woo_inventory_sync_assumed: false`

`PHIL_AI_OS_RUBY_COMMERCE_CHANNEL_AND_ORDER_APPROVAL_DECISION_2026_09_01`
