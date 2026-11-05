"""Test opt-in staging errors through the actual pinned handler and parser."""
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("error_boundary_harness", ROOT / "ruby_staging_server_test_support.py")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
sys.path.insert(0, str(ROOT))
from ruby_staging_gunicorn_logging import StagingGunicornLogger
from ruby_staging_gunicorn_worker import StagingSyncWorker, StagingWorkerConfigurationError, _BODY, _response
from gunicorn.http import errors
from gunicorn.workers.base import Worker
from gunicorn.workers.sync import SyncWorker


class ErrorResponseTests(base.HTTPBoundaryTests):
    def setUp(self):
        super().setUp()
        for target, replacement in (("Logger", StagingGunicornLogger), ("SyncWorker", StagingSyncWorker)):
            p = patch.object(base, target, replacement)
            p.start()
            self.addCleanup(p.stop)

    def assert_generic(self, result, status, marker, *, expected_body=b""):
        actual, headers, body = self.decode(result["wire"])
        self.assertEqual(actual, status)
        self.assertEqual(body, expected_body)
        self.assertNotIn(marker.encode(), result["wire"])
        self.assertNotIn(marker, "\n".join(result["logs"]))
        lower = {k.lower(): v for k, v in headers}
        self.assertEqual(lower["cache-control"], "no-store")
        self.assertEqual(lower["pragma"], "no-cache")
        self.assertEqual(lower["referrer-policy"], "no-referrer")
        self.assertEqual(lower["x-content-type-options"], "nosniff")
        self.assertEqual(lower["x-frame-options"], "DENY")
        self.assertIn("default-src 'none'", lower["content-security-policy"])
        self.assertEqual(lower["connection"], "close")
        self.assertEqual(int(lower["content-length"]), len(body))
        for name in ("set-cookie", "location", "access-control-allow-origin"):
            self.assertNotIn(name, lower)
        self.assertLess(len(result["wire"]), 1024)

    def test_malformed_callback_line_has_no_reflection_and_security_headers(self):
        app = self.fx.make()
        marker = "SYNTHETIC_CALLBACK_CODE_NO_REFLECTION"
        result = self.raw(app, ("GET /auth/google/callback?code=" + marker + "\r\n\r\n").encode(), fragment=1)
        self.assert_generic(result, 400, marker)
        self.assertEqual(self.fx.sent, [])

    def test_parser_rejection_statuses_have_same_bounded_body(self):
        app = self.fx.make()
        marker = "SYNTHETIC_HEADER_NO_REFLECTION"
        cases = [
            (self.request(headers=(("Host", marker),)), {}, 400),
            (self.request(headers=(("Expect", marker),)), {}, 417),
            (self.request(headers=(("Transfer-Encoding", marker),)), {}, 501),
            (self.request(headers=(("Cookie", marker),)), {"limit_request_field_size": 8}, 431),
            (self.request(headers=(("X_INVALID", marker),)), {"header_map": "refuse"}, 400),
        ]
        for request, options, status in cases:
            with self.subTest(status=status, options=options):
                self.assert_generic(self.raw(app, request, options=options, fragment=1), status, marker)
        self.assertEqual(self.fx.sent, [])

    def test_actual_ruby_callback_abort_generic_500_preserves_stop_and_cleanup(self):
        app = self.fx.make()
        flow, cookie = self.fx.start(app)
        worker = self.worker(app)
        marker = "SYNTHETIC_ABORT_NO_REFLECTION"
        def abort(*args, **kwargs):
            worker.handle_abort(signal.SIGABRT, None)
        with patch.object(base.requests.Session, "send", side_effect=abort):
            result = self.raw(app, self.request("/auth/google/callback", cookie=cookie,
                query=base.urlencode({"state": flow["state"], "code": marker})))
        self.assert_generic(result, 500, marker, expected_body=_BODY)
        self.assertFalse(worker.alive)
        self.assertNotIn(flow["state"].encode(), result["wire"])
        self.assertTrue(app._auth_slot.acquire(blocking=False))
        app._auth_slot.release()
        permits = 0
        try:
            while app._admission.acquire(blocking=False):
                permits += 1
            self.assertEqual(permits, base.fixtures.LIMITS.max_inflight_requests)
        finally:
            for _ in range(permits):
                app._admission.release()

    def test_ordinary_exception_generic_500_worker_stays_alive(self):
        marker = "SYNTHETIC_EXCEPTION_NO_REFLECTION"
        class Poison(Exception):
            def __str__(self):
                raise AssertionError("exception rendered")
            __repr__ = __str__
        def broken(environ, start_response):
            raise Poison(marker)
        result = self.raw(broken, self.request("/auth/google/callback", query="code=" + marker))
        self.assert_generic(result, 500, marker, expected_body=_BODY)
        self.assertTrue(result["worker_alive"])

    def test_valid_head_error_omits_body(self):
        def broken(environ, start_response):
            raise ValueError("SYNTHETIC_HEAD_PRIVATE")
        result = self.raw(broken, self.request("/", method="HEAD"))
        headers, body = result["wire"].split(b"\r\n\r\n", 1)
        self.assertTrue(headers.startswith(b"HTTP/1.1 500"))
        self.assertIn(b"Cache-Control: no-store", headers)
        self.assertIn(b"Content-Length: " + str(len(_BODY)).encode(), headers)
        self.assertEqual(body, b"")

    def test_one_nonblocking_write_no_retry_on_failure(self):
        app = self.fx.make()
        worker = self.worker(app)
        class FailingClient(base.MemorySocket):
            def __init__(self):
                super().__init__()
                self.attempts = 0
                self.blocking = []
            def setblocking(self, value):
                self.blocking.append(value)
                super().setblocking(value)
            def sendall(self, data):
                self.attempts += 1
                self.outgoing.extend(data[:12])
                raise BlockingIOError("SYNTHETIC_WRITE_PRIVATE")
        client = FailingClient()
        worker.handle_error(None, client, None, errors.InvalidRequestLine("SYNTHETIC_REQUEST_PRIVATE"))
        self.assertEqual(client.attempts, 1)
        self.assertEqual(client.blocking, [0, 1])
        self.assertEqual(bytes(client.outgoing), _response(400, unidentified=True)[:12])
        self.assertNotIn("SYNTHETIC", "\n".join(self.records.records))

    def test_control_flow_baseexception_propagates_without_appending_response(self):
        worker = self.worker(self.fx.make(auth=None))
        client = base.MemorySocket()
        client.outgoing.extend(b"HTTP/1.1 200 OK\r\n\r\npartial")
        with self.assertRaises(KeyboardInterrupt):
            worker.handle_error(None, client, None, KeyboardInterrupt())
        self.assertEqual(bytes(client.outgoing), b"HTTP/1.1 200 OK\r\n\r\npartial")

    def test_malformed_head_early_parser_error_is_empty_without_guessing(self):
        app = self.fx.make()
        result = self.raw(app, self.request(method="HEAD", headers=(("Bad Header", "SYNTHETIC_HEAD_PRIVATE"),)))
        self.assert_generic(result, 400, "SYNTHETIC_HEAD_PRIVATE")
        self.assertIn(b"Content-Length: 0\r\n", result["wire"])

    def test_unknown_parser_error_code_attribute_does_not_choose_status(self):
        worker = self.worker(self.fx.make(auth=None))
        for exc in (errors.InvalidProxyHeader("SYNTHETIC_PROXY_PRIVATE"),):
            client = base.MemorySocket()
            worker.handle_error(None, client, None, exc)
            self.assertEqual(self.decode(bytes(client.outgoing))[0], 500)
            self.assertNotIn(b"SYNTHETIC", client.outgoing)

    def test_rejects_unsafe_logger_and_unreviewed_version_before_worker_setup(self):
        cfg = base.Config()
        with patch.object(Worker, "__init__") as init:
            with self.assertRaises(StagingWorkerConfigurationError):
                StagingSyncWorker(1, 1, [], None, 1, cfg, object())
            init.assert_not_called()
        logger = self.worker(self.fx.make(auth=None)).log
        with patch.object(base.gunicorn, "__version__", "unknown"), patch.object(Worker, "__init__") as init:
            with self.assertRaises(StagingWorkerConfigurationError):
                StagingSyncWorker(1, 1, [], None, 1, cfg, logger)
            init.assert_not_called()

    def test_original_handler_parser_and_abort_methods_are_inherited(self):
        self.assertIs(StagingSyncWorker.handle, SyncWorker.handle)
        self.assertIs(StagingSyncWorker.handle_request, SyncWorker.handle_request)
        self.assertIs(StagingSyncWorker.handle_abort, Worker.handle_abort)
        self.assertIs(StagingSyncWorker.init_process, Worker.init_process)


POSITIVE_BASE = (
    "test_default_off_and_unauthenticated_contract", "test_signed_session_read_csrf_logout_cookie_flags",
    "test_wrong_owner_rejected_and_no_session_issued", "test_callback_replay_rejected",
    "test_expired_and_fresh_instance_session_rejected", "test_request_fragmentation_preserves_parser_and_session",
    "test_plain_http_and_forwarded_header_fail_closed", "test_duplicate_host_and_origin_and_framing_rejected",
    "test_transport_failure_is_app_redacted", "test_abort_after_headers_does_not_append_second_response",
    "test_raw_path_alias_observations_are_not_ingress_acceptance",
    "test_dropped_underscore_header_is_not_raw_header_rejection",
    "test_connection_header_compatibility_requires_transport_contract",
    "test_trusted_forwarded_scheme_still_needs_approved_app_boundary",
)
NEW_TESTS = tuple(name for name in ErrorResponseTests.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    suite = unittest.TestSuite(ErrorResponseTests(name) for name in (*NEW_TESTS, *POSITIVE_BASE))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
