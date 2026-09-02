import unittest

from phil_ai_os_woocommerce.payment_link_sms import PaymentLinkSmsRequest, SmsNotificationError
from phil_ai_os_woocommerce.twilio_sms import (
    TwilioDeliveryStatus,
    TwilioRequestValidator,
    TwilioSmsConfig,
    TwilioSmsProvider,
)


def request():
    return PaymentLinkSmsRequest(
        order_id=51,
        order_number="51",
        order_status="pending",
        customer_phone="050-1785-0575",
        amount_minor=1165,
        currency="JPY",
        payment_url="https://shop.example/checkout/order-pay/51/?pay_for_order=true&key=wc_order_secret",
    )


class RecordingTransport:
    def __init__(self, *, status=201, body=None):
        self.status = status
        self.body = body or {"sid": "SM123", "status": "queued"}
        self.calls = []

    def post_form(self, url, fields, *, username, password, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "fields": dict(fields),
                "username": username,
                "password": password,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.status, self.body


class TwilioSmsTests(unittest.TestCase):
    def test_disabled_by_default_makes_no_external_call(self):
        transport = RecordingTransport()
        provider = TwilioSmsProvider(TwilioSmsConfig(), transport)
        result = provider.send_payment_link_sms(request())
        self.assertEqual(result.status, "not_sent")
        self.assertEqual(transport.calls, [])
        self.assertIn("CEO activation", result.reason or "")

    def test_enabled_send_requires_configuration(self):
        provider = TwilioSmsProvider(TwilioSmsConfig(enabled=True), RecordingTransport())
        with self.assertRaisesRegex(ValueError, "account_sid"):
            provider.send_payment_link_sms(request())

    def test_enabled_adapter_builds_expected_twilio_request(self):
        transport = RecordingTransport()
        provider = TwilioSmsProvider(
            TwilioSmsConfig(
                account_sid="AC123",
                auth_token="secret",
                from_identity="RubyCakes",
                status_callback_url="https://control.example/sms/twilio/status",
                enabled=True,
            ),
            transport,
        )
        result = provider.send_payment_link_sms(request())
        self.assertEqual(result.status, "sent")
        self.assertEqual(result.provider_message_id, "SM123")
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["fields"]["To"], "+815017850575")
        self.assertEqual(call["fields"]["From"], "RubyCakes")
        self.assertEqual(call["fields"]["StatusCallback"], "https://control.example/sms/twilio/status")
        self.assertIn("https://shop.example/checkout/order-pay/51/", call["fields"]["Body"])
        self.assertEqual(call["username"], "AC123")
        self.assertEqual(call["password"], "secret")

    def test_provider_http_failure_fails_closed(self):
        transport = RecordingTransport(status=400, body={"message": "bad request"})
        provider = TwilioSmsProvider(
            TwilioSmsConfig(
                account_sid="AC123",
                auth_token="secret",
                from_identity="RubyCakes",
                enabled=True,
            ),
            transport,
        )
        with self.assertRaisesRegex(SmsNotificationError, "HTTP 400"):
            provider.send_payment_link_sms(request())
        self.assertEqual(len(transport.calls), 1)

    def test_signature_validator_matches_documented_algorithm(self):
        validator = TwilioRequestValidator("12345")
        url = "https://example.com/myapp.php?foo=1&bar=2"
        params = {
            "CallSid": "CA1234567890ABCDE",
            "Caller": "+14158675310",
            "Digits": "1234",
            "From": "+14158675310",
            "To": "+18005551212",
        }
        signature = "L/OH5YylLD5NRKLltdqwSvS0BnU="
        self.assertTrue(validator.validate(url, params, signature))
        self.assertFalse(validator.validate(url, params, "invalid"))

    def test_delivery_status_requires_sid_and_status(self):
        status = TwilioDeliveryStatus.from_form(
            {"MessageSid": "SM123", "MessageStatus": "delivered", "ErrorCode": ""}
        )
        self.assertEqual(status.message_sid, "SM123")
        self.assertEqual(status.message_status, "delivered")
        self.assertIsNone(status.error_code)
        with self.assertRaises(ValueError):
            TwilioDeliveryStatus.from_form({"MessageSid": "SM123"})


if __name__ == "__main__":
    unittest.main()
