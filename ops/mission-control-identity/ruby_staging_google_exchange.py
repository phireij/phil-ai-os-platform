"""Offline Google exchange protocol integrated with synthetic review fixtures.

There is deliberately NO network implementation or credential argument/loader.
Only the exact in-memory fixture transport is accepted. Fixed request intents
exercise the existing Core endpoints and client-secret-post shape with a public
synthetic placeholder. Parsing/cache policy is real code; fixture responses do
NOT establish Google TLS/key provenance. Never expose this module as a service.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Callable

import requests
from cryptography import x509

from ruby_staging_id_token import StagingIdTokenVerifier, VerifiedOwnerClaims
from ruby_staging_lifecycle import CodeExchangeInputs
from ruby_staging_rehearsal import StagingRehearsalProfile


TOKEN_URL = "https://oauth2.googleapis.com/token"
CERTIFICATE_URL = "https://www.googleapis.com/oauth2/v1/certs"
OFFLINE_EXCHANGE_OPT_IN = "ruby-staging-offline-google-exchange-v1"
_SYNTHETIC_SECRET = "synthetic-fixture-only-not-a-google-credential"
_TOKEN_BYTES = 65536
_CERTIFICATE_BYTES = 131072
_FLOW_VALUE = re.compile(r"[A-Za-z0-9_-]{64}", re.ASCII)


class OfflineExchangeRejected(ValueError):
    """Fixed redacted failure; no code, PKCE, token or upstream error text."""


@dataclass(frozen=True)
class FixtureHTTPRequest:
    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    body: bytes = field(repr=False)
    maximum_response_bytes: int
    timeout: tuple[int, int] = (3, 5)
    allow_redirects: bool = False
    trust_environment: bool = False


@dataclass(frozen=True)
class FixtureHTTPResponse:
    status: int
    final_url: str
    headers: tuple[tuple[str, str], ...] = field(repr=False)
    body: bytes = field(repr=False)


class OfflineGoogleFixtureTransport:
    """Bounded in-memory cassette, not an extensible/live transport adapter.

    Requests are retained only for explicit fixture assertions, with secret
    bodies excluded from repr. close() clears cassette and observations. There
    are no callbacks, sockets, external reads, automatic retries or redirects.
    """

    __slots__ = ("_replies", "_requests", "_closed", "_lock")

    def __init__(self) -> None:
        self._replies: list[FixtureHTTPResponse] = []
        self._requests: list[FixtureHTTPRequest] = []
        self._closed = False
        self._lock = threading.Lock()

    def enqueue(self, response: FixtureHTTPResponse) -> None:
        with self._lock:
            if self._closed or type(response) is not FixtureHTTPResponse or len(self._replies) >= 64:
                raise OfflineExchangeRejected("offline_exchange_rejected")
            self._replies.append(response)

    def send(self, request: FixtureHTTPRequest) -> FixtureHTTPResponse:
        with self._lock:
            if self._closed or type(request) is not FixtureHTTPRequest or not self._replies or len(self._requests) >= 64:
                raise OfflineExchangeRejected("offline_exchange_rejected")
            self._requests.append(request)
            return self._replies.pop(0)

    @property
    def requests(self) -> tuple[FixtureHTTPRequest, ...]:
        with self._lock:
            return tuple(self._requests)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._requests.clear()
            self._replies.clear()


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _nonfinite(_value: str):
    raise ValueError


def _response(response: FixtureHTTPResponse, request: FixtureHTTPRequest) -> tuple[dict, dict[str, str]]:
    if (type(response) is not FixtureHTTPResponse or type(response.status) is not int
            or response.status != 200 or type(response.final_url) is not str or response.final_url != request.url
            or type(response.body) is not bytes or not 1 <= len(response.body) <= request.maximum_response_bytes
            or type(response.headers) is not tuple or len(response.headers) > 32):
        raise ValueError
    headers: dict[str, str] = {}
    total = 0
    for pair in response.headers:
        if type(pair) is not tuple or len(pair) != 2 or any(type(v) is not str for v in pair):
            raise ValueError
        name, value = pair
        total += len(name) + len(value)
        if (total > 8192 or not re.fullmatch(r"[A-Za-z0-9-]+", name)
                or any(ord(c) < 32 or ord(c) > 126 for c in value)
                or name.lower() in headers):
            raise ValueError
        headers[name.lower()] = value
    if "location" in headers or headers.get("content-encoding", "identity").lower() != "identity":
        raise ValueError
    if headers.get("content-type", "").lower() not in ("application/json", "application/json; charset=utf-8"):
        raise ValueError
    if "content-length" in headers and (not re.fullmatch(r"[0-9]{1,6}", headers["content-length"])
            or int(headers["content-length"]) != len(response.body)):
        raise ValueError
    result = json.loads(response.body.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite)
    if type(result) is not dict or "error" in result:
        raise ValueError
    return result, headers


class OfflineGoogleCodeExchange:
    """One immutable staging policy + offline transport, default-off.

    Serializes exchanges and key refresh. Key freshness uses conservative HTTP
    Date/Age/max-age accounting, the caller's explicit TTL cap, and certificate
    validity. Unknown kid does not cause attacker-driven refresh. A stale cache
    is never reused after refresh failure. Clock rollback permanently closes the
    exchange. The caller must supply inputs from a consumed browser-bound flow.
    """

    def __init__(self, profile: StagingRehearsalProfile, *, transport: OfflineGoogleFixtureTransport,
                 max_cache_seconds: int, opt_in: str, enabled: bool = False,
                 clock: Callable[[], float] = time.time) -> None:
        try:
            if enabled is not True or opt_in != OFFLINE_EXCHANGE_OPT_IN:
                raise ValueError
            if type(profile) is not StagingRehearsalProfile or type(transport) is not OfflineGoogleFixtureTransport:
                raise ValueError
            profile.validate()
            if type(max_cache_seconds) is not int or not 1 <= max_cache_seconds <= 86400:
                raise ValueError
            self._profile, self._transport = profile, transport
            self._max_cache_seconds, self._clock = max_cache_seconds, clock
            self._lock = threading.RLock()
            self._closed = False
            self._last_time = 0.0
            self._verifier: StagingIdTokenVerifier | None = None
            self._valid_until = 0
            self._now()
        except Exception:
            raise OfflineExchangeRejected("offline_exchange_configuration_invalid") from None

    def _now(self) -> float:
        try:
            now = self._clock()
            if (self._closed or type(now) not in (int, float) or not math.isfinite(now)
                    or not self._last_time <= now <= 2**53):
                raise ValueError
            self._last_time = now
            return now
        except Exception:
            self._closed = True
            self._verifier = None
            raise OfflineExchangeRejected("offline_exchange_rejected") from None

    def matches_profile(self, profile: StagingRehearsalProfile) -> bool:
        return type(profile) is StagingRehearsalProfile and profile == self._profile

    def _key_verifier(self) -> StagingIdTokenVerifier:
        started = self._now()
        if self._verifier is not None and started < self._valid_until:
            return self._verifier
        self._verifier = None
        self._valid_until = 0
        request = FixtureHTTPRequest("GET", CERTIFICATE_URL, (("Accept", "application/json"),), b"", _CERTIFICATE_BYTES)
        payload, headers = _response(self._transport.send(request), request)
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
        # RFC 9111 corrected_initial_age = max(apparent_age, Age + response_delay).
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
        verifier = StagingIdTokenVerifier(audience=self._profile.client_id,
            owner_subject=self._profile.owner_subject, trusted_pems=pems,
            # Every nested verifier read must advance the SAME high-water mark.
            # Separate guards could miss rollback after crypto observed a later time.
            keys_valid_until=valid_until, enabled=True, clock=self._now)
        self._now()
        self._verifier, self._valid_until = verifier, valid_until
        return verifier

    def exchange_fixture(self, *, code_fixture: object, flow: CodeExchangeInputs) -> VerifiedOwnerClaims:
        """Trusted in-process caller only, not a callback/request entry point."""
        with self._lock:
            try:
                self._now()
                if (type(code_fixture) is not str or not 1 <= len(code_fixture) <= 4096
                        or any(ord(c) < 33 or ord(c) > 126 for c in code_fixture)
                        or type(flow) is not CodeExchangeInputs
                        or type(flow.nonce) is not str or not _FLOW_VALUE.fullmatch(flow.nonce)
                        or type(flow.code_verifier) is not str or not _FLOW_VALUE.fullmatch(flow.code_verifier)):
                    raise ValueError
                # Request preparation is pure encoding, not requests.Session/send.
                prepared = requests.Request("POST", TOKEN_URL, data={
                    "client_id": self._profile.client_id, "client_secret": _SYNTHETIC_SECRET,
                    "code": code_fixture, "code_verifier": flow.code_verifier,
                    "grant_type": "authorization_code", "redirect_uri": self._profile.callback,
                }).prepare()
                request = FixtureHTTPRequest("POST", TOKEN_URL,
                    (("Accept", "application/json"), ("Content-Type", "application/x-www-form-urlencoded")),
                    prepared.body.encode("ascii"), _TOKEN_BYTES)
                payload, _headers = _response(self._transport.send(request), request)
                self._now()
                token = payload.get("id_token")
                if type(token) is not str or not 1 <= len(token) <= 16384 or payload.get("token_type", "Bearer") != "Bearer":
                    raise ValueError
                claims = self._key_verifier().verify(token, expected_nonce=flow.nonce)
                self._now()
                return claims
            except Exception:
                raise OfflineExchangeRejected("offline_exchange_rejected") from None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._verifier = None
            self._valid_until = 0
            self._transport.close()
