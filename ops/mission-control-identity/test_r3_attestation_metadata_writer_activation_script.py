"""Static safety checks for the separately acknowledged R3 metadata-writer activation."""

from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "activate-google-identity-probe-r3-metadata-writer.sh"


class R3AttestationMetadataWriterActivationScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = SCRIPT.read_text(encoding="utf-8")

    def test_requires_exact_acknowledgement_and_protected_files(self) -> None:
        self.assertIn("MISSION_CONTROL_R3_METADATA_WRITER_ACTIVATION_ACKNOWLEDGEMENT", self.content)
        self.assertIn("approve-r3-metadata-writer-runtime", self.content)
        for path in (
            "google-identity-probe-client-secret",
            "google-r3-attestation-hmac-key",
            "google-ceo-subject-digest",
            "mission-control-postgres-attestation-writer-password",
        ):
            self.assertIn(path, self.content)
        self.assertIn("'0:0:400'", self.content)
        self.assertGreaterEqual(self.content.count("'0:10002:640'"), 3)

    def test_uses_only_the_private_database_network_and_exact_writer_role(self) -> None:
        self.assertIn('test "$DB_NETWORK" = buzz-prod_buzz-net', self.content)
        self.assertIn("docker network connect \"$DB_NETWORK\" \"$CONTAINER\"", self.content)
        self.assertIn("MISSION_CONTROL_R3_ATTESTATION_WRITER_ROLE=mission_control_attestation_writer", self.content)
        self.assertIn("MISSION_CONTROL_R3_ATTESTATION_DATABASE_HOST=buzz-prod-postgres-1", self.content)
        self.assertIn("socket.create_connection", self.content)

    def test_preserves_route_and_rollback_guards(self) -> None:
        self.assertIn("PathPrefix(\\`/auth/google\\`)", self.content)
        self.assertIn("docker rename \"$CONTAINER\" \"$ROLLBACK\"", self.content)
        self.assertIn("restore_and_exit()", self.content)
        self.assertIn("authority_effect=none", self.content)
        self.assertNotIn("github", self.content.lower())


if __name__ == "__main__":
    unittest.main()
