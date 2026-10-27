import ast
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from operations_hub.github_sandbox_runtime_ledger import (  # noqa: E402
    GitHubSandboxRuntimeLedger,
    GitHubSandboxRuntimeLedgerError,
)


NOW = 2_000_000_000
PLAN_DIGEST = "sha256:" + "a" * 64


class GitHubSandboxRuntimeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.ledger = GitHubSandboxRuntimeLedger(str(Path(self.tempdir.name) / "sandbox-ledger.sqlite3"))
        self.ledger.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def reserve(self, **overrides):
        values = {
            "approval_id": "approval-r3-001",
            "plan_digest": PLAN_DIGEST,
            "idempotency_key": "sandbox:approval-r3-001",
            "now_epoch_seconds": NOW,
            "expires_at_epoch": NOW + 900,
        }
        values.update(overrides)
        return self.ledger.reserve(**values)

    def test_reservation_is_durable_but_remains_inert(self):
        reservation = self.reserve()
        self.assertTrue(reservation.attempt_id.startswith("sandbox-attempt-"))
        self.assertEqual("reserved_inert_runtime_unwired", reservation.state)
        self.assertFalse(reservation.credential_read_authorized)
        self.assertFalse(reservation.token_request_authorized)
        self.assertFalse(reservation.dispatch_authorized)
        self.assertEqual("none", reservation.authority_effect)

        repeated = GitHubSandboxRuntimeLedger(self.ledger.path)
        with self.assertRaisesRegex(GitHubSandboxRuntimeLedgerError, "github_sandbox_approval_already_reserved"):
            repeated.reserve("approval-r3-001", PLAN_DIGEST, "sandbox:another", NOW, NOW + 900)

    def test_consume_is_single_use_and_bound_to_all_identifiers(self):
        reservation = self.reserve()
        consumed = self.ledger.consume("approval-r3-001", PLAN_DIGEST, "sandbox:approval-r3-001", NOW + 1)
        self.assertEqual(reservation.attempt_id, consumed.attempt_id)
        self.assertEqual("consumed_inert_runtime_unwired", consumed.state)
        self.assertIsNone(consumed.outcome_code)
        self.assertFalse(consumed.dispatch_authorized)

        with self.assertRaisesRegex(GitHubSandboxRuntimeLedgerError, "github_sandbox_reservation_not_consumable"):
            self.ledger.consume("approval-r3-001", PLAN_DIGEST, "sandbox:approval-r3-001", NOW + 2)

        self.reserve(approval_id="approval-r3-002", idempotency_key="sandbox:approval-r3-002")
        with self.assertRaisesRegex(GitHubSandboxRuntimeLedgerError, "github_sandbox_reservation_binding_mismatch"):
            self.ledger.consume("approval-r3-002", "sha256:" + "b" * 64, "sandbox:approval-r3-002", NOW + 1)

    def test_expired_or_failed_reservations_cannot_be_reused_and_store_only_fixed_codes(self):
        self.reserve(approval_id="approval-r3-expired", idempotency_key="sandbox:expired", expires_at_epoch=NOW + 1)
        with self.assertRaisesRegex(GitHubSandboxRuntimeLedgerError, "github_sandbox_reservation_expired"):
            self.ledger.consume("approval-r3-expired", PLAN_DIGEST, "sandbox:expired", NOW + 2)

        self.reserve(approval_id="approval-r3-failed", idempotency_key="sandbox:failed")
        failure = self.ledger.record_redacted_failure(
            "approval-r3-failed", PLAN_DIGEST, "sandbox:failed", "token_request_failed", NOW + 1
        )
        self.assertEqual("failed_inert_runtime_unwired", failure.state)
        self.assertEqual("token_request_failed", failure.outcome_code)
        with self.assertRaisesRegex(GitHubSandboxRuntimeLedgerError, "github_sandbox_reservation_not_finalizable"):
            self.ledger.record_redacted_failure(
                "approval-r3-failed", PLAN_DIGEST, "sandbox:failed", "dispatch_failed", NOW + 2
            )
        with self.assertRaisesRegex(GitHubSandboxRuntimeLedgerError, "github_sandbox_failure_code_invalid"):
            self.ledger.record_redacted_failure(
                "approval-r3-failed", PLAN_DIGEST, "sandbox:failed", "Bearer secret-value", NOW + 2
            )

    def test_invalid_inputs_fail_closed(self):
        for kwargs, error in (
            ({"approval_id": "approval with spaces"}, "github_sandbox_approval_identifier_invalid"),
            ({"plan_digest": "sha256:bad"}, "github_sandbox_plan_digest_invalid"),
            ({"idempotency_key": ""}, "github_sandbox_idempotency_identifier_invalid"),
            ({"expires_at_epoch": NOW}, "github_sandbox_reservation_expiry_invalid"),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(GitHubSandboxRuntimeLedgerError, error):
                    self.reserve(**kwargs)

    def test_source_has_no_credential_or_network_dependency(self):
        source = (ROOT / "src" / "operations_hub" / "github_sandbox_runtime_ledger.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse({"requests", "urllib", "http.client", "socket", "subprocess", "os", "pathlib"} & imported_modules)
        invoked_names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertNotIn("open", invoked_names)


if __name__ == "__main__":
    unittest.main()
