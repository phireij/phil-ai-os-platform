from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib import parse, request

from .payment_link_sms import PaymentLinkSmsRequest, SmsNotificationError, SmsSendResult


class TwilioTransport(Protocol):
    def post_form(
        self,
        url: str,
        fields: Mapping[str, str],
        *,
        username: str,
        password: str,
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object]]:
        ...


class UrllibTwilioTransport:
    def post_form(
        self,
        url: str,
        fields: Mapping[str, str],
        *,
        username: str,
        password: str,
        timeout_seconds: float,
    ) -> tuple[int, dict[str, object]]:
        payload = parse.urlencode(fields).encode("utf-8")
        basic = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        req = request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                body = json.loads(raw) if raw else {}
                return int(response.status), body
        except Exception as exc:
            raise SmsNotificationError("Twilio transport failed safely") from exc


@dataclass(frozen=True)
class TwilioSmsConfig:
    account_sid: str = ""
    api_key_sid: str = ""
    api_key_secret: str = ""
    from_identity: str = ""
    messaging_service_sid: str = ""
    status_callback_url: str = ""
    enabled: bool = False
    timeout_seconds: float = 10.0
    api_base_url: str = "https://api.twilio.com/2010-04-01"

    def validate_for_send(self) -> None:
        if not self.enabled:
            return
        if not self.account_sid.startswith("AC"):
            raise ValueError("Twilio account_sid must be configured")
        if not self.api_key_sid.startswith("SK"):
            raise ValueError("Twilio api_key_sid must be configured")
        if not self.api_key_secret:
            raise ValueError("Twilio api_key_secret must be configured")
        if self.messaging_service_sid:
            if not self.messaging_service_sid.startswith("MG"):
                raise ValueError("Twilio messaging_service_sid must start with MG")
        elif not self.from_identity:
            raise ValueError("Twilio messaging_service_sid or from_identity must be configured")
        if self.status_callback_url and not self.status_callback_url.startswith("https://"):
            raise ValueError("Twilio status_callback_url must use HTTPS")


class TwilioSmsProvider:
    """Bounded Twilio adapter using a restricted API key for outbound calls.

    External delivery is impossible unless `config.enabled` is explicitly true.
    No retry loop exists here. Provider failures fail closed to the caller. The
    account Auth Token is intentionally not used for outbound REST API access;
    it is reserved for validating signed Twilio webhooks at the callback boundary.
    """

    name = "twilio"

    def __init__(self, config: TwilioSmsConfig, transport: TwilioTransport | None = None) -> None:
        self.config = config
        self.transport = transport or UrllibTwilioTransport()

    def send_payment_link_sms(self, sms_request: PaymentLinkSmsRequest) -> SmsSendResult:
        self.config.validate_for_send()
        if not self.config.enabled:
            return SmsSendResult(
                status="not_sent",
                provider=self.name,
                idempotency_key=sms_request.idempotency_key,
                reason="Twilio adapter is disabled pending readiness activation gate",
            )

        fields = {
            "To": sms_request.normalized_phone,
            "Body": self._message_body(sms_request),
        }
        if self.config.messaging_service_sid:
            fields["MessagingServiceSid"] = self.config.messaging_service_sid
        else:
            fields["From"] = self.config.from_identity
        if self.config.status_callback_url:
            fields["StatusCallback"] = self.config.status_callback_url

        endpoint = (
            f"{self.config.api_base_url.rstrip('/')}/Accounts/"
            f"{self.config.account_sid}/Messages.json"
        )
        status_code, payload = self.transport.post_form(
            endpoint,
            fields,
            username=self.config.api_key_sid,
            password=self.config.api_key_secret,
            timeout_seconds=self.config.timeout_seconds,
        )
        if status_code < 200 or status_code >= 300:
            raise SmsNotificationError(f"Twilio rejected message request with HTTP {status_code}")

        sid = str(payload.get("sid") or "").strip() or None
        provider_status = str(payload.get("status") or "accepted").strip().lower()
        return SmsSendResult(
            status="sent",
            provider=self.name,
            idempotency_key=sms_request.idempotency_key,
            provider_message_id=sid,
            reason=f"provider_status={provider_status}",
        )

    @staticmethod
    def _message_body(sms_request: PaymentLinkSmsRequest) -> str:
        return (
            "Ruby's Cake Delights: Your order is confirmed. "
            f"Please complete payment here: {sms_request.payment_url}"
        )


class TwilioRequestValidator:
    """Validate Twilio form-encoded webhook signatures using the Account Auth Token.

    Twilio signs webhook requests with the account Auth Token, not an API key
    secret. Production dependency review may replace this bounded implementation
    with Twilio's official SDK validator later.
    """

    def __init__(self, auth_token: str) -> None:
        if not auth_token:
            raise ValueError("auth_token is required")
        self.auth_token = auth_token

    def expected_signature(self, url: str, form_params: Mapping[str, str]) -> str:
        material = url + "".join(
            f"{name}{value}" for name, value in sorted(form_params.items(), key=lambda item: item[0])
        )
        digest = hmac.new(
            self.auth_token.encode("utf-8"),
            material.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        return base64.b64encode(digest).decode("ascii")

    def validate(self, url: str, form_params: Mapping[str, str], signature: str) -> bool:
        if not signature:
            return False
        expected = self.expected_signature(url, form_params)
        return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class TwilioDeliveryStatus:
    message_sid: str
    message_status: str
    error_code: str | None = None

    @classmethod
    def from_form(cls, form_params: Mapping[str, str]) -> "TwilioDeliveryStatus":
        sid = str(form_params.get("MessageSid") or "").strip()
        status = str(form_params.get("MessageStatus") or "").strip().lower()
        if not sid or not status:
            raise ValueError("Twilio delivery callback requires MessageSid and MessageStatus")
        if not sid.startswith("SM"):
            raise ValueError("Twilio delivery callback MessageSid must start with SM")
        error_code = str(form_params.get("ErrorCode") or "").strip() or None
        return cls(message_sid=sid, message_status=status, error_code=error_code)

    def safe_audit_dict(self) -> dict[str, object]:
        return {
            "provider": "twilio",
            "event": "sms_delivery_status",
            "message_sid_hash": hashlib.sha256(self.message_sid.encode("utf-8")).hexdigest()[:16],
            "message_status": self.message_status,
            "error_code": self.error_code,
            "authority_effect": "none",
            "retry_requested": False,
        }


class TwilioStatusCallbackHandler:
    """Signature-validating, non-authorizing delivery callback boundary.

    The handler parses Twilio's form callback into a redacted audit projection.
    It does not mutate WooCommerce, retry a message, send another SMS, or change
    payment state. HTTP routing/persistence are intentionally separate concerns.
    """

    def __init__(self, auth_token: str) -> None:
        self.validator = TwilioRequestValidator(auth_token)

    def handle(
        self,
        request_url: str,
        form_params: Mapping[str, str],
        signature: str,
    ) -> dict[str, object]:
        if not request_url.startswith("https://"):
            raise SmsNotificationError("Twilio callback URL must use HTTPS")
        if not self.validator.validate(request_url, form_params, signature):
            raise SmsNotificationError("Twilio callback signature validation failed")
        status = TwilioDeliveryStatus.from_form(form_params)
        return status.safe_audit_dict()
