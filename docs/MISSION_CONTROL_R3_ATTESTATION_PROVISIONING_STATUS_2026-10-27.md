# Mission Control R3 Attestation Provisioning Status — 2026-10-27

## Current posture

The R3 reauthentication-attestation design remains **default-off** and has no
runtime authority. The Google identity probe remains separate from the
attestation handoff and does not create a Mission Control session.

The dedicated PostgreSQL database and its protected host files are provisioned
and independently verified. No shared application database has been used.

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

## Catalog diagnostic result

The narrowly scoped disposable-database diagnostic completed successfully.
Both the applying `psql` session and a new connection observed one
`mission_control` schema, four foundation tables, and then five tables after
the R3 metadata migration. The disposable database and role were removed at
the end of the diagnostic.

This establishes that PostgreSQL catalog visibility is consistent when the
migrations are delivered through a temporary file inside the database
container. The earlier zero-table result is therefore not evidence of a
database consistency fault and must not be used as a basis for granting
authority.

## Production-equivalent provision result

After fresh explicit approval, the dedicated database was provisioned using
the verified temporary-file migration delivery method. A separate read-only
audit confirmed:

1. Exactly one `mission_control` database and one
   `mission_control_migrator` role exist.
2. Exactly five `mission_control` tables exist.
3. The migration role has no superuser, database-creation, role-creation, or
   inherited privileges.
4. The migration-password file is `root:root` mode `0400`.
5. The attestation signing-key file is `root:10002` mode `0640`.

The provisioned schema stores only design-approved metadata and constrains all
authority flags false. Provisioning did not enable the R3 handoff, create a
Mission Control session, or permit any external action adapter.

## Next gate

The R3 handoff remains disabled. Any runtime integration needs separate,
explicit approval for the exact integration boundary and a fresh R3
confirmation flow; the database alone is not authority to activate it.

## Monitoring criteria

This record may advance only when all of the following are independently
verified:

1. A periodic read-only audit continues to observe the five-table schema,
   isolated role flags, and protected-file ownership and modes.
2. The R3 handoff remains disabled until a separately approved runtime
   integration and fresh R3 confirmation flow exist.
