import pytest

from phil_ai_os_woocommerce.payment_link_sms import (
    DisabledSmsProvider,
    MemorySmsProvider,
    PaymentLinkSmsRequest,
    PaymentLinkSmsService,
    SmsNotificationError,
    redact_payment_url,
)


def request(**overrides):
    values = {
        "order_id": 51,
        "order_number": "51",
        "order_status": "pending",
        "customer_phone": "050-1785-0575",
        "amount_minor": 1165,
        "currency": "JPY",
        "payment_url": "https://shop.example/checkout/order-pay/51/?pay_for_order=true&key=wc_order_secret",
        "requested_date": "2026-09-05",
    }
    values.update(overrides)
    return PaymentLinkSmsRequest(**values)


def test_japanese_phone_normalization_and_deterministic_idempotency():
    local = request(customer_phone="050-1785-0575")
    international = request(customer_phone="+81 50 1785 0575")
    assert local.normalized_phone == "+815017850575"
    assert international.normalized_phone == "+815017850575"
    assert local.idempotency_key == international.idempotency_key


def test_invalid_phone_is_rejected_before_provider_use():
    provider = MemorySmsProvider()
    service = PaymentLinkSmsService(provider)
    with pytest.raises(ValueError):
        service.notify(request(customer_phone="123"))
    assert provider.requests == []


@pytest.mark.parametrize("status", ["cancelled", "failed", "processing", "completed", "refunded"])
def test_paid_or_terminal_states_never_send(status):
    provider = MemorySmsProvider()
    result = PaymentLinkSmsService(provider).notify(request(order_status=status))
    assert result.status == "not_sent"
    assert provider.requests == []


def test_waiting_for_approval_never_sends():
    provider = MemorySmsProvider()
    result = PaymentLinkSmsService(provider).notify(request(order_status="waiting"))
    assert result.status == "not_sent"
    assert "approved" in result.reason
    assert provider.requests == []


def test_approved_pending_payment_sends_once():
    provider = MemorySmsProvider()
    service = PaymentLinkSmsService(provider)
    first = service.notify(request())
    second = service.notify(request())
    assert first.status == "sent"
    assert second.status == "duplicate_suppressed"
    assert len(provider.requests) == 1


def test_provider_failure_is_fail_safe_and_does_not_retry():
    provider = MemorySmsProvider(fail=True)
    service = PaymentLinkSmsService(provider)
    with pytest.raises(SmsNotificationError, match="no automatic retry"):
        service.notify(request())
    assert provider.requests == []


def test_default_provider_never_sends_externally():
    result = PaymentLinkSmsService(DisabledSmsProvider()).notify(request())
    assert result.status == "not_sent"
    assert result.provider == "disabled"


def test_audit_projection_masks_phone_and_payment_token():
    audit = request().safe_audit_dict()
    assert audit["customer_phone"] == "+81******75"
    assert audit["payment_url"] == "https://shop.example/checkout/order-pay/51/"
    assert "wc_order_secret" not in str(audit)
    assert "idempotency_key" in audit


def test_redaction_drops_query_and_fragment():
    assert (
        redact_payment_url("https://shop.example/pay/1/?key=secret#frag")
        == "https://shop.example/pay/1/"
    )


def test_non_https_payment_url_is_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        request(payment_url="http://shop.example/pay/51")
