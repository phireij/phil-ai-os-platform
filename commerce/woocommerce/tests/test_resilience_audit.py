import unittest

from phil_ai_os_woocommerce import (
    CommerceSyncAuditEvent,
    FailureInjectingTransport,
    HTTPStatusFailure,
    MemoryAuditSink,
    MockWooCommerceTransport,
    ReconciliationResult,
    execute_with_retry,
    reconcile_with_audit,
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

    def test_rate_limit_and_server_error_use_exponential_plan(self):
        inner = MockWooCommerceTransport()
        transport = FailureInjectingTransport(inner)
        transport.queue_failure("GET", "/products", 429)
        transport.queue_failure("GET", "/products", 502)
        result = execute_with_retry(lambda: transport.request("GET", "/products"))
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.retry_delays, (0.5, 1.0))

    def test_nonretryable_auth_failure_fails_immediately(self):
        inner = MockWooCommerceTransport()
        transport = FailureInjectingTransport(inner)
        transport.queue_failure("GET", "/products", 401)
        with self.assertRaises(HTTPStatusFailure) as caught:
            execute_with_retry(lambda: transport.request("GET", "/products"))
        self.assertEqual(caught.exception.status_code, 401)

    def test_nonretryable_validation_failure_fails_immediately(self):
        inner = MockWooCommerceTransport()
        transport = FailureInjectingTransport(inner)
        transport.queue_failure("POST", "/products", 400)
        with self.assertRaises(HTTPStatusFailure) as caught:
            execute_with_retry(lambda: transport.request("POST", "/products", json_body={}))
        self.assertEqual(caught.exception.status_code, 400)

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

    def test_reconcile_with_audit_emits_linked_event(self):
        sink = MemoryAuditSink()
        result = ReconciliationResult("noop", "SKU-1", "phil:test", 1, "before", "after")
        audited = reconcile_with_audit(
            lambda: result,
            correlation_id="corr-sync-1",
            entity_type="product",
            audit_sink=sink,
        )
        self.assertEqual(audited.result, result)
        self.assertEqual(audited.audit_event.correlation_id, "corr-sync-1")
        self.assertEqual(audited.audit_event.authority_effect, "none")
        self.assertEqual(sink.events, (audited.audit_event,))

    def test_reconcile_with_audit_does_not_emit_on_operation_failure(self):
        sink = MemoryAuditSink()

        def fail():
            raise ValueError("synthetic reconciliation failure")

        with self.assertRaises(ValueError):
            reconcile_with_audit(
                fail,
                correlation_id="corr-sync-fail",
                entity_type="inventory",
                audit_sink=sink,
            )
        self.assertEqual(sink.events, ())

    def test_reconcile_with_audit_rejects_unknown_entity_type(self):
        with self.assertRaises(ValueError):
            reconcile_with_audit(
                lambda: ReconciliationResult("noop", "X", "phil:test", None, None, "after"),
                correlation_id="corr-unknown",
                entity_type="order",
                audit_sink=MemoryAuditSink(),
            )


if __name__ == "__main__":
    unittest.main()
