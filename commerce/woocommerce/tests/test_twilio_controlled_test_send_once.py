import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools_twilio_controlled_test_send_once.py"
spec = importlib.util.spec_from_file_location("twilio_controlled_test_send_once", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeTransport:
    def __init__(self, status_code=201, payload=None):
        self.status_code = status_code
        self.payload = payload or {"sid": "SM1234567890", "status": "queued"}
        self.calls = []

    def post(self, *, config):
        self.calls.append(config)
        return self.status_code, self.payload


class ControlledTwilioSendOnceTests(unittest.TestCase):
    def config(self, **overrides):
        values = {
            "account_sid": "AC123",
            "api_key_sid": "SK123",
            "api_key_secret": "secret",
            "messaging_service_sid": "MG123",
            "test_to": "+819012345678",
            "execute_token": "SEND_ONE_CONTROLLED_TEST",
        }
        values.update(overrides)
        return module.ControlledTestConfig(**values)

    def test_exactly_one_transport_call_and_safe_result(self):
        transport = FakeTransport()
        result = module.execute_once(self.config(), transport=transport)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(result["messages_requested"], 1)
        self.assertFalse(result["automatic_retry"])
        self.assertFalse(result["destination_logged"])
        self.assertEqual(result["provider_status"], "queued")
        self.assertNotIn("SM1234567890", str(result))
        self.assertNotIn("+819012345678", str(result))

    def test_not_armed_fails_before_transport(self):
        transport = FakeTransport()
        with self.assertRaisesRegex(module.ControlledTestError, "execution token"):
            module.execute_once(self.config(execute_token=""), transport=transport)
        self.assertEqual(transport.calls, [])

    def test_destination_must_be_japanese_e164(self):
        for destination in ("09012345678", "+12025550123", "+81abc"):
            with self.subTest(destination=destination):
                transport = FakeTransport()
                with self.assertRaisesRegex(module.ControlledTestError, "Japanese E.164"):
                    module.execute_once(self.config(test_to=destination), transport=transport)
                self.assertEqual(transport.calls, [])

    def test_required_twilio_identity_is_fail_closed(self):
        cases = [
            ("account_sid", "", "account SID"),
            ("api_key_sid", "", "API key SID"),
            ("api_key_secret", "", "API key secret"),
            ("messaging_service_sid", "", "Messaging Service SID"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(module.ControlledTestError, expected):
                    module.execute_once(self.config(**{field: value}), transport=FakeTransport())

    def test_non_2xx_fails_without_retry(self):
        transport = FakeTransport(status_code=400, payload={"message": "rejected"})
        with self.assertRaisesRegex(module.ControlledTestError, "HTTP 400"):
            module.execute_once(self.config(), transport=transport)
        self.assertEqual(len(transport.calls), 1)

    def test_canonical_status_callback_is_required(self):
        transport = FakeTransport()
        with self.assertRaisesRegex(module.ControlledTestError, "canonical Twilio status callback"):
            module.execute_once(
                self.config(status_callback_url="https://example.com/wrong"),
                transport=transport,
            )
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
