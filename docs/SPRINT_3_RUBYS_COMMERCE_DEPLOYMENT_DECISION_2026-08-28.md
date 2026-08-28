# Sprint 3 — Ruby's Cake Delights Commerce Deployment Decision

**Date:** 2026-08-28  
**Status:** APPROVED ARCHITECTURE / IMPLEMENTATION PREPARATION  
**Authority effect:** none beyond the bounded Sprint 3 foundation

## Decision

Ruby's Cake Delights will keep its public customer-facing commerce site on **Hostinger managed web hosting**, while the **Phil AI OS Platform remains on the Hostinger VPS**.

The public customer domain remains:

- `https://www.rubyscakedelights.shop/`

The current site was created with the Hostinger website-building system and is not treated as the future commerce runtime. The future production storefront target is WordPress + WooCommerce on Hostinger managed web hosting using the same public domain.

Phil AI OS will integrate with WooCommerce across an explicit HTTPS API/webhook boundary only after the separate production activation gate.

## Deployment boundary

### Hostinger managed web hosting

Customer-facing production commerce:

- WordPress
- WooCommerce
- public pages and storefront
- products and categories
- product media
- cart and checkout
- orders
- customer accounts
- payment-provider integration
- production inventory projection

### Hostinger VPS

Phil AI OS control and intelligence:

- Control API
- WooCommerce adapter
- Mission Control
- Hermes / agents
- CX interfaces
- Operations interfaces
- reconciliation and audit
- approvals and automation

### Isolated development environment

The Sprint 3 Docker WordPress/WooCommerce environment remains **development/test only**. It is not the Ruby's production web server.

## Existing Hostinger-builder site migration rule

The current site is a **reference source**, not the commerce source of truth.

Eligible for controlled copy/review:

1. store information
2. contact information
3. policies

Explicitly excluded from migration:

- current test products
- current test product categories

All copied values must be verified before publication. Existing values are not silently authoritative. Contact details are especially subject to verification because the phone number is known to require updating.

## Source-of-truth rule

For the future WooCommerce implementation:

- new product/catalog data will be created from verified Ruby's business data, not copied from the existing test catalog;
- category design will be created for the production store rather than inherited from the current test site;
- store information, contact information, and policies may be migrated only after field-level verification;
- public-domain continuity does not imply runtime API authority.

## Cutover principles

The eventual production cutover should use a staging-first workflow with backup/rollback, SSL verification, checkout QA, policy review, and controlled DNS/domain transition where required by Hostinger. The customer-facing domain should remain unchanged.

## Explicit non-authorization

This decision does **not** authorize:

- production WooCommerce consumer credentials;
- production WooCommerce API base configuration in runtime code;
- live WooCommerce connectivity;
- live product/order/inventory mutations;
- payment-provider activation;
- DNS or production-site changes;
- a new production integration identity;
- specialist enablement or a new execution task class;
- higher autonomy or automatic production action;
- Mission Control mutation authority.

Those remain separately gated.

## Architecture North Star

The split preserves the Mission Control V1 goal: **one browser, one place to operate**, while keeping the customer storefront failure domain separate from Phil AI OS development and agent operations.
