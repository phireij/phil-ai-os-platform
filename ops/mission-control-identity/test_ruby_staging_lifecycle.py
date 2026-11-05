"""Offline tests only. Identities, durations and tokens are disposable test data."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import hashlib
import importlib
import secrets
import socket
import threading
import unittest
from unittest.mock import patch

with patch.object(socket, "socket", side_effect=AssertionError("network_forbidden")):
    from ruby_staging_lifecycle import (
        FLOW_COOKIE, SESSION_COOKIE, LifecycleError, LoginFlowStore, SessionStore,
        pkce_challenge, read_cookie, serialize_cookie,
    )


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket, "socket", side_effect=AssertionError("network_forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.clock = Clock()

    def flows(self, **kwargs):
        return LoginFlowStore(enabled=True, ttl_seconds=30, capacity=2, clock=self.clock, **kwargs)

    def sessions(self, **kwargs):
        config = dict(enabled=True, idle_seconds=10, absolute_seconds=30,
                      capacity=2, clock=self.clock)
        config.update(kwargs)
        return SessionStore(**config)


class ActivationAndPolicyTests(OfflineCase):
    def test_default_disabled(self):
        with self.assertRaisesRegex(LifecycleError, "lifecycle_inactive"):
            LoginFlowStore(ttl_seconds=30, capacity=2)
        with self.assertRaisesRegex(LifecycleError, "lifecycle_inactive"):
            SessionStore(idle_seconds=10, absolute_seconds=30, capacity=2)

    def test_enablement_requires_actual_true(self):
        for enabled in (False, None, 1, "true", []):
            with self.subTest(enabled=enabled), self.assertRaises(LifecycleError):
                LoginFlowStore(enabled=enabled, ttl_seconds=30, capacity=2)

    def test_policy_values_are_bounded_integer_values(self):
        for invalid in (0, -1, True, 1.0, float("inf"), float("nan"), "10", None, 100000):
            for field in ("idle_seconds", "absolute_seconds", "capacity"):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(LifecycleError):
                    self.sessions(**{field: invalid})
            for field in ("ttl_seconds", "capacity"):
                config = dict(ttl_seconds=30, capacity=2, enabled=True)
                config[field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaises(LifecycleError):
                    LoginFlowStore(**config)

    def test_idle_cannot_exceed_absolute(self):
        with self.assertRaisesRegex(LifecycleError, "timeout_order_invalid"):
            self.sessions(idle_seconds=31)

    def test_module_can_be_reimported_without_network(self):
        import ruby_staging_lifecycle
        # Execute a fresh module without altering the class identities under test.
        spec = importlib.util.spec_from_file_location("ruby_staging_lifecycle", ruby_staging_lifecycle.__file__)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))


class FlowTests(OfflineCase):
    def test_start_keeps_verifier_server_side_and_uses_s256(self):
        store = self.flows()
        start = store.start()
        self.assertFalse(hasattr(start, "code_verifier"))
        self.assertEqual(start.code_challenge_method, "S256")
        exchange = store.take(start.state, start.browser_token)
        self.assertIsNotNone(exchange)
        self.assertEqual(exchange.nonce, start.nonce)
        self.assertEqual(pkce_challenge(exchange.code_verifier), start.code_challenge)
        self.assertEqual(len(start.state), 64)
        self.assertEqual(len(exchange.code_verifier), 64)
        self.assertEqual(len(start.code_challenge), 43)

    def test_s256_known_vector(self):
        import base64
        verifier = "a" * 64
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.assertEqual(pkce_challenge(verifier), expected)

    def test_invalid_verifier_rejected(self):
        for value in (None, "", "a" * 63, "a" * 65, "é" * 64, "a" * 63 + "=", b"a" * 64):
            with self.subTest(value=value), self.assertRaises(LifecycleError):
                pkce_challenge(value)

    def test_flow_is_one_use(self):
        store = self.flows()
        start = store.start()
        self.assertIsNotNone(store.take(start.state, start.browser_token))
        self.assertIsNone(store.take(start.state, start.browser_token))

    def test_wrong_browser_consumes_the_flow(self):
        for bad in (None, "", "wrong", secrets.token_urlsafe(48)):
            with self.subTest(bad=bad):
                store = self.flows()
                start = store.start()
                self.assertIsNone(store.take(start.state, bad))
                self.assertIsNone(store.take(start.state, start.browser_token))

    def test_invalid_state_does_not_consume_another_flow(self):
        store = self.flows()
        start = store.start()
        for state in (None, "", [], "é" * 64, secrets.token_urlsafe(48)):
            self.assertIsNone(store.take(state, start.browser_token))
        self.assertIsNotNone(store.take(start.state, start.browser_token))

    def test_cross_instance_flow_rejected(self):
        first, second = self.flows(), self.flows()
        start = first.start()
        self.assertIsNone(second.take(start.state, start.browser_token))
        self.assertIsNotNone(first.take(start.state, start.browser_token))

    def test_flow_expires_at_exact_boundary(self):
        store = self.flows()
        start = store.start()
        self.clock.now = 130
        self.assertIsNone(store.take(start.state, start.browser_token))

    def test_capacity_is_reclaimed_on_expiry(self):
        store = self.flows()
        store.start()
        store.start()
        with self.assertRaisesRegex(LifecycleError, "flow_capacity_reached"):
            store.start()
        self.clock.now = 130
        self.assertIsNotNone(store.start())

    def test_collision_does_not_overwrite_pending_flow(self):
        store = self.flows()
        start = store.start()
        with patch("ruby_staging_lifecycle.secrets.token_urlsafe", return_value=start.state):
            with self.assertRaisesRegex(LifecycleError, "entropy_collision"):
                store.start()
        self.assertIsNotNone(store.take(start.state, start.browser_token))

    def test_malformed_entropy_creates_no_flow(self):
        store = self.flows()
        with patch("ruby_staging_lifecycle.secrets.token_urlsafe", return_value="bad"):
            with self.assertRaisesRegex(LifecycleError, "entropy_invalid"):
                store.start()
        self.assertEqual(len(store._flows), 0)

    def test_only_one_concurrent_callback_wins(self):
        store = self.flows()
        start = store.start()
        barrier = threading.Barrier(8)
        def take(_):
            barrier.wait()
            return store.take(start.state, start.browser_token)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(take, range(8)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_close_clears_and_permanently_disables(self):
        store = self.flows()
        start = store.start()
        store.close()
        store.close()
        self.assertEqual(store._flows, {})
        for action in (store.start, lambda: store.take(start.state, start.browser_token)):
            with self.assertRaisesRegex(LifecycleError, "lifecycle_closed"):
                action()

    def test_secrets_not_exposed_in_repr(self):
        store = self.flows()
        start = store.start()
        exchange = store.take(start.state, start.browser_token)
        for value in (start.state, start.browser_token, start.nonce, exchange.code_verifier):
            self.assertNotIn(value, repr(start) + repr(exchange))


class SessionTests(OfflineCase):
    def test_initial_issue_is_fresh_and_csrf_bound(self):
        store = self.sessions()
        first, second = store.issue(), store.issue()
        self.assertNotEqual(first.token, second.token)
        self.assertNotEqual(first.csrf_token, second.csrf_token)
        self.assertIsNotNone(store.lookup(first.token, csrf_token=first.csrf_token, require_csrf=True))
        self.assertIsNone(store.lookup(first.token, csrf_token=second.csrf_token, require_csrf=True))

    def test_storage_contains_token_hashes_not_raw_tokens(self):
        store = self.sessions()
        receipt = store.issue()
        self.assertEqual(list(store._sessions), [hashlib.sha256(receipt.token.encode()).digest()])
        stored = next(iter(store._sessions.values()))
        self.assertEqual(stored.csrf_hash, hashlib.sha256(receipt.csrf_token.encode()).digest())

    def test_capacity_enforced(self):
        store = self.sessions(capacity=1)
        store.issue()
        with self.assertRaisesRegex(LifecycleError, "session_capacity_reached"):
            store.issue()

    def test_rotation_at_capacity_revokes_previous_and_rotates_csrf(self):
        store = self.sessions(capacity=1)
        old = store.issue()
        new = store.issue(previous_token=old.token)
        self.assertNotEqual(old.token, new.token)
        self.assertNotEqual(old.csrf_token, new.csrf_token)
        self.assertIsNone(store.lookup(old.token))
        self.assertIsNotNone(store.lookup(new.token))
        self.assertIsNone(store.lookup(new.token, csrf_token=old.csrf_token, require_csrf=True))

    def test_rotation_does_not_adopt_unknown_or_malformed_id(self):
        store = self.sessions()
        for token in ("", "attacker", secrets.token_urlsafe(48), []):
            with self.subTest(token=token), self.assertRaisesRegex(LifecycleError, "rotation_session_missing"):
                store.issue(previous_token=token)
        self.assertEqual(len(store._sessions), 0)

    def test_expired_session_cannot_rotate(self):
        store = self.sessions()
        old = store.issue()
        self.clock.now = 110
        with self.assertRaisesRegex(LifecycleError, "rotation_session_missing"):
            store.issue(previous_token=old.token)

    def test_failed_entropy_during_rotation_leaves_old_revoked(self):
        store = self.sessions()
        old = store.issue()
        with patch("ruby_staging_lifecycle.secrets.token_urlsafe", return_value=old.token):
            with self.assertRaisesRegex(LifecycleError, "entropy_collision"):
                store.issue(previous_token=old.token)
        self.assertIsNone(store.lookup(old.token))
        self.assertEqual(len(store._sessions), 0)

    def test_collision_does_not_replace_existing_session(self):
        store = self.sessions()
        old = store.issue()
        with patch("ruby_staging_lifecycle.secrets.token_urlsafe", return_value=old.token):
            with self.assertRaisesRegex(LifecycleError, "entropy_collision"):
                store.issue()
        self.assertIsNotNone(store.lookup(old.token, csrf_token=old.csrf_token, require_csrf=True))

    def test_only_one_concurrent_rotation_wins(self):
        store = self.sessions()
        old = store.issue()
        barrier = threading.Barrier(8)
        def rotate(_):
            barrier.wait()
            try:
                return store.issue(previous_token=old.token)
            except LifecycleError as error:
                self.assertEqual(str(error), "rotation_session_missing")
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(rotate, range(8)))
        successful = [value for value in results if value is not None]
        self.assertEqual(len(successful), 1)
        self.assertIsNone(store.lookup(old.token))
        self.assertIsNotNone(store.lookup(successful[0].token))

    def test_idle_expiry_at_exact_boundary(self):
        store = self.sessions()
        receipt = store.issue()
        self.clock.now = 110
        self.assertIsNone(store.lookup(receipt.token))

    def test_activity_refreshes_idle_not_absolute_timeout(self):
        store = self.sessions()
        receipt = store.issue()
        for now in (109, 118, 127, 129):
            self.clock.now = now
            self.assertIsNotNone(store.lookup(receipt.token))
        self.clock.now = 130
        self.assertIsNone(store.lookup(receipt.token))

    def test_invalid_csrf_does_not_refresh_idle(self):
        store = self.sessions()
        receipt = store.issue()
        self.clock.now = 109
        for bad in (None, "", "bad", secrets.token_urlsafe(48), [], "é" * 64):
            self.assertIsNone(store.lookup(receipt.token, csrf_token=bad, require_csrf=True))
        self.clock.now = 110
        self.assertIsNone(store.lookup(receipt.token))

    def test_csrf_mode_must_be_boolean(self):
        store = self.sessions()
        receipt = store.issue()
        for value in (None, 0, 1, "true", "false"):
            with self.subTest(value=value), self.assertRaisesRegex(LifecycleError, "csrf_mode_invalid"):
                store.lookup(receipt.token, require_csrf=value)

    def test_lookup_snapshot_is_immutable(self):
        store = self.sessions()
        receipt = store.issue()
        snapshot = store.lookup(receipt.token)
        with self.assertRaises(FrozenInstanceError):
            snapshot.last_seen = 500

    def test_invalid_tokens_return_no_session(self):
        store = self.sessions()
        store.issue()
        for value in (None, "", [], {}, "é" * 64, b"a" * 64, secrets.token_urlsafe(48)):
            self.assertIsNone(store.lookup(value))

    def test_logout_and_global_revocation(self):
        store = self.sessions()
        first, second = store.issue(), store.issue()
        store.revoke(first.token)
        store.revoke(first.token)
        self.assertIsNone(store.lookup(first.token))
        self.assertIsNotNone(store.lookup(second.token))
        store.revoke_all()
        self.assertIsNone(store.lookup(second.token))
        self.assertIsNotNone(store.issue())

    def test_restart_and_cross_instance_session_rejected(self):
        first, second = self.sessions(), self.sessions()
        receipt = first.issue()
        self.assertIsNone(second.lookup(receipt.token))
        first.close()
        self.assertEqual(first._sessions, {})
        with self.assertRaisesRegex(LifecycleError, "lifecycle_closed"):
            first.issue()

    def test_secrets_not_exposed_in_receipt_repr(self):
        receipt = self.sessions().issue()
        self.assertNotIn(receipt.token, repr(receipt))
        self.assertNotIn(receipt.csrf_token, repr(receipt))


class ClockFailureTests(OfflineCase):
    def test_bad_clock_clears_all_state_and_closes(self):
        for value in (99, -1, float("nan"), float("inf"), True, None, "100"):
            with self.subTest(value=value):
                self.clock.now = 100
                flows, sessions = self.flows(), self.sessions()
                flow, receipt = flows.start(), sessions.issue()
                self.clock.now = value
                for action in (lambda: flows.take(flow.state, flow.browser_token),
                               lambda: sessions.lookup(receipt.token)):
                    with self.assertRaisesRegex(LifecycleError, "clock_invalid"):
                        action()
                self.assertEqual(flows._flows, {})
                self.assertEqual(sessions._sessions, {})
                self.clock.now = 101
                for action in (flows.start, sessions.issue):
                    with self.assertRaisesRegex(LifecycleError, "lifecycle_closed"):
                        action()

    def test_clock_exception_closes(self):
        def broken():
            raise RuntimeError("not_a_safe_error_message")
        store = self.sessions(clock=broken)
        with self.assertRaisesRegex(LifecycleError, "^clock_invalid$"):
            store.issue()


class CookieTests(OfflineCase):
    def test_both_cookie_names_have_host_only_security_attributes(self):
        token = secrets.token_urlsafe(48)
        for name in (FLOW_COOKIE, SESSION_COOKIE):
            self.assertEqual(serialize_cookie(name, token),
                             f"{name}={token}; Path=/; Secure; HttpOnly; SameSite=Lax")
            self.assertNotIn("Domain", serialize_cookie(name, token))

    def test_clear_cookie_uses_matching_attributes(self):
        for name in (FLOW_COOKIE, SESSION_COOKIE):
            self.assertEqual(serialize_cookie(name),
                             f"{name}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0")

    def test_foreign_names_rejected(self):
        for name in ("__Host-mc-ceo-session", "session", "", "bad\r\nX: injected"):
            with self.assertRaises(LifecycleError):
                serialize_cookie(name)
            with self.assertRaises(LifecycleError):
                read_cookie([], name)

    def test_bad_tokens_cannot_inject_headers(self):
        for token in ("", "a" * 63, "a" * 65, "a" * 64 + "\r\nX: yes", "é" * 64, [], False):
            with self.subTest(token=token), self.assertRaises(LifecycleError):
                serialize_cookie(SESSION_COOKIE, token)

    def test_read_normal_cookie_among_other_values(self):
        token = secrets.token_urlsafe(48)
        self.assertEqual(read_cookie([f"other=x; {SESSION_COOKIE}={token}; third=y"], SESSION_COOKIE), token)
        self.assertEqual(read_cookie(["other=x", f"{SESSION_COOKIE}={token}"], SESSION_COOKIE), token)

    def test_duplicate_cookies_within_or_across_headers_rejected(self):
        token = secrets.token_urlsafe(48)
        pair = f"{SESSION_COOKIE}={token}"
        for headers in ([f"{pair}; {pair}"], [pair, pair], [pair, f"{SESSION_COOKIE}="]):
            self.assertIsNone(read_cookie(headers, SESSION_COOKIE))

    def test_invalid_target_cookie_values_rejected(self):
        token = secrets.token_urlsafe(48)
        for raw in (f'{SESSION_COOKIE}="{token}"', f"{SESSION_COOKIE} = {token}",
                    f"{SESSION_COOKIE}", f"{SESSION_COOKIE}={token}=", f"{SESSION_COOKIE}=bad",
                    f"{SESSION_COOKIE}={token}\r\n", f"{SESSION_COOKIE}={token}\x7f"):
            self.assertIsNone(read_cookie([raw], SESSION_COOKIE))

    def test_size_and_type_bounds(self):
        for headers in (None, "single string", [None], ["x"] * 17, ["x" * 8193]):
            self.assertIsNone(read_cookie(headers, SESSION_COOKIE))

    def test_unicode_whitespace_is_not_cookie_syntax(self):
        token = secrets.token_urlsafe(48)
        for space in ("\u00a0", "\u0085", "\u2003"):
            for raw in (f"{space}{SESSION_COOKIE}={token}", f"{SESSION_COOKIE}={token}{space}"):
                self.assertIsNone(read_cookie([raw], SESSION_COOKIE))

    def test_production_or_other_staging_cookie_is_not_session(self):
        token = secrets.token_urlsafe(48)
        self.assertIsNone(read_cookie([f"__Host-mc-ceo-session={token}"], SESSION_COOKIE))
        self.assertIsNone(read_cookie([f"{FLOW_COOKIE}={token}"], SESSION_COOKIE))


if __name__ == "__main__":
    unittest.main()
