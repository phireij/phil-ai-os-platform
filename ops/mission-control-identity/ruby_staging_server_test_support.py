"""Original Gunicorn HTTP/WSGI path with memory-only byte transport.

No listener, socket, real TLS, Google request, credential, package installation,
Arbiter startup, or server run loop. TLS is an explicitly simulated test boundary.
"""
from __future__ import annotations
import hashlib
import http.client
import io
import json
import logging
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
# An explicit, already-materialized official source tree is required.
# This test helper never downloads or installs it and is not a server launcher.
SOURCE_INPUT = os.environ.get("RUBY_STAGING_TEST_GUNICORN_SOURCE")
if not SOURCE_INPUT:
    raise RuntimeError("pinned_gunicorn_source_required")
SOURCE = Path(SOURCE_INPUT).resolve(strict=True)
DENIED = []
OBSERVATIONS = []
PHASE = "imports"


def audit(event, args):
    if event.startswith("socket.") and event != "socket.gethostname":
        frame = sys._getframe(1)
        frames = []
        while frame:
            frames.append((frame.f_code.co_filename, frame.f_code.co_name))
            frame = frame.f_back
        DENIED.append({"event": event, "phase": PHASE,
                       "urllib3_import_capability_probe": any(name == "_has_ipv6" and
                           path.endswith("urllib3/util/connection.py") for path, name in frames)})
        raise RuntimeError("offline HTTP evaluation forbids " + event)
    if event in {"os.system", "os.exec", "os.posix_spawn", "subprocess.Popen"}:
        DENIED.append(event)
        raise RuntimeError("offline HTTP evaluation forbids " + event)


sys.addaudithook(audit)
os.environ.clear()
sys.dont_write_bytecode = True
manifest = json.loads((ROOT / "ruby_staging_gunicorn_source.json").read_text())
if manifest["commit"] != "8d98faa9a13d3399a7bea81b5169e5cd72225395":
    raise RuntimeError("unreviewed_gunicorn_source_pin")
# Reject extras as well as changed/missing files, before inserting this tree in
# sys.path. Otherwise an added top-level module could shadow a trusted import.
actual = set()
for file in SOURCE.rglob("*"):
    relative = file.relative_to(SOURCE)
    if relative.parts[0] == ".git":
        continue
    if file.is_symlink():
        raise RuntimeError("gunicorn_source_symlink")
    if file.is_file():
        actual.add(relative.as_posix())
if actual != set(manifest["files"]):
    raise RuntimeError("gunicorn_source_file_set_mismatch")
for name, digest in manifest["files"].items():
    if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != digest:
        raise RuntimeError("gunicorn_source_hash_mismatch")
sys.path[:0] = [str(SOURCE), str(ROOT)]

import gunicorn
from gunicorn.config import Config
from gunicorn.glogging import Logger
from gunicorn.workers.sync import SyncWorker
import test_ruby_staging_http_app as fixtures
from ruby_staging_http_app import StagingHTTPApplication
from ruby_staging_lifecycle import SESSION_COOKIE
import requests
PHASE = "tests"


class MemorySocket:
    """Duck-typed inert bytes object; never derives from or creates a socket."""
    def __init__(self, request=b"", *, fragment=8192):
        self.incoming = io.BytesIO(request)
        self.outgoing = bytearray()
        self.timeout = None
        self.closed = False
        self.fragment = fragment
        self.shutdowns = []

    def recv(self, size):
        return self.incoming.read(min(size, self.fragment))

    def sendall(self, data):
        assert not self.closed
        self.outgoing.extend(data)

    def send(self, data):
        self.sendall(data)
        return len(data)

    def shutdown(self, how):
        self.shutdowns.append(how)

    def settimeout(self, value):
        self.timeout = value

    def gettimeout(self):
        return self.timeout

    def setblocking(self, value):
        self.timeout = None if value else 0

    def getsockname(self):
        return ("127.0.0.1", 443)

    def close(self):
        self.closed = True


class Records(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))


class ResponseFile:
    def __init__(self, data):
        self.data = data

    def makefile(self, *args, **kwargs):
        return io.BytesIO(self.data)


class HTTPBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.HTTPApplicationTests.setUpClass()

    def setUp(self):
        self.fx = fixtures.HTTPApplicationTests("test_default_off_is_inactive_without_session_construction")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        # Existing cryptographic fixture helpers now travel through the real
        # Gunicorn handler instead of invoking WSGI directly.
        self.fx.call = self.call
        self.tmp = tempfile.TemporaryDirectory(prefix="http-boundary-")
        self.addCleanup(self.tmp.cleanup)
        self.workers = {}
        self.exchanges = []
        self.records = Records()
        self.addCleanup(self.assert_no_network)

    def assert_no_network(self):
        # urllib3 probes IPv6 at import. The audit guard rejects construction
        # before any socket/bind occurs; do not hide or permit that attempt.
        self.assertEqual(DENIED, [{"event": "socket.__new__", "phase": "imports",
                                 "urllib3_import_capability_probe": True}])

    def worker(self, app, *, tls=True, options=None):
        key = (id(app), tls, tuple(sorted((options or {}).items())))
        if key in self.workers:
            return self.workers[key]
        cfg = Config()
        settings = dict(workers=1, threads=1, worker_class="sync", http_parser="python",
                control_socket_disable=True, preload_app=False, reload=False, max_requests=0,
                bind=[], reuse_port=False, dirty_apps=[], dirty_workers=0,
                forwarded_allow_ips="", proxy_allow_ips="", forwarder_headers="",
                certfile="synthetic-no-file-no-tls" if tls else None,
                worker_tmp_dir=self.tmp.name, accesslog=None, errorlog="-", loglevel="debug")
        settings.update(options or {})
        for name, value in settings.items():
            cfg.set(name, value)
        cfg.validate()
        log = Logger(cfg)
        log.error_log.addHandler(self.records)
        self.addCleanup(log.error_log.removeHandler, self.records)
        wrapped = SimpleNamespace(cfg=cfg, wsgi=lambda: app)
        worker = SyncWorker(1, os.getpid(), [], wrapped, 1, cfg, log)
        self.addCleanup(worker.tmp.close)
        worker.load_wsgi()
        self.workers[key] = worker
        return worker

    def raw(self, app, request, *, tls=True, options=None, fragment=8192):
        worker = self.worker(app, tls=tls, options=options)
        client = MemorySocket(request, fragment=fragment)
        listener = MemorySocket()
        before = len(self.records.records)
        with patch("gunicorn.workers.sync.sock.ssl_wrap_socket", side_effect=lambda c, cfg: c) as simulated_tls:
            # Use the actual parser/handler with the explicitly selected opt-in adapters.
            worker.handle(listener, client, ("127.0.0.1", 12345))
            self.assertEqual(simulated_tls.call_count, int(tls))
        self.assertTrue(client.closed)
        result = {"wire": bytes(client.outgoing), "logs": self.records.records[before:],
                  "worker_alive": worker.alive, "simulated_tls": tls}
        self.exchanges.append(result)
        return result

    def request(self, path="/", *, method="GET", query="", cookie="", body=b"", headers=()):
        target = path + ("?" + query if query else "")
        lines = [f"{method} {target} HTTP/1.1", "Host: " + fixtures.ORIGIN[8:]]
        if cookie:
            lines.append("Cookie: " + cookie)
        if method == "POST":
            lines.append("Content-Length: " + str(len(body)))
        lines.extend(k + ": " + v for k, v in headers)
        return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body

    def decode(self, data):
        response = http.client.HTTPResponse(ResponseFile(data))
        response.begin()
        return response.status, response.getheaders(), response.read()

    def call(self, app, path="/", method="GET", query="", cookie="", body=b"", **environ):
        headers = []
        for key, value in environ.items():
            self.assertTrue(key.startswith("HTTP_"), key)
            headers.append((key[5:].replace("_", "-"), value))
        result = self.raw(app, self.request(path, method=method, query=query, cookie=cookie, body=body, headers=headers))
        return self.decode(result["wire"])

    def test_default_off_and_unauthenticated_contract(self):
        status, _, body = self.call(StagingHTTPApplication())
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["authority"], "none")
        app = self.fx.make()
        self.assertEqual(self.call(app, "/api/session")[0], 401)
        self.assertEqual(self.fx.sent, [])

    def test_signed_session_read_csrf_logout_cookie_flags(self):
        app = self.fx.make()
        session, flow, _, headers = self.fx.login(app)
        for key, value in headers:
            if key.lower() == "set-cookie":
                for flag in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
                    self.assertIn(flag, value)
        status, _, body = self.call(app, "/api/ruby-review-synthetic", cookie=session)
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["authority"], "none")
        self.assertFalse(payload["execution_authorized"])
        self.assertFalse(payload["mutation_authorized"])
        status, _, body = self.call(app, "/api/session", cookie=session)
        self.assertEqual(status, 200)
        csrf = json.loads(body)["csrf_token"]
        self.assertEqual(self.call(app, "/auth/logout", method="POST", cookie=session,
                                  HTTP_ORIGIN=fixtures.ORIGIN, HTTP_X_CSRF_TOKEN="bad")[0], 401)
        self.assertEqual(self.call(app, "/auth/logout", method="POST", cookie=session,
                                  HTTP_ORIGIN=fixtures.ORIGIN, HTTP_X_CSRF_TOKEN=csrf)[0], 200)
        self.assertEqual(self.call(app, "/api/session", cookie=session)[0], 401)
        for exchange in self.exchanges:
            self.assertNotIn("synthetic-code", "\n".join(exchange["logs"]))

    def test_wrong_owner_rejected_and_no_session_issued(self):
        app = self.fx.make()
        flow, cookie = self.fx.start(app)
        self.fx.queue(flow, sub="synthetic-wrong-owner")
        status, headers, body = self.fx.callback(app, flow, cookie)
        self.assertEqual(status, 401)
        self.assertFalse(any(k.lower() == "set-cookie" and v.startswith(SESSION_COOKIE + "=") for k, v in headers))
        self.assertEqual(self.call(app, "/api/session")[0], 401)

    def test_callback_replay_rejected(self):
        app = self.fx.make()
        session, flow, cookie, _ = self.fx.login(app)
        self.assertEqual(self.fx.callback(app, flow, cookie)[0], 401)
        self.assertEqual(self.call(app, "/api/session", cookie=session)[0], 200)

    def test_expired_and_fresh_instance_session_rejected(self):
        app = self.fx.make()
        session, _, _, _ = self.fx.login(app)
        self.assertEqual(self.call(self.fx.make(), "/api/session", cookie=session)[0], 401)
        self.fx.mono += fixtures.CONFIG.idle_seconds + 1
        self.assertEqual(self.call(app, "/api/session", cookie=session)[0], 401)

    def test_request_fragmentation_preserves_parser_and_session(self):
        app = self.fx.make()
        session, _, _, _ = self.fx.login(app)
        result = self.raw(app, self.request("/api/session", cookie=session), fragment=1)
        self.assertEqual(self.decode(result["wire"])[0], 200)

    def test_plain_http_and_forwarded_header_fail_closed(self):
        app = self.fx.make()
        for headers in ((), (("X-Forwarded-Proto", "https"),)):
            result = self.raw(app, self.request("/auth/google/start", headers=headers), tls=False)
            self.assertEqual(self.decode(result["wire"])[0], 400)
        self.assertEqual(self.fx.sent, [])

    def test_trusted_forwarded_scheme_still_needs_approved_app_boundary(self):
        app = self.fx.make()
        result = self.raw(app, self.request("/auth/google/start", headers=(("X-Forwarded-Proto", "https"),)),
                          tls=False, options={"forwarded_allow_ips": "127.0.0.1"})
        self.assertEqual(self.decode(result["wire"])[0], 400)
        self.assertEqual(self.fx.sent, [])
        OBSERVATIONS.append({"finding": "trusted_scheme_header_remains_HTTP_header_and_app_rejects",
                             "release_gate": True, "scope": "hypothetical isolated parser config, not a host trust choice"})

    def test_duplicate_host_and_origin_and_framing_rejected(self):
        app = self.fx.make()
        probes = [
            self.request("/auth/google/start", headers=(("Host", "evil.test"),)),
            self.request("/auth/google/start", headers=(("Origin", fixtures.ORIGIN), ("Origin", fixtures.ORIGIN))),
            self.request("/auth/logout", method="POST", headers=(("Content-Length", "0"),)),
            self.request("/auth/logout", method="POST", headers=(("Transfer-Encoding", "chunked"),)),
        ]
        for wire in probes:
            with self.subTest(wire=wire):
                self.assertEqual(self.decode(self.raw(app, wire)["wire"])[0], 400)
        self.assertEqual(self.fx.sent, [])

    def test_transport_failure_is_app_redacted(self):
        app = self.fx.make()
        flow, cookie = self.fx.start(app)
        self.fx.replies.append(requests.ConnectionError("SYNTHETIC_TRANSPORT_SECRET"))
        status, _, body = self.fx.callback(app, flow, cookie)
        self.assertEqual(status, 401)
        self.assertNotIn(b"SYNTHETIC_TRANSPORT_SECRET", body)
        self.assertNotIn("SYNTHETIC_TRANSPORT_SECRET", "\n".join(self.records.records))

    def test_raw_path_alias_observations_are_not_ingress_acceptance(self):
        app = self.fx.make()
        aliases = ["/auth/google/%73tart", "/auth%2Fgoogle%2Fstart", "/auth/google/start#fragment",
                   "https://other.invalid/auth/google/start"]
        statuses = {}
        for target in aliases:
            statuses[target] = self.decode(self.raw(app, self.request(target))["wire"])[0]
        # Pin the observed missing raw-target enforcement rather than disguise it
        # as secure canonical routing. This must remain an explicit release gate.
        self.assertEqual(set(statuses.values()), {303})
        OBSERVATIONS.append({"finding": "raw_target_aliases_reach_start_route", "statuses": statuses,
                             "release_gate": True})

    def test_dropped_underscore_header_is_not_raw_header_rejection(self):
        app = self.fx.make(auth=None)
        wire = self.request("/healthz", headers=(("X_UNTRUSTED_HEADER", "synthetic"),))
        self.assertEqual(self.decode(self.raw(app, wire)["wire"])[0], 200)
        self.assertEqual(self.decode(self.raw(app, wire, options={"header_map": "refuse"})["wire"])[0], 400)
        OBSERVATIONS.append({"finding": "default_header_map_drops_underscore_headers_before_app", "release_gate": True,
                             "strict_parser_setting_probe": "refuse rejects; no hosting setting chosen"})

    def test_connection_header_compatibility_requires_transport_contract(self):
        app = self.fx.make(auth=None)
        result = self.raw(app, self.request("/healthz", headers=(("Connection", "keep-alive"),)))
        self.assertEqual(self.decode(result["wire"])[0], 400)
        OBSERVATIONS.append({"finding": "connection_header_reaches_strict_app_and_rejects", "release_gate": True})

    def test_ordinary_exception_logs_query_but_does_not_stop_worker(self):
        marker = "SYNTHETIC_QUERY_MUST_NOT_BE_LOGGED"
        def broken(environ, start_response):
            raise ValueError("synthetic failure")
        result = self.raw(broken, self.request("/auth/google/callback", query="code=" + marker))
        self.assertEqual(self.decode(result["wire"])[0], 500)
        self.assertTrue(result["worker_alive"])
        self.assertIn(marker, "\n".join(result["logs"]))
        self.assertNotIn(marker.encode(), result["wire"])
        OBSERVATIONS.append({"finding": "upstream_error_logger_includes_callback_query", "release_gate": True})

    def test_parser_error_echoes_raw_target_without_app_security_headers(self):
        marker = "SYNTHETIC_PARSER_CODE"
        app = self.fx.make()
        wire = ("GET /auth/google/callback?code=" + marker + "\r\nHost: " +
                fixtures.ORIGIN[8:] + "\r\n\r\n").encode()
        result = self.raw(app, wire)
        status, headers, body = self.decode(result["wire"])
        self.assertEqual(status, 400)
        self.assertIn(marker.encode(), body)
        self.assertIn(marker, "\n".join(result["logs"]))
        lower = {k.lower(): v for k, v in headers}
        self.assertNotIn("cache-control", lower)
        self.assertNotIn("referrer-policy", lower)
        self.assertEqual(self.fx.sent, [])
        OBSERVATIONS.append({"finding": "parser_error_echoes_raw_target_and_lacks_app_security_headers", "release_gate": True})

    def test_real_abort_handler_before_headers_sets_dead_and_error_response(self):
        holder = {}
        def aborted(environ, start_response):
            holder["worker"].handle_abort(signal.SIGABRT, None)
        worker = self.worker(aborted)
        holder["worker"] = worker
        result = self.raw(aborted, self.request("/auth/google/callback", query="code=SYNTHETIC_ABORT_CODE"))
        self.assertEqual(self.decode(result["wire"])[0], 500)
        self.assertFalse(worker.alive)
        self.assertIn("SYNTHETIC_ABORT_CODE", "\n".join(result["logs"]))
        OBSERVATIONS.append({"finding": "abort_systemexit_caught_by_handle_before_headers", "alive_after": False,
                             "http_status": 500, "os_signal_delivery_in_this_test": False})

    def test_abort_after_headers_does_not_append_second_response(self):
        holder = {}
        def streaming(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain"), ("Content-Length", "100")])
            yield b"partial"
            holder["worker"].handle_abort(signal.SIGABRT, None)
        worker = self.worker(streaming)
        holder["worker"] = worker
        result = self.raw(streaming, self.request("/synthetic-stream"))
        self.assertFalse(worker.alive)
        self.assertEqual(result["wire"].count(b"HTTP/1.1"), 1)
        self.assertTrue(result["wire"].startswith(b"HTTP/1.1 200 OK"))
        self.assertNotIn(b"500 Internal", result["wire"])
        with self.assertRaises(http.client.IncompleteRead):
            self.decode(result["wire"])
