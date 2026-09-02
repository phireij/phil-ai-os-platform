from __future__ import annotations

import base64
import json
import os
from urllib import request


def main() -> int:
    account_sid = os.environ.get("RUBY_TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.environ.get("RUBY_TWILIO_AUTH_TOKEN", "").strip()
    if not account_sid.startswith("AC") or len(account_sid) != 34:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: account_sid_missing_or_invalid")
    if not auth_token:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: auth_token_missing")

    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"
    basic = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    req = request.Request(
        endpoint,
        headers={
            "Authorization": f"Basic {basic}",
            "Accept": "application/json",
            "User-Agent": "phil-ai-os-platform/twilio-production-readonly-preflight",
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=10.0) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            status_code = int(response.status)
    except Exception as exc:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: account_fetch_failed") from exc

    if status_code != 200:
        raise SystemExit(f"PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: http_{status_code}")
    if str(payload.get("sid") or "") != account_sid:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: account_identity_mismatch")
    account_status = str(payload.get("status") or "").lower()
    if account_status != "active":
        raise SystemExit(f"PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: account_status_{account_status or 'unknown'}")

    print(
        "PHIL_AI_OS_TWILIO_PRODUCTION_READONLY_PREFLIGHT_GREEN "
        "account=true active=true message_send=false mutation=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
