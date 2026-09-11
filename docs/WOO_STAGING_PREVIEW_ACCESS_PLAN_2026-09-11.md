# Ruby's Cake Delights — Private WooCommerce Staging Preview Access Plan

**Date:** 2026-09-11  
**Status:** PREPARATION / NON-PRODUCTION  
**Production cutover authorized:** NO  
**DNS/domain switch authorized:** NO  

## Objective

Provide the owner with a browser-accessible preview of the in-progress WordPress/WooCommerce site without publishing the production storefront or expanding production authority.

## Preferred Hostinger path

Use Hostinger's native WordPress staging feature when available on the current hosting plan:

1. hPanel → Websites → Ruby's Cake Delights → Dashboard.
2. WordPress → Staging.
3. Create a staging environment using a dedicated preview subdomain/name.
4. Do **not** select Publish for staging.
5. Protect the staging directory/site with Hostinger Password Protect Directories.
6. Keep WordPress search-engine visibility discouraged and verify `noindex`/crawler blocking.
7. Browse and QA the staging URL from desktop and mobile only after the privacy gate is verified.

Hostinger's staging environment is a separate testing copy. Publishing staging is an explicit later action and is not authorized by this plan.

## Proposed preview identity

Preferred human-readable target if Hostinger permits it without production-domain cutover:

`staging.rubyscakedelights.shop`

This string is a target only. It must not be treated as live until Hostinger reports the staging environment created and the privacy checks pass.

If the active DNS is external and Hostinger requires a staging A record, that DNS mutation remains a separate owner-authority gate. Do not create it automatically under this plan.

## Required privacy gates before owner browsing

- staging is not the production hostname;
- unauthenticated HTTP access is rejected by password protection (expected 401/403 or equivalent access gate);
- authenticated browsing succeeds;
- staging is excluded from search indexing (`noindex` or equivalent crawler blocking);
- staging does not publish or replace the production WordPress database/files;
- staging does not execute live KOMOJU charges;
- staging does not send unrestricted SMS;
- staging does not mutate production WooCommerce catalog/inventory;
- no production DNS/domain cutover occurs.

## GitHub readiness workflow

`.github/workflows/commerce-woocommerce-staging-preview-readonly-check.yml` provides a manual, read-only verification once the staging URL and preview credentials are stored as GitHub Actions secrets:

- `RUBY_WOO_STAGING_BASE_URL`
- `RUBY_WOO_STAGING_PREVIEW_USER`
- `RUBY_WOO_STAGING_PREVIEW_PASSWORD`

The workflow does not create staging, edit DNS, mutate WordPress/WooCommerce, or publish anything. It only checks the privacy/access boundary and crawler-blocking evidence.

## Owner-visible next action

The only external step that cannot currently be completed through the connected tooling is creation of the WordPress staging environment inside Hostinger hPanel. Once created, the staging URL can be registered in GitHub Actions and the read-only privacy check can be run before the URL is used for design review.
