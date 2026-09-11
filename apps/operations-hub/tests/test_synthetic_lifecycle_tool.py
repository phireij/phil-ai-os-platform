import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SyntheticLifecycleToolTests(unittest.TestCase):
    def test_tool_emits_non_authorizing_green_marker(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools_synthetic_lifecycle_smoke.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        output = completed.stdout
        self.assertIn("PHIL_AI_OS_SPRINT_5_MULTICHANNEL_SYNTHETIC_GREEN", output)
        self.assertIn("accepted=5", output)
        self.assertIn("duplicates_blocked=5", output)
        self.assertIn("network_call=false", output)
        self.assertIn("external_dispatch=false", output)
        self.assertIn("order_mutation=false", output)
        self.assertIn("payment=false", output)
        self.assertIn("inventory_mutation=false", output)
        self.assertIn("production_authority=false", output)


if __name__ == "__main__":
    unittest.main()
