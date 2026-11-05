"""Offline startup ownership and synthetic-session tests for the real factory."""
from dataclasses import replace
import inspect
import json
import os
import sys
import unittest
from unittest.mock import patch

DENIED = []
PHASE = "imports"
def audit(event, args):
    if (event.startswith("socket.") and event != "socket.gethostname") or event in {
            "os.system", "os.exec", "os.posix_spawn", "subprocess.Popen"}:
        DENIED.append((event, PHASE))
        raise RuntimeError("factory_test_action_denied:" + event)
sys.addaudithook(audit)
os.environ.clear()
sys.dont_write_bytecode = True

import requests
import test_ruby_staging_http_app as support
import ruby_staging_app_factory as factory
from ruby_staging_app_factory import create_staging_application, StagingFactoryConfigurationError
from ruby_staging_google_auth import StagingGoogleOwnerAuthenticator, AuthenticationConfigurationError
from ruby_staging_http_app import StagingHTTPApplication, StagingHTTPConfigurationError
from ruby_staging_lifecycle import validate_flow_policy, validate_session_policy, LifecycleError
PHASE = "tests"


class FactoryTests(support.HTTPApplicationTests):
    def options(self, **changes):
        values = dict(enabled=True, config=support.CONFIG, limits=support.LIMITS,
            client_secret=support.fixtures.SECRET, max_cache_seconds=300,
            wall_clock=lambda: self.wall, monotonic_clock=lambda: self.mono)
        values.update(changes)
        return values

    def make(self, **changes):
        app = create_staging_application(**self.options(**changes))
        self.apps.append(app)
        return app

    def assert_rejected_before_session(self, **changes):
        with patch.object(requests, "Session") as session:
            with self.assertRaisesRegex(StagingFactoryConfigurationError,
                                        "^staging_factory_configuration_invalid$"):
                create_staging_application(**self.options(**changes))
            session.assert_not_called()

    def test_disabled_ignores_all_inputs_and_allocates_no_backend(self):
        class Untouchable:
            def __getattribute__(self, name):
                raise AssertionError("disabled_input_inspected")
        poison = Untouchable()
        with patch.object(requests, "Session") as session:
            app = create_staging_application(config=poison, limits=poison,
                client_secret=poison, max_cache_seconds=poison,
                wall_clock=poison, monotonic_clock=poison)
            self.apps.append(app)
            status, _, body = self.call(app)
            self.assertEqual(status, 503)
            self.assertEqual(json.loads(body)["authority"], "none")
            session.assert_not_called()

    def test_enable_flag_and_exact_config_types_fail_before_session(self):
        for flag in (None, 0, 1, "true", [], object()):
            self.assert_rejected_before_session(enabled=flag)
        for key in ("config", "limits"):
            for value in (None, {}, object()):
                self.assert_rejected_before_session(**{key: value})

    def test_all_lifecycle_policy_bounds_fail_before_session(self):
        for field, values in {
            "flow_seconds": [False, True, 0, -1, 3601, 1.0, "5"],
            "idle_seconds": [False, True, 0, -1, 86401, 1.0, "5"],
            "absolute_seconds": [False, True, 0, -1, 86401, 1.0, "30"],
            "capacity": [False, True, 0, -1, 1025, 1.0, "32"],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assert_rejected_before_session(config=replace(support.CONFIG, **{field: value}))
        self.assert_rejected_before_session(config=replace(support.CONFIG, idle_seconds=31, absolute_seconds=30))

    def test_shared_validation_retains_existing_edge_bounds(self):
        self.assertEqual(validate_flow_policy(1, 1), (1, 1))
        self.assertEqual(validate_flow_policy(3600, 1024), (3600, 1024))
        self.assertEqual(validate_session_policy(1, 1, 1), (1, 1, 1))
        self.assertEqual(validate_session_policy(86400, 86400, 1024), (86400, 86400, 1024))
        for changes in ({"flow_seconds": 1, "idle_seconds": 1, "absolute_seconds": 1, "capacity": 1},
                        {"flow_seconds": 3600, "idle_seconds": 86400, "absolute_seconds": 86400, "capacity": 1024}):
            replace(support.CONFIG, **changes).validate()
        with self.assertRaises(LifecycleError):
            validate_session_policy(2, 1, 1)
        with self.assertRaises(StagingHTTPConfigurationError):
            replace(support.CONFIG, idle_seconds=31).validate()

    def test_identity_and_production_exclusions_fail_before_session(self):
        for changes in ({"origin": support.app_module.PRODUCTION_ORIGIN},
                        {"client_id": support.app_module.PRODUCTION_CLIENT_ID},
                        {"owner_subject": ""}, {"origin": "http://staging.invalid"},
                        {"origin": support.ORIGIN + "/path"}, {"client_id": ""}):
            self.assert_rejected_before_session(config=replace(support.CONFIG, **changes))

    def test_request_budget_policy_fails_before_session(self):
        for field in ("max_inflight_requests", "max_login_starts", "max_callback_attempts", "window_seconds"):
            for value in (0, True, -1, 99999):
                self.assert_rejected_before_session(limits=replace(support.LIMITS, **{field: value}))

    def test_invalid_secret_cache_and_clock_inputs_fail_before_session(self):
        for secret in (None, "", "bad secret", "bad\nsecret", "X" * 4097):
            self.assert_rejected_before_session(client_secret=secret)
        for cache in (None, False, True, 0, -1, 86401, "300"):
            self.assert_rejected_before_session(max_cache_seconds=cache)
        for name in ("wall_clock", "monotonic_clock"):
            for bad in (None, object()):
                self.assert_rejected_before_session(**{name: bad})
            for bad in (-1, True, float("inf"), float("nan"), "100"):
                self.assert_rejected_before_session(**{name: lambda bad=bad: bad})
            def failed_clock():
                raise ValueError("SYNTHETIC_CLOCK_PRIVATE")
            self.assert_rejected_before_session(**{name: failed_clock})
        self.assert_rejected_before_session(wall_clock=lambda: 2**53 + 1)

    def test_success_builds_one_session_and_transfers_exclusive_ownership(self):
        real_session = requests.Session
        with patch.object(requests, "Session", wraps=real_session) as create:
            app = self.make()
        create.assert_called_once_with()
        backend = app._authenticator
        self.assertIs(type(backend), StagingGoogleOwnerAuthenticator)
        self.assertTrue(backend.matches_policy(support.ORIGIN, support.CLIENT, support.OWNER))
        self.assertEqual(self.sent, [])
        session = backend._session
        with patch.object(session, "close", wraps=session.close) as close:
            app.close()
            close.assert_called_once_with()
        self.assertTrue(backend._closed)
        self.assertIsNone(backend._session)
        self.assertEqual(backend._client_secret, "")

    def test_app_failure_closes_created_backend_and_redacts_error(self):
        made = []
        def backend(*args, **kwargs):
            result = StagingGoogleOwnerAuthenticator(*args, **kwargs)
            made.append((result, result._session))
            return result
        with patch.object(factory, "StagingGoogleOwnerAuthenticator", side_effect=backend), \
                patch.object(factory, "StagingHTTPApplication", side_effect=ValueError("SYNTHETIC_APP_PRIVATE")), \
                patch.object(requests.Session, "close", autospec=True) as close:
            with self.assertRaisesRegex(StagingFactoryConfigurationError, "^staging_factory_configuration_invalid$"):
                create_staging_application(**self.options())
        self.assertEqual(len(made), 1)
        self.assertTrue(made[0][0]._closed)
        self.assertEqual(made[0][0]._client_secret, "")
        self.assertIsNone(made[0][0]._session)
        close.assert_called_once_with(made[0][1])

    def test_control_exception_during_app_creation_is_preserved_after_cleanup(self):
        for failure in (KeyboardInterrupt("synthetic-stop"), SystemExit(17)):
            made = []
            def backend(*args, **kwargs):
                result = StagingGoogleOwnerAuthenticator(*args, **kwargs)
                made.append(result)
                return result
            with patch.object(factory, "StagingGoogleOwnerAuthenticator", side_effect=backend), \
                    patch.object(factory, "StagingHTTPApplication", side_effect=failure):
                with self.assertRaises(type(failure)) as caught:
                    create_staging_application(**self.options())
            self.assertIs(caught.exception, failure)
            self.assertEqual(made[0]._client_secret, "")
            self.assertIsNone(made[0]._session)

    def test_cleanup_failure_never_replaces_primary_app_failure(self):
        primary = KeyboardInterrupt("synthetic-primary")
        with patch.object(factory, "StagingHTTPApplication", side_effect=primary), \
                patch.object(requests.Session, "close", side_effect=SystemExit(19)):
            with self.assertRaises(KeyboardInterrupt) as caught:
                create_staging_application(**self.options())
        self.assertIs(caught.exception, primary)

    def test_interrupted_backend_setup_closes_returned_session(self):
        real_session = requests.Session
        for failure in (KeyboardInterrupt("synthetic-stop"), SystemExit(23)):
            made = []
            def allocate():
                session = real_session()
                made.append(session)
                session.mount = lambda *args, **kwargs: (_ for _ in ()).throw(failure)
                return session
            with patch.object(requests, "Session", side_effect=allocate), \
                    patch.object(real_session, "close", autospec=True) as close:
                with self.assertRaises(type(failure)) as caught:
                    create_staging_application(**self.options())
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(made), 1)
            close.assert_called_once_with(made[0])

    def test_ordinary_backend_setup_failure_remains_redacted_and_closed(self):
        real_session = requests.Session
        made = []
        def allocate():
            session = real_session()
            made.append(session)
            session.mount = lambda *a, **k: (_ for _ in ()).throw(ValueError("SYNTHETIC_SETUP_PRIVATE"))
            return session
        with patch.object(requests, "Session", side_effect=allocate), \
                patch.object(real_session, "close", autospec=True) as close:
            with self.assertRaisesRegex(StagingFactoryConfigurationError, "^staging_factory_configuration_invalid$"):
                create_staging_application(**self.options())
        close.assert_called_once_with(made[0])

    def test_later_constructor_clock_failure_cleans_backend(self):
        values = iter((100.0, float("nan")))
        with patch.object(requests.Session, "close", autospec=True) as close:
            with self.assertRaises(StagingFactoryConfigurationError):
                create_staging_application(**self.options(monotonic_clock=lambda: next(values)))
        close.assert_called_once()

    def test_factory_app_signed_login_read_and_csrf_logout(self):
        app = self.make()
        session, _, _, _ = self.login(app)
        status, _, body = self.call(app, "/api/ruby-review-synthetic", cookie=session)
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["authority"], "none")
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["mutation_authorized"])
        _, _, body = self.call(app, "/api/session", cookie=session)
        csrf = json.loads(body)["csrf_token"]
        self.assertEqual(self.call(app, "/auth/logout", method="POST", cookie=session,
            HTTP_ORIGIN=support.ORIGIN, HTTP_X_CSRF_TOKEN=csrf)[0], 200)
        self.assertEqual(self.call(app, "/api/session", cookie=session)[0], 401)

    def test_factory_app_wrong_owner_remains_rejected(self):
        app = self.make()
        flow, cookie = self.start(app)
        self.queue(flow, sub="synthetic-wrong-owner")
        self.assertEqual(self.callback(app, flow, cookie)[0], 401)
        self.assertEqual(self.call(app, "/api/session")[0], 401)

    def test_later_clock_rollback_revokes_factory_app(self):
        app = self.make()
        session, _, _, _ = self.login(app)
        self.mono -= 1
        self.assertEqual(self.call(app, "/api/session", cookie=session)[0], 503)
        self.assertTrue(app._closed)
        self.assertEqual(app._authenticator._client_secret, "")

    def test_factory_is_passive_source_without_runtime_loader_or_policy_defaults(self):
        source = inspect.getsource(factory)
        for forbidden in ("os.environ", "open(", "serve_forever", "make_server", "gunicorn", "test_ruby", "setattr("):
            self.assertNotIn(forbidden, source)
        signature = inspect.signature(create_staging_application)
        self.assertIs(signature.parameters["enabled"].default, False)
        for name in ("config", "limits", "client_secret", "max_cache_seconds"):
            self.assertIsNone(signature.parameters[name].default)


if __name__ == "__main__":
    names = [name for name in FactoryTests.__dict__ if name.startswith("test_")]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(FactoryTests(name) for name in names))
    # When an outer audit guard is present, it can reject the import capability
    # probe before this hook is called. Otherwise this hook must reject it.
    if DENIED not in ([], [("socket.__new__", "imports")]):
        raise AssertionError("unexpected_factory_test_action")
    print("FACTORY_TEST_DENIALS=" + json.dumps(DENIED))
    raise SystemExit(0 if result.wasSuccessful() else 1)
