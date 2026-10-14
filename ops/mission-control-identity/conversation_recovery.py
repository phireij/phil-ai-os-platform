"""Offline encrypted backup and quarantined restore for CEO conversations.

Run only while the conversation service is stopped. Restores never replace live
files: they write a new, private pair for operator review and controlled swap.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sqlite3
import struct
import time
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from conversation_store import (
    RETENTION_SECONDS,
    ConversationConfig,
    ConversationConfigurationError,
    EncryptedSnapshot,
    _atomic_write_private,
    _derived_key,
    _initialize_ledger,
    _initialize_live,
    load_key,
)


BACKUP_MAGIC = b"PHIL-MC-CONVERSATION-BACKUP-V1\x00"
BACKUP_MAX_AGE_SECONDS = 35 * 24 * 60 * 60
MAX_CLOCK_SKEW_SECONDS = 5 * 60
MAX_BACKUP_BYTES = 128 * 1024 * 1024
MAX_DATABASE_BYTES = 64 * 1024 * 1024


def _private_path(raw: str, *, must_exist: bool) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise ConversationConfigurationError("conversation_recovery_path_invalid")
    parent = path.parent
    if (
        not parent.is_dir()
        or parent.is_symlink()
        or (os.name != "nt" and parent.stat().st_mode & 0o077)
    ):
        raise ConversationConfigurationError("conversation_recovery_parent_invalid")
    if path.exists():
        details = path.lstat()
        if (
            path.is_symlink()
            or not path.is_file()
            or (os.name != "nt" and details.st_mode & 0o077)
        ):
            raise ConversationConfigurationError("conversation_recovery_file_invalid")
        if details.st_size > MAX_BACKUP_BYTES:
            raise ConversationConfigurationError("conversation_recovery_file_too_large")
    elif must_exist:
        raise ConversationConfigurationError("conversation_recovery_file_unavailable")
    return path


def _encode_backup(master_key: bytes, live: bytes, ledger: bytes, created_at: int) -> bytes:
    payload = json.dumps(
        {
            "schema": "phil-ai-os-mission-control-conversation-backup",
            "version": 1,
            "live": base64.b64encode(live).decode("ascii"),
            "deletion_ledger": base64.b64encode(ledger).decode("ascii"),
        },
        separators=(",", ":"),
    ).encode("ascii")
    timestamp = struct.pack(">Q", created_at)
    nonce = secrets.token_bytes(12)
    authenticated_header = BACKUP_MAGIC + timestamp
    encrypted = AESGCM(_derived_key(master_key, b"backup-v1")).encrypt(
        nonce, payload, authenticated_header
    )
    return authenticated_header + nonce + encrypted


def _decode_backup(master_key: bytes, encoded: bytes, now: int) -> tuple[bytes, bytes, int]:
    minimum = len(BACKUP_MAGIC) + 8 + 12 + 16
    if len(encoded) < minimum or len(encoded) > MAX_BACKUP_BYTES or not encoded.startswith(BACKUP_MAGIC):
        raise ConversationConfigurationError("conversation_backup_invalid")
    position = len(BACKUP_MAGIC)
    timestamp = encoded[position:position + 8]
    created_at = struct.unpack(">Q", timestamp)[0]
    if created_at > now + MAX_CLOCK_SKEW_SECONDS:
        raise ConversationConfigurationError("conversation_backup_from_future")
    if now - created_at >= BACKUP_MAX_AGE_SECONDS:
        raise ConversationConfigurationError("conversation_backup_expired")
    nonce_start = position + 8
    nonce = encoded[nonce_start:nonce_start + 12]
    authenticated_header = BACKUP_MAGIC + timestamp
    try:
        plaintext = AESGCM(_derived_key(master_key, b"backup-v1")).decrypt(
            nonce, encoded[nonce_start + 12:], authenticated_header
        )
        payload = json.loads(plaintext)
        if not isinstance(payload, dict) or set(payload) != {
            "schema", "version", "live", "deletion_ledger"
        }:
            raise ValueError("invalid shape")
        if payload["schema"] != "phil-ai-os-mission-control-conversation-backup" or payload["version"] != 1:
            raise ValueError("invalid version")
        live = base64.b64decode(payload["live"], validate=True)
        ledger = base64.b64decode(payload["deletion_ledger"], validate=True)
        if not live or not ledger or len(live) > MAX_DATABASE_BYTES or len(ledger) > MAX_DATABASE_BYTES:
            raise ValueError("invalid database size")
    except Exception as exc:
        raise ConversationConfigurationError("conversation_backup_unavailable") from exc
    return live, ledger, created_at


def create_backup(config: ConversationConfig, destination: Path, now: int | None = None) -> int:
    """Create an immutable encrypted backup from a stopped service's state."""
    destination = _private_path(str(destination), must_exist=False)
    if destination.exists():
        raise ConversationConfigurationError("conversation_output_exists")
    if not config.state_file.exists() or not config.deletion_ledger_file.exists():
        raise ConversationConfigurationError("conversation_state_unavailable")
    master_key = load_key(config.key_file)
    live = EncryptedSnapshot(config.state_file, _derived_key(master_key, b"live"), _initialize_live)
    ledger = EncryptedSnapshot(
        config.deletion_ledger_file, _derived_key(master_key, b"ledger"), _initialize_ledger
    )
    created_at = int(time.time()) if now is None else now
    encoded = _encode_backup(
        master_key, live.connection.serialize(), ledger.connection.serialize(), created_at
    )
    _atomic_write_private(destination, encoded, overwrite=False)
    return created_at


def _database_from_bytes(
    serialized: bytes, initializer: Callable[[sqlite3.Connection], None]
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.deserialize(serialized)
        initializer(connection)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise ValueError("integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("foreign key check failed")
    except Exception:
        connection.close()
        raise
    return connection


def _merge_current_ledger(
    config: ConversationConfig, master_key: bytes, restored: sqlite3.Connection
) -> None:
    if not config.deletion_ledger_file.exists():
        return
    current = EncryptedSnapshot(
        config.deletion_ledger_file, _derived_key(master_key, b"ledger"), _initialize_ledger
    )
    rows = current.connection.execute(
        "SELECT conversation_id,owner_digest,deleted_at,retain_until FROM deletion_markers"
    ).fetchall()
    with restored:
        restored.executemany(
            "INSERT INTO deletion_markers VALUES (?,?,?,?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET "
            "owner_digest=excluded.owner_digest,deleted_at=excluded.deleted_at,"
            "retain_until=MAX(deletion_markers.retain_until,excluded.retain_until)",
            rows,
        )
    current.connection.close()


def restore_to_quarantine(
    config: ConversationConfig,
    backup: Path,
    quarantine_state: Path,
    quarantine_ledger: Path,
    now: int | None = None,
) -> int:
    """Validate, suppress deleted/expired records, and write a new private pair."""
    backup = _private_path(str(backup), must_exist=True)
    quarantine_state = _private_path(str(quarantine_state), must_exist=False)
    quarantine_ledger = _private_path(str(quarantine_ledger), must_exist=False)
    if (
        quarantine_state == quarantine_ledger
        or backup in {quarantine_state, quarantine_ledger}
        or quarantine_state.exists()
        or quarantine_ledger.exists()
    ):
        raise ConversationConfigurationError("conversation_output_exists")
    current_time = int(time.time()) if now is None else now
    master_key = load_key(config.key_file)
    live_bytes, ledger_bytes, created_at = _decode_backup(
        master_key, backup.read_bytes(), current_time
    )
    live: sqlite3.Connection | None = None
    ledger: sqlite3.Connection | None = None
    try:
        live = _database_from_bytes(live_bytes, _initialize_live)
        ledger = _database_from_bytes(ledger_bytes, _initialize_ledger)
    except Exception as exc:
        if live is not None:
            live.close()
        raise ConversationConfigurationError("conversation_backup_database_invalid") from exc
    try:
        _merge_current_ledger(config, master_key, ledger)
        markers = ledger.execute("SELECT conversation_id FROM deletion_markers").fetchall()
        cutoff = current_time - RETENTION_SECONDS
        with live:
            live.executemany("DELETE FROM conversations WHERE conversation_id=?", markers)
            live.execute("DELETE FROM messages WHERE created_at <= ?", (cutoff,))
            live.execute("DELETE FROM conversations WHERE last_activity_at <= ?", (cutoff,))
            live.execute("DELETE FROM idempotency_results WHERE created_at <= ?", (cutoff,))
        with ledger:
            ledger.execute(
                "DELETE FROM deletion_markers WHERE retain_until <= ?", (current_time,)
            )
        live_snapshot = EncryptedSnapshot(
            quarantine_state, _derived_key(master_key, b"live"), _initialize_live
        )
        ledger_snapshot = EncryptedSnapshot(
            quarantine_ledger, _derived_key(master_key, b"ledger"), _initialize_ledger
        )
        live_snapshot.connection.deserialize(live.serialize())
        ledger_snapshot.connection.deserialize(ledger.serialize())
        ledger_snapshot.persist(overwrite=False)
        try:
            live_snapshot.persist(overwrite=False)
        except Exception:
            quarantine_ledger.unlink(missing_ok=True)
            raise
    finally:
        live.close()
        ledger.close()
    return created_at


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Mission Control conversation recovery")
    commands = parser.add_subparsers(dest="command", required=True)
    backup_command = commands.add_parser("backup")
    backup_command.add_argument("destination")
    restore_command = commands.add_parser("restore")
    restore_command.add_argument("backup")
    restore_command.add_argument("quarantine_state")
    restore_command.add_argument("quarantine_ledger")
    args = parser.parse_args()
    config = ConversationConfig.from_environment()
    if config is None:
        raise ConversationConfigurationError("conversation_service_disabled")
    if args.command == "backup":
        created_at = create_backup(config, Path(args.destination))
    else:
        created_at = restore_to_quarantine(
            config,
            Path(args.backup),
            Path(args.quarantine_state),
            Path(args.quarantine_ledger),
        )
    print(json.dumps({"ok": True, "backup_created_at": created_at}, separators=(",", ":")))


if __name__ == "__main__":
    main()
