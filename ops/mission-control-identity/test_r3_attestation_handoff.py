"""Offline checks for the default-off internal R3 attestation handoff."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import r3_attestation_handoff as handoff  # noqa: E402
import r3_attestation_handoff_config as config  # noqa: E402


class R3AttestationHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = "google-subject-123"
        self.signing_key = b"k" * 32
        self.config = config.R3AttestationHandoffConfig(
            issuer=config.ISSUER,
            signing_key_file=mock.Mock(),
            ceo_subject_file=mock.Mock(),
        )

    def test_from_environment_preserves_the_default_off_gate(self) -> None:
        with mock.patch.object(config.R3AttestationHandoffConfig, "from_environment", side_effect=config.R3AttestationHandoffConfigurationError("inactive")):
            with self.assertRaisesRegex(config.R3AttestationHandoffConfigurationError, "inactive"):
                handoff.R3AttestationHandoff.from_environment()

    def test_issue_returns_only_safe_metadata_and_a_short_lived_internal_proof(self) -> None:
        self.config.ceo_subject_file.read_text.return_value = "sha256:" + hashlib.sha256(self.subject.encode()).hexdigest() + "\n"
        self.config.signing_key_file.read_bytes.return_value = self.signing_key
        result = handoff.R3AttestationHandoff(self.config).issue_for_verified_subject(
            verified_subject=self.subject, authenticated_at_epoch=1_700_000_000
        )
        self.assertTrue(result.token.startswith("v1."))
        self.assertEqual(config.ISSUER, result.metadata.issuer)
        self.assertEqual("sha256:" + hashlib.sha256(self.subject.encode()).hexdigest(), result.metadata.subject_sha256)
        self.assertEqual("sha256:" + hashlib.sha256(result.token.encode()).hexdigest(), result.metadata.attestation_digest)
        self.assertEqual(1_700_000_000 + handoff.ATTESTATION_TTL_SECONDS, result.metadata.expires_at_epoch)
        self.assertEqual(result.metadata.expires_at_epoch + handoff.METADATA_RETENTION_SECONDS, result.metadata.retention_expires_at_epoch)
        self.assertFalse(result.metadata.execution_authorized)
        self.assertFalse(result.metadata.mutation_authorized)
        self.assertEqual("none", result.metadata.authority_effect)
        self.assertNotIn(self.subject, repr(result.metadata))
        self.assertNotIn(result.token, repr(result.metadata))

    def test_mismatch_or_malformed_subject_never_issues_a_proof(self) -> None:
        self.config.ceo_subject_file.read_text.return_value = "sha256:" + hashlib.sha256(self.subject.encode()).hexdigest() + "\n"
        self.config.signing_key_file.read_bytes.return_value = self.signing_key
        service = handoff.R3AttestationHandoff(self.config)
        with self.assertRaisesRegex(handoff.R3AttestationHandoffError, "subject_mismatch"):
            service.issue_for_verified_subject(verified_subject="different-subject", authenticated_at_epoch=1_700_000_000)
        self.config.ceo_subject_file.read_text.return_value = "sha256:" + hashlib.sha256(self.subject.encode()).hexdigest()
        with self.assertRaisesRegex(handoff.R3AttestationHandoffError, "subject_format_invalid"):
            service.issue_for_verified_subject(verified_subject=self.subject, authenticated_at_epoch=1_700_000_000)

    def test_source_has_no_database_route_or_external_client(self) -> None:
        source = (ROOT / "r3_attestation_handoff.py").read_text(encoding="utf-8").lower()
        for forbidden in ("psycopg", "requests", "httpserver", "serve_forever", "github"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
