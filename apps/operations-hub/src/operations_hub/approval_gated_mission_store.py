"""Local, pre-activation persistence for approval-gated Mission Control work.

The store persists missions, non-executable plans, inert approval packets, and
privacy-bounded audit hashes. It has no HTTP, queue, provider, adapter, or
credential dependency and cannot record an execution authorization.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .approval_gated_policy import AssessmentRequest, PolicyDecision, assess


class ApprovalGatedMissionStoreError(ValueError):
    """Raised for a failed local persistence operation without data leakage."""


@dataclass(frozen=True)
class ApprovalGatedMissionStore:
    path: str

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS approval_gated_missions (
                    mission_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    required_gate TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('draft', 'awaiting_approval')),
                    execution_authorized INTEGER NOT NULL CHECK(execution_authorized = 0),
                    mutation_authorized INTEGER NOT NULL CHECK(mutation_authorized = 0),
                    authority_effect TEXT NOT NULL CHECK(authority_effect = 'none')
                );
                CREATE TABLE IF NOT EXISTS approval_gated_plans (
                    plan_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES approval_gated_missions(mission_id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL,
                    plan_digest TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(mission_id, revision),
                    UNIQUE(mission_id, plan_digest)
                );
                CREATE TABLE IF NOT EXISTS approval_gated_packets (
                    approval_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES approval_gated_missions(mission_id) ON DELETE CASCADE,
                    plan_id TEXT NOT NULL REFERENCES approval_gated_plans(plan_id) ON DELETE CASCADE,
                    plan_digest TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    required_gate TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    decision_state TEXT NOT NULL CHECK(decision_state = 'awaiting_decision'),
                    execution_authorized INTEGER NOT NULL CHECK(execution_authorized = 0),
                    mutation_authorized INTEGER NOT NULL CHECK(mutation_authorized = 0),
                    authority_effect TEXT NOT NULL CHECK(authority_effect = 'none')
                );
                CREATE TABLE IF NOT EXISTS approval_gated_audit_events (
                    event_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES approval_gated_missions(mission_id) ON DELETE CASCADE,
                    plan_id TEXT REFERENCES approval_gated_plans(plan_id) ON DELETE SET NULL,
                    sequence INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    previous_event_hash TEXT,
                    event_hash TEXT NOT NULL,
                    content_included INTEGER NOT NULL CHECK(content_included = 0),
                    execution_authorized INTEGER NOT NULL CHECK(execution_authorized = 0),
                    mutation_authorized INTEGER NOT NULL CHECK(mutation_authorized = 0),
                    authority_effect TEXT NOT NULL CHECK(authority_effect = 'none'),
                    UNIQUE(mission_id, sequence),
                    UNIQUE(event_hash)
                );
                """
            )

    def create_mission(
        self,
        owner_id: str,
        project_id: str,
        source: str,
        assessment: AssessmentRequest,
    ) -> dict[str, Any]:
        self._identifier(owner_id, "owner_id")
        if project_id not in {"phil-ai-os", "rubys-cake-delights-hq", "kcfc-portal"}:
            raise ApprovalGatedMissionStoreError("project_id_invalid")
        if source not in {"ceo_conversation", "project_signal", "connected_channel"}:
            raise ApprovalGatedMissionStoreError("mission_source_invalid")
        decision = assess(assessment)
        mission_id = "mission-" + uuid.uuid4().hex
        now = self._now()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO approval_gated_missions VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0, 0, 'none')",
                (mission_id, owner_id, project_id, source, now, decision.risk_level, decision.required_gate, decision.policy_version),
            )
            self._append_event(connection, mission_id, None, "intake_created", decision.policy_version, now)
            self._append_event(connection, mission_id, None, "risk_assessed", decision.policy_version, now)
            return self._mission(connection, owner_id, mission_id)

    def create_plan(self, owner_id: str, mission_id: str, steps: list[dict[str, str]]) -> dict[str, Any]:
        self._identifier(owner_id, "owner_id")
        self._identifier(mission_id, "mission_id")
        normalized_steps = self._normalize_steps(steps)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            mission = connection.execute(
                "SELECT policy_version FROM approval_gated_missions WHERE mission_id=? AND owner_id=?",
                (mission_id, owner_id),
            ).fetchone()
            if mission is None:
                raise ApprovalGatedMissionStoreError("mission_not_found")
            revision = connection.execute(
                "SELECT COALESCE(MAX(revision), 0) + 1 FROM approval_gated_plans WHERE mission_id=?", (mission_id,)
            ).fetchone()[0]
            plan_id = "plan-" + uuid.uuid4().hex
            digest = self._digest({"mission_id": mission_id, "revision": revision, "steps": normalized_steps})
            now = self._now()
            connection.execute(
                "INSERT INTO approval_gated_plans VALUES (?, ?, ?, ?, ?, ?)",
                (plan_id, mission_id, revision, digest, json.dumps(normalized_steps, separators=(",", ":")), now),
            )
            connection.execute("UPDATE approval_gated_missions SET state='awaiting_approval' WHERE mission_id=?", (mission_id,))
            self._append_event(connection, mission_id, plan_id, "plan_created", mission[0], now)
            return self._plan(connection, owner_id, plan_id)

    def create_approval_packet(self, owner_id: str, mission_id: str, plan_id: str) -> dict[str, Any]:
        self._identifier(owner_id, "owner_id")
        self._identifier(mission_id, "mission_id")
        self._identifier(plan_id, "plan_id")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT m.risk_level, m.required_gate, m.policy_version, p.plan_digest "
                "FROM approval_gated_missions m JOIN approval_gated_plans p ON p.mission_id=m.mission_id "
                "WHERE m.mission_id=? AND m.owner_id=? AND p.plan_id=?",
                (mission_id, owner_id, plan_id),
            ).fetchone()
            if row is None:
                raise ApprovalGatedMissionStoreError("mission_or_plan_not_found")
            risk_level, required_gate, policy_version, plan_digest = row
            ttl = {"R1": 1440, "R2": 240, "R3": 15}.get(risk_level)
            if ttl is None:
                raise ApprovalGatedMissionStoreError("approval_not_required_or_blocked")
            approval_id = "approval-" + uuid.uuid4().hex
            now = datetime.now(timezone.utc)
            expires_at = (now + timedelta(minutes=ttl)).isoformat().replace("+00:00", "Z")
            connection.execute(
                "INSERT INTO approval_gated_packets VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'awaiting_decision', 0, 0, 'none')",
                (approval_id, mission_id, plan_id, plan_digest, risk_level, required_gate, policy_version, expires_at),
            )
            self._append_event(connection, mission_id, plan_id, "approval_requested", policy_version, self._now())
            return self._packet(connection, owner_id, approval_id)

    def list_audit_events(self, owner_id: str, mission_id: str) -> list[dict[str, Any]]:
        self._identifier(owner_id, "owner_id")
        self._identifier(mission_id, "mission_id")
        with self._connection() as connection:
            if connection.execute("SELECT 1 FROM approval_gated_missions WHERE mission_id=? AND owner_id=?", (mission_id, owner_id)).fetchone() is None:
                raise ApprovalGatedMissionStoreError("mission_not_found")
            rows = connection.execute(
                "SELECT event_id, sequence, mission_id, plan_id, stage, occurred_at, policy_version, previous_event_hash, event_hash, content_included, execution_authorized, mutation_authorized, authority_effect "
                "FROM approval_gated_audit_events WHERE mission_id=? ORDER BY sequence",
                (mission_id,),
            ).fetchall()
        keys = ("event_id", "sequence", "mission_id", "plan_id", "stage", "occurred_at", "policy_version", "previous_event_hash", "event_hash", "content_included", "execution_authorized", "mutation_authorized", "authority_effect")
        return [self._bools(dict(zip(keys, row))) for row in rows]

    def _mission(self, connection: sqlite3.Connection, owner_id: str, mission_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT mission_id, project_id, source, created_at, risk_level, required_gate, policy_version, state, execution_authorized, mutation_authorized, authority_effect "
            "FROM approval_gated_missions WHERE mission_id=? AND owner_id=?",
            (mission_id, owner_id),
        ).fetchone()
        if row is None:
            raise ApprovalGatedMissionStoreError("mission_not_found")
        keys = ("mission_id", "project_id", "source", "created_at", "risk_level", "required_gate", "policy_version", "state", "execution_authorized", "mutation_authorized", "authority_effect")
        result = self._bools(dict(zip(keys, row)))
        result["activation_state"] = "design_only_inactive"
        return result

    def _plan(self, connection: sqlite3.Connection, owner_id: str, plan_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT p.plan_id, p.mission_id, p.revision, p.plan_digest, p.steps_json, p.created_at, m.risk_level, m.policy_version "
            "FROM approval_gated_plans p JOIN approval_gated_missions m ON m.mission_id=p.mission_id "
            "WHERE p.plan_id=? AND m.owner_id=?",
            (plan_id, owner_id),
        ).fetchone()
        if row is None:
            raise ApprovalGatedMissionStoreError("plan_not_found")
        keys = ("plan_id", "mission_id", "revision", "plan_digest", "steps_json", "created_at", "risk_level", "policy_version")
        result = dict(zip(keys, row))
        result["steps"] = json.loads(result.pop("steps_json"))
        result.update({"approval_state": "awaiting_approval", "activation_state": "design_only_inactive", "execution_authorized": False, "mutation_authorized": False, "authority_effect": "none"})
        return result

    def _packet(self, connection: sqlite3.Connection, owner_id: str, approval_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT a.approval_id, a.mission_id, a.plan_id, a.plan_digest, a.risk_level, a.required_gate, a.policy_version, a.expires_at, a.decision_state, a.execution_authorized, a.mutation_authorized, a.authority_effect "
            "FROM approval_gated_packets a JOIN approval_gated_missions m ON m.mission_id=a.mission_id "
            "WHERE a.approval_id=? AND m.owner_id=?",
            (approval_id, owner_id),
        ).fetchone()
        if row is None:
            raise ApprovalGatedMissionStoreError("approval_packet_not_found")
        keys = ("approval_id", "mission_id", "plan_id", "plan_digest", "risk_level", "required_gate", "policy_version", "expires_at", "decision_state", "execution_authorized", "mutation_authorized", "authority_effect")
        result = self._bools(dict(zip(keys, row)))
        result["activation_state"] = "design_only_inactive"
        return result

    @staticmethod
    def _normalize_steps(steps: list[dict[str, str]]) -> list[dict[str, str]]:
        if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
            raise ApprovalGatedMissionStoreError("plan_steps_invalid")
        normalized: list[dict[str, str]] = []
        for sequence, step in enumerate(steps, start=1):
            if not isinstance(step, dict) or set(step) != {"description", "mode", "target_reference"}:
                raise ApprovalGatedMissionStoreError("plan_step_invalid")
            description = step["description"]
            target = step["target_reference"]
            if not isinstance(description, str) or not description.strip() or len(description) > 2000:
                raise ApprovalGatedMissionStoreError("plan_step_invalid")
            if step["mode"] not in {"read_only", "simulation"} or not isinstance(target, str) or not target.strip() or len(target) > 500:
                raise ApprovalGatedMissionStoreError("plan_step_invalid")
            normalized.append({"sequence": sequence, "description": description.strip(), "mode": step["mode"], "target_reference": target.strip()})
        return normalized

    def _append_event(self, connection: sqlite3.Connection, mission_id: str, plan_id: str | None, stage: str, policy_version: str, occurred_at: str) -> None:
        sequence, previous_hash = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1, (SELECT event_hash FROM approval_gated_audit_events WHERE mission_id=? ORDER BY sequence DESC LIMIT 1) FROM approval_gated_audit_events WHERE mission_id=?",
            (mission_id, mission_id),
        ).fetchone()
        hash_input = {"mission_id": mission_id, "plan_id": plan_id, "sequence": sequence, "stage": stage, "occurred_at": occurred_at, "policy_version": policy_version, "previous_event_hash": previous_hash}
        event_hash = self._digest(hash_input)
        connection.execute(
            "INSERT INTO approval_gated_audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 'none')",
            ("audit-" + uuid.uuid4().hex, mission_id, plan_id, sequence, stage, occurred_at, policy_version, previous_hash, event_hash),
        )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _digest(value: dict[str, Any]) -> str:
        return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @staticmethod
    def _bools(value: dict[str, Any]) -> dict[str, Any]:
        for key in ("content_included", "execution_authorized", "mutation_authorized"):
            if key in value:
                value[key] = bool(value[key])
        return value

    @staticmethod
    def _identifier(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ApprovalGatedMissionStoreError(f"{name}_invalid")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
