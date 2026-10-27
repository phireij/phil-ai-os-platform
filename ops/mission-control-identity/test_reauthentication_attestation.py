"""Offline checks for the default-off R3 reauthentication attestation primitive."""

from __future__ import annotations

import ast
import base64
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from reauthentication_attestation import (  # noqa: E402
    ATTESTATION_TTL_SECONDS,
    ReauthenticationAttestationError,
    SingleUseAttestationRegistry,
    issue_attestation,
    verify_attestation,
)


NOW = 2_000_000_000
KEY = b"k" * 32
ISSUER = "https://accounts.google.com"
SUBJECT = "stable-google-subject"


class ReauthenticationAttestationTests(unittest.TestCase):
    def issue(self, **overrides: object) -> str:
        values = {
            "signing_key": KEY,
            "issuer": ISSUER,
            "subject": SUBJECT,
            "authenticated_at_epoch": NOW,
            "attestation_id": "attestation-identifier-001",
        }
        values.update(overrides)
        return issue_attestation(**values)

    def verify(self, token: str, **overrides: object):
        values = {
            "token": token,
            "signing_key": KEY,
            "expected_issuer": ISSUER,
            "expected_subject": SUBJECT,
            "now_epoch_seconds": NOW + 1,
        }
        values.update(overrides)
        return verify_attestation(**values)

    def test_signed_proof_uses_only_a_subject_digest_and_is_time_bound(self) -> None:
        token = self.issue()
        self.assertNotIn(SUBJECT, token)
        proof = self.verify(token)
        self.assertEqual("attestation-identifier-001", proof.attestation_id)
        self.assertTrue(proof.subject_sha256.startswith("sha256:"))
        self.assertEqual(NOW + ATTESTATION_TTL_SECONDS, proof.expires_at_epoch)

    def test_signature_binding_and_expiry_fail_closed(self) -> None:
        token = self.issue()
        for overrides, error in (
            ({"signing_key": b"x" * 32}, "attestation_signature_invalid"),
            ({"expected_subject": "other-subject"}, "attestation_binding_mismatch"),
            ({"expected_issuer": "https://example.test"}, "attestation_binding_mismatch"),
            ({"now_epoch_seconds": NOW + ATTESTATION_TTL_SECONDS + 1}, "attestation_expired_or_invalid"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ReauthenticationAttestationError, error):
                    self.verify(token, **overrides)

    def test_tampered_or_noncanonical_claims_fail_closed(self) -> None:
        token = self.issue()
        version, payload, signature = token.split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        claims["extra"] = "not-allowed"
        altered_payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        with self.assertRaisesRegex(ReauthenticationAttestationError, "signature_invalid"):
            self.verify(version + "." + altered_payload + "." + signature)
        with self.assertRaisesRegex(ReauthenticationAttestationError, "attestation_token_invalid"):
            self.verify("v2.invalid.invalid")

    def test_registry_is_single_use_bounded_and_expires_entries(self) -> None:
        proof = self.verify(self.issue())
        registry = SingleUseAttestationRegistry(maximum_entries=1)
        registry.consume(proof, NOW + 1)
        with self.assertRaisesRegex(ReauthenticationAttestationError, "already_consumed"):
            registry.consume(proof, NOW + 1)
        next_proof = self.verify(self.issue(attestation_id="attestation-identifier-002"))
        with self.assertRaisesRegex(ReauthenticationAttestationError, "registry_full"):
            registry.consume(next_proof, NOW + 1)
        registry.consume(next_proof, NOW + ATTESTATION_TTL_SECONDS + 1)

    def test_refuses_short_keys_bad_ids_and_invalid_times(self) -> None:
        with self.assertRaisesRegex(ReauthenticationAttestationError, "signing_key_invalid"):
            self.issue(signing_key=b"short")
        with self.assertRaisesRegex(ReauthenticationAttestationError, "attestation_id_invalid"):
            self.issue(attestation_id="bad")
        with self.assertRaisesRegex(ReauthenticationAttestationError, "time_invalid"):
            self.issue(authenticated_at_epoch=True)

    def test_module_has_no_network_filesystem_or_runtime_activation_dependency(self) -> None:
        source = (Path(__file__).resolve().parent / "reauthentication_attestation.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse({"os", "pathlib", "requests", "urllib", "http.client", "socket", "subprocess"} & imported_modules)
        invoked_names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertNotIn("open", invoked_names)


if __name__ == "__main__":
    unittest.main()
