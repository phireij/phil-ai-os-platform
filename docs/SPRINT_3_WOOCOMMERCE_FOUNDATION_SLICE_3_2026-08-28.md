# Sprint 3 — WooCommerce Foundation Slice 3

Date: 2026-08-28
Status: IN PROGRESS / BOUNDED FOUNDATION
Authority: A0 unchanged; `general` execution class only

## Scope completed in this slice

1. Category hierarchy planning
   - rejects duplicate category keys
   - rejects missing parents
   - rejects cycles
   - produces deterministic parent-before-child order
   - performs no WooCommerce network call

2. Product media planning
   - resolves canonical product media references
   - requires exactly one primary image when media is present
   - rejects duplicate/ambiguous positions
   - produces deterministic EN/JA manifests
   - performs no upload or WooCommerce network call

3. Resilience preparation
   - test-only failure injection transport
   - transient HTTP retry executor using the existing pure retry policy
   - no sleeping/background work
   - no live transport

4. Audit preparation
   - in-memory audit sink
   - rejects any event whose `authority_effect` is not `none`

5. Isolated WordPress/WooCommerce local foundation
   - WordPress + MariaDB Compose topology remains loopback-only
   - added WP-CLI `local-tools` profile
   - added local bootstrap script to install WordPress and activate WooCommerce in the isolated environment
   - bootstrap target is hard-bound to `127.0.0.1`
   - production Ruby domain is forbidden from local runtime files by CI

6. CI hardening
   - validates contracts/fixtures
   - runs isolated Python tests
   - validates Docker Compose configuration
   - asserts normalized loopback binding
   - validates bootstrap shell syntax
   - scans for WooCommerce consumer key/secret patterns

## Governance preserved

This slice does not add or authorize:
- production WooCommerce credentials
- production WooCommerce runtime API URL
- live WooCommerce connectivity
- production integration identity
- live product/category/inventory/media mutations
- checkout/order execution
- payment activation
- DNS changes
- specialist enablement
- new execution task classes
- higher autonomy
- automatic production actions
- Mission Control mutation authority

## Ruby's Cake Delights deployment boundary

Production customer-facing WordPress + WooCommerce remains targeted for Hostinger managed web hosting using the retained domain `https://www.rubyscakedelights.shop/`.

Phil AI OS remains on the Hostinger VPS. The existing Hostinger Website Builder site remains reference-only; only verified store information, contact information, and policies are migration candidates. Existing test products and categories are excluded.

## Validation note

The local bootstrap script is prepared and CI syntax/config checked. A full container startup + WooCommerce installation has not yet been claimed GREEN unless a runtime execution test completes successfully in a Docker-capable isolated environment.

## Next bounded work

- verify local container startup/bootstrap in an isolated CI job or Docker-capable development environment
- add parent remote-ID projection tests for category reconciliation without production connectivity
- extend media reconciliation identity/planning for replacement and reordering
- expand negative authentication/rate-limit/server-error scenarios
- connect reconciliation results to the in-memory audit sink in a bounded orchestration helper
- continue CX and Operations contract preparation without mutation authority
