from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit


ELIGIBLE_ORDER_STATUSES = frozenset({"pending"})
BLOCKED_ORDER_STATUSES = frozenset({"cancelled", "failed", "processing", "completed", "refunded"})


class SmsNotificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaymentLinkSmsRequest:
    order_id: int
    order_number: str
    order_status: str
    customer_phone: str
    amount_minor: int
    currency: str
    payment_url: str
    requested_date: str | None = None

    def __post_init__(self) -> None:
        if self.order_id <= 0:
            raise ValueError("order_id must be positive")
        if not self.order_number.strip():
            raise ValueError("order_number is required")
        if self.amount_minor < 0:
            raise ValueError("amount_minor must be non-negative")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency must be a 3-letter code")
        if not self.payment_url.startswith("https://"):
            raise ValueError("payment_url must use HTTPS")

    @property
    def normalized_phone(self) -> str:
        raw = "".join(ch for ch in self.customer_phone.strip() if ch.isdigit() or ch == "+")
        if raw.startswith("+81"):
            local = raw[3:].lstrip("0")
            normalized = f"+81{local}"
        elif raw.startswith("0"):
            normalized = f"+81{raw[1:]}"
        else:
            normalized = raw
        if not normalized.startswith("+81") or len(normalized) < 11:
            raise ValueError("customer_phone must be a valid Japanese phone number")
        return normalized

    @property
    def idempotency_key(self) -> str:
        source = f"payment-link-sms:v1:{self.order_id}:{self.order_status}:{self.normalized_phone}:{self.payment_url}"
        return sha256(source.encode("utf-8")).hexdigest()

    def safe_audit_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["customer_phone"] = self._masked_phone()
        data["payment_url"] = redact_payment_url(self.payment_url)
        data["idempotency_key"] = self.idempotency_key
        return data

    def _masked_phone(self) -> str:
        phone = self.normalized_phone
        return f"{phone[:3]}******{phone[-2:]}"


@dataclass(frozen=True)
class SmsSendResult:
    status: str
    provider: str
    idempotency_key: str
    provider_message_id: str | None = None
    reason: str | None = None


class SmsProvider(Protocol):
    name: str

    def send_payment_link_sms(self, request: PaymentLinkSmsRequest) -> SmsSendResult:
        ...


class DisabledSmsProvider:
    """A0-safe default: records intent but never contacts an external SMS service."""

    name = "disabled"

    def send_payment_link_sms(self, request: PaymentLinkSmsRequest) -> SmsSendResult:
        return SmsSendResult(
            status="not_sent",
            provider=self.name,
            idempotency_key=request.idempotency_key,
            reason="production SMS provider is not authorized/configured",
        )


class MemorySmsProvider:
    """Isolated provider used by tests and pre-production contract validation."""

    name = "memory"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[PaymentLinkSmsRequest] = []

    def send_payment_link_sms(self, request: PaymentLinkSmsRequest) -> SmsSendResult:
        if self.fail:
            raise SmsNotificationError("simulated provider failure")
        self.requests.append(request)
        return SmsSendResult(
            status="sent",
            provider=self.name,
            idempotency_key=request.idempotency_key,
            provider_message_id=f"memory-{len(self.requests)}",
        )


class PaymentLinkSmsService:
    """Bounded approval-to-payment SMS notification service.

    It deliberately does not approve orders, mutate payments, retry automatically,
    or select/activate a production SMS provider. Those remain separate authority
    gates. The only eligible state is WooCommerce `pending` (payment required).
    """

    def __init__(self, provider: SmsProvider | None = None) -> None:
        self.provider = provider or DisabledSmsProvider()
        self._sent_keys: set[str] = set()

    def notify(self, request: PaymentLinkSmsRequest) -> SmsSendResult:
        if request.order_status in BLOCKED_ORDER_STATUSES:
            return SmsSendResult(
                status="not_sent",
                provider=self.provider.name,
                idempotency_key=request.idempotency_key,
                reason=f"order status {request.order_status} is not payment-link eligible",
            )
        if request.order_status not in ELIGIBLE_ORDER_STATUSES:
            return SmsSendResult(
                status="not_sent",
                provider=self.provider.name,
                idempotency_key=request.idempotency_key,
                reason="order must be approved and pending payment",
            )

        key = request.idempotency_key
        if key in self._sent_keys:
            return SmsSendResult(
                status="duplicate_suppressed",
                provider=self.provider.name,
                idempotency_key=key,
                reason="idempotency key already sent",
            )

        try:
            result = self.provider.send_payment_link_sms(request)
        except Exception as exc:
            raise SmsNotificationError("SMS provider failed safely; no automatic retry performed") from exc

        if result.status == "sent":
            self._sent_keys.add(key)
        return result


def redact_payment_url(url: str) -> str:
    """Remove order keys/tokens from logs while retaining useful route evidence."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
