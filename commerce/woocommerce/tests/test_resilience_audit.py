import unittest

from phil_ai_os_woocommerce import (
    CommerceSyncAuditEvent,
    FailureInjectingTransport,
    HTTPStatusFailure,
    MemoryAuditSink,
    MockWooCommerceTransport,
    ReconciliationResult,
    execute_with_retry,
)


class ResilienceAuditTests(unittest.TestCase):
    def test_transient_failure_retries_without_sleeping(self):
        inner = MockWooCommerceTransport()
        transport = FailureInjectingTransport(inner)
        transport.queue_failure("GET", "/products", 503)
        result = execute_with_retry(
            lambda: transport.request("GET", "/products", params={"sku": "SKU-1"})
        )
        self.assertEqual(result.value, [])
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.retry_delays, (0.5,))

    def test_nonretryable_failure_fails_immediately(self):
        inner = MockWooCommerceTransport()
        transport = FailureInjectingTransport(inner)
        transport.queue_failure("GET", "/products", 401)
        with self.assertRaises(HTTPStatusFailure):
            execute_with_retry(lambda: transport.request("GET", "/products"))

    def test_retry_attempt_limit_is_enforced(self):
        inner = MockWooCommerceTransport()
        transport = FailureInjectingTransport(inner)
        for _ in range(4):
            transport.queue_failure("GET", "/products", 503)
        with self.assertRaises(HTTPStatusFailure):
            execute_with_retry(lambda: transport.request("GET", "/products"), max_attempts=3)

    def test_audit_sink_accepts_authority_none_event(self):
        result = ReconciliationResult("noop", "SKU-1", "phil:test", 1, "before", "after")
        event = CommerceSyncAuditEvent.from_result(
            result,
            correlation_id="corr-audit-1",
            entity_type="product",
        )
        sink = MemoryAuditSink()
        sink.emit(event)
        self.assertEqual(sink.events, (event,))

    def test_audit_sink_rejects_authority_bearing_event(self):
        event = CommerceSyncAuditEvent(
            correlation_id="corr-audit-2",
            entity_type="product",
            entity_key="SKU-1",
            action="update",
            idempotency_key="phil:test",
            remote_id=1,
            before_fingerprint="before",
            after_fingerprint="after",
            observed_at="2026-08-28T00:00:00+00:00",
            authority_effect="mutation",
        )
        with self.assertRaises(ValueError):
            MemoryAuditSink().emit(event)


if __name__ == "__main__":
    unittest.main()
