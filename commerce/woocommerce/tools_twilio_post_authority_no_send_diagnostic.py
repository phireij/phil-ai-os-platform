from __future__ import annotations

import base64
import json
import os
from urllib import error, parse, request

API_BASES = (
    ("default_us1", "https://api.twilio.com/2010-04-01"),
    ("explicit_us1", "https://api.us1.twilio.com/2010-04-01"),
)


def _auth(user: str, password: str) -> str:
    raw = f"{user}:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _probe(
    account_sid: str,
    messaging_service_sid: str,
    username: str,
    password: str,
    credential_label: str,
    endpoint_label: str,
    api_base: str,
) -> dict[str, object]:
    endpoint = f"{api_base}/Accounts/{account_sid}/Messages.json"
    # Use the account-owned Messaging Service, but deliberately omit To and Body.
    # Without a destination Twilio cannot create or deliver a message.
    form = parse.urlencode({"MessagingServiceSid": messaging_service_sid}).encode("utf-8")
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
            return {
                "credential": credential_label,
                "endpoint": endpoint_label,
                "http": int(response.status),
                "unexpected_success": True,
                "message_requested": False,
            }
    except error.HTTPError as exc:
        provider_code = None
        try:
            payload = json.loads(exc.read().decode("utf-8") or "{}")
            candidate = payload.get("code") if isinstance(payload, dict) else None
            provider_code = str(candidate).strip() if candidate is not None else None
        except Exception:
            pass
        return {
            "credential": credential_label,
            "endpoint": endpoint_label,
            "http": int(exc.code),
            "twilio_code": provider_code,
            "authorized_to_validate_post": int(exc.code) != 401,
            "message_requested": False,
        }


def main() -> int:
    account_sid = os.getenv("RUBY_TWILIO_ACCOUNT_SID", "").strip()
    messaging_service_sid = os.getenv("RUBY_TWILIO_MESSAGING_SERVICE_SID", "").strip()
    key_sid = os.getenv("RUBY_TWILIO_API_KEY_SID", "").strip()
    key_secret = os.getenv("RUBY_TWILIO_API_KEY_SECRET", "").strip()
    auth_token = os.getenv("RUBY_TWILIO_AUTH_TOKEN", "").strip()
    required = [account_sid, messaging_service_sid, key_sid, key_secret, auth_token]
    if not all(required):
        print(json.dumps({"status": "blocked", "reason": "required credential missing"}, sort_keys=True))
        return 2
    if not (messaging_service_sid.startswith("MG") and len(messaging_service_sid) == 34):
        print(json.dumps({"status": "blocked", "reason": "messaging service identity invalid"}, sort_keys=True))
        return 2

    credential_paths = (
        ("standard_api_key", key_sid, key_secret),
        ("account_sid_auth_token", account_sid, auth_token),
    )
    results = [
        _probe(
            account_sid,
            messaging_service_sid,
            username,
            password,
            credential_label,
            endpoint_label,
            api_base,
        )
        for endpoint_label, api_base in API_BASES
        for credential_label, username, password in credential_paths
    ]
    print(json.dumps({"status": "ok", "message_requested": False, "results": results}, sort_keys=True))
    print("PHIL_AI_OS_TWILIO_POST_AUTHORITY_DIAGNOSTIC_NO_SEND message_requested=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
