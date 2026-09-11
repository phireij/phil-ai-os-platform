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

The builder refuses browser scripts containing `fetch(` or `XMLHttpRequest`, so the artifact remains network-inert at the browser layer.

## GitHub artifact workflow

`.github/workflows/customer-experience-hostinger-preview-artifact.yml` builds and tests the ZIP. It does not deploy, SSH/SFTP, modify WordPress, change DNS, create orders, execute payment, send SMS, or mutate WooCommerce/inventory.

## Manual Hostinger upload boundary

Because the connected Hostinger integration does not expose WordPress File Manager/SFTP actions, the final file placement is an explicit owner/manual step:

1. Hostinger hPanel → website Dashboard → Files → File Manager.
2. Open the document root used by the temporary WordPress site, normally `public_html`.
3. Do **not** overwrite `index.php`, `wp-config.php`, `wp-content`, or any existing WordPress file/directory.
4. Upload `ruby-cx-hostinger-preview.zip` into the document root.
5. Extract it so the new sibling directory is exactly `preview/`.
6. Delete the uploaded ZIP after successful extraction if desired.
7. Open `https://darkgreen-wallaby-680439.hostingersite.com/preview/` and confirm the PRE-PRODUCTION banner appears.

If Hostinger's document root differs from `public_html`, stop and verify the site root before extracting. The preview must remain a new isolated child directory and must never replace the WordPress root.

## Verification before review

The owner should confirm:

- the current WordPress homepage still opens unchanged;
- `/preview/` opens the Phil AI OS CX preview;
- the PRE-PRODUCTION banner is visible;
- cart/order-request actions remain preview/local only;
- no payment is requested or executed;
- no SMS is sent;
- no live WooCommerce catalog/inventory mutation occurs.

## Authority boundary

This runbook authorizes only isolated owner visual review on the Hostinger temporary domain. It does not authorize production publication, production-domain connection, DNS change, live KOMOJU execution, unrestricted SMS, live WooCommerce product publication, inventory mutation, or production cutover.
