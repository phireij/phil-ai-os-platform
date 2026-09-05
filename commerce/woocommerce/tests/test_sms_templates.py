import unittest

from phil_ai_os_woocommerce.payment_link_sms import PaymentLinkSmsRequest
from phil_ai_os_woocommerce.sms_templates import TransactionalSmsTemplate


def request():
    return PaymentLinkSmsRequest(
        order_id=51,
        order_number="RCD-51",
        order_status="pending",
        customer_phone="050-1785-0575",
        amount_minor=1165,
        currency="JPY",
        payment_url="https://shop.example/checkout/order-pay/51/?key=example",
    )


class TransactionalSmsTemplateTests(unittest.TestCase):
    def test_support_contact_is_required(self):
        template = TransactionalSmsTemplate()
        with self.assertRaisesRegex(ValueError, "support_contact"):
            template.render_payment_link(request())

    def test_bilingual_payment_copy_is_one_way_safe(self):
        template = TransactionalSmsTemplate(
            locale="bilingual",
            support_contact="https://shop.example/support",
        )
        body = template.render_payment_link(request())
        self.assertIn("ご注文RCD-51", body)
        self.assertIn("Order RCD-51 confirmed", body)
        self.assertIn(request().payment_url, body)
        self.assertIn("お問い合わせ・配信停止: https://shop.example/support", body)
        self.assertIn("Help/opt-out: https://shop.example/support", body)
        self.assertIn("返信できません", body)
        self.assertIn("cannot receive replies", body)
        self.assertNotIn("Reply STOP", body)
        self.assertNotIn("Reply HELP", body)

    def test_japanese_and_english_modes_are_explicit(self):
        ja = TransactionalSmsTemplate(
            locale="ja", support_contact="https://shop.example/support"
        ).render_payment_link(request())
        en = TransactionalSmsTemplate(
            locale="en", support_contact="https://shop.example/support"
        ).render_payment_link(request())
        self.assertIn("ご注文RCD-51", ja)
        self.assertNotIn("Order RCD-51 confirmed", ja)
        self.assertIn("Order RCD-51 confirmed", en)
        self.assertNotIn("ご注文RCD-51", en)

    def test_help_and_opt_out_notices_use_alternate_contact(self):
        template = TransactionalSmsTemplate(
            locale="bilingual",
            support_contact="https://shop.example/support",
        )
        help_notice = template.render_help_notice()
        opt_out_notice = template.render_opt_out_notice()
        for rendered in (help_notice, opt_out_notice):
            self.assertIn("https://shop.example/support", rendered)
            self.assertIn("返信できません", rendered)
            self.assertIn("cannot receive replies", rendered)
        self.assertIn("SMS配信停止", opt_out_notice)
        self.assertIn("To opt out of SMS", opt_out_notice)

    def test_unsupported_locale_and_multiline_contact_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            TransactionalSmsTemplate(
                locale="fr", support_contact="https://shop.example/support"
            ).validate()
        with self.assertRaisesRegex(ValueError, "single-line"):
            TransactionalSmsTemplate(
                locale="en", support_contact="support@example.com\nunsafe"
            ).validate()


if __name__ == "__main__":
    unittest.main()
