from __future__ import annotations

import base64
import json
import os
from urllib import error, parse, request

API_BASE = "https://api.us1.twilio.com/2010-04-01"


def _auth(user: str, password: str) -> str:
    raw = f"{user}:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _probe(account_sid: str, username: str, password: str, label: str) -> dict[str, object]:
    endpoint = f"{API_BASE}/Accounts/{account_sid}/Messages.json"
    # Deliberately omit To and Body so Twilio cannot create a message.
    form = parse.urlencode({"MessagingServiceSid": "MG00000000000000000000000000000000"}).encode("utf-8")
    req = request.Request(
        endpoint,
        data=form,
        headers={
            "Authorization": _auth(username, password),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "phil-ai-os-platform/twilio-post-authority-no-send",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            return {"credential": label, "http": int(response.status), "unexpected_success": True}
    except error.HTTPError as exc:
        provider_code = None
        try:
            payload = json.loads(exc.read().decode("utf-8") or "{}")
            candidate = payload.get("code") if isinstance(payload, dict) else None
            provider_code = str(candidate).strip() if candidate is not None else None
        except Exception:
            pass
        return {
            "credential": label,
            "http": int(exc.code),
            "twilio_code": provider_code,
            "authorized_to_validate_post": int(exc.code) != 401,
            "message_requested": False,
        }


def main() -> int:
    account_sid = os.getenv("RUBY_TWILIO_ACCOUNT_SID", "").strip()
    key_sid = os.getenv("RUBY_TWILIO_API_KEY_SID", "").strip()
    key_secret = os.getenv("RUBY_TWILIO_API_KEY_SECRET", "").strip()
    auth_token = os.getenv("RUBY_TWILIO_AUTH_TOKEN", "").strip()
    required = [account_sid, key_sid, key_secret, auth_token]
    if not all(required):
        print(json.dumps({"status": "blocked", "reason": "required credential missing"}, sort_keys=True))
        return 2

    results = [
        _probe(account_sid, key_sid, key_secret, "standard_api_key"),
        _probe(account_sid, account_sid, auth_token, "account_sid_auth_token"),
    ]
    print(json.dumps({"status": "ok", "message_requested": False, "results": results}, sort_keys=True))
    print("PHIL_AI_OS_TWILIO_POST_AUTHORITY_DIAGNOSTIC_NO_SEND message_requested=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
