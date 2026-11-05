"""Offline staging-boundary rehearsal. NOT authentication or a hosted service.

Caller-supplied claims below are explicitly synthetic fixtures. No result from
this module is an authenticated principal, cookie, token, or deployment grant.
Production identity modules are neither imported nor modified. No network,
listener, credential loader, production storage path, or environment activation
switch is provided. Real staging OIDC remains a separate reviewed integration.
"""

from __future__ import annotations

import hmac
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PRODUCTION_ORIGIN = "https://miscon.phireij.cloud"
PRODUCTION_CLIENT_ID = "531519060424-c2n6uclfuko18tubr9ejs9o2fhf8s4c1.apps.googleusercontent.com"
GOOGLE_ISSUER = "https://accounts.google.com"
FIXTURE_OPT_IN = "ruby-owner-staging-offline-fixtures-v1"


class StagingRehearsalError(ValueError):
    """Bounded error code without owner, credential, or claim values."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise StagingRehearsalError(code)


def _text(value: object, maximum: int = 255) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum and value.isascii() and all("!" <= c <= "~" for c in value)


@dataclass(frozen=True)
class StagingRehearsalProfile:
    enabled: bool = False
    origin: str = ""
    callback: str = ""
    client_id: str = ""
    owner_subject: str = ""
    issuer: str = GOOGLE_ISSUER
    synthetic_only: bool = True
    provider_dispatch: bool = False

    def validate(self) -> None:
        _require(self.enabled is True, "rehearsal_disabled")
        _require(self.synthetic_only is True and self.provider_dispatch is False, "synthetic_only_required")
        _require(_text(self.origin) and re.fullmatch(r"https://[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", self.origin) is not None, "origin_invalid")
        _require(self.origin != PRODUCTION_ORIGIN, "production_origin_forbidden")
        _require(self.callback == self.origin + "/auth/google/callback", "callback_mismatch")
        _require(_text(self.client_id) and re.fullmatch(r"[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", self.client_id) is not None, "client_id_invalid")
        _require(self.client_id != PRODUCTION_CLIENT_ID, "production_client_forbidden")
        _require(_text(self.owner_subject), "owner_binding_required")
        _require(self.issuer == GOOGLE_ISSUER, "issuer_mismatch")

    def check_registration_fixture(self, registration: Mapping[str, object]) -> None:
        self.validate()
        _require(isinstance(registration, Mapping) and set(registration) == {"issuer", "client_id", "callback"}, "registration_fields_invalid")
        _require(registration["issuer"] == self.issuer, "issuer_mismatch")
        _require(registration["client_id"] == self.client_id, "audience_mismatch")
        _require(registration["callback"] == self.callback, "callback_mismatch")

    def check_request_fixture(self, headers: tuple[tuple[str, str], ...]) -> None:
        self.validate()
        _require(isinstance(headers, tuple), "headers_invalid")
        values: dict[str, list[str]] = {}
        for pair in headers:
            _require(isinstance(pair, tuple) and len(pair) == 2 and all(isinstance(v, str) for v in pair), "headers_invalid")
            name, value = pair
            values.setdefault(name.lower(), []).append(value)
        _require(set(values) == {"host", "origin"} and all(len(v) == 1 for v in values.values()), "headers_invalid")
        _require(values["host"] == [self.origin.removeprefix("https://")], "host_mismatch")
        _require(values["origin"] == [self.origin], "origin_mismatch")


@dataclass(frozen=True)
class FixtureCheckResult:
    synthetic_fixture_accepted: bool = True
    authority: str = "none"


class SyntheticCallbackRehearsal:
    """Single-use fixture checks, never an OIDC verifier or a session issuer."""

    def __init__(self, profile: StagingRehearsalProfile, *, opt_in: str, clock=time.monotonic, wall_clock=time.time):
        profile.validate()
        _require(opt_in == FIXTURE_OPT_IN, "fixture_opt_in_required")
        self.profile = profile
        self._clock = clock
        self._wall_clock = wall_clock
        self._pending: dict[str, tuple[str, str, float]] = {}
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def begin_fixture(self, *, state: str, nonce: str, browser_binding: str) -> None:
        _require(all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{16,128}", v) for v in (state, nonce, browser_binding)), "fixture_challenge_invalid")
        with self._lock:
            now = self._clock()
            self._pending = {k: v for k, v in self._pending.items() if 0 <= now - v[2] <= 300}
            _require(state not in self._seen, "fixture_state_duplicate")
            _require(len(self._pending) < 16, "fixture_capacity_exceeded")
            _require(len(self._seen) < 256, "fixture_lifetime_capacity_exceeded")
            self._seen.add(state)
            self._pending[state] = (nonce, browser_binding, now)

    def check_callback_fixture(self, *, state: str, browser_binding: str, headers: tuple[tuple[str, str], ...], registration: Mapping[str, object], claims_fixture: Mapping[str, object]) -> FixtureCheckResult:
        # Consume before validation: a failed attempt cannot be corrected/replayed.
        _require(isinstance(state, str), "fixture_state_invalid")
        with self._lock:
            pending = self._pending.pop(state, None)
        _require(pending is not None, "fixture_state_missing_or_consumed")
        nonce, expected_browser, created_at = pending
        _require(0 <= self._clock() - created_at <= 300, "fixture_flow_expired")
        _require(_text(browser_binding) and hmac.compare_digest(browser_binding, expected_browser), "fixture_browser_mismatch")
        self.profile.check_request_fixture(headers)
        self.profile.check_registration_fixture(registration)
        required = {"iss", "aud", "sub", "nonce", "iat", "exp"}
        _require(isinstance(claims_fixture, Mapping) and required <= set(claims_fixture) <= required | {"nbf"}, "fixture_claims_invalid")
        _require(claims_fixture["iss"] == self.profile.issuer, "issuer_mismatch")
        _require(claims_fixture["aud"] == self.profile.client_id, "audience_mismatch")
        _require(_text(claims_fixture["sub"]) and hmac.compare_digest(claims_fixture["sub"], self.profile.owner_subject), "owner_mismatch")
        _require(_text(claims_fixture["nonce"]) and hmac.compare_digest(claims_fixture["nonce"], nonce), "nonce_mismatch")
        for field in ("iat", "exp", "nbf"):
            if field in claims_fixture:
                value = claims_fixture[field]
                _require(type(value) in (int, float) and -(2**53) <= value <= 2**53 and math.isfinite(value), "fixture_time_invalid")
        now = self._wall_clock()
        _require(claims_fixture["iat"] <= now < claims_fixture["exp"] and claims_fixture["exp"] > claims_fixture["iat"], "fixture_token_expired_or_future")
        _require(claims_fixture.get("nbf", now) <= now, "fixture_not_before_invalid")
        return FixtureCheckResult()


def _reject_ambient_configuration() -> None:
    credential_names = {"OPENAI_API_KEY", "TWILIO_AUTH_TOKEN", "DATABASE_URL", "GOOGLE_APPLICATION_CREDENTIALS"}
    _require(not any(value and (key.startswith("MISSION_CONTROL_") or key in credential_names) for key, value in os.environ.items()), "ambient_runtime_configuration_forbidden")


class DisposableStagingRehearsal:
    """Own synthetic local files only. No server or production path accepted.

    This is an offline fixture composition, NOT a hosted owner-authentication
    boundary. The binding remains process-local and is never attached to the
    production session handler. Its encryption key is disposable fixture data,
    not an OAuth/client credential or access grant.
    """

    def __init__(self, profile: StagingRehearsalProfile, *, opt_in: str):
        profile.validate()
        _require(opt_in == FIXTURE_OPT_IN, "fixture_opt_in_required")
        _reject_ambient_configuration()
        from ruby_review_synthetic_harness import DisposableRubySyntheticHarness, HARNESS_OPT_IN

        self._temporary = tempfile.TemporaryDirectory(prefix="ruby-owner-staging-rehearsal-", dir="/tmp")
        self._closed = False
        try:
            self._harness = DisposableRubySyntheticHarness.create(
                storage_scope=Path(self._temporary.name),
                opt_in=HARNESS_OPT_IN,
                owner_subject=profile.owner_subject,
                issuer=profile.issuer,
            )
        except Exception:
            self._temporary.cleanup()
            raise

    @property
    def fixture_binding(self):
        _require(not self._closed, "rehearsal_closed")
        _reject_ambient_configuration()
        return self._harness.binding

    @property
    def fixture_directory(self) -> Path:
        _require(not self._closed, "rehearsal_closed")
        return self._harness.run_directory

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._harness.binding.records = ()
            try:
                self._harness.binding.store.close()
            finally:
                try:
                    self._harness.cleanup()
                finally:
                    self._temporary.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()
