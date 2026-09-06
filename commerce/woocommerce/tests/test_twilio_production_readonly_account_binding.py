from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest import TestCase, mock


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools_twilio_production_readonly_preflight.py"
SPEC = importlib.util.spec_from_file_location("twilio_production_readonly_preflight", TOOL_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TwilioProductionReadonlyAccountBindingTests(TestCase):
    def setUp(self) -> None:
        self.account_sid = "AC" + "a" * 32
        self.service_sid = "MG" + "b" * 32
        self.api_key_sid = "SK" + "c" * 32
        self.env = {
            "RUBY_TWILIO_ACCOUNT_SID": self.account_sid,
            "RUBY_TWILIO_API_KEY_SID": self.api_key_sid,
            "RUBY_TWILIO_API_KEY_SECRET": "secret",
            "RUBY_TWILIO_MESSAGING_SERVICE_SID": self.service_sid,
            "RUBY_TWILIO_ALPHA_SENDER": "RUBYSCAKE",
        }

    def test_matching_service_account_binding_allows_alpha_sender_check(self) -> None:
        responses = [
            (200, {"sid": self.service_sid, "account_sid": self.account_sid}),
            (200, {"alpha_senders": [{"alpha_sender": "RUBYSCAKE"}]}),
        ]
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(
            MODULE, "_get_json", side_effect=responses
        ) as get_json:
            self.assertEqual(MODULE.main(), 0)
        self.assertEqual(get_json.call_count, 2)

    def test_mismatched_service_account_binding_fails_before_alpha_sender_check(self) -> None:
        other_account_sid = "AC" + "d" * 32
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(
            MODULE,
            "_get_json",
            return_value=(200, {"sid": self.service_sid, "account_sid": other_account_sid}),
        ) as get_json:
            with self.assertRaisesRegex(SystemExit, "messaging_service_account_binding_mismatch"):
                MODULE.main()
        self.assertEqual(get_json.call_count, 1)

    def test_missing_service_account_binding_fails_closed(self) -> None:
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(
            MODULE,
            "_get_json",
            return_value=(200, {"sid": self.service_sid}),
        ) as get_json:
            with self.assertRaisesRegex(SystemExit, "messaging_service_account_binding_missing"):
                MODULE.main()
        self.assertEqual(get_json.call_count, 1)
