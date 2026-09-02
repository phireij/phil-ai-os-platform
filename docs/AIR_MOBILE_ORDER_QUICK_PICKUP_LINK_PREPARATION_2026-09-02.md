# Air Mobile Order Quick Pickup — Link Surface Preparation

**Date:** 2026-09-02  
**Scope:** Ruby's Cake Delights customer experience  
**Status:** PREPARED / PRODUCTION URL PENDING / PUBLICATION NOT AUTHORIZED

## Purpose

Prepare a bounded customer-facing link surface for **Air Mobile Order Quick Pickup** without inventing, discovering by assumption, or publishing a production URL.

## Channel roles

- **Air Mobile Order Quick Pickup:** intended quick-pickup path.
- **WooCommerce:** remains the advance-order and Yamato delivery platform.

The two paths must remain clearly distinguished so customers are not silently redirected between order systems.

## Prepared customer labels

- English: **Quick Pickup**
- Japanese: **クイック受取**

Candidate placements after later URL approval:

1. storefront home;
2. pickup-information surface;
3. checkout/order-choice surface where the difference between Quick Pickup and advance WooCommerce ordering is explicit.

## Fail-closed rules

Until the owner-approved production URL is supplied:

- `production_url=null`;
- link rendering remains disabled;
- no automatic redirect;
- no tracking parameters;
- no production publication;
- no WooCommerce mutation or integration authority;
- no Air Mobile Order credential or API integration is required for this link-only surface.

## Later acceptance gate

Before publication:

1. receive the exact production Quick Pickup URL from an owner-approved source;
2. verify HTTPS and intended destination;
3. confirm the customer-visible EN/JA wording and placement;
4. verify mobile navigation and return path;
5. verify no unintended WooCommerce cart/order state is transferred;
6. obtain the applicable pre-production/publication approval.

Machine-readable template: `contracts/cx/air-mobile-order-quick-pickup.template.json`.

**This preparation creates no live link and no production authority.**
