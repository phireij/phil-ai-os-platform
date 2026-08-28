import unittest

from phil_ai_os_woocommerce.audit import CommerceSyncAuditEvent
from phil_ai_os_woocommerce.reconciliation import ReconciliationResult
from phil_ai_os_woocommerce.retry import retry_decision


class AuditRetryTests(unittest.TestCase):
    def test_audit_event_has_no_authority_effect(self):
        result = ReconciliationResult("noop", "SKU-1", "phil:test", 1, "before", "after")
        event = CommerceSyncAuditEvent.from_result(result, correlation_id="corr-1", entity_type="product")
        self.assertEqual(event.authority_effect, "none")
        self.assertEqual(event.correlation_id, "corr-1")

    def test_retry_policy_only_retries_transient_status(self):
        self.assertTrue(retry_decision(503, 1).retry)
        self.assertEqual(retry_decision(401, 1).reason, "non_retryable_status")
        self.assertFalse(retry_decision(429, 4).retry)


if __name__ == "__main__":
    unittest.main()
