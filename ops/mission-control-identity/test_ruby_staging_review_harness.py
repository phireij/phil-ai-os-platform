"""Offline integration tests. No HTTP, actual login or external state changes."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import socket
import threading
import unittest
from unittest.mock import patch

from ruby_staging_lifecycle import FLOW_COOKIE, SESSION_COOKIE
from ruby_staging_rehearsal import StagingRehearsalProfile, StagingRehearsalError
from ruby_staging_review_harness import (
    FixtureIntegrationError, INTEGRATION_OPT_IN, StagingReviewHarness,
)


PROFILE = StagingRehearsalProfile(
    enabled=True, origin="https://ruby-staging.example.test",
    callback="https://ruby-staging.example.test/auth/google/callback",
    client_id="synthetic-client.apps.googleusercontent.com", owner_subject="synthetic-owner",
)
HOST = ("Host", "ruby-staging.example.test")
ORIGIN = ("Origin", PROFILE.origin)
RECORDS = "/api/ruby-review-synthetic/records"


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.sockets = patch.object(socket, "socket", side_effect=AssertionError("network_forbidden"))
        self.sockets.start()
        self.addCleanup(self.sockets.stop)
        self.now = 100.0
        self.harnesses = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for harness in self.harnesses:
            harness.close()

    def make(self, profile=PROFILE, **kwargs):
        values = dict(enabled=True, opt_in=INTEGRATION_OPT_IN, flow_seconds=5,
                      idle_seconds=10, absolute_seconds=30, capacity=8,
                      clock=lambda: self.now)
        values.update(kwargs)
        harness = StagingReviewHarness(profile, **values)
        self.harnesses.append(harness)
        return harness

    def login(self, harness, previous=None):
        start = harness.start_login_fixture()
        headers = (HOST, ("Cookie", start.flow_cookie.split(";", 1)[0]))
        if previous:
            headers += (("Cookie", previous),)
        result = harness.complete_login_fixture(state=start.flow.state,
            nonce_fixture=start.flow.nonce, owner_fixture=PROFILE.owner_subject, headers=headers)
        self.assertEqual(result.status, 200)
        body = json.loads(result.body)
        cookie = next(value.split(";", 1)[0] for name, value in result.headers
                      if name == "Set-Cookie" and value.startswith(SESSION_COOKIE + "="))
        return cookie, body["csrf_token"], result

    def get(self, harness, cookie=None, path=RECORDS, extra=()):
        headers = (HOST,) + ((("Cookie", cookie),) if cookie is not None else ()) + extra
        return harness.dispatch(method="GET", path=path, headers=headers)

    def logout(self, harness, cookie, csrf, origin=True):
        headers = (HOST, ("Cookie", cookie), ("X-CSRF-Token", csrf))
        if origin:
            headers += (ORIGIN,)
        return harness.dispatch(method="POST", path="/auth/fixture/logout", headers=headers)

    def assert_no_authority(self, response):
        data = json.loads(response.body)
        self.assertIs(data["synthetic"], True)
        self.assertEqual(data["authority"], "none")
        for key in ("execution_authorized", "mutation_authorized", "real_identity_verified"):
            self.assertIs(data[key], False)

    def test_default_off_and_explicit_opt_in(self):
        for overrides in ({"enabled": False}, {"enabled": "true"}, {"opt_in": "wrong"}):
            with self.subTest(overrides=overrides), self.assertRaises(FixtureIntegrationError):
                self.make(**overrides)
        with self.assertRaises(FixtureIntegrationError):
            StagingReviewHarness(PROFILE, opt_in=INTEGRATION_OPT_IN, flow_seconds=5,
                                 idle_seconds=10, absolute_seconds=30, capacity=8)

    def test_profile_production_values_rejected(self):
        for profile in (replace(PROFILE, origin="https://miscon.phireij.cloud"),
                        replace(PROFILE, provider_dispatch=True), replace(PROFILE, synthetic_only=False)):
            with self.subTest(profile=profile), self.assertRaises(StagingRehearsalError):
                self.make(profile)

    def test_no_session_cannot_read_fixture_records(self):
        harness = self.make()
        response = self.get(harness)
        self.assertEqual(response.status, 401)
        self.assertNotIn(b"record_id", response.body)
        self.assert_no_authority(response)

    def test_fixture_login_lists_three_synthetic_records(self):
        harness = self.make()
        cookie, _, login = self.login(harness)
        result = self.get(harness, cookie)
        self.assertEqual(result.status, 200)
        data = json.loads(result.body)
        self.assertEqual(len(data["records"]), 3)
        self.assertEqual({row["fulfillment_preference"] for row in data["records"]},
                         {"store pickup", "Yamato delivery", "Ruby car delivery"})
        for row in data["records"]:
            self.assertTrue(row["synthetic"])
            self.assertFalse(row["customer_confirmation"])
            self.assertEqual(row["authority_effect"], "none")
        self.assert_no_authority(result)
        self.assert_no_authority(login)

    def test_detail_and_audit_are_protected_and_synthetic(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        records = json.loads(self.get(harness, cookie).body)["records"]
        for row in records:
            for suffix in ("", "/audit"):
                path = RECORDS + "/" + row["record_id"] + suffix
                self.assertEqual(self.get(harness, path=path).status, 401)
                result = self.get(harness, cookie, path)
                self.assertEqual(result.status, 200)
                self.assert_no_authority(result)

    def test_unknown_record_returns_bounded_not_found(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        result = self.get(harness, cookie, RECORDS + "/" + "a" * 32)
        self.assertEqual(result.status, 404)
        self.assertNotIn(b"Traceback", result.body)
        self.assert_no_authority(result)

    def test_owner_or_nonce_mismatch_consumes_flow(self):
        harness = self.make()
        for owner, nonce in (("wrong-owner", None), (PROFILE.owner_subject, "wrong-nonce"),
                             ([], None), (PROFILE.owner_subject, []), ("é", None)):
            start = harness.start_login_fixture()
            args = dict(state=start.flow.state, owner_fixture=owner,
                        nonce_fixture=start.flow.nonce if nonce is None else nonce,
                        headers=(HOST, ("Cookie", start.flow_cookie.split(";", 1)[0])))
            result = harness.complete_login_fixture(**args)
            self.assertEqual(result.status, 401)
            args.update(owner_fixture=PROFILE.owner_subject, nonce_fixture=start.flow.nonce)
            self.assertEqual(harness.complete_login_fixture(**args).status, 401)
            self.assert_no_authority(result)

    def test_wrong_browser_consumes_flow(self):
        harness = self.make()
        start = harness.start_login_fixture()
        args = dict(state=start.flow.state, owner_fixture=PROFILE.owner_subject,
                    nonce_fixture=start.flow.nonce)
        result = harness.complete_login_fixture(**args, headers=(HOST, ("Cookie", f"{FLOW_COOKIE}={'x'*64}")))
        self.assertEqual(result.status, 401)
        result = harness.complete_login_fixture(**args, headers=(HOST, ("Cookie", start.flow_cookie.split(";",1)[0])))
        self.assertEqual(result.status, 401)

    def test_malformed_headers_consume_flow(self):
        harness = self.make()
        start = harness.start_login_fixture()
        args = dict(state=start.flow.state, owner_fixture=PROFILE.owner_subject, nonce_fixture=start.flow.nonce)
        good = (HOST, ("Cookie", start.flow_cookie.split(";", 1)[0]))
        self.assertEqual(harness.complete_login_fixture(**args, headers=good + (HOST,)).status, 400)
        self.assertEqual(harness.complete_login_fixture(**args, headers=good).status, 401)

    def test_flow_expiry_denies_fixture_login(self):
        harness = self.make()
        start = harness.start_login_fixture()
        self.now += 5
        result = harness.complete_login_fixture(state=start.flow.state, owner_fixture=PROFILE.owner_subject,
            nonce_fixture=start.flow.nonce, headers=(HOST, ("Cookie", start.flow_cookie.split(";",1)[0])))
        self.assertEqual(result.status, 401)

    def test_callback_simulation_does_not_require_origin(self):
        harness = self.make()
        _, _, response = self.login(harness)
        self.assertEqual(response.status, 200)

    def test_duplicate_session_cookie_blocks_fixture_login(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        start = harness.start_login_fixture()
        result = harness.complete_login_fixture(state=start.flow.state, owner_fixture=PROFILE.owner_subject,
            nonce_fixture=start.flow.nonce, headers=(HOST, ("Cookie", start.flow_cookie.split(";",1)[0]),
            ("Cookie", cookie), ("Cookie", cookie)))
        self.assertEqual(result.status, 401)

    def test_new_fixture_login_rotates_old_session(self):
        harness = self.make()
        old, old_csrf, _ = self.login(harness)
        new, new_csrf, _ = self.login(harness, previous=old)
        self.assertNotEqual(old, new)
        self.assertNotEqual(old_csrf, new_csrf)
        self.assertEqual(self.get(harness, old).status, 401)
        self.assertEqual(self.get(harness, new).status, 200)
        self.assertEqual(self.logout(harness, new, old_csrf).status, 401)

    def test_session_expires_at_idle_boundary(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        self.now += 10
        self.assertEqual(self.get(harness, cookie).status, 401)

    def test_absolute_expiry_survives_regular_reads(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        for now in (109, 118, 127):
            self.now = now
            self.assertEqual(self.get(harness, cookie).status, 200)
        self.now = 130
        self.assertEqual(self.get(harness, cookie).status, 401)

    def test_logout_requires_origin_and_csrf_and_revokes(self):
        harness = self.make()
        cookie, csrf, _ = self.login(harness)
        self.assertEqual(self.logout(harness, cookie, csrf, origin=False).status, 403)
        self.assertEqual(self.logout(harness, cookie, "wrong").status, 401)
        self.assertEqual(self.get(harness, cookie).status, 200)
        result = self.logout(harness, cookie, csrf)
        self.assertEqual(result.status, 200)
        self.assertTrue(any("Max-Age=0" in value for name, value in result.headers if name == "Set-Cookie"))
        self.assertEqual(self.get(harness, cookie).status, 401)
        self.assertEqual(self.logout(harness, cookie, csrf).status, 401)
        self.assert_no_authority(result)

    def test_failed_logout_does_not_extend_idle(self):
        harness = self.make()
        cookie, csrf, _ = self.login(harness)
        self.now = 109
        self.assertEqual(self.logout(harness, cookie, "wrong").status, 401)
        self.now = 110
        self.assertEqual(self.get(harness, cookie).status, 401)

    def test_cross_instance_cookie_denied(self):
        first, second = self.make(), self.make()
        cookie, _, _ = self.login(first)
        self.assertEqual(self.get(second, cookie).status, 401)

    def test_duplicate_cookies_and_identity_headers_denied(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        self.assertEqual(self.get(harness, cookie, extra=(("Cookie", cookie),)).status, 401)
        for extra in ((HOST,), (ORIGIN, ORIGIN), (("X-Forwarded-User", "synthetic-owner"),),
                      (("Authorization", "Bearer fake"),), (("X-Forwarded-Host", HOST[1]),),
                      (("Origin", "https://evil.example"),), (("Cookie", "bad\r\nInjected: yes"),)):
            self.assertEqual(self.get(harness, cookie, extra=extra).status, 400)

    def test_request_shape_and_unsupported_routes_denied(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        headers = (HOST, ("Cookie", cookie))
        for method, path, body, expected in (
            ("GET", "/auth/google/start", b"", 404), ("GET", "/auth/google/callback", b"", 404),
            ("GET", "/api/conversations", b"", 404), ("POST", RECORDS, b"", 405),
            ("DELETE", RECORDS, b"", 405), ("GET", RECORDS+"?x=1", b"", 400),
            ("GET", RECORDS, b"write data", 400), ("GET", "/auth/fixture/logout", b"", 405),
            ("GET", RECORDS, "", 400), ("GET", "x"*513, b"", 400)):
            result = harness.dispatch(method=method, path=path, headers=headers, body=body)
            self.assertEqual(result.status, expected)
            self.assert_no_authority(result)

    def test_security_headers_on_success_and_failure(self):
        harness = self.make()
        cookie, _, login = self.login(harness)
        for response in (login, self.get(harness, cookie), self.get(harness)):
            headers = dict(response.headers)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(headers["Referrer-Policy"], "no-referrer")
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assert_no_authority(response)

    def test_close_removes_only_owned_files_and_revokes_everything(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        directory = harness._fixture.fixture_directory
        self.assertTrue(directory.exists())
        harness.close()
        self.assertFalse(directory.exists())
        with self.assertRaisesRegex(FixtureIntegrationError, "integration_closed"):
            self.get(harness, cookie)
        with self.assertRaisesRegex(FixtureIntegrationError, "integration_closed"):
            harness.start_login_fixture()

    def test_ambient_runtime_configuration_blocks_creation_and_reads(self):
        with patch.dict(os.environ, {"MISSION_CONTROL_TEST_SENTINEL": "not-a-secret"}):
            with self.assertRaises(StagingRehearsalError):
                self.make()
        harness = self.make()
        cookie, _, _ = self.login(harness)
        with patch.dict(os.environ, {"MISSION_CONTROL_TEST_SENTINEL": "not-a-secret"}):
            with self.assertRaises(StagingRehearsalError):
                self.get(harness, cookie)

    def test_storage_error_is_redacted(self):
        harness = self.make()
        cookie, _, _ = self.login(harness)
        with patch.object(harness._fixture.fixture_binding, "list_records", side_effect=RuntimeError("private storage path and raw payload")):
            result = self.get(harness, cookie)
        self.assertEqual(result.status, 503)
        self.assertNotIn(b"private", result.body)
        self.assert_no_authority(result)

    def test_replay_race_yields_one_fixture_session(self):
        harness = self.make()
        start = harness.start_login_fixture()
        barrier = threading.Barrier(8)
        def complete(_):
            barrier.wait()
            return harness.complete_login_fixture(state=start.flow.state, owner_fixture=PROFILE.owner_subject,
                nonce_fixture=start.flow.nonce, headers=(HOST,("Cookie",start.flow_cookie.split(";",1)[0])))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(complete, range(8)))
        self.assertEqual(sum(response.status == 200 for response in results), 1)
        for response in results:
            self.assert_no_authority(response)

    def test_logout_waits_for_inflight_local_read_then_denies_later_reads(self):
        harness = self.make()
        cookie, csrf, _ = self.login(harness)
        entered, release = threading.Event(), threading.Event()
        binding = harness._fixture.fixture_binding
        original = binding.list_records
        def blocked_read():
            entered.set()
            if not release.wait(5):
                raise AssertionError("test_read_not_released")
            return original()
        with patch.object(binding, "list_records", side_effect=blocked_read):
            with ThreadPoolExecutor(max_workers=2) as pool:
                read = pool.submit(self.get, harness, cookie)
                self.assertTrue(entered.wait(5))
                logout = pool.submit(self.logout, harness, cookie, csrf)
                release.set()
                self.assertEqual(read.result().status, 200)
                self.assertEqual(logout.result().status, 200)
        self.assertEqual(self.get(harness, cookie).status, 401)

    def test_fixture_responses_do_not_expose_secret_values_in_repr(self):
        harness = self.make()
        start = harness.start_login_fixture()
        self.assertNotIn(start.flow.state, repr(start))
        cookie, csrf, response = self.login(harness)
        self.assertNotIn(cookie, repr(response))
        self.assertNotIn(csrf, repr(response))

    def test_integration_has_no_provider_or_notification_runtime(self):
        harness = self.make()
        store = harness._fixture.fixture_binding.store
        self.assertIsNone(store._provider_runtime)
        self.assertFalse(store._notification_delivery_enabled)


if __name__ == "__main__":
    unittest.main()
