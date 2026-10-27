"""Durable, non-dispatching execution records for the GitHub sandbox pilot.

This is the persistence boundary immediately before a future separately
activated adapter. It stores only opaque approval, plan, and idempotency
references plus fixed outcome codes. It deliberately has no private-key,
environment, HTTP, subprocess, queue, or GitHub SDK dependency. Reserving or
consuming an entry never authorizes token issuance or external dispatch.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass


class GitHubSandboxRuntimeLedgerError(ValueError):
    """Raised with a fixed, non-secret code for an unsafe ledger transition."""


_PLAN_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_FAILURE_CODES = frozenset({"token_request_failed", "dispatch_failed", "unknown_failure"})


@dataclass(frozen=True)
class InertExecutionReservation:
    """Durable reservation metadata that grants no credential or dispatch effect."""

    attempt_id: str
    approval_id: str
    plan_digest: str
    idempotency_key: str
    expires_at_epoch: int
    state: str = "reserved_inert_runtime_unwired"
    credential_read_authorized: bool = False
    token_request_authorized: bool = False
    dispatch_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InertExecutionConsumption:
    """A single-use terminal record that still grants no external authority."""

    attempt_id: str
    approval_id: str
    plan_digest: str
    idempotency_key: str
    state: str
    outcome_code: str | None
    credential_read_authorized: bool = False
    token_request_authorized: bool = False
    dispatch_authorized: bool = False
    authority_effect: str = "none"

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class GitHubSandboxRuntimeLedger:
    """SQLite ledger for one inert reservation and one terminal transition."""

    path: str

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS github_sandbox_runtime_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    plan_digest TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    expires_at_epoch INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('reserved_inert', 'consumed_inert', 'failed_inert', 'expired_inert')),
                    outcome_code TEXT,
                    created_at_epoch INTEGER NOT NULL,
                    finalized_at_epoch INTEGER,
                    credential_read_authorized INTEGER NOT NULL CHECK(credential_read_authorized = 0),
                    token_request_authorized INTEGER NOT NULL CHECK(token_request_authorized = 0),
                    dispatch_authorized INTEGER NOT NULL CHECK(dispatch_authorized = 0),
                    authority_effect TEXT NOT NULL CHECK(authority_effect = 'none')
                );
                """
            )

    def reserve(
        self,
        approval_id: str,
        plan_digest: str,
        idempotency_key: str,
        now_epoch_seconds: int,
        expires_at_epoch: int,
    ) -> InertExecutionReservation:
        """Persist one non-authorizing reservation or fail closed on reuse."""

        self._validate_inputs(approval_id, plan_digest, idempotency_key, now_epoch_seconds, expires_at_epoch)
        attempt_id = "sandbox-attempt-" + uuid.uuid4().hex
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT approval_id, idempotency_key FROM github_sandbox_runtime_attempts "
                "WHERE approval_id=? OR idempotency_key=?",
                (approval_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing[0] == approval_id:
                    raise GitHubSandboxRuntimeLedgerError("github_sandbox_approval_already_reserved")
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_idempotency_already_reserved")
            connection.execute(
                "INSERT INTO github_sandbox_runtime_attempts VALUES (?, ?, ?, ?, ?, 'reserved_inert', NULL, ?, NULL, 0, 0, 0, 'none')",
                (attempt_id, approval_id, plan_digest, idempotency_key, expires_at_epoch, now_epoch_seconds),
            )
        return InertExecutionReservation(attempt_id, approval_id, plan_digest, idempotency_key, expires_at_epoch)

    def consume(
        self,
        approval_id: str,
        plan_digest: str,
        idempotency_key: str,
        now_epoch_seconds: int,
    ) -> InertExecutionConsumption:
        """Atomically consume a reservation; a second attempt is permanently blocked."""

        self._validate_identifier(approval_id, "approval")
        self._validate_plan_digest(plan_digest)
        self._validate_identifier(idempotency_key, "idempotency")
        self._validate_clock(now_epoch_seconds, "clock")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT attempt_id, plan_digest, idempotency_key, expires_at_epoch, state "
                "FROM github_sandbox_runtime_attempts WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_not_found")
            attempt_id, persisted_digest, persisted_key, expires_at, state = row
            if persisted_digest != plan_digest or persisted_key != idempotency_key:
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_binding_mismatch")
            if state != "reserved_inert":
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_not_consumable")
            if now_epoch_seconds > expires_at:
                connection.execute(
                    "UPDATE github_sandbox_runtime_attempts SET state='expired_inert', finalized_at_epoch=? WHERE attempt_id=?",
                    (now_epoch_seconds, attempt_id),
                )
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_expired")
            connection.execute(
                "UPDATE github_sandbox_runtime_attempts SET state='consumed_inert', finalized_at_epoch=? WHERE attempt_id=?",
                (now_epoch_seconds, attempt_id),
            )
        return InertExecutionConsumption(attempt_id, approval_id, plan_digest, idempotency_key, "consumed_inert_runtime_unwired", None)

    def record_redacted_failure(
        self,
        approval_id: str,
        plan_digest: str,
        idempotency_key: str,
        failure_code: str,
        now_epoch_seconds: int,
    ) -> InertExecutionConsumption:
        """Persist a fixed failure code without accepting a provider error body."""

        self._validate_identifier(approval_id, "approval")
        self._validate_plan_digest(plan_digest)
        self._validate_identifier(idempotency_key, "idempotency")
        self._validate_clock(now_epoch_seconds, "clock")
        if failure_code not in _FAILURE_CODES:
            raise GitHubSandboxRuntimeLedgerError("github_sandbox_failure_code_invalid")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT attempt_id, plan_digest, idempotency_key, state FROM github_sandbox_runtime_attempts WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_not_found")
            attempt_id, persisted_digest, persisted_key, state = row
            if persisted_digest != plan_digest or persisted_key != idempotency_key:
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_binding_mismatch")
            if state != "reserved_inert":
                raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_not_finalizable")
            connection.execute(
                "UPDATE github_sandbox_runtime_attempts SET state='failed_inert', outcome_code=?, finalized_at_epoch=? WHERE attempt_id=?",
                (failure_code, now_epoch_seconds, attempt_id),
            )
        return InertExecutionConsumption(attempt_id, approval_id, plan_digest, idempotency_key, "failed_inert_runtime_unwired", failure_code)

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _validate_inputs(approval_id: str, plan_digest: str, idempotency_key: str, now: int, expires_at: int) -> None:
        GitHubSandboxRuntimeLedger._validate_identifier(approval_id, "approval")
        GitHubSandboxRuntimeLedger._validate_plan_digest(plan_digest)
        GitHubSandboxRuntimeLedger._validate_identifier(idempotency_key, "idempotency")
        GitHubSandboxRuntimeLedger._validate_clock(now, "clock")
        GitHubSandboxRuntimeLedger._validate_clock(expires_at, "expiry")
        if expires_at <= now:
            raise GitHubSandboxRuntimeLedgerError("github_sandbox_reservation_expiry_invalid")

    @staticmethod
    def _validate_identifier(value: str, label: str) -> None:
        if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
            raise GitHubSandboxRuntimeLedgerError(f"github_sandbox_{label}_identifier_invalid")

    @staticmethod
    def _validate_plan_digest(value: str) -> None:
        if not isinstance(value, str) or not _PLAN_DIGEST_PATTERN.fullmatch(value):
            raise GitHubSandboxRuntimeLedgerError("github_sandbox_plan_digest_invalid")

    @staticmethod
    def _validate_clock(value: int, label: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise GitHubSandboxRuntimeLedgerError(f"github_sandbox_{label}_invalid")
