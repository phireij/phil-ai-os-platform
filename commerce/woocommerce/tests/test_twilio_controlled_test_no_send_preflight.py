import ast
import unittest
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools_twilio_controlled_test_no_send_preflight.py"


class TwilioControlledTestNoSendPreflightTests(unittest.TestCase):
    def test_tool_never_targets_twilio_messages_endpoint(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("Messages.json", source)
        self.assertNotIn("api.twilio.com/2010-04-01", source)
        self.assertIn("message_send=false", source)
        self.assertIn("test_authority=false", source)

    def test_destination_is_presence_only_and_never_printed(self):
        source = TOOL.read_text(encoding="utf-8")
        tree = ast.parse(source)
        print_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        rendered_prints = "\n".join(ast.unparse(node) for node in print_calls)
        self.assertNotIn("test_to", rendered_prints)
        self.assertNotIn("RUBY_TWILIO_TEST_TO", rendered_prints)
        self.assertIn("controlled_destination_present=true", rendered_prints)

    def test_provider_must_remain_disabled(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn('record.get("provider_enabled") is not False', source)
        self.assertIn("provider_enabled=false", source)

    def test_callback_probe_is_non_persisting(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn('"MessageSid": "SM00000000000000000000000000000000"', source)
        self.assertIn('signed_fields = {"MessageStatus": "delivered"}', source)
        self.assertNotIn('signed_fields = {"MessageSid"', source)

    def test_callback_retry_is_bounded_and_never_expands_sms_authority(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn("CALLBACK_PROBE_ATTEMPTS = 3", source)
        self.assertIn("TRANSIENT_HTTP_CODES", source)
        self.assertIn("callback_probe_bounded_retry=true", source)
        self.assertIn("automatic_retry=false", source)
        self.assertNotIn("Messages.json", source)
        self.assertNotIn("send_payment_link_sms", source)


if __name__ == "__main__":
    unittest.main()
