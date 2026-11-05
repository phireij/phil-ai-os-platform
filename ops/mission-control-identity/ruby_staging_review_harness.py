"""Offline, in-process integration of Ruby fixtures and lifecycle primitives.

NOT an HTTP service or deployable authentication adapter.
The unsigned helper consumes caller-supplied SYNTHETIC owner/nonce values.
The signed helper verifies a synthetic token against server-supplied keys.
The offline code helper exercises exchange/cache protocol with an in-memory
cassette and public synthetic credential placeholder. None establishes real
Google key provenance or identity. Every response remains authority="none".
There is no login route, network, existing storage path, runtime activation,
provider operation or production identity import. Future real integration needs
the approved Google stack, verified owner binding and independent runtime review.
"""

from __future__ import annotations

import hmac
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from ruby_staging_lifecycle import (
    FLOW_COOKIE, SESSION_COOKIE, FlowStart, LifecycleError,
    LoginFlowStore, SessionStore, read_cookie, serialize_cookie,
)
from ruby_staging_rehearsal import (
    FIXTURE_OPT_IN, DisposableStagingRehearsal, StagingRehearsalProfile,
)


INTEGRATION_OPT_IN = "ruby-staging-in-process-review-fixtures-v1"
_RECORDS = "/api/ruby-review-synthetic/records"
_SESSION = "/auth/fixture/session"
_LOGOUT = "/auth/fixture/logout"
_HEADERS = frozenset({"host", "origin", "cookie", "x-csrf-token", "accept", "content-type"})


class FixtureIntegrationError(ValueError):
    """Fixed, non-secret integration failure."""


@dataclass(frozen=True)
class FixtureResponse:
    status: int
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    body: bytes = field(repr=False)


@dataclass(frozen=True)
class FixtureLoginStart:
    flow: FlowStart = field(repr=False)
    flow_cookie: str = field(repr=False)
    synthetic: bool = True
    authority: str = "none"


def _response(status: int, data: dict | None = None,
              cookies: tuple[str, ...] = ()) -> FixtureResponse:
    # These labels cannot be overridden by a transport payload or test caller.
    payload = dict(data or {})
    payload.update(synthetic=True, authority="none", execution_authorized=False,
                   mutation_authorized=False, real_identity_verified=False)
    headers = (
        ("Content-Type", "application/json; charset=utf-8"),
        ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
        ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
    ) + tuple(("Set-Cookie", cookie) for cookie in cookies)
    return FixtureResponse(status, headers, json.dumps(payload, separators=(",", ":")).encode("utf-8"))


class StagingReviewHarness:
    """Owned disposable fixtures, never an authorization boundary for real data.

    A single lock orders fixture reads, logout and close. Session lookup and the
    protected in-process read are inside that lock. This is NOT a guarantee for
    an eventual multiprocess service or already in-flight external operations.
    Constructor durations/capacity are required, with no production defaults.
    A supplied offline exchange and its cassette are exclusively owned by this
    harness after construction; do not share them across harness instances.
    """

    def __init__(self, profile: StagingRehearsalProfile, *, opt_in: str,
                 flow_seconds: int, idle_seconds: int, absolute_seconds: int,
                 capacity: int, enabled: bool = False,
                 clock: Callable[[], float] = time.monotonic,
                 token_verifier: object | None = None,
                 offline_exchange: object | None = None) -> None:
        if enabled is not True or opt_in != INTEGRATION_OPT_IN:
            raise FixtureIntegrationError("integration_inactive")
        if type(profile) is not StagingRehearsalProfile:
            raise FixtureIntegrationError("profile_invalid")
        profile.validate()
        if token_verifier is not None:
            from ruby_staging_id_token import StagingIdTokenVerifier
            if type(token_verifier) is not StagingIdTokenVerifier:
                raise FixtureIntegrationError("token_verifier_invalid")
        if offline_exchange is not None:
            from ruby_staging_google_exchange import OfflineGoogleCodeExchange
            if type(offline_exchange) is not OfflineGoogleCodeExchange or not offline_exchange.matches_profile(profile):
                raise FixtureIntegrationError("offline_exchange_invalid")
        self._profile = profile
        self._token_verifier = token_verifier
        self._offline_exchange = offline_exchange
        self._lock = threading.RLock()
        self._closed = False
        self._flows = LoginFlowStore(enabled=True, ttl_seconds=flow_seconds,
                                     capacity=capacity, clock=clock)
        self._sessions = SessionStore(enabled=True, idle_seconds=idle_seconds,
                                      absolute_seconds=absolute_seconds,
                                      capacity=capacity, clock=clock)
        try:
            self._fixture = DisposableStagingRehearsal(profile, opt_in=FIXTURE_OPT_IN)
        except Exception:
            self._flows.close()
            self._sessions.close()
            raise

    def _require_open(self) -> None:
        if self._closed:
            raise FixtureIntegrationError("integration_closed")

    def _headers(self, headers: tuple[tuple[str, str], ...]) -> dict[str, list[str]]:
        if type(headers) is not tuple or len(headers) > 32:
            raise FixtureIntegrationError("headers_invalid")
        total = 0
        parsed: dict[str, list[str]] = {}
        for pair in headers:
            if type(pair) is not tuple or len(pair) != 2 or any(type(v) is not str for v in pair):
                raise FixtureIntegrationError("headers_invalid")
            name, value = pair
            total += len(name) + len(value)
            if total > 8192 or not re.fullmatch(r"[A-Za-z-]+", name):
                raise FixtureIntegrationError("headers_invalid")
            if any(ord(char) < 32 or ord(char) > 126 for char in value):
                raise FixtureIntegrationError("headers_invalid")
            name = name.lower()
            if name not in _HEADERS:
                raise FixtureIntegrationError("headers_invalid")
            parsed.setdefault(name, []).append(value)
        if any(len(values) != 1 for name, values in parsed.items() if name != "cookie"):
            raise FixtureIntegrationError("headers_invalid")
        if parsed.get("host") != [self._profile.origin.removeprefix("https://")]:
            raise FixtureIntegrationError("host_invalid")
        if "origin" in parsed and parsed["origin"] != [self._profile.origin]:
            raise FixtureIntegrationError("origin_invalid")
        return parsed

    def start_login_fixture(self) -> FixtureLoginStart:
        """Test-driver operation only; no corresponding request/login route."""
        with self._lock:
            self._require_open()
            # Re-check the prior rehearsal's ambient-configuration barrier.
            self._fixture.fixture_binding
            flow = self._flows.start()
            return FixtureLoginStart(flow, serialize_cookie(FLOW_COOKIE, flow.browser_token))

    def complete_login_fixture(self, *, state: object, nonce_fixture: object,
                               owner_fixture: object,
                               headers: tuple[tuple[str, str], ...]) -> FixtureResponse:
        """Simulate the verified-owner step ONLY for disposable fixtures.

        Supplying the right owner/nonce here is not evidence of a Google login.
        No raw claims/JWT/authorization code or arbitrary verifier is accepted.
        This method must never be exposed as an HTTP or other external operation.
        """
        with self._lock:
            self._require_open()
            clear = serialize_cookie(FLOW_COOKIE)
            try:
                parsed = self._headers(headers)
            except FixtureIntegrationError:
                # Consume a matching pending state even on malformed headers.
                self._flows.take(state, None)
                return _response(400, {"error": "fixture_login_invalid"}, (clear,))
            browser = read_cookie(parsed.get("cookie", []), FLOW_COOKIE)
            exchange = self._flows.take(state, browser)
            valid = (exchange is not None and type(owner_fixture) is str
                     and type(nonce_fixture) is str and owner_fixture.isascii()
                     and nonce_fixture.isascii()
                     and len(owner_fixture) <= 255 and len(nonce_fixture) == 64
                     and hmac.compare_digest(owner_fixture, self._profile.owner_subject)
                     and hmac.compare_digest(nonce_fixture, exchange.nonce))
            if not valid:
                return _response(401, {"error": "fixture_login_invalid"}, (clear,))
            return self._issue_fixture_session(parsed, signature_verified=False)

    def complete_signed_login_fixture(self, *, state: object, id_token_fixture: object,
                                      headers: tuple[tuple[str, str], ...]) -> FixtureResponse:
        """Test signed-token + one-use-flow composition, not a real sign-in.

        The test driver cannot supply an expected nonce or override the verifier.
        The nonce comes only from the consumed browser-bound flow; trusted public
        keys/policy come from explicit server-side construction. There is still no
        code exchange, PKCE exchange proof or Google key provenance in this harness.
        """
        with self._lock:
            self._require_open()
            clear = serialize_cookie(FLOW_COOKIE)
            try:
                parsed = self._headers(headers)
            except FixtureIntegrationError:
                self._flows.take(state, None)
                return _response(400, {"error": "fixture_login_invalid"}, (clear,))
            browser = read_cookie(parsed.get("cookie", []), FLOW_COOKIE)
            exchange = self._flows.take(state, browser)
            if exchange is None:
                return _response(401, {"error": "fixture_login_invalid"}, (clear,))
            if self._token_verifier is None:
                return _response(503, {"error": "signed_fixture_verifier_unavailable"}, (clear,))
            from ruby_staging_id_token import TokenRejected
            try:
                claims = self._token_verifier.verify(id_token_fixture, expected_nonce=exchange.nonce)
            except TokenRejected:
                return _response(401, {"error": "fixture_login_invalid"}, (clear,))
            # A verifier configured for a different staging policy cannot issue
            # sessions for this harness, even if its own token verification passes.
            if (claims.issuer != self._profile.issuer or claims.audience != self._profile.client_id
                    or not hmac.compare_digest(claims.subject, self._profile.owner_subject)):
                return _response(401, {"error": "fixture_login_invalid"}, (clear,))
            return self._issue_fixture_session(parsed, signature_verified=True)

    def complete_code_login_fixture(self, *, state: object, code_fixture: object,
                                    headers: tuple[tuple[str, str], ...]) -> FixtureResponse:
        """Exercise code/PKCE/key-cache composition, without a network adapter.

        There is no request route for this test-driver method. It cannot accept
        nonce, PKCE verifier, credentials, endpoints or a transport from a request.
        The single-use browser-bound flow is consumed before any offline exchange.
        """
        with self._lock:
            self._require_open()
            clear = serialize_cookie(FLOW_COOKIE)
            try:
                parsed = self._headers(headers)
            except FixtureIntegrationError:
                self._flows.take(state, None)
                return _response(400, {"error": "fixture_login_invalid"}, (clear,))
            exchange = self._flows.take(state, read_cookie(parsed.get("cookie", []), FLOW_COOKIE))
            if exchange is None:
                return _response(401, {"error": "fixture_login_invalid"}, (clear,))
            if self._offline_exchange is None:
                return _response(503, {"error": "offline_fixture_exchange_unavailable"}, (clear,))
            from ruby_staging_google_exchange import OfflineExchangeRejected
            try:
                claims = self._offline_exchange.exchange_fixture(code_fixture=code_fixture, flow=exchange)
            except OfflineExchangeRejected:
                return _response(401, {"error": "fixture_login_invalid"}, (clear,))
            if (claims.issuer != self._profile.issuer or claims.audience != self._profile.client_id
                    or not hmac.compare_digest(claims.subject, self._profile.owner_subject)):
                return _response(401, {"error": "fixture_login_invalid"}, (clear,))
            return self._issue_fixture_session(parsed, signature_verified=True)

    def _issue_fixture_session(self, parsed: dict[str, list[str]], *, signature_verified: bool) -> FixtureResponse:
        """Private, locked fixture completion; never an external operation."""
        clear = serialize_cookie(FLOW_COOKIE)
        self._fixture.fixture_binding
        previous = read_cookie(parsed.get("cookie", []), SESSION_COOKIE)
        session_named = any(
            part.strip().partition("=")[0].strip() == SESSION_COOKIE
            for value in parsed.get("cookie", []) for part in value.split(";")
        )
        if session_named and previous is None:
            return _response(401, {"error": "fixture_login_invalid"}, (clear,))
        try:
            receipt = self._sessions.issue(previous_token=previous)
        except LifecycleError:
            return _response(401, {"error": "fixture_login_invalid"}, (clear,))
        return _response(200, {"fixture_session": True, "csrf_token": receipt.csrf_token,
                              "synthetic_token_signature_verified": signature_verified},
                         (clear, serialize_cookie(SESSION_COOKIE, receipt.token)))

    def dispatch(self, *, method: str, path: str,
                 headers: tuple[tuple[str, str], ...], body: bytes = b"") -> FixtureResponse:
        """In-memory request simulation; deliberately no socket/server adapter."""
        with self._lock:
            self._require_open()
            try:
                parsed = self._headers(headers)
            except FixtureIntegrationError:
                return _response(400, {"error": "request_invalid"})
            if type(path) is not str or len(path) > 512 or not path.isascii() or "?" in path or "#" in path:
                return _response(400, {"error": "request_invalid"})
            if type(body) is not bytes or body:
                return _response(400, {"error": "request_invalid"})
            if method not in ("GET", "POST"):
                return _response(405, {"error": "method_not_allowed"})
            if method == "POST" and path != _LOGOUT:
                return _response(405, {"error": "method_not_allowed"})
            if path == _LOGOUT and method != "POST":
                return _response(405, {"error": "method_not_allowed"})
            is_read = path in (_RECORDS, _SESSION) or re.fullmatch(
                re.escape(_RECORDS) + r"/[A-Za-z0-9_-]{16,200}(?:/audit)?", path)
            if path != _LOGOUT and not is_read:
                return _response(404, {"error": "not_found"})
            if method == "POST" and parsed.get("origin") != [self._profile.origin]:
                return _response(403, {"error": "request_denied"})
            token = read_cookie(parsed.get("cookie", []), SESSION_COOKIE)
            csrf = parsed.get("x-csrf-token", [None])[0]
            try:
                session = self._sessions.lookup(token, require_csrf=(method == "POST"), csrf_token=csrf)
            except LifecycleError:
                session = None
            if session is None:
                return _response(401, {"error": "fixture_session_required"})
            if path == _LOGOUT:
                self._sessions.revoke(token)
                return _response(200, {"fixture_session": False}, (serialize_cookie(SESSION_COOKIE),))
            binding = self._fixture.fixture_binding
            if path == _SESSION:
                return _response(200, {"fixture_session": True})
            try:
                if path == _RECORDS:
                    payload = binding.list_records()
                elif path.endswith("/audit"):
                    payload = binding.list_audit(path.split("/")[-2])
                else:
                    payload = binding.get_record(path.rsplit("/", 1)[-1])
            except Exception as error:
                # Only known fixture not-found is distinguished. Never expose
                # underlying storage paths, records, keys or exception details.
                status = 404 if getattr(error, "status", None) == 404 else 503
                return _response(status, {"error": "fixture_unavailable"})
            return _response(200, payload)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._flows.close()
            finally:
                try:
                    self._sessions.close()
                finally:
                    try:
                        if self._offline_exchange is not None:
                            self._offline_exchange.close()
                    finally:
                        self._fixture.close()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()
