from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Mapping
from urllib import parse

TWILIO_API_BASE = "https://api.us1.twilio.com/2010-04-01"
CANONICAL_STATUS_CALLBACK = "https://hermes-agent-whow.srv1833510.hstgr.cloud/v1/webhooks/twilio/sms-status"


class InspectorError(RuntimeError):
    pass


def _redact(value: str, *, prefix: int = 2, suffix: int = 4) -> str:
    value = str(value or "")
    if not value:
        return "<missing>"
    if len(value) <= prefix + suffix:
        return "<redacted>"
    return value[:prefix] + "…" + value[-suffix:]


def _fingerprint(value: str) -> str | None:
    value = str(value or "")
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _has_surrounding_whitespace(value: str) -> bool:
    return value != value.strip()


@dataclass(frozen=True)
class InspectorConfig:
    account_sid_raw: str
    api_key_sid_raw: str
    api_key_secret_raw: str
    messaging_service_sid_raw: str
    test_to_raw: str
    auth_token_raw: str
    status_callback_url: str = CANONICAL_STATUS_CALLBACK

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "InspectorConfig":
        source = os.environ if env is None else env
        return cls(
            account_sid_raw=str(source.get("RUBY_TWILIO_ACCOUNT_SID", "")),
            api_key_sid_raw=str(source.get("RUBY_TWILIO_API_KEY_SID", "")),
            api_key_secret_raw=str(source.get("RUBY_TWILIO_API_KEY_SECRET", "")),
            messaging_service_sid_raw=str(source.get("RUBY_TWILIO_MESSAGING_SERVICE_SID", "")),
            test_to_raw=str(source.get("RUBY_TWILIO_TEST_TO", "")),
            auth_token_raw=str(source.get("RUBY_TWILIO_AUTH_TOKEN", "")),
        )

    @property
    def account_sid(self) -> str:
        return self.account_sid_raw.strip()

    @property
    def api_key_sid(self) -> str:
        return self.api_key_sid_raw.strip()

    @property
    def api_key_secret(self) -> str:
        return self.api_key_secret_raw.strip()

    @property
    def messaging_service_sid(self) -> str:
        return self.messaging_service_sid_raw.strip()

    @property
    def test_to(self) -> str:
        return self.test_to_raw.strip()

    @property
    def auth_token(self) -> str:
        return self.auth_token_raw.strip()

    def validate(self) -> None:
        if not (self.account_sid.startswith("AC") and len(self.account_sid) == 34):
            raise InspectorError("Twilio account SID shape is invalid")
        if not (self.api_key_sid.startswith("SK") and len(self.api_key_sid) == 34):
            raise InspectorError("Twilio API key SID shape is invalid")
        if not self.api_key_secret:
            raise InspectorError("Twilio API key secret is missing")
        if not (self.messaging_service_sid.startswith("MG") and len(self.messaging_service_sid) == 34):
            raise InspectorError("Twilio Messaging Service SID shape is invalid")
        if self.test_to and (not self.test_to.startswith("+81") or not self.test_to[1:].isdigit()):
            raise InspectorError("Twilio controlled-test destination is not Japanese E.164")
        callback = parse.urlsplit(self.status_callback_url)
        if callback.scheme != "https" or callback.path != "/v1/webhooks/twilio/sms-status":
            raise InspectorError("canonical Twilio status callback is invalid")


def inspect_request(config: InspectorConfig) -> dict[str, object]:
    config.validate()
    endpoint = f"{TWILIO_API_BASE}/Accounts/{config.account_sid}/Messages.json"
    fields = {
        "To": config.test_to or "<controlled-japan-handset-not-loaded>",
        "MessagingServiceSid": config.messaging_service_sid,
        "Body": "<controlled-test-message-body>",
        "StatusCallback": config.status_callback_url,
    }
    encoded = parse.urlencode(fields)
    basic_material = f"{config.api_key_sid}:{config.api_key_secret}".encode("utf-8")
    encoded_basic = base64.b64encode(basic_material).decode("ascii")

    whitespace = {
        "account_sid": _has_surrounding_whitespace(config.account_sid_raw),
        "api_key_sid": _has_surrounding_whitespace(config.api_key_sid_raw),
        "api_key_secret": _has_surrounding_whitespace(config.api_key_secret_raw),
        "messaging_service_sid": _has_surrounding_whitespace(config.messaging_service_sid_raw),
        "test_to": _has_surrounding_whitespace(config.test_to_raw),
        "auth_token": _has_surrounding_whitespace(config.auth_token_raw),
    }

    return {
        "status": "ok",
        "network_request_performed": False,
        "message_requested": False,
        "checks": {
            "account_sid_shape_valid": True,
            "api_key_sid_shape_valid": True,
            "api_key_secret_present": True,
            "messaging_service_sid_shape_valid": True,
            "endpoint_uses_account_sid": f"/Accounts/{config.account_sid}/" in endpoint,
            "outbound_basic_auth_uses_api_key": True,
            "webhook_auth_token_used_for_outbound": False,
            "messaging_service_used_instead_of_from": True,
            "surrounding_whitespace_detected": any(whitespace.values()),
            "surrounding_whitespace": whitespace,
        },
        "identity_fingerprints": {
            "account_sid": _fingerprint(config.account_sid),
            "api_key_sid": _fingerprint(config.api_key_sid),
            "messaging_service_sid": _fingerprint(config.messaging_service_sid),
        },
        "sanitized_request": {
            "method": "POST",
            "url": f"{TWILIO_API_BASE}/Accounts/{_redact(config.account_sid)}/Messages.json",
            "headers": {
                "Authorization": "Basic <redacted API-Key-SID:API-Key-Secret base64>",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "phil-ai-os-platform/twilio-controlled-test-send-once",
            },
            "body": parse.urlencode(
                {
                    "To": _redact(config.test_to, prefix=3, suffix=2) if config.test_to else "<not-loaded>",
                    "MessagingServiceSid": _redact(config.messaging_service_sid),
                    "Body": "<redacted controlled test body>",
                    "StatusCallback": config.status_callback_url,
                }
            ),
            "body_fields": sorted(fields),
            "authorization_scheme": "Basic",
            "authorization_username_kind": "API Key SID (SK...) ",
            "authorization_password_kind": "API Key Secret",
            "raw_authorization_value_logged": False,
            "raw_encoded_body_logged": False,
        },
        "internal_construction": {
            "basic_auth_material_length": len(basic_material),
            "basic_auth_base64_length": len(encoded_basic),
            "form_encoded_length": len(encoded),
        },
    }


def main() -> int:
    try:
        result = inspect_request(InspectorConfig.from_env())
    except InspectorError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "network_request_performed": False}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PHIL_AI_OS_TWILIO_SUPPORT_REQUEST_INSPECTOR_COMPLETE network_request_performed=false message_requested=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
