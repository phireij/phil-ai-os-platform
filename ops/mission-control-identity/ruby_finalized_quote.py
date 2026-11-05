"""Opt-in synthetic owner-recorded quote content. No customer acceptance or execution.

Custody lives exclusively in ConversationStore's encrypted snapshot. There is
no route, identity authority, provider, catalog reprice, or payment capability.
"""
from __future__ import annotations
import hashlib
import hmac
import re
import time
from datetime import date
from ruby_inquiry import (canonical, decode, error, _object, _text, _opaque, _int,
                          IDENTIFIER, NO_AUTHORITY)

SCHEMA = "ruby.finalized-quote-record.v1"
# V2 versions the request body only. Both bodies use the original V1 receipt:
# its fingerprint binds the exact retained body, not an approval or verification.
STAFF_SCHEMA = "ruby.finalized-quote-record.v2"
SOURCE_REVIEW_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
NO_QUOTE_AUTHORITY = {**NO_AUTHORITY, "customer_accepted": False,
    "date_verified": False, "packing_verified": False, "shipping_verified": False,
    "payment_request_authorized": False, "payment_execution_authorized": False,
    "ready_for_payment_request_review": False}


def initialize_finalized_quotes(connection):
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS ruby_finalized_quote_events (
        quote_id TEXT PRIMARY KEY,
        inquiry_id TEXT NOT NULL REFERENCES ruby_custom_inquiries(inquiry_id),
        revision_id TEXT NOT NULL REFERENCES ruby_custom_inquiry_revisions(revision_id),
        owner_digest BLOB NOT NULL, project_id TEXT NOT NULL,
        source_system TEXT NOT NULL, source_instance TEXT NOT NULL,
        idempotency_hash BLOB NOT NULL, request_hash BLOB NOT NULL,
        request_json TEXT NOT NULL, customer_ref TEXT NOT NULL,
        policy_version TEXT NOT NULL, recorded_at INTEGER NOT NULL,
        UNIQUE(owner_digest,project_id,source_system,source_instance,inquiry_id,idempotency_hash)
    );
    CREATE TABLE IF NOT EXISTS ruby_finalized_quote_receipts (
        quote_id TEXT PRIMARY KEY,
        owner_digest BLOB NOT NULL, project_id TEXT NOT NULL,
        source_system TEXT NOT NULL, source_instance TEXT NOT NULL,
        inquiry_id TEXT NOT NULL, revision_id TEXT NOT NULL,
        idempotency_hash BLOB NOT NULL, request_hash BLOB NOT NULL,
        response_json TEXT NOT NULL,
        UNIQUE(owner_digest,project_id,source_system,source_instance,inquiry_id,idempotency_hash)
    );
    CREATE TABLE IF NOT EXISTS ruby_finalized_quote_audit (
        quote_id TEXT PRIMARY KEY,
        owner_digest BLOB NOT NULL, project_id TEXT NOT NULL,
        source_system TEXT NOT NULL, source_instance TEXT NOT NULL,
        inquiry_id TEXT NOT NULL, revision_id TEXT NOT NULL,
        idempotency_hash BLOB NOT NULL, request_hash BLOB NOT NULL,
        policy_version TEXT NOT NULL, recorded_at INTEGER NOT NULL,
        operation TEXT NOT NULL CHECK(operation='owner_quote_recorded')
    );
    """)


def validate_quote(body):
    value = decode(body)
    fields = {"schema_version", "expected_revision_id", "source_quote_ref", "currency", "items", "shipping_yen", "total_yen", "fulfillment"}
    staff_body = type(value) is dict and value.get("schema_version") == STAFF_SCHEMA
    _object(value, fields | {"staff_declaration"} if staff_body else fields)
    if value["schema_version"] not in (SCHEMA, STAFF_SCHEMA) or value["currency"] != "JPY":
        raise error("invalid_quote")
    if staff_body:
        declaration = value["staff_declaration"]
        _object(declaration, {"operator_ref", "source_review_fingerprint",
            "date_confirmed", "packing_confirmed", "shipping_confirmed",
            "packing_description", "verification"})
        _opaque(declaration["operator_ref"])
        if (type(declaration["source_review_fingerprint"]) is not str or
                not SOURCE_REVIEW_FINGERPRINT.fullmatch(declaration["source_review_fingerprint"]) or
                declaration["verification"] != "unverified_operator_declaration" or
                any(declaration[key] is not True for key in
                    ("date_confirmed", "packing_confirmed", "shipping_confirmed"))):
            raise error("invalid_quote")
        _text(declaration["packing_description"], 200)
        if declaration["packing_description"] != declaration["packing_description"].strip():
            raise error("invalid_quote")
        # These are explicitly unverified declarations, not staff authentication,
        # source-review verification, capacity checks or execution authority.
    if type(value["expected_revision_id"]) is not str or not IDENTIFIER.fullmatch(value["expected_revision_id"]):
        raise error("invalid_quote")
    _opaque(value["source_quote_ref"])
    items = value["items"]
    if type(items) is not list or not 1 <= len(items) <= 100:
        raise error("invalid_quote")
    seen, subtotal = set(), 0
    for item in items:
        _object(item, {"line_ref", "description", "quantity", "unit_price_yen", "line_total_yen"})
        _opaque(item["line_ref"])
        _text(item["description"], 200)
        if item["description"] != item["description"].strip() or item["line_ref"] in seen:
            raise error("invalid_quote")
        seen.add(item["line_ref"])
        _int(item["quantity"], 1, 1000)
        _int(item["unit_price_yen"], 0, 10_000_000)
        _int(item["line_total_yen"], 0, 10_000_000)
        if item["quantity"] * item["unit_price_yen"] != item["line_total_yen"]:
            raise error("invalid_quote")
        subtotal += item["line_total_yen"]
    for key in ("shipping_yen", "total_yen"):
        _int(value[key], 0, 10_000_000)
    if subtotal + value["shipping_yen"] != value["total_yen"]:
        raise error("invalid_quote")
    f = value["fulfillment"]
    _object(f, {"method", "date", "time_window", "packing_plan_ref"})
    if f["method"] not in ("pickup", "yamato", "ruby-car"):
        raise error("invalid_quote")
    _text(f["date"], 10)
    try:
        if date.fromisoformat(f["date"]).isoformat() != f["date"]:
            raise ValueError()
    except ValueError:
        raise error("invalid_quote") from None
    _text(f["time_window"], 100)
    _opaque(f["packing_plan_ref"])
    return value, hashlib.sha256(canonical(value)).digest()


class RubyFinalizedQuoteMixin:
    def _quote_policy(self, context):
        policy = self._inquiry_policy(context)
        if self._ruby_finalized_quotes_enabled is not True or policy.finalized_quotes_enabled is not True:
            raise error("quote_policy_unavailable", 503)
        return policy

    @staticmethod
    def _quote_unknown():
        return {"schema_version": SCHEMA, "state": "unknown", "reason": "quote_history_unavailable", **NO_QUOTE_AUTHORITY}

    def _quote_rows(self, context, inquiry_id, key_hash):
        scope = (self._owner, *self._inquiry_scope(context), inquiry_id, key_hash)
        return [self._live.connection.execute(
            "SELECT * FROM " + table + " WHERE owner_digest=? AND project_id=? AND source_system=? AND source_instance=? AND inquiry_id=? AND idempotency_hash=?", scope).fetchall()
            for table in ("ruby_finalized_quote_events", "ruby_finalized_quote_receipts", "ruby_finalized_quote_audit")]

    def _quote_customer_ref(self, revision, policy):
        request = decode(revision["request_json"].encode())
        if hashlib.sha256(canonical(request)).digest() != revision["request_hash"]:
            raise error("quote_binding_mismatch", 409)
        inquiry = request if revision["revision_number"] == 1 else request["inquiry"]
        self._inquiry_payload(inquiry, policy, current_catalog=False)
        # A declared synthetic contact fingerprint, not verified customer identity.
        return "declared-synthetic-sha256:" + hashlib.sha256(canonical({"inquiry_id": revision["inquiry_id"], "contact": {key: inquiry["contact"][key] for key in ("kind", "destination")}})).hexdigest()

    @staticmethod
    def _quote_receipt(event):
        return {"schema_version": SCHEMA, "state": "owner_quote_recorded",
            "quote_id": event["quote_id"], "inquiry_id": event["inquiry_id"],
            "revision_id": event["revision_id"], "recorded_at": event["recorded_at"],
            "request_fingerprint": "sha256:" + event["request_hash"].hex(),
            "customer_ref": event["customer_ref"], "customer_identity": "declared_synthetic_unverified",
            **NO_QUOTE_AUTHORITY}

    def _quote_recover(self, context, inquiry_id, rows, request_hash, policy):
        # Every retained fragment reserves the key. No replacement receipts.
        for group in rows:
            for row in group:
                if not hmac.compare_digest(row["request_hash"], request_hash):
                    raise error("idempotency_conflict", 409)
        if any(len(group) != 1 for group in rows):
            return self._quote_unknown()
        event, receipt, audit = (group[0] for group in rows)
        fields = ("quote_id", "owner_digest", "project_id", "source_system", "source_instance", "inquiry_id", "revision_id", "idempotency_hash", "request_hash")
        if any(row[key] != event[key] for row in (receipt, audit) for key in fields):
            raise error("quote_binding_mismatch", 409)
        if audit["policy_version"] != event["policy_version"] or audit["recorded_at"] != event["recorded_at"] or audit["operation"] != "owner_quote_recorded":
            raise error("quote_binding_mismatch", 409)
        revision = self._live.connection.execute("SELECT * FROM ruby_custom_inquiry_revisions WHERE revision_id=? AND inquiry_id=?", (event["revision_id"], inquiry_id)).fetchone()
        if revision is None:
            return self._quote_unknown()
        value, hashed = validate_quote(event["request_json"].encode())
        if hashed != request_hash or value["expected_revision_id"] != event["revision_id"] or event["customer_ref"] != self._quote_customer_ref(revision, policy):
            raise error("quote_binding_mismatch", 409)
        expected = self._quote_receipt(event)
        response = decode(receipt["response_json"].encode())
        if canonical(response) != canonical(expected):
            raise error("quote_binding_mismatch", 409)
        return response

    def _quote_stage(self, stage):
        """Private synthetic fault injection seam; no external effects."""

    def record_ruby_finalized_quote(self, context, inquiry_id, idempotency_key, request_body):
        with self._lock:
            policy = self._quote_policy(context)
            value, request_hash = validate_quote(request_body)
            if type(idempotency_key) is not str:
                raise error("invalid_idempotency_key")
            key_hash = self._idempotency(idempotency_key)
            owned = self._inquiry_owned(context, inquiry_id)
            if owned is None:
                raise error("not_found", 404)
            rows = self._quote_rows(context, inquiry_id, key_hash)
            if any(rows):
                return self._quote_recover(context, inquiry_id, rows, request_hash, policy)
            revision_id = value["expected_revision_id"]
            if owned["current_revision_id"] != revision_id:
                raise error("stale_revision", 409)
            connection = self._live.connection
            revision = connection.execute("SELECT * FROM ruby_custom_inquiry_revisions WHERE revision_id=? AND inquiry_id=?", (revision_id, inquiry_id)).fetchone()
            if revision is None:
                return self._quote_unknown()
            customer_ref = self._quote_customer_ref(revision, policy)
            now, quote_id = int(time.time()), self._identifier("ruby-finalized-quote")
            event = dict(quote_id=quote_id, inquiry_id=inquiry_id, revision_id=revision_id, recorded_at=now, request_hash=request_hash, customer_ref=customer_ref)
            result = self._quote_receipt(event)
            scope = (self._owner, *self._inquiry_scope(context))
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("INSERT INTO ruby_finalized_quote_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (quote_id, inquiry_id, revision_id, *scope, key_hash, request_hash, canonical(value).decode(), customer_ref, policy.policy_version, now))
                self._quote_stage("event")
                connection.execute("INSERT INTO ruby_finalized_quote_receipts VALUES (?,?,?,?,?,?,?,?,?,?)", (quote_id, *scope, inquiry_id, revision_id, key_hash, request_hash, canonical(result).decode()))
                self._quote_stage("receipt")
                connection.execute("INSERT INTO ruby_finalized_quote_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (quote_id, *scope, inquiry_id, revision_id, key_hash, request_hash, policy.policy_version, now, "owner_quote_recorded"))
                self._quote_stage("audit")
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise error("quote_write_failed", 503) from None
            try:
                self._live.persist()
            except Exception:
                self._persistence_fenced = True
                raise error("quote_outcome_unknown", 503) from None
            return result

    def resolve_ruby_finalized_quote_receipt(self, context, inquiry_id, idempotency_key, request_body):
        with self._lock:
            policy = self._quote_policy(context)
            value, request_hash = validate_quote(request_body)
            if type(idempotency_key) is not str:
                raise error("invalid_idempotency_key")
            key_hash = self._idempotency(idempotency_key)
            if self._inquiry_owned(context, inquiry_id) is None:
                return self._quote_unknown()
            return self._quote_recover(context, inquiry_id, self._quote_rows(context, inquiry_id, key_hash), request_hash, policy)

    def get_ruby_finalized_quote(self, context, inquiry_id, quote_id):
        with self._lock:
            policy = self._quote_policy(context)
            if self._inquiry_owned(context, inquiry_id) is None or type(quote_id) is not str or not IDENTIFIER.fullmatch(quote_id):
                raise error("not_found", 404)
            row = self._live.connection.execute("SELECT * FROM ruby_finalized_quote_events WHERE quote_id=? AND inquiry_id=? AND owner_digest=? AND project_id=? AND source_system=? AND source_instance=?", (quote_id, inquiry_id, self._owner, *self._inquiry_scope(context))).fetchone()
            if row is None:
                return self._quote_unknown()
            result = self._quote_recover(context, inquiry_id, self._quote_rows(context, inquiry_id, row["idempotency_hash"]), row["request_hash"], policy)
            if result["state"] == "unknown":
                return result
            return {"receipt": result, "quote": decode(row["request_json"].encode()), "cache_control": "no-store", **NO_QUOTE_AUTHORITY}
