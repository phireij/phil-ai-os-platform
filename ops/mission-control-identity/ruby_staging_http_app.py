"""Default-off staging WSGI application, with no listener or runtime loader.

This is the HTTP application boundary, not an externally exposed fixture driver.
Only the real, server-configured Google authenticator may complete a login. The
read-only payload is Core's fixed synthetic review surface; no customer store,
providers, notifications, exports or mutation routes are connected.

Deployment MUST supply a reviewed WSGI server that rejects duplicate Host/Origin,
ambiguous framing and noncanonical raw paths before normalization. Plain WSGI
cannot recover discarded duplicate headers. This app accepts direct HTTPS scheme
metadata only and rejects forwarded identity/proxy headers. TLS termination,
trusted-proxy translation, request deadlines, credential loading and serving
entrypoints are deliberately not configured here.
"""

from __future__ import annotations

import hmac
import base64
import hashlib
import html
import json
import math
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qsl, urlencode

from ruby_review_synthetic import ruby_review_synthetic_surface
from ruby_staging_google_auth import (
    StagingGoogleOwnerAuthenticator, AuthenticationRejected, valid_staging_policy,
)
from ruby_staging_id_token import ISSUER, PRODUCTION_CLIENT_ID, VerifiedOwnerClaims
from ruby_staging_lifecycle import (
    FLOW_COOKIE, SESSION_COOKIE, CodeExchangeInputs, LifecycleError, LoginFlowStore, SessionStore,
    read_cookie, serialize_cookie,
    validate_flow_policy, validate_session_policy,
)


AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
PRODUCTION_ORIGIN = "https://miscon.phireij.cloud"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{64}", re.ASCII)
_ALLOWED_HTTP = frozenset({"HTTP_HOST", "HTTP_ORIGIN", "HTTP_COOKIE", "HTTP_ACCEPT",
    "HTTP_ACCEPT_LANGUAGE", "HTTP_ACCEPT_ENCODING", "HTTP_USER_AGENT", "HTTP_REFERER",
    "HTTP_SEC_FETCH_SITE", "HTTP_SEC_FETCH_MODE", "HTTP_SEC_FETCH_DEST", "HTTP_SEC_FETCH_USER",
    "HTTP_SEC_CH_UA", "HTTP_SEC_CH_UA_MOBILE", "HTTP_SEC_CH_UA_PLATFORM", "HTTP_DNT",
    "HTTP_CACHE_CONTROL", "HTTP_PRAGMA", "HTTP_UPGRADE_INSECURE_REQUESTS", "HTTP_PRIORITY",
    "HTTP_X_CSRF_TOKEN", "HTTP_SEC_GPC"})
_CALLBACK_FIELDS = frozenset({"state", "code", "iss", "scope", "authuser", "prompt",
                              "error", "error_description", "error_uri"})
_STATUS = {200: "OK", 303: "See Other", 400: "Bad Request", 401: "Unauthorized",
           403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
           413: "Content Too Large", 429: "Too Many Requests", 503: "Service Unavailable"}
_LOGOUT_SCRIPT = """document.getElementById('sign-out').addEventListener('click',async function(){this.disabled=true;const status=document.getElementById('sign-out-status');try{const response=await fetch('/auth/logout',{method:'POST',credentials:'same-origin',redirect:'error',headers:{'X-CSRF-Token':document.getElementById('logout-csrf').value}});if(response.status===200){window.location.replace('/');return;}status.textContent='Sign out failed. Reload this page and try again.';}catch(error){status.textContent='Sign out failed. Reload this page and try again.';}this.disabled=false;});"""
_SCRIPT_HASH = base64.b64encode(hashlib.sha256(_LOGOUT_SCRIPT.encode("utf-8")).digest()).decode("ascii")


class StagingHTTPConfigurationError(ValueError):
    """Redacted, inactive configuration failure."""


class _RequestRejected(ValueError):
    pass


@dataclass(frozen=True)
class StagingRequestLimits:
    """Required source policy, not inferred host/proxy or runtime defaults.

    Global budgets intentionally do not trust a browser-supplied IP address.
    Ingress abuse controls and hard worker/network deadlines remain mandatory.
    """

    max_inflight_requests: int
    max_login_starts: int
    max_callback_attempts: int
    window_seconds: int

    def validate(self) -> None:
        for value, maximum in ((self.max_inflight_requests, 64), (self.max_login_starts, 1024),
                               (self.max_callback_attempts, 1024), (self.window_seconds, 3600)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise StagingHTTPConfigurationError("staging_http_configuration_invalid")


@dataclass(frozen=True)
class StagingHTTPConfig:
    origin: str
    client_id: str = field(repr=False)
    owner_subject: str = field(repr=False)
    flow_seconds: int
    idle_seconds: int
    absolute_seconds: int
    capacity: int

    @property
    def callback(self) -> str:
        return self.origin + "/auth/google/callback"

    def validate(self) -> None:
        if not valid_staging_policy(self.origin, self.client_id, self.owner_subject):
            raise StagingHTTPConfigurationError("staging_http_configuration_invalid")
        try:
            validate_flow_policy(self.flow_seconds, self.capacity)
            validate_session_policy(self.idle_seconds, self.absolute_seconds, self.capacity)
        except LifecycleError:
            raise StagingHTTPConfigurationError("staging_http_configuration_invalid") from None


@dataclass(frozen=True)
class _Reply:
    status: int
    body: bytes = field(repr=False)
    headers: tuple[tuple[str, str], ...] = field(repr=False)


@dataclass(frozen=True)
class _AuthenticationWork:
    code: str = field(repr=False)
    flow: CodeExchangeInputs = field(repr=False)
    previous: str | None = field(repr=False)
    generation: int


def _reply(status: int, data: dict | None = None, *, markup: str | None = None,
           location: str | None = None, cookies: tuple[str, ...] = ()) -> _Reply:
    if markup is None:
        payload = dict(data or {})
        payload.update(data_mode="synthetic", authority="none", execution_authorized=False,
                       mutation_authorized=False)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        kind = "application/json; charset=utf-8"
    else:
        body, kind = markup.encode("utf-8"), "text/html; charset=utf-8"
    headers = (("Content-Type", kind), ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"), ("Pragma", "no-cache"),
        ("Referrer-Policy", "no-referrer"), ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'; connect-src 'self'; script-src 'sha256-" + _SCRIPT_HASH + "'"),
        ("X-Frame-Options", "DENY"))
    if location is not None:
        headers += (("Location", location),)
    headers += tuple(("Set-Cookie", c) for c in cookies)
    return _Reply(status, body, headers)


def _query(raw: object, *, maximum: int = 8192) -> dict[str, str]:
    if (type(raw) is not str or len(raw) > maximum or not raw.isascii()
            or any(ord(c) < 33 or ord(c) > 126 for c in raw)
            or re.search(r"%(?![0-9a-fA-F]{2})", raw)):
        raise _RequestRejected
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True,
                          encoding="ascii", errors="strict", max_num_fields=16)
    except (ValueError, UnicodeError):
        raise _RequestRejected from None
    result = {}
    for key, value in pairs:
        if (key in result or not key or len(key) > 64 or len(value) > 4096
                or any(ord(c) < 32 or ord(c) > 126 for c in key + value)):
            raise _RequestRejected
        result[key] = value
    return result


class StagingHTTPApplication:
    """Single-process, in-memory application; default construction is inactive.

    Enabled successful construction transfers exclusive ownership of the authenticator
    to this application. Short state operations use a lock, but upstream HTTPS
    never holds it. Admission bounds concurrent application work; one nonblocking
    authentication slot avoids queuing for HTTPS. Admitted state operations still
    briefly serialize, with no owner-priority reservation. No body stream is read.
    Multiprocess/distributed state is not implemented.
    """

    def __init__(self, config: StagingHTTPConfig | None = None, *, enabled: bool = False,
                 authenticator: StagingGoogleOwnerAuthenticator | None = None,
                 limits: StagingRequestLimits | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._lock = threading.RLock()
        self._enabled = False
        self._closed = False
        self._config = None
        self._authenticator = None
        self._flows = None
        self._sessions = None
        self._clock = clock
        self._last_clock = None
        self._clock_failed = False
        self._limits = None
        self._admission = None
        self._auth_slot = threading.Lock()
        self._login_starts: deque[float] = deque()
        self._callback_attempts: deque[float] = deque()
        self._auth_generation = 0
        if enabled is False:
            return
        try:
            if (enabled is not True or type(config) is not StagingHTTPConfig
                    or type(limits) is not StagingRequestLimits):
                raise ValueError
            config.validate()
            limits.validate()
            self._now()
            if authenticator is not None and (type(authenticator) is not StagingGoogleOwnerAuthenticator
                    or not authenticator.matches_policy(origin=config.origin, client_id=config.client_id,
                                                        owner_subject=config.owner_subject)):
                raise ValueError
            flows = LoginFlowStore(enabled=True, ttl_seconds=config.flow_seconds,
                                   capacity=config.capacity, clock=self._now)
            try:
                sessions = SessionStore(enabled=True, idle_seconds=config.idle_seconds,
                    absolute_seconds=config.absolute_seconds, capacity=config.capacity, clock=self._now)
            except Exception:
                flows.close()
                raise
            self._config, self._authenticator = config, authenticator
            self._flows, self._sessions = flows, sessions
            self._limits = limits
            self._admission = threading.BoundedSemaphore(limits.max_inflight_requests)
            self._enabled = True
        except Exception:
            raise StagingHTTPConfigurationError("staging_http_configuration_invalid") from None

    def _now(self) -> float:
        # Flow and session stores share this high-water mark. Separate store
        # guards alone can miss rollback between a consumed flow and issuance.
        try:
            now = self._clock()
            if (self._closed or self._clock_failed or type(now) not in (int, float)
                    or not math.isfinite(now) or now < 0
                    or (self._last_clock is not None and now < self._last_clock)):
                raise ValueError
            self._last_clock = now
            return now
        except Exception:
            self._clock_failed = True
            raise LifecycleError("clock_invalid") from None

    def _rate_allowed(self, events: deque[float], maximum: int) -> bool:
        now = self._now()
        while events and now - events[0] >= self._limits.window_seconds:
            events.popleft()
        if len(events) >= maximum:
            return False
        events.append(now)
        return True

    def _request(self, environ: dict) -> tuple[str, str, str, str]:
        if type(environ) is not dict or len(environ) > 128:
            raise _RequestRejected
        # These required server fields describe the supported WSGI lifecycle.
        # Never infer single-process/persistent state from missing metadata.
        # They do not independently prove real topology or parser/proxy trust.
        version = environ.get("wsgi.version")
        if (type(version) is not tuple or len(version) != 2
                or any(type(part) is not int for part in version) or version != (1, 0)):
            raise _RequestRejected
        if (environ.get("wsgi.url_scheme") != "https" or environ.get("SCRIPT_NAME", "") != ""
                or type(environ.get("wsgi.multithread")) is not bool
                or environ.get("wsgi.multiprocess") is not False
                or environ.get("wsgi.run_once") is not False):
            raise _RequestRejected
        total = 0
        for name, value in environ.items():
            if type(name) is not str:
                raise _RequestRejected
            if name.startswith("HTTP_") or name in {"CONTENT_TYPE", "CONTENT_LENGTH"}:
                if name.startswith("HTTP_") and name not in _ALLOWED_HTTP:
                    raise _RequestRejected
                if type(value) is not str or any(ord(c) < 32 or ord(c) > 126 for c in value):
                    raise _RequestRejected
                total += len(name) + len(value)
        if total > 16384 or environ.get("HTTP_HOST") != self._config.origin.removeprefix("https://"):
            raise _RequestRejected
        # A browser's Global Privacy Control signal is neither identity nor
        # proxy metadata. Accept its standard value without granting authority.
        if "HTTP_SEC_GPC" in environ and environ["HTTP_SEC_GPC"] != "1":
            raise _RequestRejected
        if "HTTP_ORIGIN" in environ and environ["HTTP_ORIGIN"] != self._config.origin:
            raise _RequestRejected
        method, path, query = environ.get("REQUEST_METHOD"), environ.get("PATH_INFO"), environ.get("QUERY_STRING", "")
        if (type(method) is not str or type(path) is not str or len(path) > 256
                or not path.isascii() or not path.startswith("/") or any(c in path for c in "%?#\\")
                or type(query) is not str or len(query) > 8192):
            raise _RequestRejected
        fetch_site = environ.get("HTTP_SEC_FETCH_SITE")
        if fetch_site is not None and fetch_site not in {"same-origin", "same-site", "cross-site", "none"}:
            raise _RequestRejected
        # Google's callback redirect chain can retain cross-site fetch metadata
        # on its final top-level landing page. Permit that document navigation,
        # never cross-site API/subresource reads or writes.
        landing_navigation = (method == "GET" and path == "/"
            and environ.get("HTTP_SEC_FETCH_MODE") == "navigate"
            and environ.get("HTTP_SEC_FETCH_DEST") == "document")
        if (path not in {"/auth/google/start", "/auth/google/callback", "/healthz"}
                and fetch_site not in {None, "same-origin", "none"} and not landing_navigation):
            raise _RequestRejected
        cookie = environ.get("HTTP_COOKIE", "")
        if "," in cookie or len(cookie) > 8192:
            raise _RequestRejected
        return method, path, query, cookie

    def _consume_invalid_callback(self, raw: object) -> None:
        # Consume bounded recognizable states even when another query field or
        # header is malformed. Never exchange a code from this salvage path.
        if type(raw) is not str or len(raw) > 8192:
            return
        for part in raw.split("&")[:16]:
            try:
                values = _query(part)
            except _RequestRejected:
                continue
            state = values.get("state")
            if type(state) is str and _TOKEN.fullmatch(state):
                self._flows.take(state, None)

    @staticmethod
    def _session_cookie(cookie: str) -> tuple[str | None, bool]:
        token = read_cookie([cookie], SESSION_COOKIE)
        named = any(part.strip().partition("=")[0].strip() == SESSION_COOKIE for part in cookie.split(";"))
        return token, named and token is None

    def _callback(self, raw: str, cookie: str) -> _Reply | _AuthenticationWork:
        clear = (serialize_cookie(FLOW_COOKIE),)
        if not self._rate_allowed(self._callback_attempts, self._limits.max_callback_attempts):
            self._consume_invalid_callback(raw)
            return _reply(429, {"error": "login_rate_limited"}, cookies=clear)
        try:
            query = _query(raw)
        except _RequestRejected:
            self._consume_invalid_callback(raw)
            return _reply(400, {"error": "login_invalid"}, cookies=clear)
        state = query.get("state")
        flow = self._flows.take(state, read_cookie([cookie], FLOW_COOKIE))
        previous, bad_cookie = self._session_cookie(cookie)
        if (flow is None or bad_cookie or not set(query) <= _CALLBACK_FIELDS
                or "error" in query or "error_description" in query or "error_uri" in query
                or query.get("iss", ISSUER) != ISSUER or not query.get("code")):
            return _reply(401, {"error": "login_invalid"}, cookies=clear)
        if self._authenticator is None:
            return _reply(503, {"error": "authentication_unavailable"}, cookies=clear)
        return _AuthenticationWork(query["code"], flow, previous, self._auth_generation)

    def _complete_authentication(self, work: _AuthenticationWork) -> _Reply:
        clear = (serialize_cookie(FLOW_COOKIE),)
        if not self._auth_slot.acquire(blocking=False):
            return _reply(503, {"error": "authentication_busy"}, cookies=clear)
        authenticator = self._authenticator
        try:
            with self._lock:
                if self._closed or self._clock_failed or work.generation != self._auth_generation:
                    return _reply(503, {"error": "staging_inactive"}, cookies=clear)
            # No app state lock is held during DNS, TLS or provider response I/O.
            claims = authenticator.authenticate(code=work.code, flow=work.flow)
            with self._lock:
                if self._closed or self._clock_failed or work.generation != self._auth_generation:
                    return _reply(503, {"error": "staging_inactive"}, cookies=clear)
                if (type(claims) is not VerifiedOwnerClaims or claims.issuer != ISSUER
                        or claims.audience != self._config.client_id or claims.signature_verified is not True
                        or claims.owner_matches is not True or type(claims.subject) is not str
                        or not hmac.compare_digest(claims.subject, self._config.owner_subject)):
                    raise AuthenticationRejected("authentication_rejected")
                # Fresh verified sign-in can recover from an expired old cookie.
                live_previous = work.previous if work.previous is not None and self._sessions.lookup(work.previous) is not None else None
                receipt = self._sessions.issue(previous_token=live_previous)
                return _reply(303, {"authenticated": True}, location="/",
                              cookies=clear + (serialize_cookie(SESSION_COOKIE, receipt.token),))
        except (AuthenticationRejected, LifecycleError):
            return _reply(401, {"error": "login_invalid"}, cookies=clear)
        finally:
            with self._lock:
                closing = self._closed
                self._auth_slot.release()
            if closing:
                # close() revokes app state immediately without waiting for I/O;
                # the sole in-flight operation cleans backend resources on return.
                authenticator.close()

    def _dispatch(self, environ: dict) -> _Reply | _AuthenticationWork:
        if not self._enabled or self._closed:
            cookies = (serialize_cookie(FLOW_COOKIE),) if type(environ) is dict and environ.get("PATH_INFO") == "/auth/google/callback" else ()
            return _reply(503, {"error": "staging_inactive"}, cookies=cookies)
        try:
            method, path, raw, cookie = self._request(environ)
        except _RequestRejected:
            if type(environ) is dict and environ.get("PATH_INFO") == "/auth/google/callback":
                self._consume_invalid_callback(environ.get("QUERY_STRING"))
                return _reply(400, {"error": "request_invalid"}, cookies=(serialize_cookie(FLOW_COOKIE),))
            return _reply(400, {"error": "request_invalid"})
        if path == "/auth/google/callback" and method != "GET":
            self._consume_invalid_callback(raw)
            return _reply(405, {"error": "method_not_allowed"}, cookies=(serialize_cookie(FLOW_COOKIE),))
        if method not in {"GET", "POST"}:
            return _reply(405, {"error": "method_not_allowed"})
        if method == "GET" and (environ.get("CONTENT_LENGTH", "") not in {"", "0"}
                                or environ.get("CONTENT_TYPE", "") != ""):
            if path == "/auth/google/callback":
                self._consume_invalid_callback(raw)
                return _reply(400, {"error": "request_invalid"}, cookies=(serialize_cookie(FLOW_COOKIE),))
            return _reply(400, {"error": "request_invalid"})
        if path == "/auth/google/callback" and method == "GET":
            return self._callback(raw, cookie)
        if raw:
            return _reply(400, {"error": "request_invalid"})
        if method == "POST" and path != "/auth/logout":
            return _reply(405, {"error": "method_not_allowed"})
        if path == "/healthz" and method == "GET":
            return _reply(200, {"application": "ruby-staging", "authentication_configured": self._authenticator is not None,
                               "hosted_acceptance": "not_established"})
        if path == "/auth/google/start" and method == "GET":
            if not self._rate_allowed(self._login_starts, self._limits.max_login_starts):
                return _reply(429, {"error": "login_rate_limited"})
            if self._authenticator is None:
                return _reply(503, {"error": "authentication_unavailable"})
            flow = self._flows.start()
            location = AUTHORIZATION_URL + "?" + urlencode({"client_id": self._config.client_id,
                "redirect_uri": self._config.callback, "response_type": "code", "scope": "openid",
                "state": flow.state, "nonce": flow.nonce, "code_challenge": flow.code_challenge,
                "code_challenge_method": flow.code_challenge_method})
            return _reply(303, {"authentication_started": True}, location=location,
                          cookies=(serialize_cookie(FLOW_COOKIE, flow.browser_token),))
        token, bad_cookie = self._session_cookie(cookie)
        if bad_cookie:
            return _reply(401, {"error": "session_required"})
        if path == "/auth/logout":
            if method != "POST":
                return _reply(405, {"error": "method_not_allowed"})
            if (environ.get("HTTP_ORIGIN") != self._config.origin
                    or environ.get("CONTENT_TYPE", "") != ""):
                return _reply(403, {"error": "request_denied"})
            if environ.get("CONTENT_LENGTH", "") not in {"", "0"}:
                return _reply(400, {"error": "request_invalid"})
            if self._sessions.lookup(token, require_csrf=True, csrf_token=environ.get("HTTP_X_CSRF_TOKEN")) is None:
                return _reply(401, {"error": "session_required"})
            self._sessions.revoke(token)
            self._auth_generation += 1
            self._flows.revoke_all()
            return _reply(200, {"authenticated": False}, cookies=(serialize_cookie(SESSION_COOKIE),))
        if path not in {"/", "/api/session", "/api/ruby-review-synthetic"}:
            return _reply(404, {"error": "not_found"})
        session = self._sessions.lookup(token)
        if session is None:
            if path == "/":
                return _reply(200, markup="<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Ruby staging</title><h1>Ruby staging</h1><p>Read-only synthetic review. No customer data or execution authority.</p><a href=\"/auth/google/start\">Sign in with Google</a></html>")
            return _reply(401, {"error": "session_required"})
        if path == "/api/ruby-review-synthetic":
            return _reply(200, ruby_review_synthetic_surface())
        csrf = self._sessions.rotate_csrf(token)
        if csrf is None:
            return _reply(401, {"error": "session_required"})
        if path == "/api/session":
            return _reply(200, {"authenticated": True, "csrf_token": csrf})
        return _reply(200, markup="<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Ruby staging</title><h1>Ruby staging</h1><p>Signed-in, read-only synthetic review. No customer data or execution authority.</p><a href=\"/api/ruby-review-synthetic\">View synthetic review</a><input type=\"hidden\" id=\"logout-csrf\" name=\"csrf_token\" value=\"" + html.escape(csrf, quote=True) + "\"><button id=\"sign-out\" type=\"button\">Sign out</button><p id=\"sign-out-status\" role=\"status\"></p><noscript>Sign out requires JavaScript in this staging preview.</noscript><script>" + _LOGOUT_SCRIPT + "</script></html>")

    def __call__(self, environ, start_response):
        callback = type(environ) is dict and environ.get("PATH_INFO") == "/auth/google/callback"
        cookies = (serialize_cookie(FLOW_COOKIE),) if callback else ()
        admission = self._admission
        acquired = admission is not None and admission.acquire(blocking=False)
        try:
            if admission is not None and not acquired:
                # Fail before application processing instead of queuing behind
                # active requests. No authentication operation is attempted.
                result = _reply(503, {"error": "request_capacity_reached"}, cookies=cookies)
            else:
                try:
                    with self._lock:
                        result = self._dispatch(environ)
                    if type(result) is _AuthenticationWork:
                        result = self._complete_authentication(result)
                except Exception:
                    # No request, authorization code, token, owner or upstream
                    # exception is written to wsgi.errors or any logger.
                    result = _reply(503, {"error": "staging_unavailable"}, cookies=cookies)
                with self._lock:
                    clock_failed = self._clock_failed
                if clock_failed:
                    self.close()
                    result = _reply(503, {"error": "staging_unavailable"}, cookies=cookies)
            # Server response hooks may block/raise; never hold the state lock.
            start_response(f"{result.status} {_STATUS[result.status]}", list(result.headers))
            return [result.body]
        finally:
            if acquired:
                admission.release()

    def close(self) -> None:
        try:
            with self._lock:
                if self._closed:
                    return
                self._closed = True
                self._auth_generation += 1
                self._login_starts.clear()
                self._callback_attempts.clear()
                try:
                    if self._flows is not None:
                        self._flows.close()
                finally:
                    if self._sessions is not None:
                        self._sessions.close()
        finally:
            # Never wait for an upstream operation while closing app state.
            # An active authentication observes the generation change and closes
            # its backend when it returns. That cleanup is not a hard deadline.
            if self._authenticator is not None and self._auth_slot.acquire(blocking=False):
                try:
                    self._authenticator.close()
                finally:
                    self._auth_slot.release()


# Importing or executing the module never creates an enabled app, credential
# loader, network session, listener, or server. The image is a review artifact.
application = StagingHTTPApplication()

if __name__ == "__main__":
    print("Ruby staging application is inactive; no serving entrypoint is configured.")
