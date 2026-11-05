"""Default-off staging WSGI application, with no listener or runtime loader.

This is the HTTP application boundary, not an externally exposed fixture driver.
Only the real, server-configured Google authenticator may complete a login. The
default payload is Core's fixed synthetic review surface. Explicit private
synthetic-only binding can add owner preparation and source inquiry custody;
no customer/live store, notifications, quote recording or execution is enabled.

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
           403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed", 409: "Conflict",
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


_OWNER_LIST = "/api/ruby-owner-inquiries"
_OWNER_PREPARE = "/api/ruby-owner-quotes/prepare"
_OWNER_ID = re.compile(r"[A-Za-z0-9_-]{16,200}\Z", re.ASCII)
_OWNER_KEY = re.compile(r"[A-Za-z0-9._~-]{16,128}\Z", re.ASCII)
_OWNER_MAX_BODY = 64 * 1024
_SOURCE_PREFIX = "/api/ruby-owner-source-intake/"
_SOURCE_MAX_BODY = 512 * 1024
_SOURCE_OPERATIONS = frozenset({"source_prepare", "source_submit", "source_resolve"})
_SOURCE_ERRORS = {"source_input_invalid": 400, "source_handle_unavailable": 409,
    "source_outcome_unknown": 409, "source_intake_unavailable": 503}
_OWNER_ERRORS = {"inquiry_source_unavailable": 404, "inquiry_not_found": 404,
    "inquiry_stale": 409, "quote_input_invalid": 400, "quote_unavailable": 503}
_OWNER_PRIVATE_KEYS = frozenset({"source_handoff", "catalog_snapshot", "scope_fingerprint",
    "request_body", "idempotency_key", "original_source"})


class StagingOwnerQuoteError(ValueError):
    """Closed transport outcomes. Arbitrary exception text is never returned."""
    def __init__(self, code):
        self.code = code if type(code) is str and code in _OWNER_ERRORS else "quote_unavailable"
        super().__init__(self.code)


class StagingOwnerSourceIntakeError(ValueError):
    """Closed synthetic intake outcome, never application exception text."""
    def __init__(self, code):
        self.code = code if type(code) is str and code in _SOURCE_ERRORS else "source_intake_unavailable"
        super().__init__(self.code)


class StagingOwnerQuoteBinding:
    """Trusted private composition, never constructed from browser data.

    Callbacks are fixed list/current-detail/prepare-only operations, not a router.
    The private factory validates its actual owner-bound store/context/service.
    A successful application construction claims exclusive ownership once; before
    then the caller owns cleanup, including a failed application construction.
    """
    def __init__(self, *, issuer, owner_subject, list_inquiries, get_inquiry, prepare_quote, close,
                 prepare_source=None, submit_source=None, resolve_source=None, clear_source=None):
        if (type(issuer) is not str or issuer != ISSUER or type(owner_subject) is not str or not owner_subject
                or not owner_subject.isascii() or len(owner_subject) > 200
                or any(not callable(fn) for fn in (list_inquiries, get_inquiry, prepare_quote, close))):
            raise StagingHTTPConfigurationError("staging_owner_quote_binding_invalid")
        source_callbacks = (prepare_source, submit_source, resolve_source, clear_source)
        if any(fn is not None for fn in source_callbacks) and not all(callable(fn) for fn in source_callbacks):
            raise StagingHTTPConfigurationError("staging_owner_quote_binding_invalid")
        self._source_operations = ({"source_prepare": prepare_source, "source_submit": submit_source,
            "source_resolve": resolve_source} if prepare_source is not None else {})
        self._source_cleanup = clear_source
        self._issuer, self._subject = issuer, owner_subject
        self._operations = {"list": list_inquiries, "detail": get_inquiry, "prepare": prepare_quote}
        self._cleanup = close
        self._binding_lock = threading.Lock()
        self._owner = None
        self._closed = False

    def matches_policy(self, *, issuer, owner_subject):
        with self._binding_lock:
            return (not self._closed and self._owner is None and type(issuer) is str
                and type(owner_subject) is str and issuer == self._issuer
                and hmac.compare_digest(owner_subject, self._subject))

    def _claim(self, owner):
        with self._binding_lock:
            if self._closed or self._owner is not None:
                raise StagingHTTPConfigurationError("staging_owner_quote_binding_invalid")
            self._owner = owner

    def _run(self, owner, operation, argument):
        with self._binding_lock:
            if self._closed or self._owner is not owner or operation not in self._operations:
                raise StagingOwnerQuoteError("quote_unavailable")
            callback = self._operations[operation]
        return callback() if operation == "list" else callback(argument)

    def _run_source(self, owner, operation, argument, session, now):
        with self._binding_lock:
            if self._closed or self._owner is not owner or operation not in self._source_operations:
                raise StagingOwnerSourceIntakeError("source_intake_unavailable")
            callback = self._source_operations[operation]
        return callback(argument, session, now)

    def _clear_source(self):
        with self._binding_lock:
            callback = self._source_cleanup
        if callback is not None:
            callback()

    def close(self):
        with self._binding_lock:
            if self._closed:
                return
            self._closed = True
            callback, self._cleanup = self._cleanup, None
            clear, self._source_cleanup = self._source_cleanup, None
            self._operations.clear()
            self._source_operations.clear()
            self._owner = None
        control_failure = None
        try:
            if clear is not None: clear()
        except BaseException as failure:
            if not isinstance(failure, Exception): control_failure = failure
        try:
            callback()
        finally:
            if control_failure is not None: raise control_failure


_OWNER_ASSET_PREFIX = "/owner-quote-workbench/"
_OWNER_ASSET_CONTRACT = (
    ("index.html", "text/html; charset=utf-8", 4096),
    ("enabled.mjs", "text/javascript; charset=utf-8", 4096),
    ("view.mjs", "text/javascript; charset=utf-8", 64 * 1024),
    ("controller.mjs", "text/javascript; charset=utf-8", 64 * 1024),
    ("workbench.css", "text/css; charset=utf-8", 16 * 1024),
)


@dataclass(frozen=True)
class StagingOwnerWorkbenchAssets:
    """Closed private package bytes, never paths or a filesystem/router callback.

    Trusted private composition supplies its reviewed exact SHA-256 pins. Core
    fixes all five URLs, MIME types and bounds; the private loader verifies the
    deployed source against its own immutable review pins before constructing
    this value. This object confers no authentication or store authority.
    """
    binding: StagingOwnerQuoteBinding = field(repr=False)
    bodies: tuple[bytes, ...] = field(repr=False)
    sha256: tuple[str, ...] = field(repr=False)
    synthetic_only: bool = False

    def __post_init__(self):
        if (type(self.binding) is not StagingOwnerQuoteBinding or self.synthetic_only is not True
                or type(self.bodies) is not tuple or type(self.sha256) is not tuple
                or len(self.bodies) != len(_OWNER_ASSET_CONTRACT)
                or len(self.sha256) != len(_OWNER_ASSET_CONTRACT)):
            raise StagingHTTPConfigurationError("staging_owner_assets_invalid")
        for body, digest, (_, _, maximum) in zip(self.bodies, self.sha256, _OWNER_ASSET_CONTRACT):
            if (type(body) is not bytes or not 0 < len(body) <= maximum
                    or type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest, re.ASCII)
                    or hashlib.sha256(body).hexdigest() != digest):
                raise StagingHTTPConfigurationError("staging_owner_assets_invalid")


def _owner_asset_replies(assets, origin):
    # Called only after the app validates its existing exact HTTPS origin. No
    # Host, proxy, browser URL or asset-supplied origin participates in this CSP.
    scripts = " ".join(origin + _OWNER_ASSET_PREFIX + name
        for name, mime, _ in _OWNER_ASSET_CONTRACT if mime.startswith("text/javascript"))
    policy = ("default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; "
        "object-src 'none'; worker-src 'none'; script-src " + scripts + "; script-src-attr 'none'; "
        "style-src " + origin + _OWNER_ASSET_PREFIX + "workbench.css; style-src-attr 'none'; "
        "connect-src " + " ".join(origin + route for route in
            ("/api/session", _OWNER_LIST, _OWNER_LIST + "/", _OWNER_PREPARE, "/auth/logout")))
    return tuple((_OWNER_ASSET_PREFIX + name, _Reply(200, body, (
        ("Content-Type", mime), ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"), ("Pragma", "no-cache"),
        ("Referrer-Policy", "no-referrer"), ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", policy), ("X-Frame-Options", "DENY"))))
        for (name, mime, _), body in zip(_OWNER_ASSET_CONTRACT, assets.bodies))


_INTAKE_ASSET_PREFIX = "/owner-synthetic-intake/"
_INTAKE_ASSET_CONTRACT = (
    ("form/index.html", "text/html; charset=utf-8", 4096),
    ("form/enabled.mjs", "text/javascript; charset=utf-8", 4096),
    ("form/view.mjs", "text/javascript; charset=utf-8", 64 * 1024),
    ("form/intake.css", "text/css; charset=utf-8", 16 * 1024),
    ("src/order-intake-source-http.mjs", "text/javascript; charset=utf-8", 32 * 1024),
    ("src/order-intake-source-submission.mjs", "text/javascript; charset=utf-8", 32 * 1024),
    ("src/order-intake-synthetic-submission.mjs", "text/javascript; charset=utf-8", 32 * 1024),
    ("src/order-intake-review-handoff.mjs", "text/javascript; charset=utf-8", 32 * 1024),
    ("src/order-intake-request-envelope.mjs", "text/javascript; charset=utf-8", 32 * 1024),
    ("src/order-intake-draft-state.mjs", "text/javascript; charset=utf-8", 32 * 1024),
    ("src/order-intake-review-state.mjs", "text/javascript; charset=utf-8", 32 * 1024),
    ("src/design-notes-limit.mjs", "text/javascript; charset=utf-8", 32 * 1024),
 )


@dataclass(frozen=True)
class StagingOwnerIntakeAssets:
    """Exact synthetic intake bytes. No generic static serving or public source.

    This independent closed bundle requires an actual source-enabled binding.
    It confers no session, source mutation or quote-recording authority.
    """
    binding: StagingOwnerQuoteBinding = field(repr=False)
    bodies: tuple[bytes, ...] = field(repr=False)
    sha256: tuple[str, ...] = field(repr=False)
    synthetic_only: bool = False

    def __post_init__(self):
        if (type(self.binding) is not StagingOwnerQuoteBinding or self.synthetic_only is not True
                or type(self.bodies) is not tuple or type(self.sha256) is not tuple
                or len(self.bodies) != len(_INTAKE_ASSET_CONTRACT)
                or len(self.sha256) != len(_INTAKE_ASSET_CONTRACT)):
            raise StagingHTTPConfigurationError("staging_owner_intake_assets_invalid")
        with self.binding._binding_lock:
            if self.binding._closed or set(self.binding._source_operations) != set(_SOURCE_OPERATIONS):
                raise StagingHTTPConfigurationError("staging_owner_intake_assets_invalid")
        for body, digest, (_, _, maximum) in zip(self.bodies, self.sha256, _INTAKE_ASSET_CONTRACT):
            if (type(body) is not bytes or not 0 < len(body) <= maximum
                    or type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest, re.ASCII)
                    or hashlib.sha256(body).hexdigest() != digest):
                raise StagingHTTPConfigurationError("staging_owner_intake_assets_invalid")


def _intake_asset_replies(assets, origin):
    scripts = " ".join(origin + _INTAKE_ASSET_PREFIX + name
        for name, mime, _ in _INTAKE_ASSET_CONTRACT if mime.startswith("text/javascript"))
    policy = ("default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; "
        "object-src 'none'; worker-src 'none'; script-src " + scripts + "; script-src-attr 'none'; "
        "style-src " + origin + _INTAKE_ASSET_PREFIX + "form/intake.css; style-src-attr 'none'; "
        "connect-src " + " ".join(origin + route for route in
            ("/api/session", "/api/ruby-owner-source-intake/prepare", "/api/ruby-owner-source-intake/submit",
             "/api/ruby-owner-source-intake/resolve")))
    return tuple((_INTAKE_ASSET_PREFIX + name, _Reply(200, body, (
        ("Content-Type", mime), ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"), ("Pragma", "no-cache"),
        ("Referrer-Policy", "no-referrer"), ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", policy), ("X-Frame-Options", "DENY"))))
        for (name, mime, _), body in zip(_INTAKE_ASSET_CONTRACT, assets.bodies))


@dataclass(frozen=True)
class _OwnerAssetWork:
    reply: _Reply = field(repr=False)
    token: str = field(repr=False)
    generation: int


@dataclass(frozen=True)
class _OwnerQuoteWork:
    operation: str
    argument: object = field(repr=False)
    token: str = field(repr=False)
    csrf: str | None = field(repr=False)
    generation: int
    binding: StagingOwnerQuoteBinding = field(repr=False)
    body_length: int = 0


def _owner_json_tree(value, *, response=False, maximum=None):
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop(); count += 1
        if depth > 16 or count > 8192:
            raise _RequestRejected
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise _RequestRejected
            if response and _OWNER_PRIVATE_KEYS.intersection(item):
                raise _RequestRejected
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif item is not None and type(item) not in (str, bool, int):
            raise _RequestRejected
        elif type(item) is int and not -(2**53-1) <= item <= 2**53-1:
            raise _RequestRejected
    try:
        data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise _RequestRejected from None
    if len(data) > (maximum if maximum is not None else (128 * 1024 if response else _OWNER_MAX_BODY)):
        raise _RequestRejected


def _owner_read_json(stream, length):
    # Read only the declared body, never drain another request. Wire framing and
    # hard read deadlines remain trusted server/ingress responsibilities.
    chunks, remaining = [], length
    while remaining:
        chunk = stream.read(remaining)
        if type(chunk) is not bytes or not chunk or len(chunk) > remaining:
            raise _RequestRejected
        chunks.append(chunk); remaining -= len(chunk)
    def pairs(entries):
        value = {}
        for key, item in entries:
            if key in value: raise _RequestRejected
            value[key] = item
        return value
    def invalid(_): raise _RequestRejected
    try:
        value = json.loads(b"".join(chunks).decode("utf-8", "strict"),
            object_pairs_hook=pairs, parse_constant=invalid)
        if type(value) is not dict or set(value) != {"inquiry_id", "expected_revision_id", "idempotency_key", "authored_quote"}:
            raise _RequestRejected
        _owner_json_tree(value)
        for key in ("inquiry_id", "expected_revision_id", "idempotency_key"):
            pattern = _OWNER_KEY if key == "idempotency_key" else _OWNER_ID
            if type(value[key]) is not str or not pattern.fullmatch(value[key]):
                raise _RequestRejected
        if type(value["authored_quote"]) is not dict:
            raise _RequestRejected
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise _RequestRejected from None


def _source_read_json(stream, length, operation):
    chunks, remaining = [], length
    while remaining:
        chunk = stream.read(remaining)
        if type(chunk) is not bytes or not chunk or len(chunk) > remaining:
            raise _RequestRejected
        chunks.append(chunk); remaining -= len(chunk)
    def pairs(entries):
        value = {}
        for key, item in entries:
            if key in value: raise _RequestRejected
            value[key] = item
        return value
    def invalid(_): raise _RequestRejected
    try:
        value = json.loads(b"".join(chunks).decode("utf-8", "strict"),
            object_pairs_hook=pairs, parse_constant=invalid)
        fields = {"source_prepare": {"idempotency_key", "source_handoff_body"},
                  "source_submit": {"handle"}, "source_resolve": {"attempt"}}[operation]
        if type(value) is not dict or set(value) != fields:
            raise _RequestRejected
        _owner_json_tree(value, maximum=_SOURCE_MAX_BODY)
        if operation == "source_prepare":
            if (type(value["idempotency_key"]) is not str or not _OWNER_KEY.fullmatch(value["idempotency_key"])
                    or type(value["source_handoff_body"]) is not str): raise _RequestRejected
        elif operation == "source_submit":
            if type(value["handle"]) is not str or not _TOKEN.fullmatch(value["handle"]): raise _RequestRejected
        else:
            attempt = value["attempt"]
            if (type(attempt) is not dict or set(attempt) != {"idempotencyKey", "requestBody", "sourceHandoffBody"}
                    or any(type(v) is not str for v in attempt.values())): raise _RequestRejected
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise _RequestRejected from None


def _source_response(data, operation, argument):
    # Only prepare may return the exact caller-owned original attempt, never
    # owner identity or retained source selected from an existing inquiry.
    if type(data) is not dict: raise _RequestRejected
    if operation == "source_prepare":
        if (set(data) != {"state", "handle", "attempt"} or data["state"] != "prepared_not_submitted"
                or type(data["handle"]) is not str or not _TOKEN.fullmatch(data["handle"])): raise _RequestRejected
        attempt = data["attempt"]
        if (type(attempt) is not dict or set(attempt) != {"idempotencyKey", "requestBody", "sourceHandoffBody"}
                or any(type(v) is not str for v in attempt.values())): raise _RequestRejected
        if (attempt['idempotencyKey'] != argument['idempotency_key']
                or attempt['sourceHandoffBody'] != argument['source_handoff_body']): raise _RequestRejected
        if (len(attempt['requestBody']) > 128 * 1024
                or len(attempt['sourceHandoffBody']) > 128 * 1024): raise _RequestRejected
        _owner_json_tree(data, maximum=_SOURCE_MAX_BODY)
        # Reuse the closed Core structural schema without creating a usable
        # custody policy or exposing any server owner/scope. No catalog remap.
        from ruby_inquiry import decode, canonical, RubyInquiryMixin, RubyInquiryPolicy, MAX_BODY
        request = decode(attempt['requestBody'].encode('utf-8'))
        source = decode(attempt['sourceHandoffBody'].encode('utf-8'))
        structural_policy = RubyInquiryPolicy('', '', '', '', allowed_contact_channels=frozenset({'email'}))
        RubyInquiryMixin._inquiry_payload(request, structural_policy, current_catalog=False)
        RubyInquiryMixin._inquiry_source(source)
        if (canonical(request).decode('utf-8') != attempt['requestBody']
                or canonical(source).decode('utf-8') != attempt['sourceHandoffBody']
                or request['contact'] != {'kind': 'email', 'destination': 'synthetic-customer@example.invalid',
                                          'display_name': 'Synthetic Customer'}
                or len(canonical(dict(schema_version='ruby.inquiry-source-custody.v1',
                    request=request, source_handoff=source))) > MAX_BODY): raise _RequestRejected
        _owner_json_tree(data, maximum=_SOURCE_MAX_BODY)
    else:
        _owner_json_tree(data, response=True)
        from ruby_inquiry import RubyInquiryMixin, canonical, decode, MAX_SAFE_INTEGER
        receipt = data.get('receipt')
        if (type(receipt) is not dict or type(receipt.get('inquiry_id')) is not str
                or not _OWNER_ID.fullmatch(receipt['inquiry_id'])
                or type(receipt.get('revision_id')) is not str or not _OWNER_ID.fullmatch(receipt['revision_id'])
                or type(receipt.get('received_at')) is not int or not 0 < receipt['received_at'] <= MAX_SAFE_INTEGER
                or type(receipt.get('request_fingerprint')) is not str
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', receipt['request_fingerprint'])): raise _RequestRejected
        digest = receipt['request_fingerprint']
        if operation == 'source_resolve':
            original = argument['attempt']
            envelope = dict(schema_version='ruby.inquiry-source-custody.v1',
                request=decode(original['requestBody'].encode('utf-8')),
                source_handoff=decode(original['sourceHandoffBody'].encode('utf-8')))
            if digest != 'sha256:' + hashlib.sha256(canonical(envelope)).hexdigest(): raise _RequestRejected
        expected = RubyInquiryMixin._inquiry_make_receipt('create', receipt['inquiry_id'],
            receipt['revision_id'], 1, bytes.fromhex(digest[7:]), receipt['received_at'])
        if canonical(data) != canonical(expected): raise _RequestRejected
    result = _reply(200, data)
    if len(result.body) > _SOURCE_MAX_BODY: raise _RequestRejected
    return result


class StagingHTTPApplication:
    """Single-process, in-memory application; default construction is inactive.

    Enabled successful construction transfers exclusive ownership of the authenticator
    to this application. Short state operations use a lock, but upstream HTTPS
    never holds it. Admission bounds concurrent application work; one nonblocking
    authentication slot avoids queuing for HTTPS. Admitted state operations still
    briefly serialize, with no owner-priority reservation. Explicitly bound
    owner preparation and synthetic source operations share one work slot and
    read strictly bounded JSON outside that lock.
    Multiprocess/distributed state is not implemented.
    """

    def __init__(self, config: StagingHTTPConfig | None = None, *, enabled: bool = False,
                 authenticator: StagingGoogleOwnerAuthenticator | None = None,
                 limits: StagingRequestLimits | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 owner_quote_binding: StagingOwnerQuoteBinding | None = None,
                 owner_workbench_assets: StagingOwnerWorkbenchAssets | None = None,
                 owner_intake_assets: StagingOwnerIntakeAssets | None = None) -> None:
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
        self._source_write_attempts: deque[float] = deque()
        self._auth_generation = 0
        self._owner_quote_binding = None
        self._owner_asset_replies = ()
        self._intake_asset_replies = ()
        self._owner_quote_slot = threading.Lock()
        if enabled is False:
            return
        flows = sessions = None
        try:
            if (enabled is not True or type(config) is not StagingHTTPConfig
                    or type(limits) is not StagingRequestLimits):
                raise ValueError
            config.validate()
            limits.validate()
            if owner_quote_binding is not None and (type(owner_quote_binding) is not StagingOwnerQuoteBinding
                    or not owner_quote_binding.matches_policy(issuer=ISSUER, owner_subject=config.owner_subject)):
                raise ValueError
            asset_replies = ()
            if owner_workbench_assets is not None:
                if (type(owner_workbench_assets) is not StagingOwnerWorkbenchAssets
                        or owner_quote_binding is None
                        or owner_workbench_assets.binding is not owner_quote_binding):
                    raise ValueError
                owner_workbench_assets.__post_init__()
                asset_replies = _owner_asset_replies(owner_workbench_assets, config.origin)
            intake_replies = ()
            if owner_intake_assets is not None:
                if (type(owner_intake_assets) is not StagingOwnerIntakeAssets
                        or owner_quote_binding is None
                        or owner_intake_assets.binding is not owner_quote_binding):
                    raise ValueError
                owner_intake_assets.__post_init__()
                intake_replies = _intake_asset_replies(owner_intake_assets, config.origin)
            self._now()
            if authenticator is not None and (type(authenticator) is not StagingGoogleOwnerAuthenticator
                    or not authenticator.matches_policy(origin=config.origin, client_id=config.client_id,
                                                        owner_subject=config.owner_subject)):
                raise ValueError
            flows = LoginFlowStore(enabled=True, ttl_seconds=config.flow_seconds,
                                   capacity=config.capacity, clock=self._now)
            sessions = SessionStore(enabled=True, idle_seconds=config.idle_seconds,
                absolute_seconds=config.absolute_seconds, capacity=config.capacity, clock=self._now)
            self._config, self._authenticator = config, authenticator
            self._flows, self._sessions = flows, sessions
            self._limits = limits
            self._admission = threading.BoundedSemaphore(limits.max_inflight_requests)
            if owner_quote_binding is not None:
                owner_quote_binding._claim(self)
                self._owner_quote_binding = owner_quote_binding
            self._owner_asset_replies = asset_replies
            self._intake_asset_replies = intake_replies
            self._enabled = True
        except BaseException as failure:
            # The caller still owns authenticator and binding on failed
            # construction. Retire all locally acquired stores exactly once.
            self._enabled = False
            self._closed = True
            self._sessions = self._flows = None
            for resource in (sessions, flows):
                if resource is not None:
                    try:
                        resource.close()
                    except BaseException as cleanup:
                        if isinstance(failure, Exception) and not isinstance(cleanup, Exception):
                            failure = cleanup
            if not isinstance(failure, Exception):
                raise failure
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
                self._auth_generation += 1
                if self._owner_quote_binding is not None: self._owner_quote_binding._clear_source()
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

    def _owner_dispatch(self, environ, method, path, cookie):
        binding = self._owner_quote_binding
        if binding is None:
            return None
        operation, argument, length = None, None, 0
        if path.startswith(_SOURCE_PREFIX) and binding._source_operations:
            operation = "source_" + path[len(_SOURCE_PREFIX):]
            if operation not in _SOURCE_OPERATIONS: return _reply(404, {"error": "not_found"})
            if method != "POST": return _reply(405, {"error": "method_not_allowed"})
        elif path == _OWNER_LIST:
            if method != "GET": return _reply(405, {"error": "method_not_allowed"})
            operation = "list"
        elif path.startswith(_OWNER_LIST + "/"):
            if method != "GET": return _reply(405, {"error": "method_not_allowed"})
            argument = path[len(_OWNER_LIST)+1:]
            if not _OWNER_ID.fullmatch(argument): return _reply(400, {"error": "request_invalid"})
            operation = "detail"
        elif path == _OWNER_PREPARE:
            if method != "POST": return _reply(405, {"error": "method_not_allowed"})
            operation = "prepare"
        else:
            return None
        token, bad_cookie = self._session_cookie(cookie)
        needs_csrf = operation == "prepare" or operation in _SOURCE_OPERATIONS
        csrf = environ.get("HTTP_X_CSRF_TOKEN") if needs_csrf else None
        if needs_csrf and environ.get("HTTP_ORIGIN") != self._config.origin:
            return _reply(403, {"error": "request_denied"})
        if bad_cookie or self._sessions.lookup(token, require_csrf=needs_csrf, csrf_token=csrf) is None:
            return _reply(401, {"error": "session_required"})
        if needs_csrf:
            raw_length = environ.get("CONTENT_LENGTH")
            if (environ.get("CONTENT_TYPE") != "application/json" or type(raw_length) is not str
                    or not re.fullmatch(r"[1-9][0-9]{0,5}", raw_length, re.ASCII)):
                return _reply(400, {"error": "request_invalid"})
            length = int(raw_length)
            maximum = (1024 if operation == "source_submit" else _SOURCE_MAX_BODY) if operation in _SOURCE_OPERATIONS else _OWNER_MAX_BODY
            if length > maximum: return _reply(413, {"error": "request_too_large"})
            argument = environ.get("wsgi.input")
            if not callable(getattr(argument, "read", None)): return _reply(400, {"error": "request_invalid"})
        if (operation in {"source_prepare", "source_submit"}
                and not self._rate_allowed(self._source_write_attempts, 16)):
            return _reply(429, {"error": "source_rate_limited"})
        if not self._owner_quote_slot.acquire(blocking=False):
            return _reply(503, {"error": "quote_busy"})
        return _OwnerQuoteWork(operation, argument, token, csrf, self._auth_generation, binding, length)

    def _owner_work_live(self, work):
        return (not self._closed and not self._clock_failed
            and work.generation == self._auth_generation and self._owner_quote_binding is work.binding
            and self._sessions.lookup(work.token, require_csrf=work.operation == "prepare" or work.operation in _SOURCE_OPERATIONS, csrf_token=work.csrf) is not None)

    def _complete_owner_quote(self, work):
        try:
            with self._lock:
                if not self._owner_work_live(work): return _reply(401, {"error": "session_required"})
            argument = (_source_read_json(work.argument, work.body_length, work.operation)
                if work.operation in _SOURCE_OPERATIONS else
                (_owner_read_json(work.argument, work.body_length) if work.operation == "prepare" else work.argument))
            # Logout/expiry during body reading must prevent service invocation.
            with self._lock:
                if not self._owner_work_live(work): return _reply(401, {"error": "session_required"})
                work_now = self._now() if work.operation in _SOURCE_OPERATIONS else None
            try:
                if work.operation in _SOURCE_OPERATIONS:
                    data = work.binding._run_source(self, work.operation, argument,
                        (work.token, work.generation, work.csrf), work_now)
                    result = _source_response(data, work.operation, argument)
                else:
                    data = work.binding._run(self, work.operation, argument)
                    if type(data) is not dict: raise _RequestRejected
                    _owner_json_tree(data, response=True)
                    result = _reply(200, data)
                    if len(result.body) > 128 * 1024: raise _RequestRejected
            except StagingOwnerSourceIntakeError as failure:
                result = _reply(_SOURCE_ERRORS[failure.code], {"error": failure.code})
            except StagingOwnerQuoteError as failure:
                result = _reply(_OWNER_ERRORS[failure.code], {"error": failure.code})
            except Exception:
                if work.operation in _SOURCE_OPERATIONS:
                    if work.operation == "source_prepare": work.binding._clear_source()
                    result = _reply(503, {"error": "source_intake_unavailable"})
                else:
                    result = _reply(503, {"error": "quote_unavailable"})
            with self._lock:
                if not self._owner_work_live(work):
                    work.binding._clear_source()
                    return _reply(401, {"error": "session_required"})
            return result
        except _RequestRejected:
            with self._lock:
                if not self._owner_work_live(work): return _reply(401, {"error": "session_required"})
            return _reply(400, {"error": "request_invalid"})
        finally:
            with self._lock:
                self._owner_quote_slot.release()
                cleanup = self._owner_quote_binding if self._closed else None
                if cleanup is not None: self._owner_quote_binding = None
            if cleanup is not None:
                try: cleanup.close()
                except Exception: pass

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
        if ((self._owner_asset_replies and path.startswith(_OWNER_ASSET_PREFIX))
                or (self._intake_asset_replies and path.startswith(_INTAKE_ASSET_PREFIX))):
            if method != "GET": return _reply(405, {"error": "method_not_allowed"})
            token, bad_cookie = self._session_cookie(cookie)
            if bad_cookie or self._sessions.lookup(token) is None:
                return _reply(401, {"error": "session_required"})
            for asset_path, result in self._owner_asset_replies + self._intake_asset_replies:
                if path == asset_path:
                    return _OwnerAssetWork(result, token, self._auth_generation)
            return _reply(404, {"error": "not_found"})
        owner_work = self._owner_dispatch(environ, method, path, cookie)
        if owner_work is not None:
            return owner_work
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
            if self._owner_quote_binding is not None: self._owner_quote_binding._clear_source()
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
        if self._owner_quote_binding is not None: self._owner_quote_binding._clear_source()
        csrf = self._sessions.rotate_csrf(token)
        if csrf is None:
            return _reply(401, {"error": "session_required"})
        if path == "/api/session":
            return _reply(200, {"authenticated": True, "csrf_token": csrf})
        workbench_link = ('<a href="/owner-quote-workbench/index.html">Owner quote workbench</a>'
                          if self._owner_asset_replies else "")
        root_description = ('Signed-in synthetic intake and review. Synthetic inquiries and original source may be retained. No real customer data or quote recording, sending or execution authority.'
                            if self._intake_asset_replies else
                            'Signed-in, read-only synthetic review. No customer data or execution authority.')
        intake_link = ('<a href="/owner-synthetic-intake/form/index.html">Synthetic inquiry intake</a>'
                       if self._intake_asset_replies else "")
        return _reply(200, markup="<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Ruby staging</title><h1>Ruby staging</h1><p>" + root_description + "</p><a href=\"/api/ruby-review-synthetic\">View synthetic review</a>" + workbench_link + intake_link + "<input type=\"hidden\" id=\"logout-csrf\" name=\"csrf_token\" value=\"" + html.escape(csrf, quote=True) + "\"><button id=\"sign-out\" type=\"button\">Sign out</button><p id=\"sign-out-status\" role=\"status\"></p><noscript>Sign out requires JavaScript in this staging preview.</noscript><script>" + _LOGOUT_SCRIPT + "</script></html>")

    def __call__(self, environ, start_response):
        callback = type(environ) is dict and environ.get("PATH_INFO") == "/auth/google/callback"
        cookies = (serialize_cookie(FLOW_COOKIE),) if callback else ()
        asset_work = None
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
                    if type(result) is _OwnerAssetWork:
                        asset_work, result = result, result.reply
                    if type(result) is _AuthenticationWork:
                        result = self._complete_authentication(result)
                    elif type(result) is _OwnerQuoteWork:
                        result = self._complete_owner_quote(result)
                except Exception:
                    # No request, authorization code, token, owner or upstream
                    # exception is written to wsgi.errors or any logger.
                    result = _reply(503, {"error": "staging_unavailable"}, cookies=cookies)
                with self._lock:
                    clock_failed = self._clock_failed
                if clock_failed:
                    self.close()
                    result = _reply(503, {"error": "staging_unavailable"}, cookies=cookies)
            if asset_work is not None:
                # Final known-revocation check after dispatch. No Python guard
                # can retract bytes after admission to a server response hook.
                # Never hold this lock across that potentially blocking hook.
                with self._lock:
                    if self._closed or self._clock_failed:
                        result = _reply(503, {"error": "staging_inactive"})
                    else:
                        try:
                            live = (asset_work.generation == self._auth_generation
                                and self._sessions.lookup(asset_work.token) is not None)
                        except LifecycleError:
                            live = False
                        if not live: result = _reply(401, {"error": "session_required"})
                        if self._clock_failed:
                            result = _reply(503, {"error": "staging_unavailable"})
                if self._clock_failed:
                    self.close()
            # Server response hooks may block/raise; never hold the state lock.
            start_response(f"{result.status} {_STATUS[result.status]}", list(result.headers))
            return [result.body]
        finally:
            if acquired:
                admission.release()

    def close(self) -> None:
        cleanup = source_cleanup = None
        failure = None
        def attempt(action, *, ignore_ordinary=False):
            nonlocal failure
            try:
                action()
            except BaseException as exc:
                if not isinstance(exc, Exception):
                    if failure is None or isinstance(failure, Exception): failure = exc
                elif not ignore_ordinary and failure is None:
                    failure = exc
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._owner_asset_replies = ()
            self._intake_asset_replies = ()
            source_cleanup = self._owner_quote_binding
            if self._owner_quote_binding is not None and self._owner_quote_slot.acquire(blocking=False):
                cleanup, self._owner_quote_binding = self._owner_quote_binding, None
                self._owner_quote_slot.release()
            self._auth_generation += 1
            self._login_starts.clear()
            self._callback_attempts.clear()
            self._source_write_attempts.clear()
            for resource in (self._flows, self._sessions):
                if resource is not None: attempt(resource.close)
        if source_cleanup is not None: attempt(source_cleanup._clear_source, ignore_ordinary=True)
        if cleanup is not None: attempt(cleanup.close, ignore_ordinary=True)
        # Do not wait for active authentication; its existing completion path
        # closes the backend. This does not impose a hard shutdown deadline.
        if self._authenticator is not None and self._auth_slot.acquire(blocking=False):
            try:
                attempt(self._authenticator.close)
            finally:
                self._auth_slot.release()
        if failure is not None:
            raise failure


# Importing or executing the module never creates an enabled app, credential
# loader, network session, listener, or server. The image is a review artifact.
application = StagingHTTPApplication()

if __name__ == "__main__":
    print("Ruby staging application is inactive; no serving entrypoint is configured.")
