"""Synthetic acceptance for the non-executing Ruby review-record Core resource."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from conversation_store import ConversationConfig, ConversationRequestError, ConversationStore


PROJECT = "rubys-cake-delights-hq"


class RubyReviewRecordChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.key = self.root / "key"
        self.key.write_text("44" * 32, encoding="ascii")
        if os.name != "nt":
            os.chmod(self.root, 0o700)
            os.chmod(self.key, 0o600)
        self.config = ConversationConfig(self.root / "state.enc", self.root / "ledger.enc", self.key)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def store(
        self, subject: str = "synthetic-ruby-owner", projects: frozenset[str] = frozenset({PROJECT})
    ) -> ConversationStore:
        return ConversationStore(self.config, "https://issuer.example", subject, ruby_review_projects=projects)

    @staticmethod
    def payload(
        *, fingerprint: str = "a" * 64, sku: str = "sku_0123456789abcdef",
        fulfillment: str = "pickup_0123456789abcdef",
        source_review_ref: object = "review_0123456789abcdef",
        correlation_ref: object = "correlation_0123456789abcdef",
        blockers: object = None,
    ) -> bytes:
        return json.dumps({
            "schema_version": "ruby.pending-review.v1", "project_id": PROJECT,
            "catalog_revision": "catalog_0123456789abcdef",
            "source_packet_fingerprint": "sha256:" + fingerprint,
            "source_review_ref": source_review_ref,
            "correlation_ref": correlation_ref,
            "items": [{"sku": sku, "quantity": 2, "item_subtotal_minor": 1200}],
            "fulfillment_preference": fulfillment,
            "unresolved_blockers": ["blocker_0123456789abcdef"] if blockers is None else blockers,
            "customer_confirmation": False,
        }, separators=(",", ":")).encode()

    def test_policy_identity_idempotency_and_durable_receipt(self) -> None:
        store = self.store()
        body = self.payload()
        created = store.create_ruby_review_record("ruby-review-create-0001", body)
        self.assertEqual("pending_review", created["state"])
        self.assertFalse(created["execution_authorized"])
        self.assertEqual(created, store.create_ruby_review_record("ruby-review-create-0001", body))
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
            store.create_ruby_review_record("ruby-review-create-0001", self.payload(fingerprint="b" * 64))
        self.assertEqual(created, self.store().get_ruby_review_record(created["record_id"]))
        self.assertEqual([created], self.store().list_ruby_review_records(PROJECT)["records"])
        audit = self.store().list_ruby_review_audit(created["record_id"])
        self.assertEqual(["record_created"], [event["event_type"] for event in audit["events"]])
        self.assertEqual(created["revision_id"], audit["events"][0]["revision_id"])
        self.assertNotIn("projection", audit["events"][0])
        with self.assertRaisesRegex(ConversationRequestError, "not_found"):
            self.store("other-owner").get_ruby_review_record(created["record_id"])
        with self.assertRaisesRegex(ConversationRequestError, "not_found"):
            self.store("other-owner").list_ruby_review_audit(created["record_id"])
        revoked = self.store(projects=frozenset({"another-project"}))
        with self.assertRaisesRegex(ConversationRequestError, "project_not_allowed"):
            revoked.get_ruby_review_record(created["record_id"])
        with self.assertRaisesRegex(ConversationRequestError, "project_not_allowed"):
            revoked.list_ruby_review_audit(created["record_id"])

    def test_policy_fail_closed_project_denial_and_explicit_revision(self) -> None:
        disabled = ConversationStore(self.config, "https://issuer.example", "owner")
        with self.assertRaisesRegex(ConversationRequestError, "policy_unavailable"):
            disabled.create_ruby_review_record("ruby-review-create-0002", self.payload())
        store = self.store()
        created = store.create_ruby_review_record("ruby-review-create-0003", self.payload())
        revised_body = b'{"expected_revision_id":"' + created["revision_id"].encode() + b'","projection":' + self.payload(fingerprint="c" * 64) + b'}'
        revised = store.revise_ruby_review_record(created["record_id"], "ruby-review-revise-0001", revised_body)
        self.assertEqual(2, revised["revision_number"])
        audit = store.list_ruby_review_audit(created["record_id"])
        self.assertEqual(["record_created", "record_revised"], [event["event_type"] for event in audit["events"]])
        self.assertEqual(revised["revision_id"], audit["events"][1]["revision_id"])
        with self.assertRaisesRegex(ConversationRequestError, "stale_revision"):
            store.revise_ruby_review_record(created["record_id"], "ruby-review-revise-0002", revised_body)
        self.assertEqual("none", revised["authority_effect"])

    def test_catalog_values_are_exact_bounded_values_not_core_identifiers(self) -> None:
        store = self.store()
        actual = store.create_ruby_review_record(
            "ruby-review-create-0004",
            self.payload(sku="RCD-MCH-RD", fulfillment="store pickup"),
        )
        self.assertEqual("RCD-MCH-RD", actual["projection"]["items"][0]["sku"])
        self.assertEqual("store pickup", actual["projection"]["fulfillment_preference"])
        for index, body in enumerate((
            self.payload(sku=" RCD-MCH-RD"),
            self.payload(fulfillment="pickup\n"),
            self.payload(sku="x" * 129),
        ), start=5):
            with self.assertRaisesRegex(ConversationRequestError, "invalid_request"):
                store.create_ruby_review_record(f"ruby-review-create-000{index}", body)

    def test_producer_references_and_diagnostic_blockers_preserve_exact_meaning(self) -> None:
        store = self.store()
        producer_ref = "cart-order-request:68b25062a47063630c5b4320"
        producer_blocker = "quantity-dependent package rule requires final package policy"
        cases = (
            ("source_review_ref", self.payload(source_review_ref=producer_ref)),
            ("correlation_ref", self.payload(correlation_ref=producer_ref)),
            ("unresolved_blockers", self.payload(blockers=[producer_blocker])),
        )
        for index, (field, body) in enumerate(cases, start=8):
            created = store.create_ruby_review_record(f"ruby-review-create-000{index}", body)
            expected = [producer_blocker] if field == "unresolved_blockers" else producer_ref
            self.assertEqual(expected, created["projection"][field])
        for index, body in enumerate((
            self.payload(source_review_ref=42),
            self.payload(correlation_ref=producer_ref + "\x00"),
            self.payload(blockers=["x" * 501]),
        ), start=11):
            with self.assertRaisesRegex(ConversationRequestError, "invalid_request"):
                store.create_ruby_review_record(f"ruby-review-create-00{index}", body)

    def test_original_receipt_recovery_is_bound_and_never_infers_noncommit(self) -> None:
        store = self.store()
        create_key, create_body = "ruby-receipt-create-0001", self.payload(fingerprint="d" * 64)
        created = store.create_ruby_review_record(create_key, create_body)
        create_receipt = store.resolve_ruby_review_create_receipt(create_key, create_body)
        self.assertEqual("committed", create_receipt["state"])
        self.assertEqual(created["revision_id"], create_receipt["receipt"]["revision_id"])
        self.assertNotIn(create_key, json.dumps(create_receipt))
        self.assertNotIn("source_review_ref", json.dumps(create_receipt))

        revision_body = json.dumps({
            "expected_revision_id": created["revision_id"],
            "projection": json.loads(self.payload(fingerprint="e" * 64)),
        }, separators=(",", ":")).encode()
        revised = store.revise_ruby_review_record(created["record_id"], "ruby-receipt-revise-0001", revision_body)
        later_body = json.dumps({
            "expected_revision_id": revised["revision_id"],
            "projection": json.loads(self.payload(fingerprint="f" * 64)),
        }, separators=(",", ":")).encode()
        store.revise_ruby_review_record(created["record_id"], "ruby-receipt-revise-0002", later_body)
        revision_receipt = store.resolve_ruby_review_revision_receipt(
            created["record_id"], "ruby-receipt-revise-0001", revision_body
        )
        self.assertEqual(revised["revision_id"], revision_receipt["receipt"]["revision_id"])
        self.assertEqual(2, revision_receipt["receipt"]["revision_number"])
        self.assertEqual(created["revision_id"], create_receipt["receipt"]["revision_id"])
        self.assertEqual(1, create_receipt["receipt"]["revision_number"])
        with self.assertRaisesRegex(ConversationRequestError, "idempotency_conflict"):
            store.resolve_ruby_review_create_receipt(create_key, self.payload(fingerprint="0" * 64))
        unknown = store.resolve_ruby_review_create_receipt("ruby-receipt-unknown-0001", self.payload(fingerprint="1" * 64))
        self.assertEqual({"state": "unknown", "reason": "receipt_unavailable"}, {
            "state": unknown["state"], "reason": unknown["reason"],
        })
        with self.assertRaisesRegex(ConversationRequestError, "project_not_allowed"):
            self.store(projects=frozenset({"another-project"})).resolve_ruby_review_create_receipt(create_key, create_body)
        self.assertEqual("unknown", self.store("other-owner").resolve_ruby_review_create_receipt(create_key, create_body)["state"])


if __name__ == "__main__":
    unittest.main()
