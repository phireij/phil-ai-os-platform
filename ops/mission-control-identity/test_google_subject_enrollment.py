"""Offline checks for one-time hashed Google-subject enrollment."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import google_subject_enrollment as enrollment  # noqa: E402


class GoogleSubjectEnrollmentTests(unittest.TestCase):
    def test_enrollment_writes_only_a_digest_and_refuses_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "subject"
            target.write_text(enrollment.PENDING_MARKER, encoding="ascii")
            service = enrollment.GoogleSubjectEnrollment(target)
            service.enroll("google-subject-123")
            self.assertEqual(
                "sha256:" + hashlib.sha256(b"google-subject-123").hexdigest() + "\n",
                target.read_text(encoding="ascii"),
            )
            with self.assertRaisesRegex(enrollment.GoogleSubjectEnrollmentError, "already_completed"):
                service.enroll("other-subject")

    def test_environment_requires_exact_opt_in_and_a_pending_protected_file(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(enrollment.GoogleSubjectEnrollmentError, "inactive"):
                enrollment.GoogleSubjectEnrollment.from_environment()
        fake_details = mock.Mock(st_mode=0o100620, st_uid=0, st_gid=10002)
        target = mock.Mock()
        target.lstat.return_value = fake_details
        target.read_text.return_value = enrollment.PENDING_MARKER
        with mock.patch.dict("os.environ", {
            "MISSION_CONTROL_GOOGLE_SUBJECT_ENROLLMENT_ENABLED": "true",
            "MISSION_CONTROL_GOOGLE_SUBJECT_ENROLLMENT_FILE": "/run/secrets/subject_enrollment",
        }, clear=True), mock.patch.object(enrollment, "Path", return_value=target), mock.patch.object(enrollment.stat, "S_ISREG", return_value=True), mock.patch.object(enrollment.stat, "S_IMODE", return_value=0o620):
            self.assertIsInstance(enrollment.GoogleSubjectEnrollment.from_environment(), enrollment.GoogleSubjectEnrollment)

    def test_source_has_no_network_or_raw_subject_output(self) -> None:
        source = (ROOT / "google_subject_enrollment.py").read_text(encoding="utf-8").lower()
        for forbidden in ("requests", "httpserver", "print(", "logging"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
