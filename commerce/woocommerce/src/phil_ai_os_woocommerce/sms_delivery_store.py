from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SmsIdempotencyStore(Protocol):
    def contains(self, key: str) -> bool:
        ...

    def mark_sent(self, key: str, *, provider: str, provider_message_id: str | None) -> None:
        ...


class MemorySmsIdempotencyStore:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    def contains(self, key: str) -> bool:
        return key in self._keys

    def mark_sent(self, key: str, *, provider: str, provider_message_id: str | None) -> None:
        self._keys.add(key)


@dataclass(frozen=True)
class SqliteSmsIdempotencyStore:
    """Durable duplicate-suppression store for payment-link SMS sends.

    The schema stores only the deterministic idempotency key and provider metadata.
    It deliberately stores no customer phone number and no payment URL/token.
    """

    path: str

    def __post_init__(self) -> None:
        db_path = Path(self.path)
        if db_path.parent != Path('.'):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sms_payment_link_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_message_id TEXT,
                    sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def contains(self, key: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM sms_payment_link_idempotency WHERE idempotency_key = ? LIMIT 1",
                (key,),
            ).fetchone()
        return row is not None

    def mark_sent(self, key: str, *, provider: str, provider_message_id: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sms_payment_link_idempotency
                    (idempotency_key, provider, provider_message_id)
                VALUES (?, ?, ?)
                """,
                (key, provider, provider_message_id),
            )
