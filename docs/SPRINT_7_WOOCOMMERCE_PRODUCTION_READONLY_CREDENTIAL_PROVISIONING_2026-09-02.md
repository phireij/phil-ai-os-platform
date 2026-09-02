# Sprint 7 — WooCommerce Production Read-Only Credential Provisioning

**Date:** 2026-09-02  
**Purpose:** Safely prepare the least-privilege WooCommerce production identity required by the already-approved production activation scope.

## Safety objective

This runbook creates a **Read-only** WooCommerce REST API identity for the first production connectivity check. It does **not** create catalog mutation authority, tax mutation authority, order mutation authority, KOMOJU Live authority, DNS cutover authority, or automatic production execution.

The first production check must remain read-only and is implemented in:

- `.github/workflows/commerce-woocommerce-production-readonly-preflight.yml`
- `commerce/woocommerce/tools_production_connectivity_preflight.py`

That workflow performs only `GET /wp-json/wc/v3/products?per_page=1` and has a static no-mutation assertion.

## Step 1 — Create the WooCommerce Read-only API key

In the Ruby's Cake Delights WordPress/WooCommerce administration interface:

1. Open **WooCommerce → Settings → Advanced → REST API**.
2. Choose **Add key / Create an API key**.
3. Description: `Phil AI OS Production Read-Only Preflight`.
4. Select the WordPress user that should own this API identity. Use the minimum practical WordPress role/capabilities required for the intended read-only WooCommerce API access.
5. Permissions: **Read**.
6. Generate the API key.
7. Securely capture the displayed **Consumer Key** and **Consumer Secret** immediately. WooCommerce does not provide the secret for later viewing in the same form.

Do **not** choose Read/Write for this first identity.

## Step 2 — Store the values as GitHub Actions repository secrets

In `phireij/phil-ai-os-platform`:

1. Open **Settings**.
2. Open **Secrets and variables → Actions**.
3. Add the following repository secrets:

| Secret name | Value |
|---|---|
| `RUBY_WOO_PRODUCTION_BASE_URL` | The HTTPS base URL of the target WooCommerce WordPress site, with no `/wp-json/...` suffix |
| `RUBY_WOO_PRODUCTION_CONSUMER_KEY` | The generated Read-only WooCommerce Consumer Key |
| `RUBY_WOO_PRODUCTION_CONSUMER_SECRET` | The generated WooCommerce Consumer Secret |

Never commit these values to repository files and do not paste the key/secret into ordinary chat messages.

## Step 3 — Run the prepared read-only preflight

After all three secrets are present, manually run the GitHub Actions workflow:

**WooCommerce Production Read-Only Preflight**

Set:

- `confirm_read_only = true`

Expected GREEN markers:

- `PHIL_AI_OS_WOO_PRODUCTION_SECRET_REFS_PRESENT`
- `PHIL_AI_OS_WOO_PRODUCTION_READONLY_PREFLIGHT_GREEN wc_v3=true identity=true mutation=false catalog_write=false tax_write=false`
- `PHIL_AI_OS_WOO_PRODUCTION_PREFLIGHT_MUTATION_BOUNDARY_GREEN`

## Acceptance rule

A GREEN run proves only:

- the target HTTPS WooCommerce `wc/v3` surface is reachable;
- the Read-only production identity authenticates successfully; and
- the prepared preflight did not gain mutation authority.

It does **not** authorize or prove readiness for product loading, tax configuration, order mutation, payment activation, or public cutover.

## Fail-closed conditions

Stop and do not expand permissions if any of the following occurs:

- API authentication fails;
- the site URL is not HTTPS;
- the API key is accidentally created with broader permissions than intended;
- the workflow attempts any mutating HTTP method;
- credentials appear in logs or repository files;
- catalog/tax/legal/recovery launch gates remain incomplete for a later mutation step.

If a key is created incorrectly, revoke it in the WooCommerce REST API settings and create a new least-privilege Read-only key.

## Later mutation identity

A future Read/Write identity must be treated as a separate activation step. Even though WooCommerce production activation scope is CEO-approved, the Phil AI OS mutation preflight remains fail-closed until the approved catalog, confirmed tax configuration, final checkout/legal synchronization, and fresh near-cutover recovery evidence are all GREEN.

`PHIL_AI_OS_WOO_PRODUCTION_READONLY_CREDENTIAL_PROVISIONING_READY`
