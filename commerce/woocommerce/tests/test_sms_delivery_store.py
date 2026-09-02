import os
import tempfile
import unittest

from phil_ai_os_woocommerce.payment_link_sms import MemorySmsProvider, PaymentLinkSmsRequest, PaymentLinkSmsService
from phil_ai_os_woocommerce.sms_delivery_store import SqliteSmsIdempotencyStore


def request():
    return PaymentLinkSmsRequest(
        order_id=88,
        order_number="88",
        order_status="pending",
        customer_phone="050-1785-0575",
        amount_minor=1165,
        currency="JPY",
        payment_url="https://shop.example/checkout/order-pay/88/?pay_for_order=true&key=secret",
    )


class SqliteSmsIdempotencyStoreTests(unittest.TestCase):
    def test_duplicate_is_suppressed_across_service_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sms-idempotency.db")
            first_provider = MemorySmsProvider()
            first_service = PaymentLinkSmsService(
                first_provider,
                idempotency_store=SqliteSmsIdempotencyStore(path),
            )
            first = first_service.notify(request())
            self.assertEqual(first.status, "sent")
            self.assertEqual(len(first_provider.requests), 1)

            second_provider = MemorySmsProvider()
            second_service = PaymentLinkSmsService(
                second_provider,
                idempotency_store=SqliteSmsIdempotencyStore(path),
            )
            second = second_service.notify(request())
            self.assertEqual(second.status, "duplicate_suppressed")
            self.assertEqual(second_provider.requests, [])

    def test_store_contains_no_phone_or_payment_url_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sms-idempotency.db")
            store = SqliteSmsIdempotencyStore(path)
            key = request().idempotency_key
            store.mark_sent(key, provider="memory", provider_message_id="memory-1")
            self.assertTrue(store.contains(key))

            import sqlite3

            with sqlite3.connect(path) as connection:
                columns = [row[1] for row in connection.execute("PRAGMA table_info(sms_payment_link_idempotency)")]
            self.assertNotIn("phone", " ".join(columns).lower())
            self.assertNotIn("url", " ".join(columns).lower())


if __name__ == "__main__":
    unittest.main()
