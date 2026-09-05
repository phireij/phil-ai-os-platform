import unittest
from urllib import parse

from phil_ai_os_woocommerce.payment_link_sms import SmsNotificationError
from phil_ai_os_woocommerce.twilio_sms import (
    TwilioRequestValidator,
    TwilioStatusHttpBoundary,
)


URL = "https://control.example/v1/webhooks/twilio/sms-status"
TOKEN = "account-auth-token"


class RecordingEvidenceSink:
    def __init__(self):
        self.records = []

    def record(self, projection):
        self.records.append(dict(projection))


def signed_request(params, *, signature_url=URL, extra_headers=None):
    signature = TwilioRequestValidator(TOKEN).expected_signature(signature_url, params)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "X-Twilio-Signature": signature,
        # These are deliberately untrusted for signature URL reconstruction.
        "Host": "attacker.example",
        "X-Forwarded-Host": "attacker.example",
        "X-Forwarded-Proto": "http",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers, parse.urlencode(params).encode("utf-8")


class TwilioStatusHttpBoundaryTests(unittest.TestCase):
    def boundary(self, sink=None):
        return TwilioStatusHttpBoundary(
            auth_token=TOKEN,
            canonical_callback_url=URL,
            evidence_sink=sink,
        )

    def test_valid_signed_callback_returns_204_and_records_only_redacted_evidence(self):
        sink = RecordingEvidenceSink()
        params = {
            "MessageSid": "SM1234567890",
            "MessageStatus": "delivered",
            "ErrorCode": "",
            "To": "+819012345678",
            "From": "RUBYSCAKE",
        }
        headers, body = signed_request(params)
        response = self.boundary(sink).handle_post(
            request_path="/v1/webhooks/twilio/sms-status",
            headers=headers,
            body=body,
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.body, {})
        self.assertEqual(len(sink.records), 1)
        evidence = sink.records[0]
        self.assertEqual(evidence["provider"], "twilio")
        self.assertEqual(evidence["message_status"], "delivered")
        self.assertEqual(evidence["authority_effect"], "none")
        self.assertFalse(evidence["retry_requested"])
        rendered = repr(evidence)
        self.assertNotIn("+819012345678", rendered)
        self.assertNotIn("RUBYSCAKE", rendered)
        self.assertNotIn("SM1234567890", rendered)

    def test_missing_signature_fails_closed_without_evidence(self):
        sink = RecordingEvidenceSink()
        params = {"MessageSid": "SM123", "MessageStatus": "delivered"}
        _, body = signed_request(params)
        with self.assertRaisesRegex(SmsNotificationError, "signature is missing"):
            self.boundary(sink).handle_post(
                request_path="/v1/webhooks/twilio/sms-status",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                body=body,
            )
        self.assertEqual(sink.records, [])

    def test_invalid_signature_fails_closed_without_evidence(self):
        sink = RecordingEvidenceSink()
        params = {"MessageSid": "SM123", "MessageStatus": "failed"}
        headers, body = signed_request(params)
        headers["X-Twilio-Signature"] = "invalid"
        with self.assertRaisesRegex(SmsNotificationError, "signature validation failed"):
            self.boundary(sink).handle_post(
                request_path="/v1/webhooks/twilio/sms-status", headers=headers, body=body
            )
        self.assertEqual(sink.records, [])

    def test_missing_secret_or_canonical_url_fails_closed_at_construction(self):
        with self.assertRaisesRegex(ValueError, "AUTH_TOKEN"):
            TwilioStatusHttpBoundary(auth_token="", canonical_callback_url=URL)
        with self.assertRaisesRegex(ValueError, "STATUS_CALLBACK_URL"):
            TwilioStatusHttpBoundary(auth_token=TOKEN, canonical_callback_url="")
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            TwilioStatusHttpBoundary(
                auth_token=TOKEN,
                canonical_callback_url="http://control.example/v1/webhooks/twilio/sms-status",
            )

    def test_signature_uses_configured_canonical_url_not_proxy_headers(self):
        params = {"MessageSid": "SM123", "MessageStatus": "delivered"}
        headers, body = signed_request(params)
        response = self.boundary().handle_post(
            request_path="/v1/webhooks/twilio/sms-status", headers=headers, body=body
        )
        self.assertEqual(response.status_code, 204)

        wrong_headers, wrong_body = signed_request(
            params, signature_url="https://attacker.example/v1/webhooks/twilio/sms-status"
        )
        with self.assertRaisesRegex(SmsNotificationError, "signature validation failed"):
            self.boundary().handle_post(
                request_path="/v1/webhooks/twilio/sms-status",
                headers=wrong_headers,
                body=wrong_body,
            )

    def test_missing_required_sid_or_status_fails_closed(self):
        for params in (
            {"MessageStatus": "delivered"},
            {"MessageSid": "SM123"},
        ):
            with self.subTest(params=params):
                headers, body = signed_request(params)
                with self.assertRaisesRegex(SmsNotificationError, "required fields"):
                    self.boundary().handle_post(
                        request_path="/v1/webhooks/twilio/sms-status",
                        headers=headers,
                        body=body,
                    )

    def test_invalid_path_content_type_malformed_body_and_duplicates_fail_closed(self):
        params = {"MessageSid": "SM123", "MessageStatus": "delivered"}
        headers, body = signed_request(params)
        with self.assertRaisesRegex(SmsNotificationError, "path mismatch"):
            self.boundary().handle_post(request_path="/wrong", headers=headers, body=body)
        with self.assertRaisesRegex(SmsNotificationError, "content type"):
            self.boundary().handle_post(
                request_path="/v1/webhooks/twilio/sms-status",
                headers={**headers, "Content-Type": "application/json"},
                body=body,
            )
        with self.assertRaisesRegex(SmsNotificationError, "malformed"):
            self.boundary().handle_post(
                request_path="/v1/webhooks/twilio/sms-status",
                headers=headers,
                body=b"not-a-form-field",
            )
        duplicate_body = b"MessageSid=SM123&MessageSid=SM456&MessageStatus=delivered"
        duplicate_params = {"MessageSid": "SM123", "MessageStatus": "delivered"}
        duplicate_headers, _ = signed_request(duplicate_params)
        with self.assertRaisesRegex(SmsNotificationError, "duplicate"):
            self.boundary().handle_post(
                request_path="/v1/webhooks/twilio/sms-status",
                headers=duplicate_headers,
                body=duplicate_body,
            )

    def test_oversized_body_fails_before_signature_processing(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Twilio-Signature": "invalid",
        }
        with self.assertRaisesRegex(SmsNotificationError, "safe limit"):
            self.boundary().handle_post(
                request_path="/v1/webhooks/twilio/sms-status",
                headers=headers,
                body=b"x" * (TwilioStatusHttpBoundary.max_body_bytes + 1),
            )


if __name__ == "__main__":
    unittest.main()
