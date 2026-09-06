from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools_twilio_post_authority_no_send_diagnostic.py"


class TwilioPostAuthorityNoSendDiagnosticTests(unittest.TestCase):
    def test_diagnostic_cannot_supply_real_destination_or_body(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('method="POST"', source)
        self.assertIn('"MessagingServiceSid"', source)
        self.assertNotIn('"To"', source)
        self.assertNotIn('"Body"', source)
        self.assertNotIn("RUBY_TWILIO_TEST_TO", source)
        self.assertIn('"message_requested": False', source)

    def test_both_credential_paths_are_compared(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"standard_api_key"', source)
        self.assertIn('"account_sid_auth_token"', source)


if __name__ == "__main__":
    unittest.main()
