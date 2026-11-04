"""Synthetic-only quote currentness and response custody in the existing store.

No shopper authentication, route, token, provider or execution authority exists.
The injected fixture verifier MUST NOT be exposed as a production verifier.
Receipts are historical evidence only; currentness is always read separately.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import time

from ruby_inquiry import canonical, decode, error, _object, _text, IDENTIFIER
from ruby_finalized_quote import NO_QUOTE_AUTHORITY

SCHEMA = "ruby.synthetic-quote-custody.v1"
FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
CUSTODY_TABLES = ("ruby_quote_custody_events", "ruby_quote_custody_receipts",
                  "ruby_quote_custody_audit", "ruby_quote_custody_heads")


@dataclass(frozen=True)
class SyntheticResponseVerification:
    """A test assertion, explicitly not an identity credential or authenticator."""
    inquiry_id: str
    quote_id: str
    customer_ref: str
    request_fingerprint: str
    actor_ref: str
    synthetic_only: bool = True


def initialize_quote_custody(connection):
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS ruby_quote_custody_events (
        event_id TEXT PRIMARY KEY, inquiry_id TEXT NOT NULL,
        owner_digest BLOB NOT NULL, project_id TEXT NOT NULL,
        source_system TEXT NOT NULL, source_instance TEXT NOT NULL,
        sequence INTEGER NOT NULL CHECK(sequence >= 1), prior_event_id TEXT,
        quote_id TEXT NOT NULL, operation TEXT NOT NULL,
        idempotency_hash BLOB NOT NULL, request_hash BLOB NOT NULL,
        request_json TEXT NOT NULL, actor_ref TEXT NOT NULL,
        policy_version TEXT NOT NULL, recorded_at INTEGER NOT NULL,
        UNIQUE(inquiry_id, sequence),
        UNIQUE(owner_digest,project_id,source_system,source_instance,inquiry_id,idempotency_hash)
    );
    CREATE TABLE IF NOT EXISTS ruby_quote_custody_receipts (
        event_id TEXT PRIMARY KEY, inquiry_id TEXT NOT NULL,
        idempotency_hash BLOB NOT NULL, request_hash BLOB NOT NULL, response_json TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ruby_quote_custody_audit (
        event_id TEXT PRIMARY KEY, inquiry_id TEXT NOT NULL,
        quote_id TEXT NOT NULL, operation TEXT NOT NULL,
        request_hash BLOB NOT NULL, policy_version TEXT NOT NULL,
        recorded_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ruby_quote_custody_heads (
        inquiry_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
        sequence INTEGER NOT NULL CHECK(sequence >= 1)
    );
    """)


def _identifier(value, *, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not str or not IDENTIFIER.fullmatch(value):
        raise error("invalid_quote_custody")


def validate_custody(body):
    value = decode(body)
    if type(value) is not dict:
        raise error("invalid_quote_custody")
    operation = value.get("operation")
    common = {"schema_version", "operation", "expected_event_id", "quote_id"}
    if operation == "select":
        _object(value, common | {"quote_fingerprint", "consent_text"})
        _text(value["consent_text"], 2000, multiline=True)
    elif operation == "respond":
        _object(value, common | {"quote_fingerprint", "consent_fingerprint", "decision"})
        if value["decision"] not in ("accept", "decline"):
            raise error("invalid_quote_custody")
        if type(value["consent_fingerprint"]) is not str or not FP.fullmatch(value["consent_fingerprint"]):
            raise error("invalid_quote_custody")
    elif operation == "withdraw":
        _object(value, common)
    else:
        raise error("invalid_quote_custody")
    if value["schema_version"] != SCHEMA:
        raise error("invalid_quote_custody")
    _identifier(value["quote_id"])
    _identifier(value["expected_event_id"], nullable=True)
    if operation != "withdraw" and (type(value["quote_fingerprint"]) is not str or not FP.fullmatch(value["quote_fingerprint"])):
        raise error("invalid_quote_custody")
    return value, hashlib.sha256(canonical(value)).digest()


def fingerprint(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


class RubyQuoteCustodyMixin:
    def _custody_policy(self, context):
        policy = self._quote_policy(context)
        if self._ruby_quote_custody_enabled is not True or policy.quote_custody_enabled is not True:
            raise error("quote_custody_policy_unavailable", 503)
        return policy

    @staticmethod
    def _custody_unknown():
        return {"schema_version": SCHEMA, "state": "unknown",
                "reason": "quote_custody_history_unavailable", **NO_QUOTE_AUTHORITY}

    @staticmethod
    def _custody_receipt(row):
        return {"schema_version": SCHEMA, "state": "synthetic_event_recorded",
                "event_id": row["event_id"], "inquiry_id": row["inquiry_id"],
                "quote_id": row["quote_id"], "operation": row["operation"],
                "request_fingerprint": "sha256:" + row["request_hash"].hex(),
                "recorded_at": row["recorded_at"], "actor_ref": row["actor_ref"],
                "customer_identity_verified": False, "current_quote_verified": False,
                **NO_QUOTE_AUTHORITY}

    def _custody_history(self, context, inquiry_id):
        """Validate complete retained chain; any missing fragment fails closed."""
        connection = self._live.connection
        rows = connection.execute("SELECT * FROM ruby_quote_custody_events WHERE inquiry_id=? ORDER BY sequence", (inquiry_id,)).fetchall()
        head = connection.execute("SELECT * FROM ruby_quote_custody_heads WHERE inquiry_id=?", (inquiry_id,)).fetchone()
        audit_count = connection.execute("SELECT COUNT(*) FROM ruby_quote_custody_audit WHERE inquiry_id=?", (inquiry_id,)).fetchone()[0]
        receipt_count = connection.execute("SELECT COUNT(*) FROM ruby_quote_custody_receipts WHERE inquiry_id=?", (inquiry_id,)).fetchone()[0]
        if head is None:
            return [] if not rows and not audit_count and not receipt_count else None
        if len(rows) != head["sequence"] or audit_count != len(rows) or receipt_count != len(rows) or not rows or rows[-1]["event_id"] != head["event_id"]:
            return None
        prior = None
        for number, row in enumerate(rows, 1):
            if (row["owner_digest"], row["project_id"], row["source_system"], row["source_instance"]) != (self._owner, *self._inquiry_scope(context)):
                raise error("quote_custody_binding_mismatch", 409)
            value, request_hash = validate_custody(row["request_json"].encode())
            if (row["sequence"] != number or row["prior_event_id"] != prior or value["expected_event_id"] != prior or
                    value["quote_id"] != row["quote_id"] or value["operation"] != row["operation"] or request_hash != row["request_hash"]):
                raise error("quote_custody_binding_mismatch", 409)
            receipt = connection.execute("SELECT * FROM ruby_quote_custody_receipts WHERE event_id=?", (row["event_id"],)).fetchone()
            audit = connection.execute("SELECT * FROM ruby_quote_custody_audit WHERE event_id=?", (row["event_id"],)).fetchone()
            if receipt is None or audit is None:
                return None
            if (receipt["inquiry_id"] != inquiry_id or receipt["idempotency_hash"] != row["idempotency_hash"] or receipt["request_hash"] != request_hash or
                    canonical(decode(receipt["response_json"].encode())) != canonical(self._custody_receipt(row)) or
                    any(audit[key] != row[key] for key in ("inquiry_id", "quote_id", "operation", "request_hash", "policy_version", "recorded_at"))):
                raise error("quote_custody_binding_mismatch", 409)
            prior = row["event_id"]
        return rows

    def _custody_quote(self, context, inquiry_id, quote_id, policy):
        row = self._live.connection.execute("SELECT * FROM ruby_finalized_quote_events WHERE quote_id=? AND inquiry_id=? AND owner_digest=? AND project_id=? AND source_system=? AND source_instance=?", (quote_id, inquiry_id, self._owner, *self._inquiry_scope(context))).fetchone()
        if row is None:
            return None
        receipt = self._quote_recover(context, inquiry_id, self._quote_rows(context, inquiry_id, row["idempotency_hash"]), row["request_hash"], policy)
        return None if receipt["state"] == "unknown" else receipt

    def _custody_actor(self, context, inquiry_id, value, request_hash, quote):
        if value["operation"] != "respond":
            return "synthetic-owner"
        try:
            result = self._ruby_quote_synthetic_verifier(context, inquiry_id, value["quote_id"], quote["customer_ref"], "sha256:" + request_hash.hex())
        except Exception:
            raise error("synthetic_verification_unavailable", 503) from None
        if (type(result) is not SyntheticResponseVerification or result.synthetic_only is not True or
                (result.inquiry_id, result.quote_id, result.customer_ref, result.request_fingerprint) !=
                (inquiry_id, value["quote_id"], quote["customer_ref"], "sha256:" + request_hash.hex()) or
                type(result.actor_ref) is not str or not re.fullmatch(r"synthetic:[A-Za-z0-9_.-]{1,100}", result.actor_ref)):
            raise error("synthetic_verification_rejected", 403)
        return result.actor_ref

    def _custody_stage(self, stage):
        """Private local fault injection seam, never an external hook."""

    def record_ruby_quote_custody(self, context, inquiry_id, idempotency_key, request_body):
        with self._lock:
            policy = self._custody_policy(context)
            value, request_hash = validate_custody(request_body)
            if type(idempotency_key) is not str:
                raise error("invalid_idempotency_key")
            key_hash = self._idempotency(idempotency_key)
            owned = self._inquiry_owned(context, inquiry_id)
            if owned is None:
                raise error("not_found", 404)
            history = self._custody_history(context, inquiry_id)
            if history is None:
                return self._custody_unknown()
            prior_request = next((row for row in history if hmac.compare_digest(row["idempotency_hash"], key_hash)), None)
            if prior_request is not None and not hmac.compare_digest(prior_request["request_hash"], request_hash):
                raise error("idempotency_conflict", 409)
            quote = self._custody_quote(context, inquiry_id, value["quote_id"], policy)
            if quote is None:
                return self._custody_unknown()
            actor = self._custody_actor(context, inquiry_id, value, request_hash, quote)
            if prior_request is not None:
                if prior_request["actor_ref"] != actor:
                    raise error("idempotency_conflict", 409)
                return self._custody_receipt(prior_request)
            head_id = history[-1]["event_id"] if history else None
            if value["expected_event_id"] != head_id:
                raise error("stale_quote_custody", 409)
            if owned["current_revision_id"] != quote["revision_id"]:
                raise error("stale_revision", 409)
            if value["operation"] == "select":
                if any(row["quote_id"] == value["quote_id"] for row in history):
                    raise error("quote_already_selected", 409)
                if value["quote_fingerprint"] != quote["request_fingerprint"]:
                    raise error("quote_custody_binding_mismatch", 409)
            else:
                if not history or history[-1]["operation"] == "withdraw" or history[-1]["quote_id"] != value["quote_id"]:
                    raise error("quote_not_current", 409)
                if value["operation"] == "respond":
                    if history[-1]["operation"] != "select":
                        raise error("quote_already_responded", 409)
                    selected = decode(history[-1]["request_json"].encode())
                    if (value["quote_fingerprint"] != quote["request_fingerprint"] or
                            value["consent_fingerprint"] != fingerprint(selected["consent_text"].encode())):
                        raise error("quote_custody_binding_mismatch", 409)
            row = dict(event_id=self._identifier("ruby-quote-custody"), inquiry_id=inquiry_id,
                       sequence=len(history)+1, prior_event_id=head_id, quote_id=value["quote_id"],
                       operation=value["operation"], request_hash=request_hash, actor_ref=actor,
                       policy_version=policy.policy_version, recorded_at=int(time.time()))
            receipt = self._custody_receipt(row)
            connection = self._live.connection
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("INSERT INTO ruby_quote_custody_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (row["event_id"], inquiry_id, self._owner, *self._inquiry_scope(context), row["sequence"], head_id, value["quote_id"], value["operation"], key_hash, request_hash, canonical(value).decode(), actor, policy.policy_version, row["recorded_at"]))
                self._custody_stage("event")
                connection.execute("INSERT INTO ruby_quote_custody_receipts VALUES (?,?,?,?,?)", (row["event_id"], inquiry_id, key_hash, request_hash, canonical(receipt).decode()))
                self._custody_stage("receipt")
                connection.execute("INSERT INTO ruby_quote_custody_audit VALUES (?,?,?,?,?,?,?)", (row["event_id"], inquiry_id, value["quote_id"], value["operation"], request_hash, policy.policy_version, row["recorded_at"]))
                self._custody_stage("audit")
                connection.execute("INSERT INTO ruby_quote_custody_heads VALUES (?,?,?) ON CONFLICT(inquiry_id) DO UPDATE SET event_id=excluded.event_id,sequence=excluded.sequence", (inquiry_id, row["event_id"], row["sequence"]))
                self._custody_stage("head")
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise error("quote_custody_write_failed", 503) from None
            try:
                self._live.persist()
            except Exception:
                self._persistence_fenced = True
                raise error("quote_custody_outcome_unknown", 503) from None
            return receipt

    def resolve_ruby_quote_custody_receipt(self, context, inquiry_id, idempotency_key, request_body):
        with self._lock:
            policy = self._custody_policy(context)
            value, request_hash = validate_custody(request_body)
            if type(idempotency_key) is not str:
                raise error("invalid_idempotency_key")
            key_hash = self._idempotency(idempotency_key)
            if self._inquiry_owned(context, inquiry_id) is None:
                return self._custody_unknown()
            history = self._custody_history(context, inquiry_id)
            if history is not None:
                for row in history:
                    if hmac.compare_digest(row["idempotency_hash"], key_hash):
                        if not hmac.compare_digest(row["request_hash"], request_hash):
                            raise error("idempotency_conflict", 409)
                        if self._custody_quote(context, inquiry_id, row["quote_id"], policy) is None:
                            return self._custody_unknown()
                        return self._custody_receipt(row)
            return self._custody_unknown()

    def get_ruby_quote_custody(self, context, inquiry_id):
        with self._lock:
            policy = self._custody_policy(context)
            owned = self._inquiry_owned(context, inquiry_id)
            if owned is None:
                raise error("not_found", 404)
            history = self._custody_history(context, inquiry_id)
            if not history:
                return self._custody_unknown()
            last = history[-1]
            quote = self._custody_quote(context, inquiry_id, last["quote_id"], policy)
            if quote is None:
                return self._custody_unknown()
            state = "synthetic_current_offer"
            if last["operation"] == "withdraw":
                state = "withdrawn"
            elif owned["current_revision_id"] != quote["revision_id"]:
                state = "stale_inquiry_revision"
            decision = decode(last["request_json"].encode()).get("decision") if last["operation"] == "respond" else None
            return {"schema_version": SCHEMA, "state": state, "event_id": last["event_id"],
                    "quote_id": last["quote_id"], "quote_fingerprint": quote["request_fingerprint"],
                    "synthetic_decision": decision, "cache_control": "no-store",
                    "customer_identity_verified": False, "current_quote_verified": False,
                    **NO_QUOTE_AUTHORITY}
