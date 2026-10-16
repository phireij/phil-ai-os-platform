"""Offline destination diagnosis; no Telegram calls or secrets."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("diagnostic", Path(__file__).with_name("diagnose-telegram-delivery.py"))
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


class DiagnosticTests(unittest.TestCase):
    def test_self_destination_is_distinguished_from_private_recipient(self):
        self.assertEqual(diagnostic.destination_category({"id": 123}, {"id": 123, "type": "private"}), "bot_self_destination")
        self.assertEqual(diagnostic.destination_category({"id": 123}, {"id": 456, "type": "private"}), "private_send_permission_unverified")

    def test_missing_or_malformed_identity_does_not_claim_success(self):
        for bot, chat in [({}, {}), ({"id": True}, {"id": 1}), ({"id": "123"}, {"id": 123})]:
            self.assertEqual(diagnostic.destination_category(bot, chat), "unknown")

    def test_readonly_output_excludes_identity_and_content(self):
        output = io.StringIO()
        with patch.object(Path, "read_text", return_value="secret-value"), patch.object(diagnostic, "_request", side_effect=[("ok", {"id": 123, "username": "secret-name"}), ("ok", {"id": 123, "type": "private", "bio": "secret-content"})]) as request, contextlib.redirect_stdout(output):
            diagnostic.main()
        self.assertEqual([call.args[1] for call in request.call_args_list], ["getMe", "getChat"])
        self.assertEqual(output.getvalue(), "telegram_get_me=credentials_accepted\ntelegram_get_chat=destination_accepted\ntelegram_destination=bot_self_destination\n")

    def test_bad_credentials_skip_destination_request(self):
        with patch.object(Path, "read_text", return_value="secret-value"), patch.object(diagnostic, "_request", return_value=("http_401", {})) as request, contextlib.redirect_stdout(io.StringIO()) as output:
            diagnostic.main()
        self.assertEqual(request.call_count, 1)
        self.assertIn("telegram_get_chat=skipped", output.getvalue())


if __name__ == "__main__":
    unittest.main()
