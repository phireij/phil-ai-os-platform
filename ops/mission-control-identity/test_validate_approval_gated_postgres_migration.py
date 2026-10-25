import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class ApprovalGatedPostgresMigrationValidationTests(unittest.TestCase):
    def test_static_validator_accepts_the_inactive_migration(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "validate_approval_gated_postgres_migration.py")],
            cwd=ROOT.parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("APPROVAL_GATED_POSTGRES_MIGRATION_GREEN", result.stdout)


if __name__ == "__main__":
    unittest.main()
