import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from operations_hub.approval_session_policy import (
    ApprovalSessionPolicyError,
    ValidatedCEOPrincipal,
    assess_approval_session,
)


NOW = datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)


def principal(**changes):
    base = {
        "issuer": "https://accounts.google.com",
        "subject": "ceo-stable-subject",
        "authenticated_at": NOW - timedelta(minutes=1),
        "session_started_at": NOW - timedelta(minutes=5),
        "last_activity_at": NOW - timedelta(minutes=1),
    }
    base.update(changes)
    return ValidatedCEOPrincipal(**base)


class ApprovalSessionPolicyTests(unittest.TestCase):
    def test_r2_and_r3_enforce_approved_freshness_windows_without_authority(self):
        r2 = assess_approval_session(principal(authenticated_at=NOW - timedelta(minutes=14)), "https://accounts.google.com", "ceo-stable-subject", "R2", NOW)
        r3 = assess_approval_session(principal(authenticated_at=NOW - timedelta(minutes=6)), "https://accounts.google.com", "ceo-stable-subject", "R3", NOW)
        self.assertEqual(900, r2.required_auth_age_seconds)
        self.assertTrue(r2.reauthentication_current)
        self.assertEqual(300, r3.required_auth_age_seconds)
        self.assertFalse(r3.reauthentication_current)
        self.assertFalse(r2.approval_authorized)
        self.assertFalse(r3.approval_authorized)

    def test_exact_issuer_and_subject_are_required(self):
        result = assess_approval_session(principal(subject="other-subject"), "https://accounts.google.com", "ceo-stable-subject", "R1", NOW)
        self.assertFalse(result.principal_matches)
        self.assertFalse(result.approval_authorized)

    def test_idle_and_absolute_session_limits_are_checked(self):
        idle = assess_approval_session(principal(last_activity_at=NOW - timedelta(minutes=31)), "https://accounts.google.com", "ceo-stable-subject", "R1", NOW)
        old = assess_approval_session(principal(session_started_at=NOW - timedelta(hours=8, seconds=1)), "https://accounts.google.com", "ceo-stable-subject", "R1", NOW)
        self.assertFalse(idle.session_current)
        self.assertFalse(old.session_current)

    def test_future_authentication_time_fails_closed(self):
        result = assess_approval_session(principal(authenticated_at=NOW + timedelta(seconds=1)), "https://accounts.google.com", "ceo-stable-subject", "R3", NOW)
        self.assertFalse(result.reauthentication_current)

    def test_only_google_issuer_configuration_is_accepted(self):
        with self.assertRaisesRegex(ApprovalSessionPolicyError, "expected_issuer_invalid"):
            assess_approval_session(principal(), "https://example.invalid", "ceo-stable-subject", "R1", NOW)

    def test_result_remains_design_only(self):
        result = assess_approval_session(principal(), "https://accounts.google.com", "ceo-stable-subject", "R3", NOW)
        self.assertEqual("design_only_inactive", result.activation_state)
        self.assertFalse(result.approval_authorized)
        self.assertEqual("none", result.authority_effect)


if __name__ == "__main__":
    unittest.main()
