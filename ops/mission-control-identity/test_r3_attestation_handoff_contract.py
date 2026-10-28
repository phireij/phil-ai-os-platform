"""Offline checks for the default-off internal R3 attestation handoff."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock
import stat


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import r3_attestation_handoff_config as config  # noqa: E402


class R3AttestationHandoffChecks(unittest.TestCase):
    def test_configuration_is_inactive_without_an_exact_opt_in(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(config.R3AttestationHandoffConfigurationError, "handoff_inactive"):
                config.R3AttestationHandoffConfig.from_environment()

    def test_wrong_issuer_is_rejected_before_protected_file_access(self) -> None:
        environment = {
            "MISSION_CONTROL_R3_ATTESTATION_HANDOFF_ENABLED": "true",
            "MISSION_CONTROL_R3_ATTESTATION_ISSUER": "https://example.test",
        }
        with mock.patch.dict("os.environ", environment, clear=True):
            with mock.patch.object(config, "_protected_signing_key") as signing_key:
                with self.assertRaisesRegex(config.R3AttestationHandoffConfigurationError, "issuer_invalid"):
                    config.R3AttestationHandoffConfig.from_environment()
                signing_key.assert_not_called()

    def test_signing_key_path_is_exact_and_subject_path_is_absolute(self) -> None:
        with mock.patch.dict("os.environ", {"MISSION_CONTROL_R3_ATTESTATION_SIGNING_KEY_FILE": "/tmp/key"}, clear=True):
            with self.assertRaisesRegex(config.R3AttestationHandoffConfigurationError, "signing_key_path_invalid"):
                config._protected_signing_key("MISSION_CONTROL_R3_ATTESTATION_SIGNING_KEY_FILE")
        with mock.patch.dict("os.environ", {"MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE": "relative"}, clear=True):
            with self.assertRaisesRegex(config.R3AttestationHandoffConfigurationError, "subject_file_invalid"):
                config._protected_subject_file("MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE")

    def test_subject_digest_requires_the_dedicated_read_only_app_group(self) -> None:
        details = mock.Mock(
            st_mode=stat.S_IFREG | 0o640,
            st_uid=0,
            st_gid=10002,
            st_size=72,
        )
        subject_path = Path.cwd() / "ceo_subject_digest"
        environment = {"MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE": str(subject_path)}
        with mock.patch.dict("os.environ", environment, clear=True):
            with mock.patch.object(Path, "lstat", return_value=details):
                self.assertEqual(
                    config._protected_subject_file("MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE"),
                    subject_path,
                )
            details.st_gid = 0
            with mock.patch.object(Path, "lstat", return_value=details):
                with self.assertRaisesRegex(config.R3AttestationHandoffConfigurationError, "subject_file_permissions"):
                    config._protected_subject_file("MISSION_CONTROL_GOOGLE_CEO_SUBJECT_FILE")

    def test_design_only_migration_excludes_sensitive_data_and_authority(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "validate_r3_attestation_handoff_migration.py")],
            cwd=ROOT.parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("R3_ATTESTATION_HANDOFF_MIGRATION_GREEN", result.stdout)

    def test_foundation_migration_remains_design_only_and_authority_free(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "validate_approval_gated_foundation_migration.py")],
            cwd=ROOT.parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("APPROVAL_GATED_FOUNDATION_MIGRATION_GREEN", result.stdout)


if __name__ == "__main__":
    unittest.main()
