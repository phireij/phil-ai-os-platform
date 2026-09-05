from __future__ import annotations

import base64
import json
import os
from urllib import request


def _get_json(endpoint: str, basic: str, failure_label: str) -> tuple[int, dict[str, object]]:
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
            return int(response.status), payload
    except Exception as exc:
        raise SystemExit(f"PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: {failure_label}_fetch_failed") from exc


def main() -> int:
    account_sid = os.environ.get("RUBY_TWILIO_ACCOUNT_SID", "").strip()
    api_key_sid = os.environ.get("RUBY_TWILIO_API_KEY_SID", "").strip()
    api_key_secret = os.environ.get("RUBY_TWILIO_API_KEY_SECRET", "").strip()
    messaging_service_sid = os.environ.get("RUBY_TWILIO_MESSAGING_SERVICE_SID", "").strip()
    expected_alpha_sender = os.environ.get("RUBY_TWILIO_ALPHA_SENDER", "RUBYSCAKE").strip()

    if not account_sid.startswith("AC") or len(account_sid) != 34:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: account_sid_missing_or_invalid")
    if not api_key_sid.startswith("SK") or len(api_key_sid) != 34:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: api_key_sid_missing_or_invalid")
    if not api_key_secret:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: api_key_secret_missing")
    if not messaging_service_sid.startswith("MG") or len(messaging_service_sid) != 34:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: messaging_service_sid_missing_or_invalid")
    if not expected_alpha_sender:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: alpha_sender_missing")

    basic = base64.b64encode(f"{api_key_sid}:{api_key_secret}".encode("utf-8")).decode("ascii")

    # Restricted and Standard API keys cannot read Twilio's /Accounts resource.
    # Validate the scoped production surface directly instead: the expected
    # Messaging Service and its configured Alphanumeric Sender.
    service_endpoint = f"https://messaging.twilio.com/v1/Services/{messaging_service_sid}"
    service_status_code, service_payload = _get_json(service_endpoint, basic, "messaging_service")
    if service_status_code != 200:
        raise SystemExit(
            f"PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: messaging_service_http_{service_status_code}"
        )
    if str(service_payload.get("sid") or "") != messaging_service_sid:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: messaging_service_identity_mismatch")

    alpha_endpoint = f"https://messaging.twilio.com/v1/Services/{messaging_service_sid}/AlphaSenders"
    alpha_status_code, alpha_payload = _get_json(alpha_endpoint, basic, "alpha_sender")
    if alpha_status_code != 200:
        raise SystemExit(f"PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: alpha_sender_http_{alpha_status_code}")
    senders = alpha_payload.get("alpha_senders")
    if not isinstance(senders, list):
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_FAILED: alpha_sender_payload_invalid")
    alpha_names = {
        str(item.get("alpha_sender") or "").strip()
        for item in senders
        if isinstance(item, dict)
    }
    if expected_alpha_sender not in alpha_names:
        raise SystemExit("PHIL_AI_OS_TWILIO_PREFLIGHT_BLOCKED: expected_alpha_sender_not_found")

    print(
        "PHIL_AI_OS_TWILIO_PRODUCTION_READONLY_PREFLIGHT_GREEN "
        "account_sid_shape=true restricted_api_key=true messaging_service=true "
        "alpha_sender=true message_send=false mutation=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
