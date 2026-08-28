# Sprint 3 — WooCommerce Security & Activation Checklist

**State:** PREPARATION ONLY — activation is not authorized by this document.

## Credential boundary

Before any production connection is proposed:

- production store URL is explicitly identified and reviewed;
- a dedicated least-privilege WooCommerce integration identity is designed;
- consumer key/secret storage location is approved;
- no key is committed to GitHub or copied into fixtures/logs;
- credential rotation and revocation procedure exists;
- HTTPS-only transport is enforced;
- secrets are unavailable to CX/Operations surfaces that do not require them.

## Authority boundary

A new explicit CEO gate is required before:

- introducing the production integration identity or credentials;
- enabling a live WooCommerce transport;
- permitting product/category/media/inventory/order writes;
- enabling checkout/order execution;
- adding a commerce execution task class;
- enabling a specialist or increasing autonomy;
- granting Mission Control mutation authority.

## Data-integrity gate

Prior to activation, prove in an isolated environment:

- stable SKU/category identity mapping;
- duplicate/replay resistance;
- create/update/no-op reconciliation;
- inventory conflict and stale-revision handling;
- media ordering/primary-image reconciliation;
- bilingual field/slugs validation;
- retry behavior for transient errors and fail-closed behavior for auth/validation errors;
- audit event linkage to correlation/idempotency identity;
- rollback snapshot/restore plan for any production mutation trial.

## First production trial principle

If later authorized, the first production trial must be narrow, reversible, observable, and explicitly scoped. This checklist does not itself authorize that trial.

`PHIL_AI_OS_SPRINT_3_WOOCOMMERCE_ACTIVATION_GATE_PREPARED_NOT_AUTHORIZED`
