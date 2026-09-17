# Ruby's Cake Delights — Hostinger Temporary-Domain CX Preview Runbook

**Date:** 2026-09-11  
**Status:** PRE-PRODUCTION / OWNER DESIGN REVIEW ONLY  
**Production publication authorized:** NO  
**DNS/domain switch authorized:** NO

## Purpose

Expose the current Phil AI OS customer-experience preview on the existing Hostinger temporary WordPress host without replacing the WordPress homepage and without enabling live commerce effects.

Observed owner preview host:

`darkgreen-wallaby-680439.hostingersite.com`

Target isolated path:

`/preview/`

Expected owner-visible URL after manual upload/extract:

`https://darkgreen-wallaby-680439.hostingersite.com/preview/`

This URL is a target path only until the preview bundle has actually been uploaded and verified.

## Bundle source

The repository builds `ruby-cx-hostinger-preview.zip` from `apps/customer-experience/` using:

`python apps/customer-experience/tools_build_hostinger_preview.py`

The bundle contains a top-level `preview/` directory. Every bundled HTML page is transformed to include:

- `noindex,nofollow,noarchive,nosnippet`;
- a visible `PRE-PRODUCTION PREVIEW` boundary banner;
- the existing local-only CX flows and synthetic fixtures;
- no production Ruby domain reference.

The builder refuses unapproved browser network calls. Only allowlisted bundled fixture reads are permitted, so the artifact remains fail-closed and cannot create an order, execute payment, reserve inventory/capacity, mutate WooCommerce, or publish production.

## GitHub artifact workflow

`.github/workflows/customer-experience-hostinger-preview-artifact.yml` builds and tests the ZIP. It does not deploy, SSH/SFTP, modify WordPress, change DNS, create orders, execute payment, send SMS, or mutate WooCommerce/inventory.

The artifact safety test must now prove that the deployable ZIP contains the first-party Quick Pickup route and its required local modules/fixtures, including:

- `preview/quick-pickup.html`;
- `preview/src/quick-pickup-route.js`;
- `preview/src/quick-pickup-route-copy.js`;
- `preview/src/quick-pickup-checkout-contract.js`;
- inventory, capacity, and operator-disable Quick Pickup modules;
- `first-party-quick-pickup.json` and the inventory/capacity/disable-control fixtures.

This artifact-level proof does **not** mean the files have been uploaded to Hostinger.

## Manual Hostinger upload boundary

Because the connected Hostinger integration does not expose WordPress File Manager/SFTP actions, the final file placement is an explicit owner/manual or controlled-browser step:

1. Hostinger hPanel → website Dashboard → Files → File Manager.
2. Open the document root used by the temporary WordPress site, normally `public_html`.
3. Do **not** overwrite `index.php`, `wp-config.php`, `wp-content`, or any existing WordPress file/directory.
4. Upload the current exact-head `ruby-cx-hostinger-preview.zip` into the document root.
5. Replace only the isolated `preview/` child contents with the current artifact. Do not merge an old and new preview tree if that would leave stale files behind.
6. Extract the ZIP so the sibling directory remains exactly `preview/`.
7. Delete the uploaded ZIP after successful extraction if desired.
8. Open `https://darkgreen-wallaby-680439.hostingersite.com/preview/` and confirm the PRE-PRODUCTION banner appears.

If Hostinger's document root differs from `public_html`, stop and verify the site root before extracting. The preview must remain a new isolated child directory and must never replace the WordPress root.

## Quick Pickup deployment-freshness verification

Before repeating actual first-party Quick Pickup acceptance, verify the deployed preview tree itself is current:

1. Open `https://darkgreen-wallaby-680439.hostingersite.com/preview/quick-pickup.html?lang=en`.
2. Open `https://darkgreen-wallaby-680439.hostingersite.com/preview/quick-pickup.html?lang=ja`.
3. Confirm the page is the isolated first-party Quick Pickup route and visibly states that ordering is disabled.
4. Confirm the PRE-PRODUCTION banner is visible and no order/payment action is exposed.

If `/preview/` is reachable but `/preview/quick-pickup.html` returns WordPress `Page not found`, treat that as **STALE_OR_INCOMPLETE_PREVIEW_DEPLOYMENT**. Do not substitute the legacy Air Mobile preview and do not promote any Quick Pickup readiness flag. Reinstall the current exact-head preview artifact first, then repeat bounded acceptance.

## Verification before review

The owner/operator should confirm:

- the current WordPress homepage still opens unchanged;
- `/preview/` opens the Phil AI OS CX preview;
- `/preview/quick-pickup.html?lang=en` and `?lang=ja` both resolve from the current artifact;
- the PRE-PRODUCTION banner is visible;
- Quick Pickup ordering remains disabled until independent readiness gates are accepted;
- cart/order-request actions remain preview/local only;
- no payment is requested or executed;
- no SMS is sent;
- no live WooCommerce catalog/inventory mutation occurs.

## Authority boundary

This runbook authorizes only isolated owner visual review and bounded synthetic preproduction acceptance on the Hostinger temporary domain. It does not authorize production publication, production-domain connection, DNS change, live KOMOJU execution, unrestricted SMS, live WooCommerce product publication, inventory/capacity mutation, order creation, payment execution, or production cutover.
