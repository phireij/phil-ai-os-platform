# Sprint 7 — Production Secret Handling Plan

Date: 2026-08-28
Status: PREPARATION ONLY / NO PRODUCTION SECRET INTRODUCTION AUTHORIZED

## Objective

Define how future production credentials will be introduced, stored, accessed, rotated and revoked without committing secret material to GitHub or exposing it to surfaces that do not need it.

## Rules

1. **Do not commit secrets.** Production tokens, API keys, consumer keys/secrets, passwords, webhook secrets and merchant credentials must never be committed to the repository, fixtures, documentation, screenshots or logs.
2. **Least privilege.** Each production integration uses the narrowest identity and scopes required for its approved function.
3. **Approved secret store.** Credentials are introduced only after the storage location is explicitly approved for the target runtime.
4. **Runtime separation.** Customer Experience and read-only Operations/Mission Control surfaces do not receive credentials they do not need.
5. **HTTPS only.** Production HTTP integrations require TLS/HTTPS transport.
6. **No credential echo.** Startup, health, error and audit logs must not print credential values.
7. **Rotation and revocation.** Every production integration must have a documented rotation/revocation procedure before activation.
8. **One integration at a time.** Credentials are introduced only for the production capability currently passing its activation gate; unrelated integrations remain unconfigured.
9. **Explicit CEO gate.** Introducing a new production integration identity or credential requires explicit approval when it crosses the existing authority baseline.
10. **Immediate containment on exposure.** If secret exposure is suspected, stop the affected activation, revoke/rotate the credential, verify logs/repository history and re-run credential scans before resuming.

## Integration-specific prerequisites

### WooCommerce

- dedicated least-privilege integration identity;
- approved consumer key/secret storage;
- HTTPS endpoint;
- rotation/revocation procedure;
- no key material in CX, fixtures or GitHub;
- production connectivity separately authorized.

### KOMOJU

- merchant/account access completed through the intended WooCommerce integration path;
- Test Mode credentials/configuration isolated from later Live Mode;
- Live Mode remains a separate production gate;
- no payment credential exposed to Phil AI OS surfaces that only prepare/observe handoff intent.

### External channels

- dedicated app/bot/business integration identity where applicable;
- minimum webhook/read/write scopes;
- signing/webhook secret protected in approved runtime storage;
- outbound reply/write authority enabled only after its specific activation approval.

## Pre-activation verification

Before any production secret is introduced:

- [ ] target integration and required scope identified;
- [ ] least-privilege identity approved;
- [ ] secret storage location approved;
- [ ] rotation/revocation steps documented;
- [ ] logs verified not to echo secrets;
- [ ] credential-pattern repository scans GREEN;
- [ ] rollback/abort procedure exists;
- [ ] explicit production activation approval recorded where required.

This plan defines handling requirements only. It does not authorize creation or use of any production credential.

`PHIL_AI_OS_SPRINT_7_SECRET_HANDLING_PLAN_READY_NOT_AUTHORIZED`
