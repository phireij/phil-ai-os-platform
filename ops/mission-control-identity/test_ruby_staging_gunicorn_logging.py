"""Regression tests selecting the opt-in logger in the inert HTTP harness only."""
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("log_boundary_harness", ROOT / "ruby_staging_server_test_support.py")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
sys.path.insert(0, str(ROOT))
from ruby_staging_gunicorn_logging import StagingGunicornLogger, StagingLoggingConfigurationError


class RawRecords(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    def emit(self, record):
        self.records.append(record)


class RedactionTests(base.HTTPBoundaryTests):
    def setUp(self):
        super().setUp()
        self.logger_patch = patch.object(base, "Logger", StagingGunicornLogger)
        self.logger_patch.start()
        self.addCleanup(self.logger_patch.stop)

    def test_genuine_ruby_callback_abort_redacts_and_preserves_stop_cleanup(self):
        app = self.fx.make()
        flow, cookie = self.fx.start(app)
        worker = self.worker(app)
        marker = "SYNTHETIC_CALLBACK_CODE_PRIVATE"
        def abort_during_send(*args, **kwargs):
            worker.handle_abort(signal.SIGABRT, None)
        with patch.object(base.requests.Session, "send", side_effect=abort_during_send) as send:
            status, headers, body = self.fx.callback(app, flow, cookie,
                query=base.urlencode({"state": flow["state"], "code": marker}))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(status, 500)
        self.assertFalse(worker.alive)
        logs = "\n".join(self.exchanges[-1]["logs"])
        self.assertIn("staging_request_error", logs)
        self.assertNotIn(marker, logs)
        self.assertNotIn(flow["state"], logs)
        self.assertNotIn(marker.encode(), body)
        permits = 0
        try:
            while app._admission.acquire(blocking=False):
                permits += 1
            self.assertEqual(permits, base.fixtures.LIMITS.max_inflight_requests)
        finally:
            for _ in range(permits):
                app._admission.release()
        self.assertTrue(app._auth_slot.acquire(blocking=False))
        app._auth_slot.release()

    def test_partial_request_debug_log_redacted(self):
        app = self.fx.make()
        marker = "SYNTHETIC_PARTIAL_CODE_PRIVATE"
        result = self.raw(app, ("GET /auth/google/callback?code=" + marker + " HTTP/1.1").encode())
        self.assertEqual(result["wire"], b"")
        self.assertIn("staging_request_incomplete", "\n".join(result["logs"]))
        self.assertNotIn(marker, "\n".join(result["logs"]))
        self.assertEqual(self.fx.sent, [])

    def test_parser_error_log_redacted_but_response_gate_remains(self):
        app = self.fx.make()
        marker = "SYNTHETIC_MALFORMED_PRIVATE"
        result = self.raw(app, ("GET /auth/google/callback?code=" + marker + "\r\n\r\n").encode())
        status, headers, body = self.decode(result["wire"])
        self.assertEqual(status, 400)
        self.assertIn("staging_server_warning", "\n".join(result["logs"]))
        self.assertNotIn(marker, "\n".join(result["logs"]))
        # This is intentionally NOT fixed by a diagnostic logger.
        self.assertIn(marker.encode(), body)
        self.assertNotIn("cache-control", {k.lower(): v for k, v in headers})

    def test_successful_session_and_access_records_exclude_all_request_atoms(self):
        app = self.fx.make()
        session, flow, _, _ = self.fx.login(app)
        worker = self.worker(app, options={"accesslog": "-"})
        records = RawRecords()
        worker.log.access_log.addHandler(records)
        self.addCleanup(worker.log.access_log.removeHandler, records)
        result = self.raw(app, self.request("/api/session", cookie=session,
            headers=(("User-Agent", "SYNTHETIC_AGENT_PRIVATE"),)), options={"accesslog": "-"})
        self.assertEqual(self.decode(result["wire"])[0], 200)
        self.assertEqual([r.getMessage() for r in records.records], ["staging_http_response status=200"])
        rendered = "\n".join(r.getMessage() for r in records.records)
        for value in (session, flow["state"], "SYNTHETIC_AGENT_PRIVATE", "/api/session"):
            self.assertNotIn(value, rendered)

    def test_methods_drop_message_arguments_exception_stack_and_extras(self):
        logger = self.worker(self.fx.make(auth=None)).log
        records = RawRecords()
        logger.error_log.addHandler(records)
        self.addCleanup(logger.error_log.removeHandler, records)
        class Unrenderable:
            def __str__(self):
                raise AssertionError("untrusted diagnostic rendered")
            __repr__ = __str__
        for name in ("debug", "info", "warning", "error", "critical", "exception"):
            try:
                raise ValueError("SYNTHETIC_EXCEPTION_PRIVATE")
            except ValueError:
                getattr(logger, name)(Unrenderable(), Unrenderable(), exc_info=True,
                                      stack_info=True, extra={"private": "SYNTHETIC_EXTRA_PRIVATE"})
        logger.log("ERROR", Unrenderable(), Unrenderable())
        logger.log(Unrenderable(), Unrenderable())
        self.assertEqual(len(records.records), 8)
        for record in records.records:
            self.assertEqual(record.args, ())
            self.assertIsNone(record.exc_info)
            self.assertIsNone(record.stack_info)
            self.assertFalse(hasattr(record, "private"))
            self.assertTrue(record.getMessage().startswith("staging_server_"))
            self.assertNotIn("PRIVATE", record.getMessage())

    def test_status_atoms_are_numeric_only(self):
        logger = self.worker(self.fx.make(auth=None)).log
        for status, expected in ((200, 200), ("401 Unauthorized", 401), ("200 PRIVATE", 200),
                                 ("200\nPRIVATE", "unknown"), ("２００", "unknown"),
                                 (True, "unknown"), (99, "unknown"), (600, "unknown"),
                                 ("PRIVATE", "unknown")):
            self.assertEqual(logger.atoms(SimpleNamespace(status=status), object(), object(), object()), {"s": expected})

    def test_custom_output_configuration_rejected_before_setup(self):
        changes = [("capture_output", True), ("syslog", True), ("errorlog", "unopened-private.log"),
                   ("accesslog", "unopened-access.log"), ("logconfig", "unopened.conf"),
                   ("logconfig_json", "unopened.json"), ("logconfig_dict", {"version": 1})]
        for name, value in changes:
            cfg = base.Config()
            cfg.set(name, value)
            with patch("gunicorn.glogging.Logger.setup") as setup:
                with self.assertRaises(StagingLoggingConfigurationError):
                    StagingGunicornLogger(cfg)
                setup.assert_not_called()

    def test_unreviewed_version_rejected_before_setup(self):
        with patch.object(base.gunicorn, "__version__", "unreviewed"), patch("gunicorn.glogging.Logger.setup") as setup:
            with self.assertRaises(StagingLoggingConfigurationError):
                StagingGunicornLogger(base.Config())
            setup.assert_not_called()


# Positive compatibility checks must remain unchanged under the new logger.
POSITIVE_BASE = (
    "test_default_off_and_unauthenticated_contract", "test_signed_session_read_csrf_logout_cookie_flags",
    "test_wrong_owner_rejected_and_no_session_issued", "test_callback_replay_rejected",
    "test_expired_and_fresh_instance_session_rejected", "test_request_fragmentation_preserves_parser_and_session",
    "test_plain_http_and_forwarded_header_fail_closed", "test_duplicate_host_and_origin_and_framing_rejected",
    "test_transport_failure_is_app_redacted", "test_abort_after_headers_does_not_append_second_response",
)
NEW_TESTS = tuple(name for name in RedactionTests.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    suite = unittest.TestSuite(RedactionTests(name) for name in (*NEW_TESTS, *POSITIVE_BASE))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
