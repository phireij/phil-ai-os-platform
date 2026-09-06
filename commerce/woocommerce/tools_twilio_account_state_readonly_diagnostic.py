from __future__ import annotations

import base64
import json
import os
from urllib import error, request

ACCOUNT_ENDPOINT = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"


def _basic(account_sid: str, auth_token: str) -> str:
    raw = f"{account_sid}:{auth_token}".encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def main() -> int:
    account_sid = os.environ.get("RUBY_TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.environ.get("RUBY_TWILIO_AUTH_TOKEN", "").strip()
    if not account_sid.startswith("AC") or not auth_token:
        print(json.dumps({"status": "blocked", "reason": "required Twilio account credentials missing"}, sort_keys=True))
        return 2

    req = request.Request(
        ACCOUNT_ENDPOINT.format(account_sid=account_sid),
        headers={
            "Authorization": "Basic " + _basic(account_sid, auth_token),
            "Accept": "application/json",
            "User-Agent": "phil-ai-os-platform/twilio-account-state-readonly-diagnostic",
        },
        method="GET",
    )

    try:
        with request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            account_status = str(payload.get("status") or "unknown").strip().lower()
            result = {
                "status": "ok",
                "http": int(response.status),
                "account_status": account_status,
                "message_requested": False,
                "account_sid_logged": False,
            }
            print(json.dumps(result, sort_keys=True))
            print("PHIL_AI_OS_TWILIO_ACCOUNT_STATE_READONLY_DIAGNOSTIC_COMPLETE message_requested=false")
            return 0
    except error.HTTPError as exc:
        provider_code = None
        try:
            raw = exc.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            candidate = payload.get("code") if isinstance(payload, dict) else None
            provider_code = str(candidate).strip() if candidate is not None else None
        except Exception:
            provider_code = None
        result = {
            "status": "ok",
            "http": int(exc.code),
            "twilio_code": provider_code,
            "account_status": "unresolved",
            "message_requested": False,
            "account_sid_logged": False,
        }
        print(json.dumps(result, sort_keys=True))
        print("PHIL_AI_OS_TWILIO_ACCOUNT_STATE_READONLY_DIAGNOSTIC_COMPLETE message_requested=false")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "blocked", "reason": type(exc).__name__, "message_requested": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
