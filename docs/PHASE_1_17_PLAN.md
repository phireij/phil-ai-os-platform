# Phase 1.17 — Automated Backup, Retention, and Recovery Operations

**Status:** STARTING  
**Date:** August 24, 2026

## Objective

Turn the already validated manual SQLite backup/restore procedure from Phase 1.15 into a conservative automated production operation without changing Phil AI OS execution authority.

## Scope

- SQLite-safe online backup of the Control API state database
- SHA-256 checksum generation
- `PRAGMA integrity_check` validation on every backup
- isolated restore validation
- timestamped backup inventory
- conservative retention rotation
- machine-readable latest-backup status
- integration with the Phase 1.16 operational monitor
- Telegram alert on backup/integrity/recovery-validation failure

## Safety Constraints

- never copy a live SQLite database with a raw file copy while it is active
- never restore over production during automated validation
- never delete a backup until a newer validated backup exists
- never expose database contents or secrets in GitHub Actions logs
- keep routed execution disabled and the execution kill switch enabled
- do not restart Control API for routine backup operations

## Initial Acceptance Gates

1. Discover the exact live database path and durable storage mount from the production Control API.
2. Create an isolated backup directory with restrictive permissions.
3. Produce one automated SQLite backup through the SQLite backup API.
4. Validate `PRAGMA integrity_check = ok` on the backup.
5. Validate a restore copy in an isolated temporary directory.
6. Generate checksum and machine-readable metadata.
7. Confirm production Control API remains healthy throughout.
8. Add retention only after backup + validation are proven.
9. Add monitoring/Telegram failure reporting only after the backup operation is stable.

## Proposed Retention Baseline

Initial conservative policy, subject to live validation:

- hourly: latest 24
- daily: latest 14
- weekly: latest 8

Rotation will not be enabled until storage impact and recovery behavior are validated.

## Completion Criteria

Phase 1.17 is complete only when an automated backup cycle, integrity check, isolated restore validation, retention policy, monitoring status, and failure-alert path are all live-validated on the VPS with no production-state mutation or execution-policy regression.
