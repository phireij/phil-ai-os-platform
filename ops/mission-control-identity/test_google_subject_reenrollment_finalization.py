"""Static safety checks for the one-time Google-subject finalization script."""

from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "finalize-google-subject-reenrollment.sh"


class GoogleSubjectReenrollmentFinalizationTests(unittest.TestCase):
    def test_restores_the_app_readable_digest_permission_boundary(self) -> None:
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("-g root -m 400", content)
        self.assertGreaterEqual(content.count("-g 10002 -m 640"), 3)
        self.assertIn("r3_metadata_writer_restored=true", content)


if __name__ == "__main__":
    unittest.main()
