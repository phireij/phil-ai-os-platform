"""Offline checks for the default-off R3 metadata-writer configuration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import r3_attestation_metadata_writer_config as config  # noqa: E402


class R3AttestationMetadataWriterConfigurationTests(unittest.TestCase):
    def test_configuration_is_inactive_without_exact_opt_in(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(config.R3AttestationMetadataWriterConfigurationError, "writer_inactive"):
                config.R3AttestationMetadataWriterConfig.from_environment()

    def test_database_and_role_are_exact_before_password_access(self) -> None:
        environment = {"MISSION_CONTROL_R3_ATTESTATION_METADATA_WRITER_ENABLED": "true"}
        with mock.patch.dict("os.environ", environment, clear=True):
            with mock.patch.object(config, "_protected_password_file") as password_file:
                with self.assertRaisesRegex(config.R3AttestationMetadataWriterConfigurationError, "database_invalid"):
                    config.R3AttestationMetadataWriterConfig.from_environment()
                password_file.assert_not_called()

    def test_password_path_must_be_the_designated_protected_file(self) -> None:
        environment = {"MISSION_CONTROL_R3_ATTESTATION_WRITER_PASSWORD_FILE": "/tmp/password"}
        with mock.patch.dict("os.environ", environment, clear=True):
            with self.assertRaisesRegex(config.R3AttestationMetadataWriterConfigurationError, "password_path_invalid"):
                config._protected_password_file("MISSION_CONTROL_R3_ATTESTATION_WRITER_PASSWORD_FILE")

    def test_source_has_no_database_driver_or_runtime_entrypoint(self) -> None:
        source = (ROOT / "r3_attestation_metadata_writer_config.py").read_text(encoding="utf-8").lower()
        for forbidden in ("psycopg", "sqlalchemy", "connect(", "cursor(", "httpserver", "serve_forever", "github"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
