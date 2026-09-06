import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from phil_ai_os_woocommerce.payment_link_sms import PaymentLinkSmsRequest
from phil_ai_os_woocommerce.sms_templates import TransactionalSmsTemplate
from phil_ai_os_woocommerce.twilio_sms import TWILIO_STATUS_CALLBACK_PATH


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "twilio-production-message-readiness-candidate.json"
)


class TwilioProductionMessageReadinessCandidateTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_candidate_is_explicitly_non_authorizing(self):
        self.assertEqual(self.record["status"], "readiness_candidate_only")
        self.assertFalse(self.record["provider_enabled"])
        self.assertFalse(self.record["automatic_retry_enabled"])
        self.assertFalse(self.record["unrestricted_send_authority"])
        self.assertFalse(self.record["controlled_handset_test_executed"])

    def test_identity_and_authentication_boundaries_are_canonical(self):
        self.assertEqual(self.record["messaging_service_name"], "Ruby Transactional SMS")
        self.assertEqual(self.record["sender_identity"], "RUBYSCAKE")
        self.assertEqual(self.record["outbound_authentication"], "restricted_api_key")
        self.assertEqual(self.record["webhook_authentication"], "account_auth_token")

    def test_callback_url_is_exact_https_contract(self):
        parsed = urlsplit(self.record["status_callback_url"])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.path, TWILIO_STATUS_CALLBACK_PATH)
        self.assertFalse(parsed.query)
        self.assertFalse(parsed.fragment)

    def test_bilingual_template_renders_help_and_opt_out_without_reply_instruction(self):
        template = TransactionalSmsTemplate(
            locale=self.record["template_locale"],
            support_contact=self.record["support_contact"],
        )
        template.validate()
        sms_request = PaymentLinkSmsRequest(
            order_id=1,
            order_number="RCD-READINESS",
            order_status="pending",
            customer_phone="050-0000-0000",
            amount_minor=1000,
            currency="JPY",
            payment_url="https://shop.example/order-pay/readiness",
        )
        rendered = template.render_payment_link(sms_request)
        self.assertIn("お問い合わせ・配信停止", rendered)
        self.assertIn("Help/opt-out", rendered)
        self.assertIn(self.record["support_contact"], rendered)
        self.assertNotIn("Reply STOP", rendered)
        self.assertNotIn("Reply HELP", rendered)

    def test_fixture_contains_no_secret_material_or_test_destination(self):
        serialized = json.dumps(self.record, sort_keys=True).upper()
        for forbidden in (
            "RUBY_TWILIO_API_KEY_SECRET",
            "RUBY_TWILIO_AUTH_TOKEN",
            "RUBY_TWILIO_TEST_TO",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn("api_key_secret", self.record)
        self.assertNotIn("auth_token", self.record)
        self.assertNotIn("test_destination", self.record)


if __name__ == "__main__":
    unittest.main()
