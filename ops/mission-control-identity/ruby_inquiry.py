"""Dedicated closed Ruby complete-inquiry contract, source-only synthetic mode.

Methods run in the existing owner-bound encrypted ConversationStore. Nothing
registers them on a route, chooses production policy, or sends a reply.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Callable

SCHEMA = "ruby.custom-inquiry.v1"
SOURCE_ENVELOPE = "ruby.inquiry-source-custody.v1"
MAX_BODY = 128 * 1024
MAX_SAFE_INTEGER = 2**53 - 1
REQUIRED_CART_BLOCKERS = frozenset({
    "physical_carton_fit_unverified", "packed_weight_unverified",
    "stock_or_production_capacity_unverified", "fulfillment_date_and_fee_unconfirmed",
})
NO_AUTHORITY = {
    "authority_effect": "none", "customer_confirmation": False,
    "order_authorized": False, "payment_authorized": False,
    "inventory_authorized": False, "dispatch_authorized": False,
    "send_authorized": False, "publication_authorized": False,
}
OPAQUE = re.compile(r"[A-Za-z0-9_.:-]{1,120}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{16,200}\Z")


def error(code="invalid_inquiry", status=400):
    from conversation_store import ConversationRequestError
    return ConversationRequestError(code, status)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise error()


def _text(value, maximum, *, empty=False, multiline=False):
    if type(value) is not str or len(value) > maximum or (not empty and not value):
        raise error()
    for char in value:
        if unicodedata.category(char).startswith("C") and not (multiline and char in "\n\t"):
            raise error()
    return value


def _opaque(value):
    if type(value) is not str or not OPAQUE.fullmatch(value):
        raise error()
    return value


def _int(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise error()


def decode(body):
    if type(body) is not bytes or len(body) > MAX_BODY:
        raise error("inquiry_body_invalid")
    def pairs(entries):
        value = {}
        for key, entry in entries:
            if key in value:
                raise ValueError("duplicate")
            value[key] = entry
        return value
    def reject_constant(value):
        raise ValueError("constant")
    try:
        return json.loads(body.decode("utf-8", "strict"), object_pairs_hook=pairs, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise error("inquiry_body_invalid") from None


@dataclass(frozen=True)
class RubyInquiryContext:
    """Trusted server-injected context, never constructed from the JSON body."""
    issuer: str
    subject: str
    project_id: str
    source_system: str
    source_instance: str


@dataclass(frozen=True)
class RubyInquiryPolicy:
    project_id: str
    source_system: str
    source_instance: str
    policy_version: str
    allowed_contact_channels: frozenset[str] = frozenset()
    synthetic_only: bool = True
    catalog_revision: str | None = None
    catalog_prices: tuple[tuple[str, int], ...] = ()
    finalized_quotes_enabled: bool = False
    quote_custody_enabled: bool = False
    quote_consent_enabled: bool = False
    source_handoff_retention_enabled: bool = False


PolicyResolver = Callable[[RubyInquiryContext], RubyInquiryPolicy | None]


def initialize_inquiries(connection):
    connection.executescript("""
    CREATE TABLE IF NOT EXISTS ruby_custom_inquiries (
        inquiry_id TEXT PRIMARY KEY, owner_digest BLOB NOT NULL,
        project_id TEXT NOT NULL, source_system TEXT NOT NULL, source_instance TEXT NOT NULL,
        current_revision_id TEXT NOT NULL, created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ruby_custom_inquiry_revisions (
        revision_id TEXT PRIMARY KEY,
        inquiry_id TEXT NOT NULL REFERENCES ruby_custom_inquiries(inquiry_id),
        revision_number INTEGER NOT NULL CHECK(revision_number >= 1),
        prior_revision_id TEXT,
        request_hash BLOB NOT NULL, request_json TEXT NOT NULL,
        operation TEXT NOT NULL, idempotency_hash BLOB NOT NULL,
        policy_version TEXT NOT NULL, created_at INTEGER NOT NULL,
        UNIQUE(inquiry_id, revision_number)
    );
    CREATE TABLE IF NOT EXISTS ruby_custom_inquiry_receipts (
        owner_digest BLOB NOT NULL, project_id TEXT NOT NULL,
        source_system TEXT NOT NULL, source_instance TEXT NOT NULL,
        operation TEXT NOT NULL, idempotency_hash BLOB NOT NULL,
        request_hash BLOB NOT NULL, inquiry_id TEXT NOT NULL,
        revision_id TEXT NOT NULL, response_json TEXT NOT NULL,
        PRIMARY KEY(owner_digest, project_id, source_system, source_instance, operation, idempotency_hash)
    );
    CREATE TABLE IF NOT EXISTS ruby_custom_inquiry_audit (
        event_id TEXT PRIMARY KEY,
        inquiry_id TEXT NOT NULL REFERENCES ruby_custom_inquiries(inquiry_id),
        revision_id TEXT NOT NULL REFERENCES ruby_custom_inquiry_revisions(revision_id),
        owner_digest BLOB NOT NULL, project_id TEXT NOT NULL,
        source_system TEXT NOT NULL, source_instance TEXT NOT NULL,
        policy_version TEXT NOT NULL, operation TEXT NOT NULL CHECK(operation IN ('create','revise')),
        occurred_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ruby_inquiries_owner_source
        ON ruby_custom_inquiries(owner_digest,project_id,source_system,source_instance,created_at,inquiry_id);
    """)


class RubyInquiryMixin:
    def _inquiry_policy(self, context):
        if self._readonly_preflight:
            raise error("inquiry_readonly", 503)
        if type(context) is not RubyInquiryContext or not self.matches_owner_context(context.issuer, context.subject):
            raise error("inquiry_access_denied", 403)
        if self._ruby_inquiry_policy is None:
            raise error("inquiry_policy_unavailable", 503)
        try:
            policy = self._ruby_inquiry_policy(context)
        except Exception:
            raise error("inquiry_policy_unavailable", 503) from None
        if type(policy) is not RubyInquiryPolicy or policy.synthetic_only is not True:
            raise error("inquiry_policy_unavailable", 503)
        if (policy.project_id, policy.source_system, policy.source_instance) != (context.project_id, context.source_system, context.source_instance):
            raise error("inquiry_access_denied", 403)
        for value in (policy.project_id, policy.source_system, policy.source_instance, policy.policy_version):
            _opaque(value)
        if type(policy.allowed_contact_channels) is not frozenset or not policy.allowed_contact_channels or not policy.allowed_contact_channels <= {"email"}:
            raise error("inquiry_policy_unavailable", 503)
        try:
            if type(policy.catalog_prices) is not tuple:
                raise ValueError()
            seen = set()
            for item in policy.catalog_prices:
                if type(item) is not tuple or len(item) != 2:
                    raise ValueError()
                sku, price = item
                _text(sku, 128)
                _int(price, 1, MAX_SAFE_INTEGER)
                if sku in seen or sku != sku.strip():
                    raise ValueError()
                seen.add(sku)
            if policy.catalog_revision is not None:
                _opaque(policy.catalog_revision)
        except Exception:
            raise error("inquiry_policy_unavailable", 503) from None
        return policy

    @staticmethod
    def _inquiry_payload(value, policy, *, current_catalog):
        if type(value) is dict and any(k in value for k in ("images", "reference_images", "uploads")):
            raise error("inquiry_uploads_unsupported")
        _object(value, {"schema_version", "source_request_ref", "contact", "customization", "fulfillment", "cart"})
        if value["schema_version"] != SCHEMA:
            raise error()
        _opaque(value["source_request_ref"])
        contact = value["contact"]
        if type(contact) is not dict or set(contact) not in ({"kind", "destination"}, {"kind", "destination", "display_name"}):
            raise error()
        if type(contact["kind"]) is not str or contact["kind"] not in policy.allowed_contact_channels:
            raise error("inquiry_contact_channel_unsupported")
        _text(contact["destination"], 512)
        # Deliberate fail-closed synthetic milestone, NOT a production email validator.
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@example\.invalid", contact["destination"]):
            raise error("inquiry_synthetic_contact_required")
        if "display_name" in contact:
            _text(contact["display_name"], 120, empty=True)
        custom = value["customization"]
        if type(custom) is dict and any(k in custom for k in ("images", "reference_images", "referenceImages", "referenceImageCount")):
            raise error("inquiry_uploads_unsupported")
        _object(custom, {"cake_type", "custom_notes", "photo_topper", "edible_topper", "addons", "icing_requested"})
        if custom["cake_type"] not in ("basic", "custom"):
            raise error()
        _text(custom["custom_notes"], 4000, empty=True, multiline=True)
        for key in ("photo_topper", "edible_topper", "icing_requested"):
            if type(custom[key]) is not bool:
                raise error()
        if custom["cake_type"] == "basic" and (custom["custom_notes"] != "" or custom["photo_topper"] or custom["edible_topper"]):
            raise error()
        addons = custom["addons"]
        if type(addons) is not list or len(addons) > 3 or any(type(v) is not str or v not in {"candles", "number-candle", "message-plaque"} for v in addons) or len(set(addons)) != len(addons):
            raise error()
        fulfillment = value["fulfillment"]
        _object(fulfillment, {"method", "requested_date", "pickup_time", "yamato_window"})
        if fulfillment["method"] not in ("pickup", "yamato", "ruby-car"):
            raise error()
        requested = fulfillment["requested_date"]
        if type(requested) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", requested, re.ASCII):
            raise error()
        try:
            date.fromisoformat(requested)
        except ValueError:
            raise error() from None
        pickup = fulfillment["pickup_time"]
        if type(pickup) is not str or (pickup != "" and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", pickup, re.ASCII)):
            raise error()
        if fulfillment["method"] != "pickup" and pickup != "":
            raise error()
        if fulfillment["yamato_window"] not in ("none", "08-12", "14-16", "16-18", "18-20", "19-21"):
            raise error()
        if fulfillment["method"] != "yamato" and fulfillment["yamato_window"] != "none":
            raise error()
        cart = value["cart"]
        if cart is not None:
            _object(cart, {"catalog_revision", "items", "subtotal_minor", "unresolved_blockers"})
            _opaque(cart["catalog_revision"])
            items = cart["items"]
            if type(items) is not list or not 1 <= len(items) <= 100:
                raise error()
            prices = dict(policy.catalog_prices) if current_catalog else {}
            if current_catalog and (policy.catalog_revision is None or cart["catalog_revision"] != policy.catalog_revision):
                raise error("inquiry_catalog_conflict", 409)
            skus, subtotal = set(), 0
            for item in items:
                _object(item, {"sku", "quantity", "unit_price_minor", "line_total_minor"})
                _text(item["sku"], 128)
                if item["sku"] != item["sku"].strip() or item["sku"] in skus:
                    raise error()
                skus.add(item["sku"])
                _int(item["quantity"], 1, 1000)
                _int(item["unit_price_minor"], 1, MAX_SAFE_INTEGER)
                _int(item["line_total_minor"], 1, MAX_SAFE_INTEGER)
                if item["quantity"] * item["unit_price_minor"] != item["line_total_minor"]:
                    raise error()
                if current_catalog and (item["sku"] not in prices or type(prices[item["sku"]]) is not int or prices[item["sku"]] != item["unit_price_minor"]):
                    raise error("inquiry_catalog_conflict", 409)
                subtotal += item["line_total_minor"]
            _int(cart["subtotal_minor"], 0, MAX_SAFE_INTEGER)
            if subtotal != cart["subtotal_minor"]:
                raise error()
            blockers = cart["unresolved_blockers"]
            if type(blockers) is not list or len(blockers) > 20:
                raise error()
            for blocker in blockers:
                _text(blocker, 500)
                if blocker != blocker.strip():
                    raise error()
            if len(set(blockers)) != len(blockers) or not REQUIRED_CART_BLOCKERS <= set(blockers):
                raise error()
        return value

    @staticmethod
    def _inquiry_scope(context):
        return (context.project_id, context.source_system, context.source_instance)

    def _inquiry_source_policy(self, policy):
        if (policy.source_handoff_retention_enabled is not True or
                not callable(self._ruby_inquiry_source_mapper)):
            raise error("inquiry_source_policy_unavailable", 503)

    @staticmethod
    def _inquiry_source(value):
        """Bound the opaque source before invoking the trusted private mapper."""
        if type(value) is not dict:
            raise error("inquiry_source_invalid")
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > 16 or count > 8192:
                raise error("inquiry_source_invalid")
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise error("inquiry_source_invalid")
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                pending.extend((child, depth + 1) for child in item)
            elif item is not None and type(item) not in (str, bool, int):
                raise error("inquiry_source_invalid")
            elif type(item) is int and not -MAX_SAFE_INTEGER <= item <= MAX_SAFE_INTEGER:
                raise error("inquiry_source_invalid")
        try:
            encoded = canonical(value)
        except (ValueError, UnicodeError, RecursionError):
            raise error("inquiry_source_invalid") from None
        if len(encoded) > MAX_BODY:
            raise error("inquiry_source_invalid")
        return encoded

    @staticmethod
    def _inquiry_split_request(value, *, revision):
        source = None
        if type(value) is dict and value.get("schema_version") == SOURCE_ENVELOPE:
            _object(value, {"schema_version", "request", "source_handoff"})
            source = value["source_handoff"]
            RubyInquiryMixin._inquiry_source(source)
            value = value["request"]
        if revision:
            _object(value, {"expected_revision_id", "inquiry"})
            prior = value["expected_revision_id"]
            if type(prior) is not str or not IDENTIFIER.fullmatch(prior):
                raise error()
            inquiry = value["inquiry"]
        else:
            inquiry, prior = value, None
        # A reserved envelope can never be nested or supplied as an inquiry.
        _object(inquiry, {"schema_version", "source_request_ref", "contact", "customization", "fulfillment", "cart"})
        if inquiry["schema_version"] != SCHEMA:
            raise error()
        return inquiry, prior, source

    def _inquiry_stored_request(self, revision):
        """Verify the complete accepted request, including any retained source."""
        try:
            value = decode(revision["request_json"].encode("utf-8"))
            if hashlib.sha256(canonical(value)).digest() != revision["request_hash"]:
                raise ValueError()
            inquiry, prior, source = self._inquiry_split_request(value, revision=revision["revision_number"] != 1)
            if prior != revision["prior_revision_id"]:
                raise ValueError()
            return inquiry, prior, source
        except Exception:
            raise error("inquiry_history_unavailable", 503) from None

    def _inquiry_request(self, body, policy, *, revision, current_catalog=False, source_handoff_body=None):
        value = decode(body)
        inquiry, prior, embedded_source = self._inquiry_split_request(value, revision=revision)
        # The envelope is internal custody representation, not a new wire format.
        if embedded_source is not None:
            raise error("inquiry_source_invalid")
        self._inquiry_payload(inquiry, policy, current_catalog=current_catalog)
        if source_handoff_body is not None:
            self._inquiry_source_policy(policy)
            source = decode(source_handoff_body)
            self._inquiry_source(source)
            value = {"schema_version": SOURCE_ENVELOPE, "request": value, "source_handoff": source}
        encoded = canonical(value)
        if len(encoded) > MAX_BODY:
            raise error("inquiry_body_invalid")
        return value, inquiry, prior, hashlib.sha256(encoded).digest()

    def _inquiry_validate_source(self, value, inquiry, policy):
        if value.get("schema_version") != SOURCE_ENVELOPE:
            return
        self._inquiry_source_policy(policy)
        try:
            # The callback receives detached data. It cannot mutate custody bytes,
            # normalized inquiry, contact, or the exact idempotency identity.
            source = decode(canonical(value["source_handoff"]))
            contact = decode(canonical(inquiry["contact"]))
            mapped = self._ruby_inquiry_source_mapper(source, contact)
            if type(mapped) is not dict or canonical(mapped) != canonical(inquiry):
                raise ValueError()
        except Exception:
            raise error("inquiry_source_mismatch") from None

    @staticmethod
    def _inquiry_unknown(operation):
        return {"schema_version": SCHEMA, "state": "unknown", "reason": "receipt_unavailable", "operation": operation, **NO_AUTHORITY}

    def _inquiry_owned(self, context, inquiry_id):
        if type(inquiry_id) is not str or not IDENTIFIER.fullmatch(inquiry_id):
            raise error("not_found", 404)
        return self._live.connection.execute(
            "SELECT * FROM ruby_custom_inquiries WHERE inquiry_id=? AND owner_digest=? AND project_id=? AND source_system=? AND source_instance=?",
            (inquiry_id, self._owner, *self._inquiry_scope(context)),
        ).fetchone()

    def _inquiry_existing(self, context, operation, key_hash):
        return self._live.connection.execute(
            "SELECT * FROM ruby_custom_inquiry_receipts WHERE owner_digest=? AND project_id=? AND source_system=? AND source_instance=? AND operation=? AND idempotency_hash=?",
            (self._owner, *self._inquiry_scope(context), operation, key_hash),
        ).fetchone()

    def _inquiry_receipt(self, context, stored, request_hash, operation, prior, inquiry_id):
        if not hmac.compare_digest(stored["request_hash"], request_hash):
            raise error("idempotency_conflict", 409)
        row = self._live.connection.execute(
            "SELECT r.*,i.owner_digest,i.project_id,i.source_system,i.source_instance FROM ruby_custom_inquiry_revisions r JOIN ruby_custom_inquiries i ON i.inquiry_id=r.inquiry_id WHERE r.revision_id=?",
            (stored["revision_id"],),
        ).fetchone()
        if row is None:
            return self._inquiry_unknown(operation)
        if (row["owner_digest"] != self._owner or (row["project_id"], row["source_system"], row["source_instance"]) != self._inquiry_scope(context)
                or row["inquiry_id"] != stored["inquiry_id"] or (inquiry_id is not None and inquiry_id != row["inquiry_id"])
                or row["prior_revision_id"] != prior or row["request_hash"] != request_hash
                or row["operation"] != stored["operation"] or row["idempotency_hash"] != stored["idempotency_hash"]):
            raise error("receipt_binding_mismatch", 409)
        try:
            full_request = decode(row["request_json"].encode("utf-8"))
            if hashlib.sha256(canonical(full_request)).digest() != request_hash:
                raise ValueError()
            expected = self._inquiry_make_receipt(operation, row["inquiry_id"], row["revision_id"], row["revision_number"], request_hash, row["created_at"])
            response = decode(stored["response_json"].encode("utf-8"))
            if canonical(response) != canonical(expected):
                raise ValueError()
        except Exception:
            raise error("receipt_binding_mismatch", 409) from None
        # The full revision and original receipt must also have the atomic audit evidence.
        audit = self._live.connection.execute("SELECT * FROM ruby_custom_inquiry_audit WHERE revision_id=?", (row["revision_id"],)).fetchall()
        if not audit:
            return self._inquiry_unknown(operation)
        if len(audit) != 1 or any(audit[0][key] != row[key] for key in ("inquiry_id", "owner_digest", "project_id", "source_system", "source_instance", "policy_version")) or audit[0]["operation"] != operation or audit[0]["occurred_at"] != row["created_at"]:
            raise error("receipt_binding_mismatch", 409)
        return response

    @staticmethod
    def _inquiry_make_receipt(operation, inquiry_id, revision_id, number, request_hash, now):
        return {
            "schema_version": SCHEMA, "state": "complete_received", "operation": operation,
            "receipt": {"inquiry_id": inquiry_id, "revision_id": revision_id, "revision_number": number,
                        "state": "pending_review", "received_at": now,
                        "request_fingerprint": "sha256:" + request_hash.hex(), **NO_AUTHORITY},
            **NO_AUTHORITY,
        }

    def _inquiry_stage(self, stage):
        """Private fault-injection seam; no production callback or external effect."""

    def create_ruby_inquiry(self, context, idempotency_key, request_body, *, source_handoff_body=None):
        return self._write_ruby_inquiry(context, None, idempotency_key, request_body, source_handoff_body=source_handoff_body)

    def revise_ruby_inquiry(self, context, inquiry_id, idempotency_key, request_body, *, source_handoff_body=None):
        return self._write_ruby_inquiry(context, inquiry_id, idempotency_key, request_body, source_handoff_body=source_handoff_body)

    def _write_ruby_inquiry(self, context, inquiry_id, idempotency_key, request_body, *, source_handoff_body=None):
        with self._lock:
            policy = self._inquiry_policy(context)
            if self._readonly_preflight:
                raise error("inquiry_readonly", 503)
            value, inquiry, prior, request_hash = self._inquiry_request(request_body, policy, revision=inquiry_id is not None, source_handoff_body=source_handoff_body)
            if type(idempotency_key) is not str:
                raise error("invalid_idempotency_key")
            key_hash = self._idempotency(idempotency_key)
            operation = "create" if inquiry_id is None else "revise"
            scoped_operation = operation if inquiry_id is None else "revise:" + inquiry_id
            owned = self._inquiry_owned(context, inquiry_id) if inquiry_id is not None else None
            if inquiry_id is not None and owned is None:
                raise error("not_found", 404)
            existing = self._inquiry_existing(context, scoped_operation, key_hash)
            if existing is not None:
                return self._inquiry_receipt(context, existing, request_hash, operation, prior, inquiry_id)
            # A missing receipt beside a matching retained revision is unknown,
            # never an invitation to mint a replacement receipt/new inquiry.
            retained = self._live.connection.execute(
                "SELECT r.request_hash FROM ruby_custom_inquiry_revisions r JOIN ruby_custom_inquiries i ON r.inquiry_id=i.inquiry_id WHERE i.owner_digest=? AND i.project_id=? AND i.source_system=? AND i.source_instance=? AND r.operation=? AND r.idempotency_hash=?",
                (self._owner, *self._inquiry_scope(context), scoped_operation, key_hash),
            ).fetchone()
            if retained:
                if not hmac.compare_digest(retained["request_hash"], request_hash):
                    raise error("idempotency_conflict", 409)
                return self._inquiry_unknown(operation)
            self._inquiry_payload(inquiry, policy, current_catalog=True)
            self._inquiry_validate_source(value, inquiry, policy)
            connection = self._live.connection
            if owned is not None:
                if owned["current_revision_id"] != prior:
                    raise error("stale_revision", 409)
                current = connection.execute("SELECT * FROM ruby_custom_inquiry_revisions WHERE revision_id=? AND inquiry_id=?", (prior, inquiry_id)).fetchone()
                if current is None:
                    return self._inquiry_unknown(operation)
                _, _, prior_source = self._inquiry_stored_request(current)
                if prior_source is not None and source_handoff_body is None:
                    raise error("inquiry_source_required", 409)
                number = current["revision_number"] + 1
            else:
                inquiry_id, number = self._identifier("ruby-inquiry"), 1
            now, revision_id = int(time.time()), self._identifier("ruby-inquiry-revision")
            result = self._inquiry_make_receipt(operation, inquiry_id, revision_id, number, request_hash, now)
            try:
                connection.execute("BEGIN IMMEDIATE")
                if owned is None:
                    connection.execute("INSERT INTO ruby_custom_inquiries VALUES (?,?,?,?,?,?,?)", (inquiry_id, self._owner, *self._inquiry_scope(context), revision_id, now))
                else:
                    connection.execute("UPDATE ruby_custom_inquiries SET current_revision_id=? WHERE inquiry_id=?", (revision_id, inquiry_id))
                self._inquiry_stage("pointer")
                connection.execute("INSERT INTO ruby_custom_inquiry_revisions VALUES (?,?,?,?,?,?,?,?,?,?)", (revision_id, inquiry_id, number, prior, request_hash, canonical(value).decode("utf-8"), scoped_operation, key_hash, policy.policy_version, now))
                self._inquiry_stage("detail")
                connection.execute("INSERT INTO ruby_custom_inquiry_audit VALUES (?,?,?,?,?,?,?,?,?,?)", (self._identifier("ruby-inquiry-audit"), inquiry_id, revision_id, self._owner, *self._inquiry_scope(context), policy.policy_version, operation, now))
                self._inquiry_stage("audit")
                connection.execute("INSERT INTO ruby_custom_inquiry_receipts VALUES (?,?,?,?,?,?,?,?,?,?)", (self._owner, *self._inquiry_scope(context), scoped_operation, key_hash, request_hash, inquiry_id, revision_id, canonical(result).decode("utf-8")))
                self._inquiry_stage("receipt")
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise error("inquiry_write_failed", 503) from None
            try:
                self._live.persist()
            except Exception:
                # Do NOT restore old memory here: os.replace may have committed.
                # The shared snapshot callback fences every store entry until
                # explicit disk reconciliation succeeds.
                self._persistence_fenced = True
                raise error("inquiry_outcome_unknown", 503) from None
            return result

    def resolve_ruby_inquiry_receipt(self, context, operation, idempotency_key, request_body, *, inquiry_id=None, source_handoff_body=None):
        with self._lock:
            policy = self._inquiry_policy(context)
            if operation not in ("create", "revise") or (operation == "create") != (inquiry_id is None):
                raise error()
            value, inquiry, prior, request_hash = self._inquiry_request(request_body, policy, revision=operation == "revise", source_handoff_body=source_handoff_body)
            if type(idempotency_key) is not str:
                raise error("invalid_idempotency_key")
            if inquiry_id is not None and self._inquiry_owned(context, inquiry_id) is None:
                return self._inquiry_unknown(operation)
            scoped_operation = operation if operation == "create" else "revise:" + inquiry_id
            existing = self._inquiry_existing(context, scoped_operation, self._idempotency(idempotency_key))
            if existing is None:
                return self._inquiry_unknown(operation)
            return self._inquiry_receipt(context, existing, request_hash, operation, prior, inquiry_id)

    def get_ruby_inquiry(self, context, inquiry_id):
        with self._lock:
            self._inquiry_policy(context)
            owned = self._inquiry_owned(context, inquiry_id)
            if owned is None:
                raise error("not_found", 404)
            revision = self._live.connection.execute("SELECT * FROM ruby_custom_inquiry_revisions WHERE revision_id=? AND inquiry_id=?", (owned["current_revision_id"], inquiry_id)).fetchone()
            if revision is None:
                raise error("inquiry_history_unavailable", 503)
            inquiry, _, _ = self._inquiry_stored_request(revision)
            return {"inquiry_id": inquiry_id, "revision_id": revision["revision_id"], "revision_number": revision["revision_number"], "state": "pending_review", "inquiry": inquiry, "contact_verification": {"state": "declared_unverified"}, "policy_version": revision["policy_version"], "cache_control": "no-store", **NO_AUTHORITY}

    def get_ruby_inquiry_source(self, context, inquiry_id, expected_revision_id):
        """Explicit owner-scoped current-source read; never a public HTTP route.

        No reconstruction, historical fallback, repricing, or repair occurs here.
        Existing reads/receipts do not expose the source or its fingerprint.
        """
        with self._lock:
            policy = self._inquiry_policy(context)
            self._inquiry_source_policy(policy)
            owned = self._inquiry_owned(context, inquiry_id)
            if owned is None:
                raise error("not_found", 404)
            if (type(expected_revision_id) is not str or
                    not IDENTIFIER.fullmatch(expected_revision_id) or
                    owned["current_revision_id"] != expected_revision_id):
                raise error("stale_revision", 409)
            revision = self._live.connection.execute(
                "SELECT * FROM ruby_custom_inquiry_revisions WHERE revision_id=? AND inquiry_id=?",
                (expected_revision_id, inquiry_id)).fetchone()
            if revision is None:
                raise error("inquiry_history_unavailable", 503)
            inquiry, prior, source = self._inquiry_stored_request(revision)
            self._inquiry_payload(inquiry, policy, current_catalog=False)
            if source is None:
                raise error("inquiry_source_unavailable", 404)
            stored = self._inquiry_existing(context, revision["operation"], revision["idempotency_hash"])
            if (stored is None or stored["revision_id"] != expected_revision_id or
                    stored["inquiry_id"] != inquiry_id):
                raise error("inquiry_history_unavailable", 503)
            result = self._inquiry_receipt(context, stored, revision["request_hash"],
                "create" if revision["revision_number"] == 1 else "revise", prior, inquiry_id)
            if result["state"] != "complete_received":
                raise error("inquiry_history_unavailable", 503)
            return {"inquiry_id": inquiry_id, "revision_id": expected_revision_id,
                    "source_handoff": source,
                    "source_fingerprint": "sha256:" + hashlib.sha256(canonical(source)).hexdigest(),
                    "cache_control": "no-store", **NO_AUTHORITY}

    def list_ruby_inquiries(self, context, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise error("invalid_query")
        with self._lock:
            self._inquiry_policy(context)
            # This is the minimal derived summary, never a second authority.
            rows = self._live.connection.execute(
                "SELECT i.inquiry_id,i.created_at,r.revision_id,r.revision_number,r.created_at AS updated_at FROM ruby_custom_inquiries i JOIN ruby_custom_inquiry_revisions r ON r.revision_id=i.current_revision_id AND r.inquiry_id=i.inquiry_id WHERE i.owner_digest=? AND i.project_id=? AND i.source_system=? AND i.source_instance=? ORDER BY i.created_at,i.inquiry_id LIMIT ?",
                (self._owner, *self._inquiry_scope(context), limit),
            ).fetchall()
            return {"inquiries": [{**dict(row), "state": "pending_review"} for row in rows], "cache_control": "no-store", **NO_AUTHORITY}

    def list_ruby_inquiry_audit(self, context, inquiry_id, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise error("invalid_query")
        with self._lock:
            self._inquiry_policy(context)
            if self._inquiry_owned(context, inquiry_id) is None:
                raise error("not_found", 404)
            rows = self._live.connection.execute(
                "SELECT event_id,inquiry_id,revision_id,project_id,source_system,source_instance,policy_version,operation,occurred_at FROM ruby_custom_inquiry_audit WHERE inquiry_id=? AND owner_digest=? ORDER BY occurred_at,event_id LIMIT ?",
                (inquiry_id, self._owner, limit),
            ).fetchall()
            return {"events": [dict(row) for row in rows], "cache_control": "no-store", **NO_AUTHORITY}
