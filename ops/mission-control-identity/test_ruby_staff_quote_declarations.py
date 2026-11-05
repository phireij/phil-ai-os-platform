"""Source-only declaration regression checks using disposable encrypted custody.

Socket entry points are blocked for every test. No subprocesses or real actors.
"""
import copy
import hashlib
import unittest
from dataclasses import replace
from unittest.mock import patch

from conversation_store import ConversationStore, ConversationRequestError
from ruby_finalized_quote import SCHEMA, STAFF_SCHEMA, NO_QUOTE_AUTHORITY, validate_quote
from ruby_inquiry import canonical, MAX_BODY
from ruby_quote_custody import (SCHEMA as CUSTODY_SCHEMA, BOUND_RESPONSE_SCHEMA,
    SyntheticResponseVerification, fingerprint)
from test_ruby_inquiry import InquiryChecks, CONTEXT, ISSUER, SUBJECT, body, encoded

QUOTE_KEY = "synthetic-staff-quote-key-0001"
CONSENT = "SYNTHETIC CONSENT ONLY. No customer, order, payment, or fulfillment authority."


def verifier(context, inquiry_id, quote_id, customer_ref, request_fingerprint):
    return SyntheticResponseVerification(inquiry_id, quote_id, customer_ref,
        request_fingerprint, "synthetic:customer-one")


def quote(revision):
    # Independent golden V1 input also allows the existing quote test module to
    # import this test class without circular quote/custody fixture imports.
    return {"schema_version": SCHEMA, "expected_revision_id": revision,
        "source_quote_ref": "synthetic-staff-quote-one", "currency": "JPY",
        "items": [{"line_ref": "cake", "description": "Synthetic custom cake",
            "quantity": 2, "unit_price_yen": 3100, "line_total_yen": 6200}],
        "shipping_yen": 0, "total_yen": 6200,
        "fulfillment": {"method": "pickup", "date": "2028-02-29",
            "time_window": "14:30", "packing_plan_ref": "synthetic-plan-unverified"}}


def staff_quote(revision):
    return {
        **quote(revision),
        "schema_version": STAFF_SCHEMA,
        "staff_declaration": {
            "operator_ref": "synthetic:operator-one",
            "source_review_fingerprint": "sha256:" + hashlib.sha256(b"synthetic review").hexdigest(),
            "date_confirmed": True,
            "packing_confirmed": True,
            "shipping_confirmed": True,
            "packing_description": "Synthetic box A, divider and padding. 箱の記録。",
            "verification": "unverified_operator_declaration",
        },
    }


class StaffQuoteDeclarationChecks(unittest.TestCase):
    tearDown = InquiryChecks.tearDown
    create = InquiryChecks.create

    def setUp(self):
        for entry in ("socket.socket", "socket.create_connection", "socket.getaddrinfo"):
            blocker = patch(entry, side_effect=AssertionError("socket access prohibited"))
            blocker.start()
            self.addCleanup(blocker.stop)
        InquiryChecks.setUp(self)
        self.inquiry = self.create()["receipt"]
        self.iid = self.inquiry["inquiry_id"]
        self.value = staff_quote(self.inquiry["revision_id"])

    def open(self):
        return ConversationStore(self.config, ISSUER, SUBJECT,
            ruby_inquiry_policy=lambda c: replace(self.policy, finalized_quotes_enabled=True,
                quote_custody_enabled=True, quote_consent_enabled=True) if self.policy else None,
            ruby_finalized_quotes_enabled=True, ruby_quote_custody_enabled=True,
            ruby_quote_consent_enabled=True, ruby_quote_synthetic_verifier=verifier)

    def record(self, value=None, key=QUOTE_KEY):
        return self.store.record_ruby_finalized_quote(CONTEXT, self.iid, key,
            encoded(self.value if value is None else value))

    def resolve(self, value=None, key=QUOTE_KEY):
        return self.store.resolve_ruby_finalized_quote_receipt(CONTEXT, self.iid, key,
            encoded(self.value if value is None else value))

    def counts(self):
        return tuple(self.store._live.connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            for table in ("ruby_finalized_quote_events", "ruby_finalized_quote_receipts", "ruby_finalized_quote_audit"))

    def assert_inert(self, value):
        for name, expected in NO_QUOTE_AUTHORITY.items():
            self.assertEqual(value[name], expected)
            if type(expected) is bool:
                self.assertIs(value[name], False)

    def test_v2_encrypted_readback_restart_and_original_v1_receipt(self):
        receipt = self.record()
        self.assertEqual(receipt["schema_version"], SCHEMA)
        self.assertEqual(receipt["request_fingerprint"], fingerprint(canonical(self.value)))
        detail = self.store.get_ruby_finalized_quote(CONTEXT, self.iid, receipt["quote_id"])
        self.assertEqual(detail["quote"], self.value)
        self.assertEqual(self.resolve(), receipt)
        self.assertEqual(self.record(), receipt)
        self.assertEqual(self.counts(), (1, 1, 1))
        self.assert_inert(receipt)
        self.assert_inert(detail)
        event = self.store._live.connection.execute("SELECT * FROM ruby_finalized_quote_events").fetchone()
        self.assertEqual(event["request_json"], canonical(self.value).decode())
        self.assertEqual(event["request_hash"], hashlib.sha256(canonical(self.value)).digest())
        for table in ("ruby_finalized_quote_receipts", "ruby_finalized_quote_audit"):
            row = self.store._live.connection.execute("SELECT * FROM " + table).fetchone()
            self.assertEqual(row["request_hash"], event["request_hash"])
            self.assertNotIn("request_json", row.keys())
            self.assertNotIn("synthetic:operator-one", repr(dict(row)))
        raw = self.config.state_file.read_bytes()
        for marker in (self.value["staff_declaration"]["operator_ref"],
                       self.value["staff_declaration"]["packing_description"], QUOTE_KEY):
            self.assertNotIn(marker.encode(), raw)
        # A new store instance loads persisted ciphertext, not the old connection.
        self.store.close()
        self.store = self.open()
        self.assertEqual(self.resolve(), receipt)
        self.assertEqual(self.store.get_ruby_finalized_quote(CONTEXT, self.iid, receipt["quote_id"]), detail)

    def test_v1_legacy_body_and_receipt_remain_unchanged(self):
        legacy = quote(self.inquiry["revision_id"])
        receipt = self.record(legacy)
        self.assertEqual(receipt["schema_version"], SCHEMA)
        self.assertEqual(set(receipt), {"schema_version", "state", "quote_id", "inquiry_id", "revision_id",
            "recorded_at", "request_fingerprint", "customer_ref", "customer_identity"} | set(NO_QUOTE_AUTHORITY))
        self.assertEqual(self.store.get_ruby_finalized_quote(CONTEXT, self.iid, receipt["quote_id"])["quote"], legacy)
        self.store.close()
        self.store = self.open()
        self.assertEqual(self.resolve(legacy), receipt)
        self.assert_inert(receipt)

    def test_closed_body_and_declaration_require_all_fields(self):
        values = []
        for key in self.value:
            changed = copy.deepcopy(self.value)
            del changed[key]
            values.append(changed)
        for key in self.value["staff_declaration"]:
            changed = copy.deepcopy(self.value)
            del changed["staff_declaration"][key]
            values.append(changed)
        for extra in ("role", "staff_authenticated", "date_verified", "payment_request_authorized"):
            changed = copy.deepcopy(self.value)
            changed["staff_declaration"][extra] = True
            values.append(changed)
        values.extend((dict(self.value, customer_accepted=True),
                       dict(self.value, schema_version=SCHEMA),
                       dict(self.value, schema_version="ruby.finalized-quote-record.v3")))
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(ConversationRequestError):
                    self.record(value)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_confirmations_require_literal_true_not_false_or_coercion(self):
        for key in ("date_confirmed", "packing_confirmed", "shipping_confirmed"):
            for invalid in (False, None, 0, 1, "true", "false", [], {}):
                value = copy.deepcopy(self.value)
                value["staff_declaration"][key] = invalid
                with self.subTest(key=key, invalid=invalid):
                    with self.assertRaises(ConversationRequestError):
                        self.record(value)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_malformed_declaration_refs_marker_and_existing_text_bounds(self):
        invalid_fields = {
            "operator_ref": (None, True, "", "operator name", "x" * 121, "operator\n"),
            "source_review_fingerprint": (None, True, "", "sha256:" + "a" * 63,
                "sha256:" + "a" * 65, "sha256:" + "A" * 64, "sha256:" + "g" * 64, "sha256:" + "a" * 64 + "\n"),
            "verification": (None, True, "verified", "unverified_operator_declaration "),
            "packing_description": (None, True, "", " ", "\u3000", " padded", "padded ", "x" * 201, "box\nA", "box\x00A"),
        }
        for key, invalids in invalid_fields.items():
            for invalid in invalids:
                value = copy.deepcopy(self.value)
                value["staff_declaration"][key] = invalid
                with self.subTest(key=key, invalid=invalid):
                    with self.assertRaises(ConversationRequestError):
                        self.record(value)
        for invalid in (None, False, [], "declared"):
            with self.assertRaises(ConversationRequestError):
                self.record(dict(self.value, staff_declaration=invalid))
        self.assertEqual(self.counts(), (0, 0, 0))
        # Reuse the existing opaque and description bounds, without normalization.
        self.value["staff_declaration"].update(operator_ref="x" * 120, packing_description="箱" * 200)
        receipt = self.record()
        self.assertEqual(self.store.get_ruby_finalized_quote(CONTEXT, self.iid, receipt["quote_id"])["quote"], self.value)

    def test_duplicate_json_keys_and_existing_body_bound_rejected(self):
        raw = encoded(self.value).replace(b'"date_confirmed":true', b'"date_confirmed":false,"date_confirmed":true')
        for malformed in (raw, b" " * (MAX_BODY + 1)):
            with self.assertRaises(ConversationRequestError):
                self.store.record_ruby_finalized_quote(CONTEXT, self.iid, QUOTE_KEY, malformed)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_changed_declarations_and_body_version_conflict_under_same_key(self):
        receipt = self.record()
        for key, changed in (("operator_ref", "synthetic:operator-two"),
                             ("source_review_fingerprint", "sha256:" + "0" * 64),
                             ("packing_description", "A different synthetic box")):
            value = copy.deepcopy(self.value)
            value["staff_declaration"][key] = changed
            self.assertNotEqual(validate_quote(encoded(value))[1], validate_quote(encoded(self.value))[1])
            for operation in (self.record, self.resolve):
                with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
                    operation(value)
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
            self.record(quote(self.inquiry["revision_id"]))
        self.assertEqual(self.resolve(), receipt)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_new_v2_append_rejects_stale_revision_but_original_recovery_is_immutable(self):
        receipt = self.record()
        revised = body()
        revised["customization"]["custom_notes"] = "Later synthetic inquiry revision"
        self.store.revise_ruby_inquiry(CONTEXT, self.iid, "synthetic-staff-revision-002",
            encoded({"expected_revision_id": self.value["expected_revision_id"], "inquiry": revised}))
        with self.assertRaisesRegex(ConversationRequestError, "stale_revision"):
            self.record(key="synthetic-new-staff-quote-002")
        self.assertEqual(self.resolve(), receipt)
        self.assertEqual(self.record(), receipt)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_retained_declaration_tampering_is_not_rehashed_or_repaired(self):
        self.record()
        value = copy.deepcopy(self.value)
        value["staff_declaration"]["operator_ref"] = "synthetic:changed-retained"
        self.store._live.connection.execute("UPDATE ruby_finalized_quote_events SET request_json=?", (canonical(value).decode(),))
        for operation in (self.record, self.resolve):
            with self.assertRaisesRegex(ConversationRequestError, "quote_binding_mismatch"):
                operation()
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_missing_evidence_reserves_key_and_never_reconstructs(self):
        self.record()
        self.store._live.connection.execute("DELETE FROM ruby_finalized_quote_receipts")
        self.store._live.persist()
        self.store.close()
        self.store = self.open()
        self.assertEqual(self.resolve()["state"], "unknown")
        self.assertEqual(self.record()["state"], "unknown")
        changed = copy.deepcopy(self.value)
        changed["staff_declaration"]["packing_description"] = "Different box"
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
            self.record(changed)
        self.assertEqual(self.counts(), (1, 0, 1))

    def test_returned_declarations_do_not_alias_retained_evidence(self):
        receipt = self.record()
        detail = self.store.get_ruby_finalized_quote(CONTEXT, self.iid, receipt["quote_id"])
        detail["quote"]["staff_declaration"]["packing_description"] = "Changed local output"
        self.assertEqual(self.store.get_ruby_finalized_quote(CONTEXT, self.iid, receipt["quote_id"])["quote"], self.value)
        self.assertEqual(self.resolve(), receipt)

    def test_declarations_do_not_bypass_current_policy_or_owner_scope(self):
        self.record()
        with self.assertRaisesRegex(ConversationRequestError, "inquiry_access_denied"):
            self.store.record_ruby_finalized_quote(replace(CONTEXT, subject="different-owner"),
                self.iid, QUOTE_KEY, encoded(self.value))
        self.policy = None
        for operation in (self.record, self.resolve):
            with self.assertRaisesRegex(ConversationRequestError, "inquiry_policy_unavailable"):
                operation()
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_v2_selection_bound_response_readback_and_restart_remain_inert(self):
        quote_receipt = self.record()
        self.assertEqual(self.store.get_ruby_quote_response_context(CONTEXT, self.iid)["state"], "unknown")
        selection = {"schema_version": CUSTODY_SCHEMA, "operation": "select", "expected_event_id": None,
            "quote_id": quote_receipt["quote_id"], "quote_fingerprint": quote_receipt["request_fingerprint"], "consent_text": CONSENT}
        selected = self.store.record_ruby_quote_custody(CONTEXT, self.iid, "synthetic-staff-select-0001", encoded(selection))
        context = self.store.get_ruby_quote_response_context(CONTEXT, self.iid)
        self.assertEqual(context["quote_snapshot"]["quote"], self.value)
        request = {"schema_version": BOUND_RESPONSE_SCHEMA, "operation": "respond", "expected_event_id": selected["event_id"],
            "quote_id": quote_receipt["quote_id"], "quote_fingerprint": quote_receipt["request_fingerprint"],
            "consent_fingerprint": fingerprint(CONSENT.encode()), "decision": "accept", "selection_fingerprint": context["selection_fingerprint"]}
        response = self.store.record_ruby_quote_custody(CONTEXT, self.iid, "synthetic-staff-response-0001", encoded(request))
        for value in (quote_receipt, selected, context, response, self.store.get_ruby_quote_custody(CONTEXT, self.iid)):
            self.assert_inert(value)
        self.store.close()
        self.store = self.open()
        self.assertEqual(self.store.resolve_ruby_quote_custody_receipt(CONTEXT, self.iid, "synthetic-staff-response-0001", encoded(request)), response)
        self.assertEqual(self.store.get_ruby_finalized_quote(CONTEXT, self.iid, quote_receipt["quote_id"])["quote"], self.value)
        self.assert_inert(self.store.get_ruby_quote_response_context(CONTEXT, self.iid))


if __name__ == "__main__":
    unittest.main()
