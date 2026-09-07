import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_twilio_support_request_inspector.py"
spec = importlib.util.spec_from_file_location("twilio_support_request_inspector", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TwilioSupportRequestInspectorTests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "account_sid_raw": "AC" + "1" * 32,
            "api_key_sid_raw": "SK" + "2" * 32,
            "api_key_secret_raw": "super-secret-api-key-material",
            "messaging_service_sid_raw": "MG" + "3" * 32,
            "test_to_raw": "+819012345678",
            "auth_token_raw": "webhook-auth-token-material",
        }
        values.update(overrides)
        return module.InspectorConfig(**values)

    def test_builds_support_safe_request_without_network_or_message(self):
        config = self.config()
        result = module.inspect_request(config)
        rendered = json.dumps(result, sort_keys=True)

        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["network_request_performed"])
        self.assertFalse(result["message_requested"])
        self.assertTrue(result["checks"]["endpoint_uses_account_sid"])
        self.assertTrue(result["checks"]["outbound_basic_auth_uses_api_key"])
        self.assertFalse(result["checks"]["webhook_auth_token_used_for_outbound"])
        self.assertTrue(result["checks"]["messaging_service_used_instead_of_from"])
        self.assertEqual(result["sanitized_request"]["method"], "POST")
        self.assertIn("MessagingServiceSid", result["sanitized_request"]["body_fields"])
        self.assertNotIn("From", result["sanitized_request"]["body_fields"])

        for secret in (
            config.account_sid,
            config.api_key_sid,
            config.api_key_secret,
            config.messaging_service_sid,
            config.test_to,
            config.auth_token,
        ):
            self.assertNotIn(secret, rendered)

    def test_detects_surrounding_whitespace_without_logging_secret(self):
        config = self.config(api_key_secret_raw=" secret-with-spaces \n")
        result = module.inspect_request(config)
        rendered = json.dumps(result, sort_keys=True)

        self.assertTrue(result["checks"]["surrounding_whitespace_detected"])
        self.assertTrue(result["checks"]["surrounding_whitespace"]["api_key_secret"])
        self.assertNotIn("secret-with-spaces", rendered)

    def test_requires_expected_identity_shapes(self):
        cases = [
            ("account_sid_raw", "AC123", "account SID"),
            ("api_key_sid_raw", "SK123", "API key SID"),
            ("messaging_service_sid_raw", "MG123", "Messaging Service SID"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(module.InspectorError, expected):
                    module.inspect_request(self.config(**{field: value}))

    def test_no_destination_is_allowed_for_inspection(self):
        result = module.inspect_request(self.config(test_to_raw=""))
        self.assertFalse(result["message_requested"])
        self.assertEqual(result["sanitized_request"]["body"].split("&")[0], "To=%3Cnot-loaded%3E")

    def test_source_has_no_network_transport(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("urlopen", source)
        self.assertNotIn("Request(", source)
        self.assertNotIn("http.client", source)


if __name__ == "__main__":
    unittest.main()
