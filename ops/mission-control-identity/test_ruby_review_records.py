"""Synthetic acceptance for the non-executing Ruby review-record Core resource."""

from __future__ import annotations

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

    def store(self, subject: str = "synthetic-ruby-owner") -> ConversationStore:
        return ConversationStore(self.config, "https://issuer.example", subject, ruby_review_projects=frozenset({PROJECT}))

    @staticmethod
    def payload(*, fingerprint: str = "a" * 64) -> bytes:
        return (
            '{"schema_version":"ruby.pending-review.v1","project_id":"rubys-cake-delights-hq",'
            '"catalog_revision":"catalog_0123456789abcdef","source_packet_fingerprint":"sha256:' + fingerprint + '",'
            '"source_review_ref":"review_0123456789abcdef","correlation_ref":"correlation_0123456789abcdef",'
            '"items":[{"sku":"sku_0123456789abcdef","quantity":2,"item_subtotal_minor":1200}],'
            '"fulfillment_preference":"pickup_0123456789abcdef","unresolved_blockers":["blocker_0123456789abcdef"],'
            '"customer_confirmation":false}'
        ).encode()

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
        with self.assertRaisesRegex(ConversationRequestError, "not_found"):
            self.store("other-owner").get_ruby_review_record(created["record_id"])

    def test_policy_fail_closed_project_denial_and_explicit_revision(self) -> None:
        disabled = ConversationStore(self.config, "https://issuer.example", "owner")
        with self.assertRaisesRegex(ConversationRequestError, "policy_unavailable"):
            disabled.create_ruby_review_record("ruby-review-create-0002", self.payload())
        store = self.store()
        created = store.create_ruby_review_record("ruby-review-create-0003", self.payload())
        revised_body = b'{"expected_revision_id":"' + created["revision_id"].encode() + b'","projection":' + self.payload(fingerprint="c" * 64) + b'}'
        revised = store.revise_ruby_review_record(created["record_id"], "ruby-review-revise-0001", revised_body)
        self.assertEqual(2, revised["revision_number"])
        with self.assertRaisesRegex(ConversationRequestError, "stale_revision"):
            store.revise_ruby_review_record(created["record_id"], "ruby-review-revise-0002", revised_body)
        self.assertEqual("none", revised["authority_effect"])


if __name__ == "__main__":
    unittest.main()
