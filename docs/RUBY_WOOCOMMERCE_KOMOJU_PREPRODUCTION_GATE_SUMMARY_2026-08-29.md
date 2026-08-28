# Ruby WooCommerce + KOMOJU — Pre-Production Gate Summary

Date: 2026-08-29  
Status: **PREPARATION GREEN / ACCOUNT-SIDE WORDPRESS CREATION NEXT**

## Closed prerequisites

- Verified Ruby Business Profile: 15/15 resolved.
- Current phone: 050-1785-0575 verified.
- Customer policies approved.
- Tokushoho legacy source captured and reconciled.
- Current email/phone reflected in Tokushoho working draft.
- Existing builder test products/categories excluded.

## Corrected Hostinger migration model

The public Ruby storefront is Hostinger Website Builder. Hostinger's native WordPress staging function requires an existing WordPress installation and eligible plan, so the first migration environment is a **separate non-public WordPress + WooCommerce pre-production site**, not a clone of the builder site.

## Current KOMOJU integration model

Current official WooCommerce flow uses the KOMOJU Payments plugin and **Sign into KOMOJU** connection flow, which automatically configures secret/webhook information. Test Mode remains a separate authorization gate; Live Mode remains prohibited until later approval.

## Remaining gates after the parallel WordPress site exists

1. WordPress/WooCommerce health and HTTPS evidence.
2. Verified content migration.
3. Approved catalog creation without old test catalog migration.
4. Pickup and Yamato Cool shipping configuration/QA.
5. Shipping rates/taxes/checkout synchronization.
6. Separate KOMOJU Test Mode authorization and evidence.
7. Actual merchant payment-method verification.
8. Tokushoho final synchronization/publication approval.
9. Fresh recovery proof near cutover.
10. Explicit production cutover and Live Mode approvals.

`PHIL_AI_OS_RUBY_PREPRODUCTION_GATE_SUMMARY_GREEN_NEXT_ACCOUNT_STEP_WORDPRESS`
