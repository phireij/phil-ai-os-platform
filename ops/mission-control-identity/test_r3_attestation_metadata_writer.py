"""Offline checks for the private, INSERT-only R3 metadata writer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import r3_attestation_handoff as handoff  # noqa: E402
import r3_attestation_metadata_writer as writer  # noqa: E402
import r3_attestation_metadata_writer_config as config  # noqa: E402


class R3AttestationMetadataWriterTests(unittest.TestCase):
    def metadata(self, **overrides):
        values = {
            "attestation_id": "A" * 22,
            "issuer": "https://accounts.google.com",
            "subject_sha256": "sha256:" + "a" * 64,
            "attestation_digest": "sha256:" + "b" * 64,
            "verification_id": "r3v_" + "C" * 22,
            "authenticated_at_epoch": 1_700_000_000,
            "expires_at_epoch": 1_700_000_300,
            "retention_expires_at_epoch": 1_731_536_300,
        }
        values.update(overrides)
        return handoff.R3AttestationMetadata(**values)

    def test_prepared_values_exclude_proofs_and_force_no_authority(self) -> None:
        values = writer._validated_values(self.metadata())
        self.assertEqual("A" * 22, values[0])
        self.assertEqual(False, values[-3])
        self.assertEqual(False, values[-2])
        self.assertEqual("none", values[-1])
        self.assertNotIn("token", repr(values).lower())

    def test_unsafe_metadata_is_rejected_before_password_or_database_access(self) -> None:
        service = writer.R3AttestationMetadataWriter(mock.Mock())
        service._config.password_file.read_text.side_effect = AssertionError("must not read")
        with self.assertRaisesRegex(writer.R3AttestationMetadataWriterError, "metadata_invalid"):
            service.write(self.metadata(mutation_authorized=True))

    def test_writer_config_is_still_required(self) -> None:
        with mock.patch.object(config.R3AttestationMetadataWriterConfig, "from_environment", side_effect=config.R3AttestationMetadataWriterConfigurationError("inactive")):
            with self.assertRaisesRegex(config.R3AttestationMetadataWriterConfigurationError, "inactive"):
                writer.R3AttestationMetadataWriter.from_environment()

    def test_source_has_no_route_or_external_action_client(self) -> None:
        source = (ROOT / "r3_attestation_metadata_writer.py").read_text(encoding="utf-8").lower()
        for forbidden in ("requests", "httpserver", "serve_forever", "github"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
