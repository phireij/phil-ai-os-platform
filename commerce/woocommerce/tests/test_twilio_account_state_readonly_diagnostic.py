from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools_twilio_account_state_readonly_diagnostic.py"


class TwilioAccountStateReadonlyDiagnosticTests(unittest.TestCase):
    def test_readonly_account_resource_only(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Accounts/{account_sid}.json", source)
        self.assertIn('method="GET"', source)
        self.assertNotIn("Messages.json", source)
        self.assertNotIn('method="POST"', source)
        self.assertNotIn('"To"', source)
        self.assertNotIn('"Body"', source)

    def test_safe_output_contract(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"account_status"', source)
        self.assertIn('"account_sid_logged": False', source)
        self.assertIn('"message_requested": False', source)


if __name__ == "__main__":
    unittest.main()
