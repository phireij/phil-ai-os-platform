"""Offline fixture assertions only; no live OIDC/security-deployment claim."""

import dataclasses
import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import unittest
from unittest import mock
from conversation_store import ConversationRequestError

from ruby_staging_rehearsal import (
    DisposableStagingRehearsal, FIXTURE_OPT_IN, GOOGLE_ISSUER,
    PRODUCTION_CLIENT_ID, PRODUCTION_ORIGIN, StagingRehearsalError,
    StagingRehearsalProfile, SyntheticCallbackRehearsal,
)


def profile(**overrides):
    values = dict(enabled=True, origin="https://ruby-staging.example.invalid",
                  callback="https://ruby-staging.example.invalid/auth/google/callback",
                  client_id="synthetic-fixture-client.apps.googleusercontent.com",
                  owner_subject="synthetic-fixture-owner")
    values.update(overrides)
    return StagingRehearsalProfile(**values)


class ProfileTests(unittest.TestCase):
    def test_disabled_default(self):
        with self.assertRaisesRegex(StagingRehearsalError, "disabled"):
            StagingRehearsalProfile().validate()

    def test_exact_configuration(self):
        profile().validate()

    def test_fail_closed_configuration_matrix(self):
        cases = [dict(enabled=1), dict(enabled="true"), dict(synthetic_only=False),
                 dict(synthetic_only=1), dict(provider_dispatch=True), dict(provider_dispatch=0),
                 dict(origin=PRODUCTION_ORIGIN, callback=PRODUCTION_ORIGIN+"/auth/google/callback"),
                 dict(client_id=PRODUCTION_CLIENT_ID), dict(owner_subject=""),
                 dict(owner_subject="owner\n"), dict(issuer="https://attacker.invalid"),
                 dict(origin="http://ruby-staging.example.invalid"),
                 dict(origin="https://ruby-staging.example.invalid/"),
                 dict(origin="https://ruby-staging.example.invalid:443"),
                 dict(origin="https://ruby-staging.example.invalid@attacker.invalid"),
                 dict(origin="https://RUBY-staging.example.invalid"),
                 dict(callback="https://other.example.invalid/auth/google/callback"),
                 dict(callback=profile().callback+"?redirect=evil"),
                 dict(client_id=""), dict(client_id="placeholder")]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(StagingRehearsalError):
                profile(**change).validate()


class CallbackFixtureTests(unittest.TestCase):
    def setUp(self):
        self.profile = profile()
        self.now = 1000.0
        self.flow = SyntheticCallbackRehearsal(self.profile, opt_in=FIXTURE_OPT_IN,
                                             clock=lambda: self.now, wall_clock=lambda: self.now)
        self.state = "synthetic_state_123456"
        self.nonce = "synthetic_nonce_123456"
        self.browser = "synthetic_browser_123456"
        self.flow.begin_fixture(state=self.state, nonce=self.nonce, browser_binding=self.browser)
        self.arguments = dict(state=self.state, browser_binding=self.browser,
            headers=(("Host", "ruby-staging.example.invalid"), ("Origin", self.profile.origin)),
            registration=dict(issuer=GOOGLE_ISSUER, client_id=self.profile.client_id, callback=self.profile.callback),
            claims_fixture=dict(iss=GOOGLE_ISSUER, aud=self.profile.client_id, sub=self.profile.owner_subject,
                                nonce=self.nonce, iat=990.0, exp=1100.0))

    def test_synthetic_success_grants_no_authority(self):
        result = self.flow.check_callback_fixture(**self.arguments)
        self.assertEqual(dataclasses.asdict(result), {"synthetic_fixture_accepted": True, "authority": "none"})
        self.assertFalse(hasattr(result, "subject"))

    def test_replay_denied(self):
        self.flow.check_callback_fixture(**self.arguments)
        with self.assertRaisesRegex(StagingRehearsalError, "consumed"):
            self.flow.check_callback_fixture(**self.arguments)

    def test_consumed_state_cannot_be_registered_again(self):
        self.flow.check_callback_fixture(**self.arguments)
        with self.assertRaisesRegex(StagingRehearsalError, "duplicate"):
            self.flow.begin_fixture(state=self.state, nonce=self.nonce, browser_binding=self.browser)

    def test_failed_state_cannot_be_registered_again(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"sub": "other-owner"})
        with self.assertRaisesRegex(StagingRehearsalError, "duplicate"):
            self.flow.begin_fixture(state=self.state, nonce=self.nonce, browser_binding=self.browser)

    def test_expired_state_cannot_be_registered_again(self):
        self.now += 301
        with self.assertRaisesRegex(StagingRehearsalError, "duplicate"):
            self.flow.begin_fixture(state=self.state, nonce=self.nonce, browser_binding=self.browser)

    def test_concurrent_replay_allows_only_one_fixture_check(self):
        results = []
        def complete():
            try:
                self.flow.check_callback_fixture(**self.arguments)
                results.append("accepted")
            except StagingRehearsalError:
                results.append("rejected")
        threads = [threading.Thread(target=complete) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), ["accepted", "rejected"])

    def _reject_then_replay(self, **changes):
        with self.assertRaises(StagingRehearsalError):
            self.flow.check_callback_fixture(**(self.arguments | changes))
        with self.assertRaisesRegex(StagingRehearsalError, "consumed"):
            self.flow.check_callback_fixture(**self.arguments)

    def test_wrong_owner_consumes_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"sub": "other-owner"})

    def test_wrong_audience_consumes_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"aud": PRODUCTION_CLIENT_ID})

    def test_wrong_issuer_consumes_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"iss": "https://attacker.invalid"})

    def test_wrong_nonce_consumes_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"nonce": "different-nonce"})

    def test_wrong_browser_consumes_state(self):
        self._reject_then_replay(browser_binding="other-browser")

    def test_wrong_origin_consumes_state(self):
        self._reject_then_replay(headers=(("Host", "ruby-staging.example.invalid"), ("Origin", PRODUCTION_ORIGIN)))

    def test_wrong_host_consumes_state(self):
        self._reject_then_replay(headers=(("Host", "miscon.phireij.cloud"), ("Origin", self.profile.origin)))

    def test_wrong_callback_consumes_state(self):
        self._reject_then_replay(registration=self.arguments["registration"] | {"callback": PRODUCTION_ORIGIN+"/auth/google/callback"})

    def test_duplicate_origin_consumes_state(self):
        self._reject_then_replay(headers=self.arguments["headers"]+(("oRiGiN", self.profile.origin),))

    def test_duplicate_host_consumes_state(self):
        self._reject_then_replay(headers=self.arguments["headers"]+(("host", "ruby-staging.example.invalid"),))

    def test_untrusted_forwarded_host_consumes_state(self):
        self._reject_then_replay(headers=self.arguments["headers"]+(("X-Forwarded-Host", "ruby-staging.example.invalid"),))

    def test_missing_origin_consumes_state(self):
        self._reject_then_replay(headers=self.arguments["headers"][:1])

    def test_expired_flow_consumes_state(self):
        self.now += 301
        self._reject_then_replay()

    def test_expired_claims_consume_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"exp": 999.0})

    def test_future_claims_consume_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"iat": 1001.0})

    def test_nan_claims_consume_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"exp": float("nan")})

    def test_boolean_time_claims_consume_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"iat": True})

    def test_oversized_time_claims_consume_state_with_bounded_error(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"exp": 10**1000})

    def test_missing_registration_consumes_state_with_bounded_error(self):
        self._reject_then_replay(registration=None)

    def test_not_before_claims_consume_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"nbf": 1001.0})

    def test_unknown_claims_consume_state(self):
        self._reject_then_replay(claims_fixture=self.arguments["claims_fixture"] | {"email": "not-needed@example.invalid"})

    def test_unknown_registration_consumes_state(self):
        self._reject_then_replay(registration=self.arguments["registration"] | {"client_secret": "never-accepted"})

    def test_duplicate_state_does_not_replace_binding(self):
        with self.assertRaisesRegex(StagingRehearsalError, "duplicate"):
            self.flow.begin_fixture(state=self.state, nonce="replacement_nonce_123456", browser_binding=self.browser)
        self.flow.check_callback_fixture(**self.arguments)

    def test_state_capacity_bounded(self):
        for index in range(15):
            self.flow.begin_fixture(state=f"synthetic_state_{index:016}", nonce=self.nonce, browser_binding=self.browser)
        with self.assertRaisesRegex(StagingRehearsalError, "capacity"):
            self.flow.begin_fixture(state="one_too_many_states", nonce=self.nonce, browser_binding=self.browser)

    def test_opt_in_required(self):
        with self.assertRaisesRegex(StagingRehearsalError, "opt_in"):
            SyntheticCallbackRehearsal(self.profile, opt_in="")

    def test_lifetime_state_capacity_is_bounded(self):
        for index in range(255):
            self.now += 301
            self.flow.begin_fixture(state=f"synthetic_state_{index:016}", nonce=self.nonce, browser_binding=self.browser)
        self.now += 301
        with self.assertRaisesRegex(StagingRehearsalError, "lifetime_capacity"):
            self.flow.begin_fixture(state="one_too_many_lifetime_states", nonce=self.nonce, browser_binding=self.browser)


class CompositionTests(unittest.TestCase):
    def test_isolated_synthetic_state_no_network_no_providers(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")), mock.patch.object(socket.socket, "bind", side_effect=AssertionError("listener forbidden")):
            with DisposableStagingRehearsal(profile(), opt_in=FIXTURE_OPT_IN) as rehearsal:
                directory = rehearsal.fixture_directory
                binding = rehearsal.fixture_binding
                self.assertTrue(directory.is_relative_to("/tmp"))
                self.assertIsNone(binding.store._provider_runtime)
                self.assertFalse(binding.store._notification_delivery_enabled)
                self.assertTrue(binding.is_available_for(profile().owner_subject))
                self.assertFalse(binding.is_available_for("other-owner"))
                self.assertTrue(binding.list_records())
            self.assertFalse(directory.exists())
            self.assertTrue(binding.store._closed)
            self.assertIsNone(binding.store._lease.fd)
            self.assertFalse(binding.is_available_for(profile().owner_subject))
            with self.assertRaises(ConversationRequestError):
                binding.list_records()
            with self.assertRaisesRegex(StagingRehearsalError, "closed"):
                rehearsal.fixture_binding

    def test_independent_fixture_directories_and_keys(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with DisposableStagingRehearsal(profile(), opt_in=FIXTURE_OPT_IN) as first, DisposableStagingRehearsal(profile(), opt_in=FIXTURE_OPT_IN) as second:
                self.assertNotEqual(first.fixture_directory, second.fixture_directory)
                self.assertNotEqual((first.fixture_directory/"harness.key").read_bytes(), (second.fixture_directory/"harness.key").read_bytes())

    def test_repeated_close_is_safe(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            rehearsal = DisposableStagingRehearsal(profile(), opt_in=FIXTURE_OPT_IN)
            rehearsal.close()
            rehearsal.close()

    def test_cleanup_runs_if_store_close_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            rehearsal = DisposableStagingRehearsal(profile(), opt_in=FIXTURE_OPT_IN)
            directory = rehearsal.fixture_directory
            store = rehearsal.fixture_binding.store
            original_close = store.close
            def close_then_raise():
                original_close()
                raise RuntimeError("fixture close failure")
            with mock.patch.object(store, "close", side_effect=close_then_raise):
                with self.assertRaisesRegex(RuntimeError, "fixture close failure"):
                    rehearsal.close()
            self.assertFalse(directory.exists())
            self.assertTrue(store._closed)
            self.assertIsNone(store._lease.fd)

    def test_ambient_configuration_denied_before_writes(self):
        for key in ("MISSION_CONTROL_CONVERSATION_STATE_FILE", "MISSION_CONTROL_GOOGLE_CLIENT_SECRET_FILE", "MISSION_CONTROL_OPENAI_ENABLED", "MISSION_CONTROL_TELEGRAM_DELIVERY_ENABLED", "OPENAI_API_KEY", "TWILIO_AUTH_TOKEN", "DATABASE_URL", "GOOGLE_APPLICATION_CREDENTIALS"):
            with self.subTest(key=key), mock.patch.dict(os.environ, {key: "fixture-value"}, clear=True), mock.patch("tempfile.TemporaryDirectory", side_effect=AssertionError("must reject before writes")):
                with self.assertRaisesRegex(StagingRehearsalError, "ambient"):
                    DisposableStagingRehearsal(profile(), opt_in=FIXTURE_OPT_IN)

    def test_disabled_composition_denied_before_writes(self):
        with mock.patch("tempfile.TemporaryDirectory", side_effect=AssertionError("must reject before writes")):
            with self.assertRaisesRegex(StagingRehearsalError, "disabled"):
                DisposableStagingRehearsal(profile(enabled=False), opt_in=FIXTURE_OPT_IN)


if __name__ == "__main__":
    unittest.main()
