import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import monitor


class SafetySnapshotTests(unittest.TestCase):
    def test_safe_snapshot(self):
        data = {
            "audit_consistency": "CONSISTENT",
            "audit_issues": 0,
            "audit_integrity": "PASS",
            "unknown_approval_links": 0,
            "multiple_successes_per_approval": 0,
            "execution_kill_switch": True,
            "routed_execution_enabled": False,
            "live_test_enabled": False,
        }
        findings = monitor.evaluate_safety_snapshot(data, strict=True)
        self.assertEqual(8, len(findings))
        self.assertTrue(all(f.ok for f in findings))

    def test_dangerous_runtime_is_flagged(self):
        findings = monitor.evaluate_safety_snapshot({"execution_kill_switch": False}, strict=False)
        self.assertEqual(1, len(findings))
        self.assertFalse(findings[0].ok)

    def test_strict_missing_fields_fail(self):
        findings = monitor.evaluate_safety_snapshot({}, strict=True)
        self.assertTrue(findings)
        self.assertTrue(all(not f.ok for f in findings))


class DedupTests(unittest.TestCase):
    def test_alert_dedup_and_recovery(self):
        notifier = Mock()
        state = {}
        bad = monitor.Finding("x", False, "bad")
        good = monitor.Finding("x", True, "good")

        state = monitor.process_findings([bad], state, notifier, cooldown=100, now=1000)
        self.assertEqual(1, notifier.send.call_count)
        state = monitor.process_findings([bad], state, notifier, cooldown=100, now=1050)
        self.assertEqual(1, notifier.send.call_count)
        state = monitor.process_findings([bad], state, notifier, cooldown=100, now=1101)
        self.assertEqual(2, notifier.send.call_count)
        state = monitor.process_findings([good], state, notifier, cooldown=100, now=1110)
        self.assertEqual(3, notifier.send.call_count)

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            monitor.save_state(path, {"a": 1})
            self.assertEqual({"a": 1}, monitor.load_state(path))


if __name__ == "__main__":
    unittest.main()
