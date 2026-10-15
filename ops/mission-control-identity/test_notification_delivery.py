"""Offline checks for the dormant Mission Control Telegram transport."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from notification_delivery import (
    NotificationConfigurationError,
    TelegramDeliveryConfig,
    TelegramTransport,
)


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    @staticmethod
    def read(_limit: int) -> bytes:
        return b'{"ok":true,"result":{"message_id":1}}'


class TelegramDeliveryChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        if os.name != "nt":
            os.chmod(self.root, 0o700)
        self.token = self.root / "telegram-token"
        self.chat = self.root / "telegram-chat"
        self.token.write_text("123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdef", encoding="ascii")
        self.chat.write_text("123456789", encoding="ascii")
        if os.name != "nt":
            os.chmod(self.token, 0o600)
            os.chmod(self.chat, 0o600)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_delivery_is_disabled_by_default_and_explicit_enable_requires_private_files(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(TelegramDeliveryConfig.from_environment())
        with patch.dict(os.environ, {"MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED": "true"}, clear=True):
            with self.assertRaises(NotificationConfigurationError):
                TelegramDeliveryConfig.from_environment()

    def test_transport_posts_only_identifier_message(self) -> None:
        environment = {
            "MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED": "true",
            "MISSION_CONTROL_TELEGRAM_BOT_TOKEN_FILE": str(self.token),
            "MISSION_CONTROL_TELEGRAM_CHAT_ID_FILE": str(self.chat),
        }
        with patch.dict(os.environ, environment, clear=True):
            config = TelegramDeliveryConfig.from_environment()
        self.assertIsNotNone(config)
        transport = TelegramTransport(config)
        notification = {
            "notification_id": "notification_abcdefghijklmno",
            "decision_id": "decision_abcdefghijklmno",
            "proposal_id": "proposal_abcdefghijklmno",
        }
        with patch("notification_delivery.urlopen", return_value=_Response()) as open_mock:
            transport.send(notification)
        request = open_mock.call_args.args[0]
        self.assertEqual("POST", request.get_method())
        self.assertTrue(request.full_url.startswith("https://api.telegram.org/bot"))
        body = request.data.decode("utf-8")
        self.assertIn(notification["notification_id"], body)
        self.assertIn(notification["decision_id"], body)
        self.assertIn(notification["proposal_id"], body)
        self.assertNotIn("rationale", body)


if __name__ == "__main__":
    unittest.main()
