# Ruby Final Catalog Owner Handoff — Operator Guide

Date: 2026-09-04
Status: READY FOR OWNER CATALOG INPUT — NO CATALOG OR PRODUCTION MUTATION AUTHORIZED

## Purpose

This guide is the single operator entry point for the remaining Sprint 3 owner-input gate: the final owner-approved Ruby's Cake Delights production catalog.

Sprint 3 remains the current primary sprint. The final owner-approved catalog is the only Sprint 3 owner-input closure gate. This guide does not replace any approval or grant any WooCommerce write authority.

## Controlled sequence

### 1. Complete the owner catalog package

Start from:

`commerce/woocommerce/fixtures/production-catalog-intake.template.json`

The completed package must contain the final owner-approved product list, category hierarchy, English/Japanese product copy and slugs, JPY pricing, fulfillment/shipping metadata, approved media references and provenance, timezone-aware source timestamps, and an explicit owner catalog approval reference.

Do not fabricate missing catalog content. Keep the template pending until the owner has supplied/finalized the real catalog.

### 2. Validate the owner package

Use:

`commerce/woocommerce/tools_validate_owner_catalog_package.py`

A GREEN result means only:

`ready_for_preproduction_configuration=true`

It does **not** authorize WooCommerce mutation or production publication.

The validator reconciles the package against the current verified tax/shipping/COD state and the existing catalog contract.

### 3. Obtain/read a WooCommerce catalog snapshot

The existing read-only snapshot capability is:

`commerce/woocommerce/tools_production_readonly_catalog_snapshot.py`

Snapshot contract:

- GET/read-only network behavior
- catalog metadata only
- `mutation_authorized=false`
- `production_publish_authorized=false`

A read-only snapshot does not authorize catalog changes.

### 4. Build the proposed preproduction change plan

Use:

`commerce/woocommerce/tools_plan_preproduction_catalog_changes.py`

Inputs:

1. validated owner catalog package
2. read-only WooCommerce catalog snapshot

The planner may classify category/product items only as:

- `create_candidate`
- `update_candidate`
- `noop`

Existing WooCommerce SKUs that are absent from the owner package are surfaced for review. They are **not** automatically deleted.

Media reconciliation remains review-required.

The planner performs no network calls and grants no write authority.

### 5. Validate that the plan is review-only

Use:

`commerce/woocommerce/tools_validate_preproduction_catalog_plan.py`

A GREEN result means only:

`accepted_for_human_review=true`

The acceptance validator rejects:

- delete/unknown actions
- automatic deletion
- mutation authority
- production publication authority
- media-review bypass
- network-execution drift

Even an accepted plan has:

- `execution_authorized=false`
- `mutation_authorized=false`
- `production_publish_authorized=false`

### 6. Separate approval gate before any catalog write

Do **not** convert the accepted dry-run plan into a WooCommerce mutation unless a separate explicit catalog-mutation approval has been granted under the current governance boundary.

This operator guide does not provide that approval.

### 7. Revalidate preproduction catalog availability

After any later separately authorized preproduction catalog configuration, first use the GET-only preproduction catalog probe:

`scripts/probe_ruby_preproduction_catalog.mjs`

The probe must remain read-only. Its purpose is only to confirm that a usable preproduction product exists before browser-based checkout QA begins.

### 8. Repeat guarded final-screen capture only after catalog availability

Guarded workflow:

`.github/workflows/ruby-preproduction-final-screen-capture.yml`

Do not rerun this while the GET-only preproduction probe still reports no purchasable product.

The guarded capture remains non-transactional:

- no Place order click
- no real order
- no KOMOJU payment execution
- no production publication
- sanitized evidence only

Actual final-screen evidence must still be reviewed against the existing static checklist before the actual-screen gate can become GREEN.

## Related owner gates that remain separate

The final catalog handoff does not itself approve:

- Tokushoho candidate text
- Tokushoho publication execution
- real KOMOJU payment execution
- Air Mobile Order Quick Pickup production-link activation
- production/public-domain cutover
- DNS changes
- Mission Control mutation authority
- automatic production execution
- higher autonomy

## Current fail-closed decision

`FINAL_CATALOG_OWNER_HANDOFF_PATH_READY_OWNER_CATALOG_PENDING_NO_MUTATION_AUTHORITY`
