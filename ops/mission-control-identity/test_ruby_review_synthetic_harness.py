"""Focused offline checks for the explicit disposable Ruby synthetic harness."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from conversation_store import ConversationRequestError, ConversationStore
from ruby_review_synthetic_harness import (
    HARNESS_OPT_IN,
    DisposableRubySyntheticHarness,
    RubySyntheticHarnessError,
)
from ruby_review_transport import RUBY_PROJECT, RubySyntheticReadBinding


OWNER = "synthetic-ceo-subject"
ISSUER = "https://accounts.google.com"


class RubySyntheticHarnessChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.scope = Path(self.temp.name) / "scope"
        self.scope.mkdir()
        if os.name != "nt":
            os.chmod(self.scope, 0o700)

    def create(self) -> DisposableRubySyntheticHarness:
        return DisposableRubySyntheticHarness.create(
            storage_scope=self.scope,
            opt_in=HARNESS_OPT_IN,
            owner_subject=OWNER,
            issuer=ISSUER,
        )

    def test_absent_or_invalid_opt_in_creates_no_artifacts(self) -> None:
        for value in (None, "", "enabled", "ruby-synthetic-harness-v2"):
            with self.assertRaisesRegex(RubySyntheticHarnessError, "opt_in_required"):
                DisposableRubySyntheticHarness.create(
                    storage_scope=self.scope,
                    opt_in=value,
                    owner_subject=OWNER,
                    issuer=ISSUER,
                )
        self.assertEqual([], list(self.scope.iterdir()))

    def test_invalid_owner_or_issuer_is_rejected_before_artifact_creation(self) -> None:
        invalid_contexts = (
            (None, ISSUER, "owner_invalid"),
            ("owner\u00e9", ISSUER, "owner_invalid"),
            ("o" * 256, ISSUER, "owner_invalid"),
            (OWNER, None, "issuer_invalid"),
            (OWNER, "https://issuer.\u4f8b", "issuer_invalid"),
            (OWNER, "https://" + "a" * 248, "issuer_invalid"),
        )
        for owner_subject, issuer, code in invalid_contexts:
            with self.assertRaisesRegex(RubySyntheticHarnessError, code):
                DisposableRubySyntheticHarness.create(
                    storage_scope=self.scope,
                    opt_in=HARNESS_OPT_IN,
                    owner_subject=owner_subject,  # type: ignore[arg-type]
                    issuer=issuer,  # type: ignore[arg-type]
                )
        self.assertEqual([], list(self.scope.iterdir()))

    def test_malformed_storage_scope_is_rejected_without_writes(self) -> None:
        invalid = self.scope / "not-a-directory"
        invalid.write_text("sentinel", encoding="utf-8")
        with self.assertRaisesRegex(RubySyntheticHarnessError, "storage_scope_invalid"):
            DisposableRubySyntheticHarness.create(
                storage_scope=invalid,
                opt_in=HARNESS_OPT_IN,
                owner_subject=OWNER,
                issuer=ISSUER,
            )
        self.assertEqual("sentinel", invalid.read_text(encoding="utf-8"))

    def test_restart_preserves_original_receipts_and_unknown_history_fails_closed(self) -> None:
        harness = self.create()
        self.addCleanup(harness.cleanup)
        restarted = harness.reopen_binding(owner_subject=OWNER, issuer=ISSUER)
        self.assertEqual(("committed", 1), (restarted.resolve_receipt("create-pickup")["state"], restarted.resolve_receipt("create-pickup")["receipt"]["revision_number"]))
        self.assertEqual(("committed", 2), (restarted.resolve_receipt("revise-pickup")["state"], restarted.resolve_receipt("revise-pickup")["receipt"]["revision_number"]))
        pickup = next(record for record in restarted.records if record.create_receipt.reference == "create-pickup")
        self.assertEqual(3, restarted.get_record(pickup.record_id)["revision_number"])
        self.assertEqual("not_found", self._receipt_error(restarted, "receipt-not-recorded"))
        restarted.store._live.connection.execute(
            "DELETE FROM ruby_review_record_revisions WHERE record_id=?", (pickup.record_id,)
        )
        self.assertEqual("unknown", restarted.resolve_receipt("create-pickup")["state"])

    def test_owner_store_mismatch_is_not_reopened_or_readable(self) -> None:
        harness = self.create()
        self.addCleanup(harness.cleanup)
        with self.assertRaisesRegex(RubySyntheticHarnessError, "owner_context_mismatch"):
            harness.reopen_binding(owner_subject="different-owner", issuer=ISSUER)
        with self.assertRaisesRegex(RubySyntheticHarnessError, "owner_context_invalid"):
            harness.reopen_binding(owner_subject="owner\u00e9", issuer=ISSUER)
        foreign_store = ConversationStore(
            harness.config,
            ISSUER,
            "different-owner",
            ruby_review_projects=frozenset({RUBY_PROJECT}),
        )
        foreign_binding = RubySyntheticReadBinding(
            store=foreign_store,
            issuer=ISSUER,
            owner_subject=OWNER,
            project_id=RUBY_PROJECT,
            records=harness.binding.records,
        )
        with self.assertRaisesRegex(ConversationRequestError, "synthetic_binding_unavailable"):
            foreign_binding.list_records()

    def test_ambient_core_configuration_is_rejected_without_external_read_or_artifacts(self) -> None:
        external_manifest = Path(self.temp.name) / "external-manifest.json"
        external_manifest.write_text('{"sentinel":"preserve"}', encoding="utf-8")
        with mock.patch.dict(os.environ, {"MISSION_CONTROL_EVIDENCE_MANIFEST_FILE": str(external_manifest)}):
            with mock.patch("conversation_store.EvidenceReferenceVerifier.from_file") as read_manifest:
                with self.assertRaisesRegex(RubySyntheticHarnessError, "ambient_core_configuration_forbidden"):
                    self.create()
                read_manifest.assert_not_called()
        self.assertEqual('{"sentinel":"preserve"}', external_manifest.read_text(encoding="utf-8"))
        self.assertEqual([], list(self.scope.iterdir()))

        with mock.patch.dict(os.environ, {"MISSION_CONTROL_CONVERSATION_READONLY_PREFLIGHT": "true"}):
            with self.assertRaisesRegex(RubySyntheticHarnessError, "ambient_core_configuration_forbidden"):
                self.create()
        self.assertEqual([], list(self.scope.iterdir()))

    def test_cleanup_removes_only_its_own_run_directory(self) -> None:
        sibling = self.scope / "ruby-synthetic-harness-not-owned"
        sibling.mkdir()
        sentinel = sibling / "sentinel"
        sentinel.write_text("preserve", encoding="utf-8")
        harness = self.create()
        run_directory = harness.run_directory
        harness.cleanup()
        self.assertFalse(run_directory.exists())
        self.assertEqual("preserve", sentinel.read_text(encoding="utf-8"))
        harness.cleanup()

    def test_normal_session_startup_remains_unbound_and_route_unchanged(self) -> None:
        identity_root = Path(__file__).resolve().parent
        session_source = (identity_root / "google_ceo_session.py").read_text(encoding="utf-8")
        activation_source = (identity_root / "activate-google-ceo-session.sh").read_text(encoding="utf-8")
        self.assertIn("server.ruby_review_transport_binding = None", session_source)
        self.assertNotIn("ruby_review_synthetic_harness", session_source)
        self.assertIn("PathPrefix(\\`/auth/google\\`)", activation_source)
        self.assertNotIn("/api/ruby-review-synthetic", activation_source)

    def _receipt_error(self, binding: RubySyntheticReadBinding, reference: str) -> str:
        with self.assertRaises(ConversationRequestError) as raised:
            binding.resolve_receipt(reference)
        return raised.exception.code


if __name__ == "__main__":
    unittest.main()
