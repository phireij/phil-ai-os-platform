"""Offline acceptance for the disabled synthetic Ruby review read adapter."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from conversation_store import ConversationConfig, ConversationRequestError, ConversationStore
from ruby_review_transport import RUBY_PROJECT, RubySyntheticReadBinding, build_disposable_synthetic_binding


class RubySyntheticTransportChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.key = self.root / "key"
        self.key.write_text("55" * 32, encoding="ascii")
        if os.name != "nt":
            os.chmod(self.root, 0o700)
            os.chmod(self.key, 0o600)
        self.config = ConversationConfig(self.root / "state.enc", self.root / "ledger.enc", self.key)
        self.binding = build_disposable_synthetic_binding(
            self.config, owner_subject="synthetic-ceo-subject", issuer="https://accounts.google.com"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_controlled_fixtures_are_owner_project_bound_and_read_only(self) -> None:
        self.assertTrue(self.binding.is_available_for("synthetic-ceo-subject"))
        self.assertFalse(self.binding.is_available_for("different-owner"))
        before = self.config.state_file.read_bytes()
        records = self.binding.list_records()["records"]
        self.assertEqual({"store pickup", "Yamato delivery", "Ruby car delivery"}, {row["fulfillment_preference"] for row in records})
        self.assertTrue(all(row["synthetic"] and row["project_id"] == RUBY_PROJECT for row in records))
        pickup = next(row for row in records if row["fulfillment_preference"] == "store pickup")
        detail = self.binding.get_record(pickup["record_id"])
        audit = self.binding.list_audit(pickup["record_id"])
        self.assertNotIn("source_review_ref", json.dumps(detail))
        self.assertEqual(["record_created", "record_revised", "record_revised"], [event["event_type"] for event in audit["events"]])
        self.assertEqual(before, self.config.state_file.read_bytes())
        with self.assertRaisesRegex(ConversationRequestError, "not_found"):
            self.binding.get_record("ruby-review-not-owned-0001")

    def test_receipts_bind_original_create_and_revision_after_later_catalog_change(self) -> None:
        before = self.config.state_file.read_bytes()
        create = self.binding.resolve_receipt("create-pickup")
        revise = self.binding.resolve_receipt("revise-pickup")
        self.assertEqual(("committed", 1), (create["state"], create["receipt"]["revision_number"]))
        self.assertEqual(("committed", 2), (revise["state"], revise["receipt"]["revision_number"]))
        receipt = next(item.revision_receipt for item in self.binding.records if item.revision_receipt is not None)
        self.assertEqual("catalog_pickup_fixture_v2", receipt.catalog_revision)
        self.assertIn("controlled pickup revision fixture", receipt.blockers)
        self.assertNotIn("idempotency", json.dumps(revise))
        self.assertNotIn("projection", json.dumps(revise))
        self.assertEqual(before, self.config.state_file.read_bytes())

    def test_fresh_process_and_missing_or_contradictory_history_fail_closed(self) -> None:
        fresh = ConversationStore(
            self.config, "https://accounts.google.com", "synthetic-ceo-subject", ruby_review_projects=frozenset({RUBY_PROJECT})
        )
        rebound = RubySyntheticReadBinding(
            store=fresh, issuer="https://accounts.google.com", owner_subject="synthetic-ceo-subject", project_id=RUBY_PROJECT, records=self.binding.records
        )
        self.assertEqual(3, len(rebound.list_records()["records"]))
        create = next(item.create_receipt for item in rebound.records if item.create_receipt.reference == "create-yamato")
        fresh._live.connection.execute(
            "DELETE FROM ruby_review_record_revisions WHERE record_id=?", (create.record_id,)
        )
        self.assertEqual("unknown", rebound.resolve_receipt(create.reference)["state"])

        contradictory = build_disposable_synthetic_binding(
            ConversationConfig(self.root / "other-state.enc", self.root / "other-ledger.enc", self.key),
            owner_subject="synthetic-ceo-subject", issuer="https://accounts.google.com",
        )
        receipt = next(item.create_receipt for item in contradictory.records if item.create_receipt.reference == "create-ruby-car")
        contradictory.store._live.connection.execute(
            "UPDATE ruby_review_records SET project_id=? WHERE record_id=?", ("wrong-project", receipt.record_id)
        )
        with self.assertRaisesRegex(ConversationRequestError, "receipt_binding_mismatch"):
            contradictory.resolve_receipt(receipt.reference)

        no_policy = ConversationStore(self.config, "https://accounts.google.com", "synthetic-ceo-subject")
        unavailable = RubySyntheticReadBinding(
            store=no_policy, issuer="https://accounts.google.com", owner_subject="synthetic-ceo-subject", project_id=RUBY_PROJECT, records=self.binding.records
        )
        self.assertFalse(unavailable.is_available_for("synthetic-ceo-subject"))

    def test_binding_rejects_mismatched_store_owner_or_issuer_before_reading(self) -> None:
        for issuer, owner_subject in (
            ("https://accounts.google.com", "different-owner"),
            ("https://issuer.example", "synthetic-ceo-subject"),
        ):
            mismatch = RubySyntheticReadBinding(
                store=self.binding.store,
                issuer=issuer,
                owner_subject=owner_subject,
                project_id=RUBY_PROJECT,
                records=self.binding.records,
            )
            self.assertFalse(mismatch.is_available_for(owner_subject))
            with self.assertRaisesRegex(ConversationRequestError, "synthetic_binding_unavailable"):
                mismatch.list_records()


if __name__ == "__main__":
    unittest.main()
