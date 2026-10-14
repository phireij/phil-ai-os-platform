# Mission Control encrypted conversation foundation

**Status:** inactive implementation candidate. No conversation storage, route, provider call, task proposal, assignment, or execution is activated by this change.

The candidate extends the verified Google CEO session service with an optional, owner-scoped conversation API. It starts in the current session-only mode unless `MISSION_CONTROL_CONVERSATION_ENABLED=true` and three protected absolute paths are supplied: an encryption-key file, a dedicated live-state file, and a separate deletion-ledger file. The existing production deployment sets none of these values, so merging this code cannot enable conversation authority.

## Storage boundary

The service uses SQLite for transactions and indexes, but holds the database in process memory. A successful mutation serializes the whole database and writes only an AES-256-GCM authenticated envelope to disk, through a mode-0600 temporary file, `fsync`, and atomic replacement. No plaintext SQLite database, journal, or WAL is persisted. Independent HMAC-derived keys isolate the live snapshot and deletion ledger while one protected master key remains outside both files. Persistence failures restore the previous in-memory snapshot before another request can observe the uncommitted mutation.

The encrypted deletion ledger is persisted before live deletion. A restart or restore replays its owner-bound markers before records can be served. The candidate applies the approved 90-day live retention policy and retains deletion markers for 90 days, which is longer than the approved 35-day maximum backup age.

`conversation_recovery.py` supplies an offline maintenance boundary. With the conversation container stopped, `backup` creates one immutable AES-256-GCM envelope containing the live database and deletion ledger. The authenticated creation timestamp makes a backup ineligible at 35 days, rejects future-dated or tampered envelopes, and uses a third derived key. `restore` never overwrites live files. It writes a new private state/ledger pair to operator-selected quarantine paths after merging the current deletion ledger, replaying deletion markers, applying retention, and checking SQLite integrity and foreign keys. A reviewed operator must inspect and deliberately swap the quarantined pair later; the command cannot activate it.

## API boundary

When explicitly enabled, the same exact-subject CEO session protects these routes:

- `GET /api/conversations` lists caller-owned metadata only.
- `POST /api/conversations` creates an empty caller-owned conversation with CSRF, exact Origin, bounded input, and idempotency enforcement.
- `GET /api/conversations/{id}/messages` lists caller-owned messages.
- `POST /api/conversations/{id}/messages` atomically stores a bounded CEO message and a terminal `runtime_unavailable` response state. It never fabricates an assistant response or calls a provider.
- `GET /api/conversations/{id}/responses/{message_id}` returns only the caller-owned sanitized response state.
- `DELETE /api/conversations/{id}` records the protected deletion marker first and then removes the live conversation.

Conversation identifiers are lookup keys only. Every operation derives ownership from the validated CEO binding. Unknown and non-owned identifiers share the same non-disclosing response. Message bodies, credentials, encryption keys, cookies, CSRF tokens, and protected subject values are absent from application logs.

## Remaining gates

Twenty-five focused offline checks pass on 14 October 2026: five encrypted storage/recovery checks, seven CEO session/API checks, and thirteen Google identity checks. They cover inactive defaults, exact owner isolation, encryption at rest, idempotency conflict and rollback, retention, deletion replay, backup expiry/tamper/wrong-key rejection, CSRF and Origin enforcement, hardened cookies, identity validation, and absence of response authority. Exact Linux image construction remains a CI gate because the local Docker daemon was unavailable.

Before any real CEO message can be accepted, review the candidate and its CI evidence, approve key ownership/recovery/rotation, configure the dedicated persistent and backup volumes, add UI integration, and complete a separately approved image publication and guarded deployment. The OpenAI response runtime remains disabled until its budget, terms, regional processing, credential, egress, and no-tool checks are complete.

## Offline recovery commands

These commands are designed for a stopped container with its existing environment and protected mounts. Destination directories must already exist, be absolute, and grant no group or other access. Outputs must not already exist.

```sh
python3 /srv/conversation_recovery.py backup /protected-backups/conversation-YYYYMMDDTHHMMSSZ.enc
python3 /srv/conversation_recovery.py restore \
  /protected-backups/conversation-YYYYMMDDTHHMMSSZ.enc \
  /protected-quarantine/conversation-state.enc \
  /protected-quarantine/conversation-deletion-ledger.enc
```

The command emits only success and the authenticated backup creation epoch. It does not emit message content, keys, subjects, file contents, or database details.
