from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Mapping
from urllib import error, parse, request

TWILIO_API_REGIONS = (
    ("us1", "https://api.twilio.com/2010-04-01"),
    ("jp1", "https://api.tokyo.jp1.twilio.com/2010-04-01"),
)
NONEXISTENT_MESSAGE_SID = "SM" + ("0" * 32)
CANONICAL_STATUS_CALLBACK = "https://hermes-agent-whow.srv1833510.hstgr.cloud/v1/webhooks/twilio/sms-status"
CONTROLLED_TEST_BODY = (
    "Ruby's Cake Delights SMS delivery test. No action required. "
    "ルビーズケーキデライツ SMS配信テストです。対応は不要です。 "
    "Help / お問い合わせ: order@rubyscakedelights.com"
)


class ControlledTestError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlledTestConfig:
    account_sid: str
    api_key_sid: str
    api_key_secret: str
    messaging_service_sid: str
    test_to: str
    execute_token: str
    status_callback_url: str = CANONICAL_STATUS_CALLBACK
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ControlledTestConfig":
        source = os.environ if env is None else env
        return cls(
            account_sid=str(source.get("RUBY_TWILIO_ACCOUNT_SID", "")).strip(),
            api_key_sid=str(source.get("RUBY_TWILIO_API_KEY_SID", "")).strip(),
            api_key_secret=str(source.get("RUBY_TWILIO_API_KEY_SECRET", "")).strip(),
            messaging_service_sid=str(source.get("RUBY_TWILIO_MESSAGING_SERVICE_SID", "")).strip(),
            test_to=str(source.get("RUBY_TWILIO_TEST_TO", "")).strip(),
            execute_token=str(source.get("RUBY_TWILIO_CONTROLLED_TEST_EXECUTE", "")).strip(),
        )

    def validate(self) -> None:
        if self.execute_token != "SEND_ONE_CONTROLLED_TEST":
            raise ControlledTestError("controlled test execution token is not armed")
        if not self.account_sid.startswith("AC"):
            raise ControlledTestError("Twilio account SID is not configured")
        if not self.api_key_sid.startswith("SK"):
            raise ControlledTestError("Twilio API key SID is not configured")
        if not self.api_key_secret:
            raise ControlledTestError("Twilio API key secret is not configured")
        if not self.messaging_service_sid.startswith("MG"):
            raise ControlledTestError("Twilio Messaging Service SID is not configured")
        if not self.test_to.startswith("+81") or not self.test_to[1:].isdigit():
            raise ControlledTestError("controlled test destination must be a Japanese E.164 number")
        callback = parse.urlsplit(self.status_callback_url)
        if callback.scheme != "https" or callback.path != "/v1/webhooks/twilio/sms-status":
            raise ControlledTestError("canonical Twilio status callback is required")


def _provider_error_details(exc: error.HTTPError) -> tuple[int, str | None]:
    provider_code = None
    try:
        raw = exc.read().decode("utf-8")
        payload = json.loads(raw) if raw else {}
        candidate = payload.get("code") if isinstance(payload, dict) else None
        provider_code = str(candidate).strip() if candidate is not None else None
    except Exception:
        provider_code = None
    return int(exc.code), provider_code


class OneShotTwilioTransport:
    def _basic(self, config: ControlledTestConfig) -> str:
        credentials = f"{config.api_key_sid}:{config.api_key_secret}".encode("utf-8")
        return base64.b64encode(credentials).decode("ascii")

    def _region_authenticates(self, *, config: ControlledTestConfig, region: str, api_base: str) -> bool:
        probe_endpoint = (
            f"{api_base}/Accounts/{config.account_sid}/Messages/{NONEXISTENT_MESSAGE_SID}.json"
        )
        req = request.Request(
            probe_endpoint,
            headers={
                "Authorization": "Basic " + self._basic(config),
                "Accept": "application/json",
                "User-Agent": "phil-ai-os-platform/twilio-controlled-test-region-probe",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=config.timeout_seconds) as response:
                raise ControlledTestError(
                    f"Twilio region auth probe returned unexpected HTTP {int(response.status)} "
                    f"for region={region}; no message requested"
                )
        except error.HTTPError as exc:
            status_code, provider_code = _provider_error_details(exc)
            if status_code == 404 and provider_code == "20404":
                return True
            if status_code == 401 and provider_code == "20003":
                return False
            suffix = f" twilio_code={provider_code}" if provider_code else ""
            raise ControlledTestError(
                f"Twilio region auth probe failed region={region} HTTP {status_code}{suffix}; "
                "no message requested"
            ) from exc
        except ControlledTestError:
            raise
        except Exception as exc:
            raise ControlledTestError(
                f"Twilio region auth probe transport failed region={region}; no message requested"
            ) from exc

    def _resolve_api_base(self, *, config: ControlledTestConfig) -> tuple[str, str]:
        authenticated: list[tuple[str, str]] = []
        for region, api_base in TWILIO_API_REGIONS:
            if self._region_authenticates(config=config, region=region, api_base=api_base):
                authenticated.append((region, api_base))
        if not authenticated:
            raise ControlledTestError(
                "Twilio API key did not authenticate to the supported Messages API regions; "
                "no message requested"
            )
        if len(authenticated) != 1:
            raise ControlledTestError(
                "Twilio API key region was ambiguous across supported Messages API regions; "
                "no message requested"
            )
        return authenticated[0]

    def post(self, *, config: ControlledTestConfig) -> tuple[int, dict[str, object]]:
        region, api_base = self._resolve_api_base(config=config)
        endpoint = f"{api_base}/Accounts/{config.account_sid}/Messages.json"
        form = parse.urlencode(
            {
                "To": config.test_to,
                "MessagingServiceSid": config.messaging_service_sid,
                "Body": CONTROLLED_TEST_BODY,
                "StatusCallback": config.status_callback_url,
            }
        ).encode("utf-8")
        req = request.Request(
            endpoint,
            data=form,
            headers={
                "Authorization": "Basic " + self._basic(config),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "phil-ai-os-platform/twilio-controlled-test-send-once",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                payload = json.loads(raw) if raw else {}
                if isinstance(payload, dict):
                    payload["_phil_ai_os_region"] = region
                return int(response.status), payload
        except error.HTTPError as exc:
            status_code, provider_code = _provider_error_details(exc)
            suffix = f" twilio_code={provider_code}" if provider_code else ""
            raise ControlledTestError(
                f"Twilio controlled test rejected region={region} HTTP {status_code}{suffix}; "
                "no retry performed"
            ) from exc
        except Exception as exc:
            raise ControlledTestError("Twilio controlled test transport failed safely; no retry performed") from exc


def execute_once(
    config: ControlledTestConfig,
    *,
    transport: OneShotTwilioTransport | None = None,
) -> dict[str, object]:
    config.validate()
    sender = transport or OneShotTwilioTransport()
    status_code, payload = sender.post(config=config)
    if status_code < 200 or status_code >= 300:
        provider_code = str(payload.get("code") or "").strip()
        suffix = f" twilio_code={provider_code}" if provider_code else ""
        raise ControlledTestError(f"Twilio rejected controlled test with HTTP {status_code}{suffix}")
    sid = str(payload.get("sid") or "").strip()
    provider_status = str(payload.get("status") or "accepted").strip().lower()
    region = str(payload.get("_phil_ai_os_region") or "unknown").strip().lower()
    return {
        "controlled_test": True,
        "messages_requested": 1,
        "automatic_retry": False,
        "destination_logged": False,
        "message_sid_hash": hashlib.sha256(sid.encode("utf-8")).hexdigest()[:16] if sid else None,
        "provider_status": provider_status,
        "twilio_region": region,
        "authority_effect": "none",
    }


def main() -> int:
    try:
        result = execute_once(ControlledTestConfig.from_env())
    except ControlledTestError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "automatic_retry": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    print("PHIL_AI_OS_TWILIO_SINGLE_CONTROLLED_TEST_REQUESTED messages_requested=1 automatic_retry=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
