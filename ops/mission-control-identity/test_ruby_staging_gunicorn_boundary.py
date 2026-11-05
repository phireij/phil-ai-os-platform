"""Original parser/handler with opt-in canonical boundary, no real transport."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("canonical_http_harness", ROOT / "ruby_staging_server_test_support.py")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
sys.path.insert(0, str(ROOT))
from ruby_staging_gunicorn_logging import StagingGunicornLogger
from ruby_staging_gunicorn_worker import StagingSyncWorker
from ruby_staging_gunicorn_boundary import StagingCanonicalWorker, StagingBoundaryConfigurationError
from gunicorn.workers.base import Worker


class CanonicalBoundaryTests(base.HTTPBoundaryTests):
    def setUp(self):
        super().setUp()
        for target, replacement in (("Logger", StagingGunicornLogger), ("SyncWorker", StagingCanonicalWorker)):
            p = patch.object(base, target, replacement)
            p.start()
            self.addCleanup(p.stop)

    def worker(self, app, *, tls=True, options=None):
        strict = {"header_map": "refuse", "forwarder_headers": ""}
        strict.update(options or {})
        return super().worker(app, tls=tls, options=strict)

    def test_connection_header_compatibility_requires_transport_contract(self):
        # This canonical transport now owns the narrow exception; the app alone
        # still rejects Connection and the generic worker remains unchanged.
        app = self.fx.make(auth=None)
        for token in ("close", "keep-alive", "Close", "Keep-Alive"):
            result = self.raw(app, self.request("/healthz", headers=(("Connection", token),)))
            status, headers, _ = self.decode(result["wire"])
            self.assertEqual(status, 200)
            self.assertIn(("Connection", "close"), headers)

    def test_unsafe_transport_headers_never_reach_wsgi_or_continue(self):
        called = []
        def app(environ, start_response):
            called.append(environ)
            start_response("200 OK", [("Content-Length", "0")])
            return []
        cases = (
            (("Expect", "100-continue"),), (("Expect", "other"),),
            (("Transfer-Encoding", "chunked"),), (("TE", "trailers"),),
            (("Trailer", "X-Secret"),), (("Upgrade", "websocket"),),
            (("Connection", "Host"),), (("Connection", "Origin"),),
            (("Connection", "close, keep-alive"),), (("Connection", ""),),
            (("Connection", "keep-alive"), ("Connection", "close")),
            (("Connection", "close"), ("Expect", "100-continue")),
            (("Connection", "X-CSRF-Token"),), (("Connection", "Cookie"),),
        )
        for headers in cases:
            with self.subTest(headers=headers):
                result = self.raw(app, self.request("/", headers=headers), fragment=1)
                self.assertIn(self.decode(result["wire"])[0], (400, 417))
                self.assertNotIn(b"100 Continue", result["wire"])
                self.assertEqual(called, [])

    def test_connection_removal_preserves_other_header_evidence(self):
        seen = []
        def app(environ, start_response):
            seen.append(environ)
            start_response("200 OK", [("Content-Length", "0")])
            return []
        result = self.raw(app, self.request("/", headers=(
            ("Connection", "keep-alive"), ("Origin", "first"), ("Origin", "second"),
            ("X-Forwarded-Proto", "https"))))
        self.assertEqual(self.decode(result["wire"])[0], 200)
        self.assertNotIn("HTTP_CONNECTION", seen[0])
        self.assertEqual(seen[0]["HTTP_ORIGIN"], "first,second")
        self.assertEqual(seen[0]["HTTP_X_FORWARDED_PROTO"], "https")

    def test_header_validation_is_atomic_and_rejects_invalid_shapes(self):
        from types import SimpleNamespace
        from gunicorn.http.errors import InvalidHeader
        from ruby_staging_gunicorn_boundary import _validated_headers
        bad = (
            None, (), [["CONNECTION", "close"]], [("CONNECTION",)],
            [("CONNECTION", 1)], [(1, "close")],
            [("CONNECTION", "close"), ("TE", "trailers")],
            [("CONNECTION", "close"), ("CONNECTION", "close")],
            [("CONNECTION", "cloſe")], [("CONNECTION", "keep-alive ")],
        )
        for headers in bad:
            req = SimpleNamespace(headers=headers, _expected_100_continue=False)
            with self.subTest(headers=headers), self.assertRaises(InvalidHeader):
                _validated_headers(req)
            self.assertIs(req.headers, headers)
        for flag in (True, None, 0, 1):
            req = SimpleNamespace(headers=[], _expected_100_continue=flag)
            with self.assertRaises(InvalidHeader):
                _validated_headers(req)
        original = [("HOST", "example.invalid"), ("CONNECTION", "close"),
                    ("ORIGIN", "one"), ("ORIGIN", "two")]
        req = SimpleNamespace(headers=original, _expected_100_continue=False)
        self.assertEqual(_validated_headers(req), [original[0], original[2], original[3]])
        self.assertIs(req.headers, original)

    def test_aliases_and_non_origin_targets_rejected_before_wsgi(self):
        app = self.fx.make()
        targets = (
            "/auth/google/%73tart", "/auth%2Fgoogle%2Fstart", "/auth%252Fgoogle/start",
            "/auth/google/start#fragment", "/auth/google/start?x=1#fragment",
            "https://other.invalid/auth/google/start", "//other.invalid/auth/google/start",
            "/auth//google/start", "/auth/./google/start", "/auth/a/../google/start",
            "/auth\\google/start", "/auth/google/start%00", "/auth/google/start\x00",
        )
        worker = self.worker(app)
        for target in targets:
            with self.subTest(target=target), patch.object(worker, "wsgi", wraps=worker.wsgi) as wsgi:
                result = self.raw(app, self.request(target), fragment=1)
                self.assertEqual(self.decode(result["wire"])[0], 400)
                wsgi.assert_not_called()
        self.assertEqual(self.fx.sent, [])

    def test_valid_literal_unknown_path_remains_404(self):
        app = self.fx.make(auth=None)
        for path in ("/missing", "/missing.txt", "/auth/google/start/"):
            self.assertEqual(self.call(app, path)[0], 404)

    def test_origin_form_target_reaches_wsgi_without_path_query_rewrite(self):
        seen = []
        def app(environ, start_response):
            seen.append((environ["RAW_URI"], environ["PATH_INFO"], environ["QUERY_STRING"]))
            start_response("200 OK", [("Content-Length", "0")])
            return []
        target = "/literal?code=a%2Fb%2Bc%3D%252F%23%3F&state=unchanged"
        self.assertEqual(self.decode(self.raw(app, self.request(target))["wire"])[0], 200)
        self.assertEqual(seen, [(target, "/literal", target.split("?", 1)[1])])

    def test_encoded_query_code_survives_genuine_signed_callback(self):
        app = self.fx.make()
        flow, cookie = self.fx.start(app)
        code = "synthetic/a+b=%2F#?"
        self.fx.queue(flow)
        status, headers, body = self.fx.callback(app, flow, cookie,
            query=base.urlencode({"state": flow["state"], "code": code}))
        self.assertEqual(status, 303)
        post = self.fx.sent[0][1]
        from urllib.parse import parse_qs
        self.assertEqual(parse_qs(post.body)["code"], [code])

    def test_underscore_header_never_dropped_or_forwarded_to_wsgi(self):
        app = self.fx.make(auth=None)
        for name in ("X_UNTRUSTED_HEADER", "X_CSRF_TOKEN", "Content_Length", "SCRIPT_NAME", "PATH_INFO"):
            for options in ({}, {"forwarded_allow_ips": "127.0.0.1"}):
                with self.subTest(name=name, options=options):
                    worker = self.worker(app, options=options)
                    with patch.object(worker, "wsgi", wraps=worker.wsgi) as wsgi:
                        result = self.raw(app, self.request("/healthz", headers=((name, "SYNTHETIC_PRIVATE"),)),
                                          options=options, fragment=1)
                    self.assertEqual(self.decode(result["wire"])[0], 400)
                    self.assertNotIn(b"SYNTHETIC_PRIVATE", result["wire"])
                    wsgi.assert_not_called()

    def test_constructor_refuses_policy_bypasses_before_worker_setup(self):
        invalid = (("header_map", "drop"), ("header_map", "dangerous"),
                   ("forwarder_headers", "SCRIPT_NAME"), ("forwarder_headers", "*"),
                   ("http_parser", "auto"), ("http_parser", "fast"), ("protocol", "uwsgi"),
                   ("http_protocols", "h1,h2"), ("permit_obsolete_folding", True),
                   ("strip_header_spaces", True), ("casefold_http_method", True),
                   ("permit_unconventional_http_method", True), ("permit_unconventional_http_version", True))
        cfg = self.worker(self.fx.make(auth=None)).cfg
        logger = self.worker(self.fx.make(auth=None)).log
        for name, value in invalid:
            original = cfg.settings[name].value
            cfg.set(name, value)
            try:
                with patch.object(Worker, "__init__") as init:
                    with self.assertRaises(StagingBoundaryConfigurationError):
                        StagingCanonicalWorker(1, 1, [], None, 1, cfg, logger)
                    init.assert_not_called()
            finally:
                cfg.settings[name].value = original

    def test_policy_mutation_fails_closed_before_parser_and_stops_worker(self):
        app = self.fx.make(auth=None)
        worker = self.worker(app)
        worker.cfg.set("header_map", "drop")
        client = base.MemorySocket(self.request("/healthz", headers=(("X_HIDDEN", "private"),)))
        with patch("gunicorn.http.get_parser") as parser, patch.object(worker, "wsgi") as wsgi, \
                patch("gunicorn.workers.sync.sock.ssl_wrap_socket") as tls:
            worker.handle(base.MemorySocket(), client, ("127.0.0.1", 12345))
        parser.assert_not_called()
        wsgi.assert_not_called()
        tls.assert_not_called()
        self.assertFalse(worker.alive)
        self.assertTrue(client.closed)
        self.assertEqual(bytes(client.outgoing), b"")
        self.assertEqual(client.incoming.tell(), 0)

    def test_path_mutating_hooks_and_script_name_are_not_silently_trusted(self):
        worker = self.worker(self.fx.make(auth=None))
        def pre(worker, req):
            req.path = "/auth/google/start"
        def post(worker, req, environ, response):
            pass
        for name, value in (("pre_request", pre), ("post_request", post), ("raw_env", ["SCRIPT_NAME=/prefix"])):
            original = worker.cfg.settings[name].value
            worker.cfg.set(name, value)
            try:
                with self.assertRaises(StagingBoundaryConfigurationError):
                    StagingCanonicalWorker(1, 1, [], None, 1, worker.cfg, worker.log)
            finally:
                worker.cfg.settings[name].value = original
        with patch.dict(os.environ, {"SCRIPT_NAME": "/prefix"}):
            with self.assertRaises(StagingBoundaryConfigurationError):
                StagingCanonicalWorker(1, 1, [], None, 1, worker.cfg, worker.log)

    def test_rejected_alias_does_not_exchange_or_consume_valid_flow(self):
        app = self.fx.make()
        flow, cookie = self.fx.start(app)
        query = base.urlencode({"state": flow["state"], "code": "synthetic-code"})
        result = self.raw(app, self.request("/auth/google/%63allback", query=query, cookie=cookie))
        status, headers, body = self.decode(result["wire"])
        self.assertEqual(status, 400)
        self.assertFalse(any(k.lower() == "set-cookie" for k, v in headers))
        self.assertEqual(self.fx.sent, [])
        # Rejection before WSGI intentionally leaves the bounded original flow
        # pending. A canonical retry may still complete once before its expiry.
        self.fx.queue(flow)
        self.assertEqual(self.fx.callback(app, flow, cookie)[0], 303)
        self.assertEqual(self.fx.callback(app, flow, cookie)[0], 401)

    def test_original_error_abort_and_signal_methods_remain_inherited(self):
        self.assertIs(StagingCanonicalWorker.handle_error, StagingSyncWorker.handle_error)
        self.assertIs(StagingCanonicalWorker.handle_abort, Worker.handle_abort)
        self.assertIs(StagingCanonicalWorker.init_process, Worker.init_process)


POSITIVE_BASE = (
    "test_default_off_and_unauthenticated_contract", "test_signed_session_read_csrf_logout_cookie_flags",
    "test_wrong_owner_rejected_and_no_session_issued", "test_callback_replay_rejected",
    "test_expired_and_fresh_instance_session_rejected", "test_request_fragmentation_preserves_parser_and_session",
    "test_plain_http_and_forwarded_header_fail_closed", "test_duplicate_host_and_origin_and_framing_rejected",
    "test_transport_failure_is_app_redacted", "test_abort_after_headers_does_not_append_second_response",
    "test_trusted_forwarded_scheme_still_needs_approved_app_boundary",
)
NEW_TESTS = tuple(name for name in CanonicalBoundaryTests.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    suite = unittest.TestSuite(CanonicalBoundaryTests(name) for name in (*NEW_TESTS, *POSITIVE_BASE))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
