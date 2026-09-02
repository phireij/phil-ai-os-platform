import unittest

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


class PaymentLinkSmsTests(unittest.TestCase):
    def test_japanese_phone_normalization_and_deterministic_idempotency(self):
        local = request(customer_phone="050-1785-0575")
        international = request(customer_phone="+81 50 1785 0575")
        self.assertEqual(local.normalized_phone, "+815017850575")
        self.assertEqual(international.normalized_phone, "+815017850575")
        self.assertEqual(local.idempotency_key, international.idempotency_key)

    def test_invalid_phone_is_rejected_before_provider_use(self):
        provider = MemorySmsProvider()
        service = PaymentLinkSmsService(provider)
        with self.assertRaises(ValueError):
            service.notify(request(customer_phone="123"))
        self.assertEqual(provider.requests, [])

    def test_paid_or_terminal_states_never_send(self):
        for status in ("cancelled", "failed", "processing", "completed", "refunded"):
            with self.subTest(status=status):
                provider = MemorySmsProvider()
                result = PaymentLinkSmsService(provider).notify(request(order_status=status))
                self.assertEqual(result.status, "not_sent")
                self.assertEqual(provider.requests, [])

    def test_waiting_for_approval_never_sends(self):
        provider = MemorySmsProvider()
        result = PaymentLinkSmsService(provider).notify(request(order_status="waiting"))
        self.assertEqual(result.status, "not_sent")
        self.assertIn("approved", result.reason or "")
        self.assertEqual(provider.requests, [])

    def test_approved_pending_payment_sends_once(self):
        provider = MemorySmsProvider()
        service = PaymentLinkSmsService(provider)
        first = service.notify(request())
        second = service.notify(request())
        self.assertEqual(first.status, "sent")
        self.assertEqual(second.status, "duplicate_suppressed")
        self.assertEqual(len(provider.requests), 1)

    def test_provider_failure_is_fail_safe_and_does_not_retry(self):
        provider = MemorySmsProvider(fail=True)
        service = PaymentLinkSmsService(provider)
        with self.assertRaisesRegex(SmsNotificationError, "no automatic retry"):
            service.notify(request())
        self.assertEqual(provider.requests, [])

    def test_default_provider_never_sends_externally(self):
        result = PaymentLinkSmsService(DisabledSmsProvider()).notify(request())
        self.assertEqual(result.status, "not_sent")
        self.assertEqual(result.provider, "disabled")

    def test_audit_projection_masks_phone_and_payment_token(self):
        audit = request().safe_audit_dict()
        self.assertEqual(audit["customer_phone"], "+81******75")
        self.assertEqual(audit["payment_url"], "https://shop.example/checkout/order-pay/51/")
        self.assertNotIn("wc_order_secret", str(audit))
        self.assertIn("idempotency_key", audit)

    def test_redaction_drops_query_and_fragment(self):
        self.assertEqual(
            redact_payment_url("https://shop.example/pay/1/?key=secret#frag"),
            "https://shop.example/pay/1/",
        )

    def test_non_https_payment_url_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            request(payment_url="http://shop.example/pay/51")


if __name__ == "__main__":
    unittest.main()
