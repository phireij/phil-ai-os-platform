"""Default-off, server-owned Google authentication for isolated Ruby staging.

The caller must consume its browser-bound, one-use login flow before calling
authenticate. No request-supplied policy, key, transport, endpoint, credential
loader or listener is provided. A constructor credential is held in memory only.
This module imports neither the offline exchange nor any rehearsal fixture.

Only the fixed Google token and certificate HTTPS endpoints are contacted. TLS
verification cannot be disabled; environment proxy/CA/netrc configuration,
redirects, retries, cookies and response hooks are not used. Reads are bounded
and checked against monotonic deadlines. Requests' connect/read timeouts and
these checks are NOT a hard DNS or whole-request deadline: resolver isolation,
network egress restrictions and an outer worker deadline require deployment
acceptance. No such deployment or live request is authorized by this source.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
from email.utils import parsedate_to_datetime
from typing import Callable

import requests
from cryptography import x509

from ruby_staging_id_token import (
    PRODUCTION_CLIENT_ID, StagingIdTokenVerifier, VerifiedOwnerClaims,
)
from ruby_staging_lifecycle import CodeExchangeInputs


TOKEN_URL = "https://oauth2.googleapis.com/token"
CERTIFICATE_URL = "https://www.googleapis.com/oauth2/v1/certs"
PRODUCTION_ORIGIN = "https://miscon.phireij.cloud"
_CLIENT = re.compile(r"[A-Za-z0-9_-]{1,200}\.apps\.googleusercontent\.com", re.ASCII)
_SUBJECT = re.compile(r"[A-Za-z0-9_-]{1,255}", re.ASCII)
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.ASCII)
_FLOW_VALUE = re.compile(r"[A-Za-z0-9_-]{64}", re.ASCII)
_HEADER_NAME = re.compile(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+", re.ASCII)
_TOKEN_BYTES = 65536
_CERTIFICATE_BYTES = 131072
_READ_BYTES = 8192
_EXCHANGE_SECONDS = 20
_BODY_SECONDS = 10


class AuthenticationRejected(ValueError):
    """Constant error with no credential, code, token or upstream response."""


class AuthenticationConfigurationError(ValueError):
    """Constant, redacted configuration error."""


def valid_staging_policy(origin: object, client_id: object, owner_subject: object) -> bool:
    """Pure exact policy check, shared with the trusted application constructor."""
    if type(origin) is not str or not origin.startswith("https://") or len(origin) > 261:
        return False
    host = origin[8:]
    labels = host.split(".")
    if (len(host) > 253 or len(labels) < 2 or not all(_LABEL.fullmatch(label) for label in labels)
            or labels[-1].isdigit() or origin == PRODUCTION_ORIGIN):
        return False
    return (type(client_id) is str and _CLIENT.fullmatch(client_id) is not None
            and client_id != PRODUCTION_CLIENT_ID and type(owner_subject) is str
            and _SUBJECT.fullmatch(owner_subject) is not None)


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _nonfinite(_value: str):
    raise ValueError


def _headers(response: requests.Response, url: str, maximum: int) -> dict[str, str]:
    # requests.Response.headers has already coalesced duplicate fields. Inspect
    # urllib3's raw multi-dict instead, preserving duplicates and enforcing caps
    # before reading the body. The HTTP stack itself parses headers beforehand;
    # deployment still needs its own socket/header resource limits.
    if (type(response.status_code) is not int or response.status_code != 200
            or type(response.url) is not str or response.url != url or response.history):
        raise ValueError
    values: dict[str, str] = {}
    total = 0
    for index, (name, value) in enumerate(response.raw.headers.iteritems()):
        if type(name) is not str or type(value) is not str:
            raise ValueError
        total += len(name) + len(value)
        key = name.lower()
        if (index >= 32 or total > 8192 or not _HEADER_NAME.fullmatch(name)
                or any(ord(c) < 32 or ord(c) > 126 for c in value) or key in values):
            raise ValueError
        values[key] = value
    if (set(values) & {"location", "set-cookie"}
            or values.get("content-encoding", "identity").lower() != "identity"
            or values.get("content-type", "").lower() not in
            ("application/json", "application/json; charset=utf-8")):
        raise ValueError
    if "transfer-encoding" in values:
        if values["transfer-encoding"].lower() != "chunked" or "content-length" in values:
            raise ValueError
    length = values.get("content-length")
    if length is not None and (not re.fullmatch(r"[0-9]{1,6}", length)
                               or not 1 <= int(length) <= maximum):
        raise ValueError
    return values


class StagingGoogleOwnerAuthenticator:
    """One staging policy and internally owned, serialized HTTPS session.

    A verified result carries no session or execution grant. The application
    separately enforces one-use flow, browser binding, session and read policy.
    Unknown key IDs never trigger a refresh while a trusted cache is fresh.
    Stale keys are discarded before refresh; failures cannot revive them. Wall
    clock rollback permanently closes this instance, including its connection
    pools. Both the verifier and cache share the same wall-clock high-water mark.
    """

    def __init__(self, origin: str, client_id: str, owner_subject: str,
                 client_secret: str, max_cache_seconds: int, enabled: bool = False,
                 clock: Callable[[], float] = time.time) -> None:
        self._session: requests.Session | None = None
        self._client_secret = ""
        self._closed = True
        self._lock = threading.RLock()
        self._verifier: StagingIdTokenVerifier | None = None
        self._valid_until = 0
        try:
            # Every configuration check, including the initial clock read,
            # precedes Session construction. Merely importing is inactive.
            if enabled is not True or not valid_staging_policy(origin, client_id, owner_subject):
                raise ValueError
            if (type(client_secret) is not str or not 1 <= len(client_secret) <= 4096
                    or any(ord(c) < 33 or ord(c) > 126 for c in client_secret)
                    or type(max_cache_seconds) is not int or not 1 <= max_cache_seconds <= 86400
                    or not callable(clock)):
                raise ValueError
            now = clock()
            if type(now) not in (int, float) or not math.isfinite(now) or not 0 <= now <= 2**53:
                raise ValueError
            self._origin, self._client_id, self._owner_subject = origin, client_id, owner_subject
            self._callback = origin + "/auth/google/callback"
            self._client_secret = client_secret
            self._max_cache_seconds, self._clock, self._last_time = max_cache_seconds, clock, now
            session = requests.Session()
            self._session = session
            session.trust_env = False
            session.auth = None
            session.cookies.clear()
            session.proxies.clear()
            session.headers.clear()
            session.hooks = {"response": []}
            for adapter in session.adapters.values():
                adapter.close()
            session.adapters.clear()
            # requests' zero-retry adapter also disables read/status retries.
            session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
            self._closed = False
        except Exception:
            self._close_unlocked()
            raise AuthenticationConfigurationError("authentication_configuration_invalid") from None

    def matches_policy(self, origin: str, client_id: str, owner_subject: str) -> bool:
        with self._lock:
            return (not self._closed and valid_staging_policy(origin, client_id, owner_subject)
                    and (origin, client_id, owner_subject) ==
                    (self._origin, self._client_id, self._owner_subject))

    def _close_unlocked(self) -> None:
        self._closed = True
        self._verifier = None
        self._valid_until = 0
        self._client_secret = ""
        session, self._session = self._session, None
        if session is not None:
            try:
                try:
                    session.cookies.clear()
                finally:
                    session.close()
            except Exception:
                pass

    def _now(self) -> float:
        try:
            now = self._clock()
            if (self._closed or type(now) not in (int, float) or not math.isfinite(now)
                    or not self._last_time <= now <= 2**53):
                raise ValueError
            self._last_time = now
            return now
        except Exception:
            self._close_unlocked()
            raise AuthenticationRejected("authentication_rejected") from None

    @staticmethod
    def _monotonic() -> float:
        value = time.monotonic()
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError
        return value

    def _read_json(self, method: str, url: str, maximum: int, deadline: float,
                   data: dict[str, str] | None = None) -> tuple[dict, dict[str, str]]:
        # Only private call sites select URLs/method/body. No public request or
        # transport argument exists. The session is not reused for other work.
        response = None
        session = self._session
        if self._closed or session is None:
            raise ValueError
        try:
            started = self._monotonic()
            if started >= deadline:
                raise ValueError
            session.cookies.clear()
            response = session.request(method, url, data=data,
                headers={"Accept": "application/json", "Accept-Encoding": "identity"},
                timeout=(3, 5), allow_redirects=False, stream=True, verify=True,
                proxies={}, auth=None, hooks={})
            received = self._monotonic()
            if received < started or received >= deadline:
                raise ValueError
            headers = _headers(response, url, maximum)
            body_deadline = min(deadline, received + _BODY_SECONDS)
            chunks = []
            size = 0
            previous = received
            while True:
                before = self._monotonic()
                if not previous <= before < body_deadline:
                    raise ValueError
                # read1 performs at most one underlying buffered read. Never
                # ask urllib3 to decompress or buffer an unbounded response.
                chunk = response.raw.read1(min(_READ_BYTES, maximum + 1 - size), decode_content=False)
                after = self._monotonic()
                if not before <= after < body_deadline:
                    raise ValueError
                previous = after
                if type(chunk) is not bytes or len(chunk) > min(_READ_BYTES, maximum + 1 - size):
                    raise ValueError
                if not chunk:
                    break
                size += len(chunk)
                if size > maximum:
                    raise ValueError
                chunks.append(chunk)
            if size == 0 or ("content-length" in headers and int(headers["content-length"]) != size):
                raise ValueError
            payload = json.loads(b"".join(chunks).decode("utf-8"),
                                 object_pairs_hook=_pairs, parse_constant=_nonfinite)
            if type(payload) is not dict or "error" in payload:
                raise ValueError
            return payload, headers
        finally:
            try:
                if response is not None:
                    response.close()
            finally:
                session.cookies.clear()

    def _key_verifier(self, deadline: float) -> StagingIdTokenVerifier:
        started = self._now()
        if self._verifier is not None and started < self._valid_until:
            return self._verifier
        self._verifier = None
        self._valid_until = 0
        payload, headers = self._read_json("GET", CERTIFICATE_URL, _CERTIFICATE_BYTES, deadline)
        received = self._now()
        directives: dict[str, str] = {}
        for item in headers.get("cache-control", "").split(","):
            name, _, value = item.strip().lower().partition("=")
            if not name or name in directives:
                raise ValueError
            directives[name] = value.strip()
        if (set(directives) & {"no-cache", "no-store", "private"}
                or not re.fullmatch(r"[0-9]{1,8}", directives.get("max-age", ""))):
            raise ValueError
        date = parsedate_to_datetime(headers["date"])
        if date.tzinfo is None or date.utcoffset().total_seconds() != 0 or date.timestamp() > received:
            raise ValueError
        age = headers.get("age", "0")
        if not re.fullmatch(r"[0-9]{1,8}", age):
            raise ValueError
        # RFC 9111 corrected age accounts for both observed Age and response delay.
        corrected_age = max(received - date.timestamp(), int(age) + received - started)
        remaining = int(directives["max-age"]) - corrected_age
        valid_until = math.floor(received + min(remaining, self._max_cache_seconds))
        if valid_until <= received or not 1 <= len(payload) <= 8:
            raise ValueError
        pems = {}
        for kid, value in payload.items():
            if (type(value) is not str or not value.startswith("-----BEGIN CERTIFICATE-----")
                    or not value.isascii() or len(value) > 16384):
                raise ValueError
            pems[kid] = value.encode("ascii")
            certificate = x509.load_pem_x509_certificate(pems[kid])
            valid_until = min(valid_until, int(certificate.not_valid_after_utc.timestamp()))
        verifier = StagingIdTokenVerifier(audience=self._client_id,
            owner_subject=self._owner_subject, trusted_pems=pems, keys_valid_until=valid_until,
            enabled=True, clock=self._now)
        self._now()
        self._verifier, self._valid_until = verifier, valid_until
        return verifier

    def authenticate(self, *, code: object, flow: CodeExchangeInputs) -> VerifiedOwnerClaims:
        """Trusted server call after the browser-bound flow has been consumed."""
        with self._lock:
            try:
                self._now()
                if (type(code) is not str or not 1 <= len(code) <= 4096
                        or any(ord(c) < 33 or ord(c) > 126 for c in code)
                        or type(flow) is not CodeExchangeInputs
                        or type(flow.nonce) is not str or not _FLOW_VALUE.fullmatch(flow.nonce)
                        or type(flow.code_verifier) is not str or not _FLOW_VALUE.fullmatch(flow.code_verifier)):
                    raise ValueError
                started = self._monotonic()
                deadline = started + _EXCHANGE_SECONDS
                payload, _headers_ignored = self._read_json("POST", TOKEN_URL, _TOKEN_BYTES, deadline, {
                    "client_id": self._client_id, "client_secret": self._client_secret,
                    "code": code, "code_verifier": flow.code_verifier,
                    "grant_type": "authorization_code", "redirect_uri": self._callback,
                })
                self._now()
                token = payload.get("id_token")
                if type(token) is not str or not 1 <= len(token) <= 16384 or payload.get("token_type", "Bearer") != "Bearer":
                    raise ValueError
                claims = self._key_verifier(deadline).verify(token, expected_nonce=flow.nonce)
                self._now()
                finished = self._monotonic()
                if not started <= finished < deadline or type(claims) is not VerifiedOwnerClaims:
                    raise ValueError
                return claims
            except Exception:
                raise AuthenticationRejected("authentication_rejected") from None

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()
