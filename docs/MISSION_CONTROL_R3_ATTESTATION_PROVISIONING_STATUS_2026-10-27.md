# Mission Control R3 Attestation Provisioning Status — 2026-10-27

## Current posture

The R3 reauthentication-attestation design remains **default-off** and has no
runtime authority. The Google identity probe remains separate from the
attestation handoff and does not create a Mission Control session.

The intended dedicated PostgreSQL database and its protected host files are
not provisioned. No shared application database has been used.

## Designed boundary

- Dedicated database: `mission_control`.
- Dedicated migration role: `mission_control_migrator`, with no superuser,
  database-creation, role-creation, or inherited privileges.
- Planned schema artifacts: the approval-gated foundation and R3 attestation
  metadata design-only migrations.
- Planned protected files: a migration-role password readable only by root and
  a signing key readable only by root and the designated service group.
- Authority effect: `none`; neither schema can make execution or mutation
  authorized.

## 2026-10-27 verification record

1. The immutable GitHub source checksums for both schema files were verified
   before each guarded run.
2. The database guard created no retained database, role, password file, or
   signing-key file after a failed check; cleanup was verified after each run.
3. PostgreSQL reported successful `BEGIN`, schema/table creation, and `COMMIT`
   while applying the foundation and R3 SQL files through a temporary
   container file.
4. A separate, immediate catalog query in the same named database and role
   returned zero visible `mission_control` schemas and tables. The guarded run
   therefore rolled back instead of retaining credentials or state.

## Next gate

Dedicated-database provisioning is paused pending a narrowly scoped
PostgreSQL catalog-visibility diagnosis. That diagnosis must use a disposable
database, verify in-session and second-session catalog state, remove the
disposable database afterwards, and must not activate the handoff or any
external action adapter.

## Monitoring criteria

This record may advance only when all of the following are independently
verified:

1. The disposable diagnostic resolves the catalog-visibility discrepancy.
2. A new explicit approval authorizes a production-equivalent dedicated
   database provision attempt.
3. Post-provision verification observes exactly the intended five tables and
   the expected protected-file ownership and modes.
4. The R3 handoff remains disabled until a separately approved runtime
   integration and fresh R3 confirmation flow exist.
