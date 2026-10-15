"""Fail-closed, identifier-only Telegram delivery for Mission Control.

This module has no inbound Telegram handling, no task authority, and no
configuration default that can send a message.  It is deliberately used from
the CEO session process so delivery updates share the store's in-process lock
and cannot race encrypted-snapshot persistence.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NotificationConfigurationError(ValueError):
    """A safe-to-log notification configuration failure."""


class NotificationTransportError(RuntimeError):
    """A safe-to-log Telegram transport failure."""


def _protected_secret_file(variable: str, *, minimum: int, maximum: int) -> Path:
    raw = os.environ.get(variable, "")
    if not raw or not Path(raw).is_absolute():
        raise NotificationConfigurationError("telegram_secret_file_unset")
    path = Path(raw)
    try:
        details = path.lstat()
    except OSError as exc:
        raise NotificationConfigurationError("telegram_secret_file_unavailable") from exc
    if path.is_symlink() or not path.is_file() or (os.name != "nt" and details.st_mode & 0o077):
        raise NotificationConfigurationError("telegram_secret_file_invalid")
    if details.st_size < minimum or details.st_size > maximum:
        raise NotificationConfigurationError("telegram_secret_file_invalid")
    return path


@dataclass(frozen=True)
class TelegramDeliveryConfig:
    bot_token_file: Path
    chat_id_file: Path
    retry_seconds: int = 15 * 60
    poll_seconds: int = 30

    @classmethod
    def from_environment(cls) -> TelegramDeliveryConfig | None:
        enabled = os.environ.get("MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED", "")
        if enabled in {"", "false"}:
            return None
        if enabled != "true":
            raise NotificationConfigurationError("telegram_delivery_enabled_invalid")
        bot_token_file = _protected_secret_file(
            "MISSION_CONTROL_TELEGRAM_BOT_TOKEN_FILE", minimum=16, maximum=512
        )
        chat_id_file = _protected_secret_file(
            "MISSION_CONTROL_TELEGRAM_CHAT_ID_FILE", minimum=1, maximum=64
        )
        if bot_token_file == chat_id_file:
            raise NotificationConfigurationError("telegram_secret_paths_overlap")
        return cls(bot_token_file, chat_id_file)


class TelegramTransport:
    """Outbound-only Telegram sender that never logs or persists secrets."""

    def __init__(self, config: TelegramDeliveryConfig) -> None:
        try:
            self._token = config.bot_token_file.read_text(encoding="ascii").strip()
            self._chat_id = config.chat_id_file.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as exc:
            raise NotificationConfigurationError("telegram_secret_unavailable") from exc
        if not re.fullmatch(r"[0-9]{6,16}:[A-Za-z0-9_-]{20,256}", self._token):
            raise NotificationConfigurationError("telegram_bot_token_invalid")
        if not re.fullmatch(r"-?[0-9]{1,32}", self._chat_id) or self._chat_id == "0":
            raise NotificationConfigurationError("telegram_chat_id_invalid")
        self._timeout_seconds = 10

    @staticmethod
    def _body(notification: dict[str, Any]) -> str:
        # Only durable Mission Control identifiers are permitted in a message.
        return (
            "Mission Control notification\n"
            "Event: CEO decision recorded\n"
            f"Notification: {notification['notification_id']}\n"
            f"Decision: {notification['decision_id']}\n"
            f"Proposal: {notification['proposal_id']}\n"
            "Authority effect: none"
        )

    def send(self, notification: dict[str, Any]) -> None:
        payload = json.dumps(
            {"chat_id": self._chat_id, "text": self._body(notification), "disable_web_page_preview": True},
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            f"https://api.telegram.org/bot{self._token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310: fixed Telegram API host
                if response.status != 200:
                    raise NotificationTransportError("telegram_http_error")
                result = json.loads(response.read(16_384).decode("utf-8"))
        except (HTTPError, URLError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise NotificationTransportError("telegram_transport_unavailable") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise NotificationTransportError("telegram_rejected")


class NotificationDeliveryWorker:
    """Bounded in-process delivery loop.  It is never started by default."""

    def __init__(
        self,
        store: Any,
        transport: TelegramTransport,
        *,
        retry_seconds: int,
        poll_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._transport = transport
        self._retry_seconds = retry_seconds
        self._poll_seconds = poll_seconds
        self._clock = clock
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="mission-control-telegram-delivery", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self._poll_seconds + 1)

    def run_once(self) -> bool:
        return self._store.dispatch_one_notification(
            self._transport.send,
            now=int(self._clock()),
            retry_seconds=self._retry_seconds,
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self._poll_seconds)
