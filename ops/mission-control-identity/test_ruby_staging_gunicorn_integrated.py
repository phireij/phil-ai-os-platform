"""Composition acceptance for all three opt-in staging adapters, offline only.

No serving process, real TLS, listener, DNS or Google connection. The helper
validates an explicit pinned official source tree before importing its handler.
"""
import importlib.util
import json
import logging
from pathlib import Path
import signal
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "integrated_boundary_tests", ROOT / "test_ruby_staging_gunicorn_boundary.py")
canonical = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = canonical
spec.loader.exec_module(canonical)
base = canonical.base
from ruby_staging_gunicorn_worker import _BODY, _response
from gunicorn.http import errors


class IntegratedStagingServerTests(canonical.CanonicalBoundaryTests):
    def assert_safe_error(self, result, status, marker, body=b""):
        actual, headers, returned = self.decode(result["wire"])
        self.assertEqual((actual, returned), (status, body))
        self.assertNotIn(marker.encode(), result["wire"])
        self.assertNotIn(marker, "\n".join(result["logs"]))
        lower = {k.lower(): v for k, v in headers}
        for name, value in {"cache-control": "no-store", "pragma": "no-cache",
                            "referrer-policy": "no-referrer", "x-content-type-options": "nosniff",
                            "x-frame-options": "DENY", "connection": "close"}.items():
            self.assertEqual(lower[name], value)
        self.assertIn("default-src 'none'", lower["content-security-policy"])
        self.assertEqual(int(lower["content-length"]), len(returned))
        self.assertTrue({"set-cookie", "location", "access-control-allow-origin"}.isdisjoint(lower))
        self.assertLess(len(result["wire"]), 1024)

    def test_composed_parser_errors_redact_raw_callback_and_keep_security_headers(self):
        app = self.fx.make()
        marker = "SYNTHETIC_COMPOSED_MALFORMED"
        result = self.raw(app, ("GET /auth/google/callback?code=" + marker + "\r\n\r\n").encode(), fragment=1)
        self.assert_safe_error(result, 400, marker)
        self.assertEqual(self.fx.sent, [])

    def test_composed_header_and_path_errors_never_reach_wsgi(self):
        app = self.fx.make(auth=None)
        marker = "SYNTHETIC_COMPOSED_PRIVATE"
        requests = [self.request("/auth/google/%73tart", query="code=" + marker),
                    self.request("/auth/google/start", headers=(("X_CSRF_TOKEN", marker),))]
        worker = self.worker(app)
        for request in requests:
            with patch.object(worker, "wsgi", wraps=worker.wsgi) as wsgi:
                result = self.raw(app, request, fragment=1)
            wsgi.assert_not_called()
            # Canonical target validation has a Request; early parser errors do not.
            expected_body = _BODY if b"%73" in request else b""
            self.assert_safe_error(result, 400, marker, expected_body)

    def test_composed_actual_callback_abort_redacts_and_releases_admission(self):
        app = self.fx.make()
        flow, cookie = self.fx.start(app)
        worker = self.worker(app)
        marker = "SYNTHETIC_COMPOSED_ABORT"
        def abort(*args, **kwargs):
            worker.handle_abort(signal.SIGABRT, None)
        with patch.object(base.requests.Session, "send", side_effect=abort):
            result = self.raw(app, self.request("/auth/google/callback", cookie=cookie,
                query=base.urlencode({"state": flow["state"], "code": marker})))
        self.assert_safe_error(result, 500, marker, _BODY)
        self.assertFalse(worker.alive)
        self.assertNotIn(flow["state"], "\n".join(result["logs"]))
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

    def test_composed_ordinary_exception_is_generic_without_stopping_worker(self):
        marker = "SYNTHETIC_COMPOSED_EXCEPTION"
        class Unrenderable(Exception):
            def __str__(self):
                raise AssertionError("exception_must_not_render")
            __repr__ = __str__
        def broken(environ, start_response):
            raise Unrenderable(marker)
        result = self.raw(broken, self.request("/auth/google/callback", query="code=" + marker))
        self.assert_safe_error(result, 500, marker, _BODY)
        self.assertTrue(result["worker_alive"])

    def test_composed_valid_head_error_has_no_body(self):
        def broken(environ, start_response):
            raise ValueError("SYNTHETIC_COMPOSED_HEAD")
        result = self.raw(broken, self.request("/", method="HEAD"))
        headers, body = result["wire"].split(b"\r\n\r\n", 1)
        self.assertTrue(headers.startswith(b"HTTP/1.1 500"))
        self.assertIn(b"Cache-Control: no-store", headers)
        self.assertIn(b"Content-Length: " + str(len(_BODY)).encode(), headers)
        self.assertEqual(body, b"")
        self.assertNotIn("SYNTHETIC_COMPOSED_HEAD", "\n".join(result["logs"]))

    def test_composed_write_failure_is_single_attempt_and_redacted(self):
        worker = self.worker(self.fx.make(auth=None))
        class PartialClient(base.MemorySocket):
            def __init__(self):
                super().__init__()
                self.attempts = 0
            def sendall(self, data):
                self.attempts += 1
                self.outgoing.extend(data[:12])
                raise BlockingIOError("SYNTHETIC_COMPOSED_WRITE")
        client = PartialClient()
        worker.handle_error(None, client, None, errors.InvalidRequestLine("SYNTHETIC_COMPOSED_TARGET"))
        self.assertEqual(client.attempts, 1)
        self.assertEqual(bytes(client.outgoing), _response(400, unidentified=True)[:12])
        self.assertNotIn("SYNTHETIC_COMPOSED", "\n".join(self.records.records))

    def test_composed_access_logs_retain_status_only_after_signed_login(self):
        app = self.fx.make()
        session, flow, _, _ = self.fx.login(app)
        worker = self.worker(app, options={"accesslog": "-"})
        records = base.Records()
        worker.log.access_log.addHandler(records)
        self.addCleanup(worker.log.access_log.removeHandler, records)
        result = self.raw(app, self.request("/api/session", cookie=session,
            headers=(("User-Agent", "SYNTHETIC_COMPOSED_AGENT"),)), options={"accesslog": "-"})
        self.assertEqual(self.decode(result["wire"])[0], 200)
        self.assertEqual(records.records, ["staging_http_response status=200"])
        for value in (session, flow["state"], "/api/session", "SYNTHETIC_COMPOSED_AGENT"):
            self.assertNotIn(value, "\n".join(records.records))

    def test_composed_imports_use_this_checkout_and_exact_official_source(self):
        for name in ("ruby_staging_http_app", "ruby_staging_google_auth", "ruby_staging_lifecycle",
                     "ruby_staging_gunicorn_logging", "ruby_staging_gunicorn_worker", "ruby_staging_gunicorn_boundary"):
            self.assertEqual(Path(sys.modules[name].__file__).resolve(), ROOT / (name + ".py"))
        self.assertEqual(Path(base.gunicorn.__file__).resolve(), base.SOURCE / "gunicorn/__init__.py")
        self.assertEqual(base.gunicorn.__version__, "26.2.2")
        status, _, body = self.call(base.StagingHTTPApplication())
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["authority"], "none")
        self.assertEqual(self.fx.sent, [])


if __name__ == "__main__":
    names = [name for name in IntegratedStagingServerTests.__dict__ if name.startswith("test_")]
    suite = unittest.TestSuite(IntegratedStagingServerTests(name) for name in names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
