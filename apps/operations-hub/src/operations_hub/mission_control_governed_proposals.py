"""Fail-closed local model for Mission Control task proposals and CEO decisions.

This module deliberately has no HTTP, provider, queue, agent, or Control API
dependency.  It is a small persistence boundary that can be exercised before a
runtime is selected.  In particular, recording a CEO decision never assigns a
task, starts work, grants authority, or changes any execution setting.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class GovernedProposalError(ValueError):
    """A request failed without revealing another owner's records."""


@dataclass(frozen=True)
class GovernedProposalStore:
    """SQLite-only candidate store; callers must supply a validated CEO id."""

    path: str

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    sender TEXT NOT NULL CHECK(sender IN ('ceo', 'chief_of_staff')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    source_message_id TEXT NOT NULL REFERENCES messages(message_id),
                    project_id TEXT NOT NULL,
                    task_class TEXT NOT NULL CHECK(task_class = 'general'),
                    scope TEXT NOT NULL,
                    expected_result TEXT NOT NULL,
                    required_authority TEXT NOT NULL,
                    authority_assessment TEXT NOT NULL,
                    proposal_state TEXT NOT NULL CHECK(proposal_state = 'draft'),
                    source_evidence_refs TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    assigned_agent_id TEXT,
                    assignment_id TEXT,
                    execution_authorized INTEGER NOT NULL CHECK(execution_authorized = 0),
                    mutation_authorized INTEGER NOT NULL CHECK(mutation_authorized = 0),
                    authority_effect TEXT NOT NULL CHECK(authority_effect = 'none'),
                    UNIQUE(owner_id, conversation_id, source_message_id, scope, expected_result)
                );
                CREATE TABLE IF NOT EXISTS proposal_idempotency (
                    owner_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    proposal_id TEXT NOT NULL REFERENCES task_proposals(proposal_id) ON DELETE CASCADE,
                    PRIMARY KEY(owner_id, conversation_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS ceo_decisions (
                    decision_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL UNIQUE REFERENCES task_proposals(proposal_id) ON DELETE CASCADE,
                    owner_id TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected')),
                    rationale TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    decision_scope TEXT NOT NULL,
                    authority_effect TEXT NOT NULL CHECK(authority_effect = 'none'),
                    assignment_id TEXT,
                    execution_authorized INTEGER NOT NULL CHECK(execution_authorized = 0),
                    mutation_authorized INTEGER NOT NULL CHECK(mutation_authorized = 0)
                );
                """
            )

    def seed_conversation(self, owner_id: str, conversation_id: str, message_id: str, *, sender: str = "ceo") -> None:
        self._require_identifier(owner_id, "owner_id")
        self._require_identifier(conversation_id, "conversation_id")
        self._require_identifier(message_id, "message_id")
        if sender not in {"ceo", "chief_of_staff"}:
            raise GovernedProposalError("message_sender_invalid")
        now = self._now()
        with self._connection() as connection:
            connection.execute("INSERT INTO conversations VALUES (?, ?, ?)", (conversation_id, owner_id, now))
            connection.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", (message_id, conversation_id, sender, now))

    def create_proposal(
        self, owner_id: str, conversation_id: str, payload: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        self._require_identifier(owner_id, "owner_id")
        self._require_identifier(conversation_id, "conversation_id")
        self._require_identifier(idempotency_key, "idempotency_key")
        normalized = self._validate_proposal(payload)
        fingerprint = self._fingerprint(normalized)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT request_fingerprint, proposal_id FROM proposal_idempotency WHERE owner_id=? AND conversation_id=? AND idempotency_key=?",
                (owner_id, conversation_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise GovernedProposalError("idempotency_conflict")
                return self._proposal(connection, owner_id, existing[1])
            source = connection.execute(
                "SELECT m.sender FROM conversations c JOIN messages m USING (conversation_id) "
                "WHERE c.owner_id=? AND c.conversation_id=? AND m.message_id=?",
                (owner_id, conversation_id, normalized["source_message_id"]),
            ).fetchone()
            if source is None:
                raise GovernedProposalError("conversation_or_source_message_not_found")
            if source[0] != "ceo":
                raise GovernedProposalError("source_message_must_be_ceo_authored")
            proposal_id = "proposal-" + hashlib.sha256((owner_id + conversation_id + fingerprint).encode()).hexdigest()[:24]
            now = self._now()
            assessment = "within_current_a0" if normalized["required_authority"] == "none" else "requires_governance"
            connection.execute(
                "INSERT INTO task_proposals VALUES (?, ?, ?, ?, ?, 'general', ?, ?, ?, ?, 'draft', ?, ?, NULL, NULL, 0, 0, 'none')",
                (proposal_id, owner_id, conversation_id, normalized["source_message_id"], normalized["project_id"], normalized["scope"], normalized["expected_result"], normalized["required_authority"], assessment, json.dumps(normalized["source_evidence_refs"]), now),
            )
            connection.execute(
                "INSERT INTO proposal_idempotency VALUES (?, ?, ?, ?, ?)",
                (owner_id, conversation_id, idempotency_key, fingerprint, proposal_id),
            )
            return self._proposal(connection, owner_id, proposal_id)

    def record_decision(self, owner_id: str, proposal_id: str, decision: str, rationale: str, expires_at: str) -> dict[str, Any]:
        self._require_identifier(owner_id, "owner_id")
        self._require_identifier(proposal_id, "proposal_id")
        if decision not in {"approved", "rejected"}:
            raise GovernedProposalError("decision_invalid")
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 5000:
            raise GovernedProposalError("decision_rationale_invalid")
        expiry = self._parse_timestamp(expires_at, "decision_expiry_invalid")
        now = datetime.now(timezone.utc)
        if expiry <= now:
            raise GovernedProposalError("decision_expired")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            proposal = connection.execute(
                "SELECT project_id, required_authority FROM task_proposals WHERE proposal_id=? AND owner_id=?",
                (proposal_id, owner_id),
            ).fetchone()
            if proposal is None:
                raise GovernedProposalError("proposal_not_found")
            if connection.execute("SELECT 1 FROM ceo_decisions WHERE proposal_id=?", (proposal_id,)).fetchone():
                raise GovernedProposalError("decision_already_recorded")
            decision_id = "decision-" + hashlib.sha256((owner_id + proposal_id + decision + expires_at).encode()).hexdigest()[:24]
            scope = json.dumps({"project_id": proposal[0], "required_authority": proposal[1]}, separators=(",", ":"))
            connection.execute(
                "INSERT INTO ceo_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'none', NULL, 0, 0)",
                (decision_id, proposal_id, owner_id, decision, rationale.strip(), self._now(), expires_at, scope),
            )
            return self._decision(connection, owner_id, decision_id)

    def list_proposals(self, owner_id: str, conversation_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT proposal_id FROM task_proposals WHERE owner_id=? AND conversation_id=? ORDER BY created_at, proposal_id",
                (owner_id, conversation_id),
            ).fetchall()
            return [self._proposal(connection, owner_id, row[0]) for row in rows]

    def _proposal(self, connection: sqlite3.Connection, owner_id: str, proposal_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT proposal_id, conversation_id, source_message_id, project_id, task_class, scope, expected_result, required_authority, authority_assessment, proposal_state, source_evidence_refs, created_at, assigned_agent_id, assignment_id, execution_authorized, mutation_authorized, authority_effect FROM task_proposals WHERE proposal_id=? AND owner_id=?",
            (proposal_id, owner_id),
        ).fetchone()
        if row is None:
            raise GovernedProposalError("proposal_not_found")
        keys = ("proposal_id", "conversation_id", "source_message_id", "project_id", "task_class", "scope", "expected_result", "required_authority", "authority_assessment", "proposal_state", "source_evidence_refs", "created_at", "assigned_agent_id", "assignment_id", "execution_authorized", "mutation_authorized", "authority_effect")
        result = dict(zip(keys, row))
        result["source_evidence_refs"] = json.loads(result["source_evidence_refs"])
        result["approval_id"] = None
        result["execution_authorized"] = bool(result["execution_authorized"])
        result["mutation_authorized"] = bool(result["mutation_authorized"])
        return result

    def _decision(self, connection: sqlite3.Connection, owner_id: str, decision_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT decision_id, proposal_id, decision, rationale, decided_at, expires_at, decision_scope, authority_effect, assignment_id, execution_authorized, mutation_authorized FROM ceo_decisions WHERE decision_id=? AND owner_id=?",
            (decision_id, owner_id),
        ).fetchone()
        if row is None:
            raise GovernedProposalError("decision_not_found")
        keys = ("decision_id", "proposal_id", "decision", "rationale", "decided_at", "expires_at", "decision_scope", "authority_effect", "assignment_id", "execution_authorized", "mutation_authorized")
        result = dict(zip(keys, row))
        result["decision_scope"] = json.loads(result["decision_scope"])
        result["execution_authorized"] = bool(result["execution_authorized"])
        result["mutation_authorized"] = bool(result["mutation_authorized"])
        return result

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _validate_proposal(payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) != {"source_message_id", "project_id", "task_class", "scope", "expected_result", "required_authority", "source_evidence_refs"}:
            raise GovernedProposalError("proposal_payload_invalid")
        if payload["project_id"] not in {"phil-ai-os", "rubys-cake-delights-hq", "kcfc-portal"} or payload["task_class"] != "general" or payload["required_authority"] not in {"none", "A0", "A1", "L2", "L3"}:
            raise GovernedProposalError("proposal_payload_invalid")
        for key, maximum in (("source_message_id", 200), ("scope", 20000), ("expected_result", 5000)):
            if not isinstance(payload[key], str) or not payload[key].strip() or len(payload[key]) > maximum:
                raise GovernedProposalError("proposal_payload_invalid")
        refs = payload["source_evidence_refs"]
        if not isinstance(refs, list) or len(refs) > 20 or len(set(refs)) != len(refs) or any(not isinstance(ref, str) or not ref or len(ref) > 500 for ref in refs):
            raise GovernedProposalError("proposal_payload_invalid")
        return {key: payload[key] for key in sorted(payload)}

    @staticmethod
    def _fingerprint(value: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _require_identifier(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise GovernedProposalError(f"{name}_invalid")

    @staticmethod
    def _parse_timestamp(value: str, code: str) -> datetime:
        if not isinstance(value, str):
            raise GovernedProposalError(code)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise GovernedProposalError(code) from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise GovernedProposalError(code)
        return parsed
