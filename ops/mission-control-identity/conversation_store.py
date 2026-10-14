"""Encrypted, owner-scoped Mission Control conversation persistence.

The store keeps SQLite in memory and persists only an authenticated AES-GCM
snapshot. It has no provider integration and grants no task authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAGIC = b"PHIL-MC-CONVERSATION-STATE-V1\x00"
RETENTION_SECONDS = 90 * 24 * 60 * 60
DELETION_MARKER_SECONDS = 90 * 24 * 60 * 60
MAX_MESSAGE_CHARACTERS = 20_000
MAX_PAGE_SIZE = 100
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,200}")
IDEMPOTENCY_PATTERN = re.compile(r"[A-Za-z0-9._~-]{16,128}")


class ConversationConfigurationError(ValueError):
    """A safe-to-log configuration failure."""


class ConversationRequestError(ValueError):
    def __init__(self, code: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class ConversationConfig:
    state_file: Path
    deletion_ledger_file: Path
    key_file: Path

    @classmethod
    def from_environment(cls) -> ConversationConfig | None:
        if os.environ.get("MISSION_CONTROL_CONVERSATION_ENABLED") != "true":
            return None
        state_file = _absolute_state_path("MISSION_CONTROL_CONVERSATION_STATE_FILE")
        ledger_file = _absolute_state_path("MISSION_CONTROL_CONVERSATION_DELETION_LEDGER_FILE")
        key_file = _protected_key_file("MISSION_CONTROL_CONVERSATION_KEY_FILE")
        if state_file == ledger_file or key_file in {state_file, ledger_file}:
            raise ConversationConfigurationError("conversation_paths_overlap")
        return cls(state_file, ledger_file, key_file)


def _absolute_state_path(variable: str) -> Path:
    raw = os.environ.get(variable, "")
    if not raw or not Path(raw).is_absolute():
        raise ConversationConfigurationError("conversation_state_path_invalid")
    path = Path(raw)
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise ConversationConfigurationError("conversation_state_file_invalid")
    if path.exists():
        details = path.stat()
        if details.st_mode & 0o077 or details.st_size > 64 * 1024 * 1024:
            raise ConversationConfigurationError("conversation_state_file_invalid")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ConversationConfigurationError("conversation_state_parent_invalid")
    mode = parent.stat().st_mode & 0o777
    if mode & 0o077:
        raise ConversationConfigurationError("conversation_state_parent_permissions")
    return path


def _protected_key_file(variable: str) -> Path:
    raw = os.environ.get(variable, "")
    if not raw or not Path(raw).is_absolute():
        raise ConversationConfigurationError("conversation_key_file_unset")
    path = Path(raw)
    try:
        details = path.lstat()
    except OSError as exc:
        raise ConversationConfigurationError("conversation_key_file_unavailable") from exc
    if path.is_symlink() or not path.is_file() or details.st_mode & 0o077:
        raise ConversationConfigurationError("conversation_key_file_invalid")
    if details.st_size < 64 or details.st_size > 128:
        raise ConversationConfigurationError("conversation_key_file_size_invalid")
    return path


def load_key(path: Path) -> bytes:
    try:
        value = path.read_text(encoding="ascii").strip()
        key = bytes.fromhex(value)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ConversationConfigurationError("conversation_key_invalid") from exc
    if len(key) != 32:
        raise ConversationConfigurationError("conversation_key_invalid")
    return key


def owner_digest(key: bytes, issuer: str, subject: str) -> bytes:
    return hmac.new(key, f"{issuer}|{subject}".encode("utf-8"), hashlib.sha256).digest()


def _derived_key(master: bytes, purpose: bytes) -> bytes:
    return hmac.new(master, b"phil-ai-os-mission-control\x00" + purpose, hashlib.sha256).digest()


def _iso(timestamp: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _initialize_live(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            owner_digest BLOB NOT NULL,
            created_at INTEGER NOT NULL,
            last_activity_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS conversations_owner_order
            ON conversations(owner_digest, created_at, conversation_id);
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            sender TEXT NOT NULL CHECK(sender IN ('ceo', 'chief_of_staff')),
            body TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS messages_conversation_order
            ON messages(conversation_id, created_at, message_id);
        CREATE TABLE IF NOT EXISTS response_states (
            message_id TEXT PRIMARY KEY REFERENCES messages(message_id) ON DELETE CASCADE,
            conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
            state TEXT NOT NULL CHECK(state IN ('queued', 'responding', 'complete', 'unavailable', 'failed')),
            created_at INTEGER NOT NULL,
            completed_at INTEGER,
            error_code TEXT
        );
        CREATE TABLE IF NOT EXISTS idempotency_results (
            owner_digest BLOB NOT NULL,
            operation TEXT NOT NULL,
            idempotency_hash BLOB NOT NULL,
            request_hash BLOB NOT NULL,
            response_json TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(owner_digest, operation, idempotency_hash)
        );
        """
    )


def _initialize_ledger(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS deletion_markers (
            conversation_id TEXT PRIMARY KEY,
            owner_digest BLOB NOT NULL,
            deleted_at INTEGER NOT NULL,
            retain_until INTEGER NOT NULL
        );
        """
    )


class EncryptedSnapshot:
    def __init__(self, path: Path, key: bytes, initializer: Any) -> None:
        self.path = path
        self.key = key
        self.connection = _connect()
        if path.exists():
            self._load()
        initializer(self.connection)

    def _load(self) -> None:
        encoded = self.path.read_bytes()
        if not encoded.startswith(MAGIC) or len(encoded) < len(MAGIC) + 12 + 16:
            raise ConversationConfigurationError("conversation_snapshot_invalid")
        nonce = encoded[len(MAGIC):len(MAGIC) + 12]
        try:
            plaintext = AESGCM(self.key).decrypt(nonce, encoded[len(MAGIC) + 12:], MAGIC)
            source = sqlite3.connect(":memory:")
            try:
                source.deserialize(plaintext)
                source.backup(self.connection)
            finally:
                source.close()
        except Exception as exc:
            raise ConversationConfigurationError("conversation_snapshot_unavailable") from exc

    def persist(self, *, overwrite: bool = True) -> None:
        plaintext = self.connection.serialize()
        nonce = secrets.token_bytes(12)
        encoded = MAGIC + nonce + AESGCM(self.key).encrypt(nonce, plaintext, MAGIC)
        _atomic_write_private(self.path, encoded, overwrite=overwrite)


def _atomic_write_private(path: Path, encoded: bytes, *, overwrite: bool) -> None:
    if not overwrite and path.exists():
        raise ConversationConfigurationError("conversation_output_exists")
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise ConversationConfigurationError("conversation_output_exists") from exc
            temporary.unlink()
        os.chmod(path, 0o600)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


class ConversationStore:
    def __init__(self, config: ConversationConfig, issuer: str, subject: str) -> None:
        self._key = load_key(config.key_file)
        self._owner = owner_digest(_derived_key(self._key, b"owner"), issuer, subject)
        self._lock = threading.Lock()
        self._live = EncryptedSnapshot(config.state_file, _derived_key(self._key, b"live"), _initialize_live)
        self._ledger = EncryptedSnapshot(config.deletion_ledger_file, _derived_key(self._key, b"ledger"), _initialize_ledger)
        self._last_purge = 0
        with self._lock:
            self._purge_locked(int(time.time()))

    @staticmethod
    def _identifier(prefix: str) -> str:
        return f"{prefix}_{secrets.token_urlsafe(24)}"

    def _idempotency(self, value: str) -> bytes:
        if not IDEMPOTENCY_PATTERN.fullmatch(value):
            raise ConversationRequestError("invalid_idempotency_key", 400)
        return hmac.new(self._key, value.encode("ascii"), hashlib.sha256).digest()

    @staticmethod
    def _request_hash(payload: bytes) -> bytes:
        return hashlib.sha256(payload).digest()

    def _purge_locked(self, now: int) -> None:
        cutoff = now - RETENTION_SECONDS
        live_before = self._live.connection.serialize()
        ledger_before = self._ledger.connection.serialize()
        markers = self._ledger.connection.execute(
            "SELECT conversation_id FROM deletion_markers"
        ).fetchall()
        try:
            with self._live.connection:
                self._live.connection.executemany(
                    "DELETE FROM conversations WHERE conversation_id=?", markers
                )
                self._live.connection.execute("DELETE FROM messages WHERE created_at <= ?", (cutoff,))
                self._live.connection.execute(
                    "DELETE FROM conversations WHERE last_activity_at <= ?",
                    (cutoff,),
                )
                self._live.connection.execute("DELETE FROM idempotency_results WHERE created_at <= ?", (cutoff,))
            with self._ledger.connection:
                self._ledger.connection.execute("DELETE FROM deletion_markers WHERE retain_until <= ?", (now,))
            self._live.persist()
            self._ledger.persist()
        except Exception:
            self._live.connection.deserialize(live_before)
            self._ledger.connection.deserialize(ledger_before)
            raise
        self._last_purge = now

    def _purge_if_due_locked(self, now: int) -> None:
        if now < self._last_purge or now - self._last_purge >= 3600:
            self._purge_locked(now)

    def create_conversation(self, idempotency_key: str, request_body: bytes) -> dict[str, Any]:
        if request_body not in {b"", b"{}"}:
            raise ConversationRequestError("invalid_request", 400)
        now = int(time.time())
        key_hash = self._idempotency(idempotency_key)
        request_hash = self._request_hash(b"{}")
        with self._lock:
            self._purge_if_due_locked(now)
            existing = self._live.connection.execute(
                "SELECT request_hash,response_json FROM idempotency_results "
                "WHERE owner_digest=? AND operation='create' AND idempotency_hash=?",
                (self._owner, key_hash),
            ).fetchone()
            if existing:
                if not hmac.compare_digest(existing["request_hash"], request_hash):
                    raise ConversationRequestError("idempotency_conflict", 409)
                return json.loads(existing["response_json"])
            conversation_id = self._identifier("conv")
            result = {
                "conversation_id": conversation_id,
                "created_at": _iso(now),
                "authority_effect": "none",
            }
            before = self._live.connection.serialize()
            try:
                with self._live.connection:
                    self._live.connection.execute(
                        "INSERT INTO conversations VALUES (?,?,?,?)",
                        (conversation_id, self._owner, now, now),
                    )
                    self._live.connection.execute(
                        "INSERT INTO idempotency_results VALUES (?,?,?,?,?,?,?)",
                        (self._owner, "create", key_hash, request_hash, json.dumps(result), conversation_id, now),
                    )
                self._live.persist()
            except Exception:
                self._live.connection.deserialize(before)
                raise
            return result

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1 or limit > MAX_PAGE_SIZE:
            raise ConversationRequestError("invalid_limit", 400)
        with self._lock:
            self._purge_if_due_locked(int(time.time()))
            rows = self._live.connection.execute(
                "SELECT conversation_id,created_at,last_activity_at FROM conversations "
                "WHERE owner_digest=? ORDER BY created_at,conversation_id LIMIT ?",
                (self._owner, limit),
            ).fetchall()
        return [
            {
                "conversation_id": row["conversation_id"],
                "created_at": _iso(row["created_at"]),
                "last_activity_at": _iso(row["last_activity_at"]),
                "authority_effect": "none",
            }
            for row in rows
        ]

    def submit_message(self, conversation_id: str, idempotency_key: str, request_body: bytes) -> dict[str, Any]:
        if not ID_PATTERN.fullmatch(conversation_id):
            raise ConversationRequestError("not_found", 404)
        try:
            decoded = json.loads(request_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConversationRequestError("invalid_request", 400) from exc
        if not isinstance(decoded, dict) or set(decoded) != {"body"} or not isinstance(decoded["body"], str):
            raise ConversationRequestError("invalid_request", 400)
        body = decoded["body"]
        if not body or len(body) > MAX_MESSAGE_CHARACTERS:
            raise ConversationRequestError("invalid_message", 400)
        normalized = json.dumps({"body": body}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        now = int(time.time())
        key_hash = self._idempotency(idempotency_key)
        request_hash = self._request_hash(normalized)
        operation = f"submit:{conversation_id}"
        with self._lock:
            self._purge_if_due_locked(now)
            owned = self._live.connection.execute(
                "SELECT 1 FROM conversations WHERE conversation_id=? AND owner_digest=?",
                (conversation_id, self._owner),
            ).fetchone()
            if not owned:
                raise ConversationRequestError("not_found", 404)
            existing = self._live.connection.execute(
                "SELECT request_hash,response_json FROM idempotency_results "
                "WHERE owner_digest=? AND operation=? AND idempotency_hash=?",
                (self._owner, operation, key_hash),
            ).fetchone()
            if existing:
                if not hmac.compare_digest(existing["request_hash"], request_hash):
                    raise ConversationRequestError("idempotency_conflict", 409)
                return json.loads(existing["response_json"])
            message_id = self._identifier("msg")
            result = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "response_state": "unavailable",
                "error_code": "runtime_unavailable",
                "created_at": _iso(now),
                "authority_effect": "none",
            }
            before = self._live.connection.serialize()
            try:
                with self._live.connection:
                    self._live.connection.execute(
                        "INSERT INTO messages VALUES (?,?,'ceo',?,?)",
                        (message_id, conversation_id, body, now),
                    )
                    self._live.connection.execute(
                        "INSERT INTO response_states VALUES (?,?, 'unavailable',?,?, 'runtime_unavailable')",
                        (message_id, conversation_id, now, now),
                    )
                    self._live.connection.execute(
                        "UPDATE conversations SET last_activity_at=? WHERE conversation_id=?",
                        (now, conversation_id),
                    )
                    self._live.connection.execute(
                        "INSERT INTO idempotency_results VALUES (?,?,?,?,?,?,?)",
                        (self._owner, operation, key_hash, request_hash, json.dumps(result), conversation_id, now),
                    )
                self._live.persist()
            except Exception:
                self._live.connection.deserialize(before)
                raise
            return result

    def list_messages(self, conversation_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if not ID_PATTERN.fullmatch(conversation_id):
            raise ConversationRequestError("not_found", 404)
        if limit < 1 or limit > MAX_PAGE_SIZE:
            raise ConversationRequestError("invalid_limit", 400)
        with self._lock:
            self._purge_if_due_locked(int(time.time()))
            owned = self._live.connection.execute(
                "SELECT 1 FROM conversations WHERE conversation_id=? AND owner_digest=?",
                (conversation_id, self._owner),
            ).fetchone()
            if not owned:
                raise ConversationRequestError("not_found", 404)
            rows = self._live.connection.execute(
                "SELECT m.message_id,m.sender,m.body,m.created_at,r.state AS response_state,r.error_code "
                "FROM messages m LEFT JOIN response_states r ON r.message_id=m.message_id "
                "WHERE m.conversation_id=? ORDER BY m.created_at,m.message_id LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return [
            {
                "conversation_id": conversation_id,
                "message_id": row["message_id"],
                "sender": row["sender"],
                "body": row["body"],
                "created_at": _iso(row["created_at"]),
                "response_state": row["response_state"],
                "error_code": row["error_code"],
                "authority_effect": "none",
            }
            for row in rows
        ]

    def get_response_state(self, conversation_id: str, message_id: str) -> dict[str, Any]:
        if not ID_PATTERN.fullmatch(conversation_id) or not ID_PATTERN.fullmatch(message_id):
            raise ConversationRequestError("not_found", 404)
        with self._lock:
            self._purge_if_due_locked(int(time.time()))
            row = self._live.connection.execute(
                "SELECT r.state,r.created_at,r.completed_at,r.error_code "
                "FROM response_states r JOIN conversations c USING (conversation_id) "
                "WHERE r.conversation_id=? AND r.message_id=? AND c.owner_digest=?",
                (conversation_id, message_id, self._owner),
            ).fetchone()
            if row is None:
                raise ConversationRequestError("not_found", 404)
        return {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "state": row["state"],
            "created_at": _iso(row["created_at"]),
            "started_at": None,
            "completed_at": _iso(row["completed_at"]) if row["completed_at"] is not None else None,
            "assistant_message_id": None,
            "error_code": row["error_code"],
            "authority_effect": "none",
        }

    def delete_conversation(self, conversation_id: str) -> None:
        if not ID_PATTERN.fullmatch(conversation_id):
            raise ConversationRequestError("not_found", 404)
        now = int(time.time())
        with self._lock:
            self._purge_if_due_locked(now)
            owned = self._live.connection.execute(
                "SELECT 1 FROM conversations WHERE conversation_id=? AND owner_digest=?",
                (conversation_id, self._owner),
            ).fetchone()
            marked = self._ledger.connection.execute(
                "SELECT 1 FROM deletion_markers WHERE conversation_id=? AND owner_digest=?",
                (conversation_id, self._owner),
            ).fetchone()
            if not owned and not marked:
                raise ConversationRequestError("not_found", 404)
            if not marked:
                ledger_before = self._ledger.connection.serialize()
                try:
                    with self._ledger.connection:
                        self._ledger.connection.execute(
                            "INSERT INTO deletion_markers VALUES (?,?,?,?)",
                            (conversation_id, self._owner, now, now + DELETION_MARKER_SECONDS),
                        )
                    self._ledger.persist()
                except Exception:
                    self._ledger.connection.deserialize(ledger_before)
                    raise
            try:
                with self._live.connection:
                    self._live.connection.execute(
                        "DELETE FROM conversations WHERE conversation_id=? AND owner_digest=?",
                        (conversation_id, self._owner),
                    )
                    self._live.connection.execute(
                        "DELETE FROM idempotency_results WHERE owner_digest=? AND resource_id=?",
                        (self._owner, conversation_id),
                    )
                self._live.persist()
            except Exception:
                # The durable deletion marker is already committed. Keep the
                # live process suppressed too; restart replay provides recovery.
                raise
