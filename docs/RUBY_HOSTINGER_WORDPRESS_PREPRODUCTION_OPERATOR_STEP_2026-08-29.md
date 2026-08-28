# Ruby's Cake Delights — Hostinger WordPress Pre-Production Operator Step

Date: 2026-08-29  
Status: **NEXT HUMAN/ACCOUNT-SIDE STEP / PUBLIC SITE MUST REMAIN UNCHANGED**

## Why this step is required

Ruby's current public site is built with Hostinger Website Builder. Hostinger's native WordPress staging feature requires an existing WordPress installation detected in hPanel, so the first migration environment must be a separate WordPress site rather than a staging clone of the current builder site.

## What the authorized Hostinger account owner should do

1. Sign in to Hostinger hPanel.
2. Open **Websites**.
3. Create/add a **new website** using WordPress / the CMS installer available in the account.
4. Use a temporary/non-production address offered by Hostinger, or a separate subdomain that does **not** replace `rubyscakedelights.shop`.
5. Install WordPress.
6. Confirm the new WordPress site opens successfully over HTTPS.
7. Open WordPress Admin and install/activate **WooCommerce**.
8. Do **not** publish/switch the Ruby public domain to this site.
9. Do **not** connect KOMOJU Test Mode or Live Mode yet.
10. Record the pre-production URL and whether hPanel shows `WordPress → Staging` for this WordPress installation.

## Information to return to the CTO workflow

After the site exists, record only:

- pre-production URL;
- WordPress admin reachable: yes/no;
- WooCommerce active: yes/no;
- HTTPS/SSL: yes/no;
- Hostinger native WordPress `Staging` menu available: yes/no;
- hosting plan name if visible and convenient.

Do not send passwords, secret keys, API keys, KOMOJU secrets or other credentials in chat or GitHub.

## Hard boundaries

- `rubyscakedelights.shop` stays on the current Website Builder site.
- Existing Website Builder products/categories remain non-authoritative test data.
- No KOMOJU merchant-account connection yet.
- No real payment authority.
- No production WooCommerce/API mutation authority.

`PHIL_AI_OS_RUBY_HOSTINGER_OPERATOR_NEXT_STEP_CREATE_PARALLEL_WORDPRESS_NO_CUTOVER`
