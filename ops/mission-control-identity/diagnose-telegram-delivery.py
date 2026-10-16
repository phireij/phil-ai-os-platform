"""Run a credential-safe, read-only Telegram transport diagnostic.

This program emits only fixed status categories.  It never prints a token,
chat identifier, Telegram response body, exception text, or URL, and it
never invokes Telegram's sendMessage endpoint.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOKEN_FILE = Path("/run/secrets/telegram/bot_token")
CHAT_ID_FILE = Path("/run/secrets/telegram/chat_id")
TIMEOUT_SECONDS = 10


def _request(token: str, method: str, payload: dict[str, str] | None = None) -> tuple[str, dict]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310: fixed Telegram API host
            if response.status != 200:
                return "api_http_error", {}
            result = json.loads(response.read(16_384).decode("utf-8"))
    except HTTPError as error:
        return f"http_{error.code}", {}
    except (URLError, OSError, UnicodeError, json.JSONDecodeError):
        return "transport_unavailable", {}
    except BaseException:
        return "unexpected_failure", {}
    if isinstance(result, dict) and result.get("ok") is True and isinstance(result.get("result"), dict):
        return "ok", result["result"]
    return "response_rejected", {}


def destination_category(bot: dict, chat: dict) -> str:
    """Classify locally; never disclose identities or infer send permission."""
    bot_id, chat_id = bot.get("id"), chat.get("id")
    if type(bot_id) is not int or type(chat_id) is not int:
        return "unknown"
    if bot_id == chat_id:
        return "bot_self_destination"
    kind = chat.get("type")
    if kind in {"private", "group", "supergroup", "channel"}:
        return kind + "_send_permission_unverified"
    return "unknown"


def main() -> int:
    try:
        token = TOKEN_FILE.read_text(encoding="ascii").strip()
        chat_id = CHAT_ID_FILE.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        print("telegram_diagnostic=secret_files_unavailable")
        return 0

    token_status, bot = _request(token, "getMe")
    if token_status == "ok":
        print("telegram_get_me=credentials_accepted")
    elif token_status in {"http_401", "http_404", "response_rejected"}:
        print("telegram_get_me=credentials_rejected")
        print("telegram_get_chat=skipped")
        return 0
    elif token_status.startswith("http_"):
        print("telegram_get_me=api_http_error")
        print("telegram_get_chat=skipped")
        return 0
    else:
        print(f"telegram_get_me={token_status}")
        print("telegram_get_chat=skipped")
        return 0

    destination_status, chat = _request(token, "getChat", {"chat_id": chat_id})
    if destination_status == "ok":
        print("telegram_get_chat=destination_accepted")
        print("telegram_destination=" + destination_category(bot, chat))
    elif destination_status in {"http_400", "http_403", "http_404", "response_rejected"}:
        print("telegram_get_chat=destination_rejected")
    elif destination_status.startswith("http_"):
        print("telegram_get_chat=api_http_error")
    else:
        print(f"telegram_get_chat={destination_status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
