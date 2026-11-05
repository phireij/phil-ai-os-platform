"""Inactive, in-memory primitives for a future Ruby staging login adapter.

This is NOT an identity verifier or HTTP service. The caller of SessionStore.issue
must already have verified the Google signature/claims and exact owner binding.
Nothing imports or invokes this module from a production path. Explicit local
enablement exercises the primitives, not authentication, hosting or provider access.
No environment variables, files, sockets, production modules or secret stores are
read. Policies have no deployment defaults. All state dies with this instance.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable


FLOW_COOKIE = "__Host-ruby-staging-flow"
SESSION_COOKIE = "__Host-ruby-staging-session"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{64}", re.ASCII)
_COOKIE_NAMES = frozenset((FLOW_COOKIE, SESSION_COOKIE))


class LifecycleError(ValueError):
    """Fixed, non-secret error codes only."""


def _positive_int(value: object, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise LifecycleError(name)
    return value


def _digest(token: object) -> bytes | None:
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        return None
    return hashlib.sha256(token.encode("ascii")).digest()


def _new_token() -> str:
    token = secrets.token_urlsafe(48)
    if _digest(token) is None:
        raise LifecycleError("entropy_invalid")
    return token


def pkce_challenge(verifier: str) -> str:
    """S256 only; the verifier stays server-side until the code exchange."""
    if _digest(verifier) is None:
        raise LifecycleError("verifier_invalid")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class _EphemeralStore:
    def __init__(self, *, enabled: bool, clock: Callable[[], float]) -> None:
        if enabled is not True:
            raise LifecycleError("lifecycle_inactive")
        self._clock = clock
        self._lock = threading.Lock()
        self._last_clock: float | None = None
        self._closed = False

    def _now(self) -> float:
        if self._closed:
            raise LifecycleError("lifecycle_closed")
        try:
            now = self._clock()
            valid = type(now) in (int, float) and math.isfinite(now) and now >= 0
        except Exception:
            valid = False
        if not valid or (self._last_clock is not None and now < self._last_clock):
            self._closed = True
            self._clear()
            raise LifecycleError("clock_invalid")
        self._last_clock = now
        return now

    def _clear(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._clear()


@dataclass(frozen=True)
class FlowStart:
    state: str = field(repr=False)
    browser_token: str = field(repr=False)
    nonce: str = field(repr=False)
    code_challenge: str
    code_challenge_method: str = "S256"


@dataclass(frozen=True)
class CodeExchangeInputs:
    """Internal server values, not a principal or a verified identity."""

    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)


@dataclass(frozen=True)
class _PendingFlow:
    browser_hash: bytes = field(repr=False)
    exchange: CodeExchangeInputs = field(repr=False)
    created_at: float


class LoginFlowStore(_EphemeralStore):
    """One fixed server adapter/client/callback per store; never share instances.

    The eventual adapter binds its configured client and callback to this store,
    sends state/nonce/challenge to Google, and keeps browser_token in the separate
    flow cookie. An attempt consumes the matching state BEFORE browser validation.
    Returned exchange inputs still require real code exchange and ID-token checks.
    """

    def __init__(self, *, ttl_seconds: int, capacity: int,
                 enabled: bool = False, clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(enabled=enabled, clock=clock)
        self._ttl = _positive_int(ttl_seconds, "flow_ttl_invalid", 3600)
        self._capacity = _positive_int(capacity, "flow_capacity_invalid", 1024)
        self._flows: dict[bytes, _PendingFlow] = {}

    def _clear(self) -> None:
        self._flows.clear()

    def _expire(self, now: float) -> None:
        for digest, flow in tuple(self._flows.items()):
            if now - flow.created_at >= self._ttl:
                del self._flows[digest]

    def start(self) -> FlowStart:
        with self._lock:
            now = self._now()
            self._expire(now)
            if len(self._flows) >= self._capacity:
                raise LifecycleError("flow_capacity_reached")
            # Never overwrite a pending challenge, even if the RNG fails.
            for _ in range(4):
                state = _new_token()
                state_hash = _digest(state)
                if state_hash not in self._flows:
                    break
            else:
                raise LifecycleError("entropy_collision")
            browser, nonce, verifier = _new_token(), _new_token(), _new_token()
            self._flows[state_hash] = _PendingFlow(  # type: ignore[index]
                _digest(browser), CodeExchangeInputs(nonce, verifier), now  # type: ignore[arg-type]
            )
            return FlowStart(state, browser, nonce, pkce_challenge(verifier))

    def take(self, state: object, browser_token: object) -> CodeExchangeInputs | None:
        with self._lock:
            now = self._now()
            self._expire(now)
            state_hash = _digest(state)
            flow = self._flows.pop(state_hash, None) if state_hash is not None else None
            browser_hash = _digest(browser_token)
            if flow is None or browser_hash is None:
                return None
            if not hmac.compare_digest(flow.browser_hash, browser_hash):
                return None
            return flow.exchange

    def revoke_all(self) -> None:
        """Invalidate pending logins, for example after an owner logs out."""
        with self._lock:
            self._now()
            self._clear()


@dataclass(frozen=True)
class SessionReceipt:
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)


@dataclass(frozen=True)
class SessionSnapshot:
    issued_at: float
    last_seen: float


@dataclass
class _Session:
    csrf_hash: bytes = field(repr=False)
    issued_at: float
    last_seen: float


class SessionStore(_EphemeralStore):
    """Opaque token storage ONLY, callable only after server-side owner verification.

    There is deliberately no issue-from-claims, request adapter or identity input.
    A successful lookup proves possession of a locally issued token, not Google
    identity. Initial issue is trusted caller work; rotation requires the current
    live token and is atomic. No cookie value is adopted as a new session ID.
    """

    def __init__(self, *, idle_seconds: int, absolute_seconds: int, capacity: int,
                 enabled: bool = False, clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(enabled=enabled, clock=clock)
        self._idle = _positive_int(idle_seconds, "idle_timeout_invalid", 86400)
        self._absolute = _positive_int(absolute_seconds, "absolute_timeout_invalid", 86400)
        if self._idle > self._absolute:
            raise LifecycleError("timeout_order_invalid")
        self._capacity = _positive_int(capacity, "session_capacity_invalid", 1024)
        self._sessions: dict[bytes, _Session] = {}

    def _clear(self) -> None:
        self._sessions.clear()

    def _expire(self, now: float) -> None:
        for digest, session in tuple(self._sessions.items()):
            if now - session.issued_at >= self._absolute or now - session.last_seen >= self._idle:
                del self._sessions[digest]

    def issue(self, *, previous_token: str | None = None) -> SessionReceipt:
        """Use only after fresh owner verification; not as an HTTP operation.

        If rotation is requested, failure to find that live session fails closed.
        After a valid rotation starts, its old token remains revoked on any error.
        """
        with self._lock:
            now = self._now()
            self._expire(now)
            previous_hash = _digest(previous_token)
            if previous_token is not None:
                if previous_hash is None or self._sessions.pop(previous_hash, None) is None:
                    raise LifecycleError("rotation_session_missing")
            if len(self._sessions) >= self._capacity:
                raise LifecycleError("session_capacity_reached")
            for _ in range(4):
                token = _new_token()
                token_hash = _digest(token)
                if token_hash != previous_hash and token_hash not in self._sessions:
                    break
            else:
                raise LifecycleError("entropy_collision")
            csrf = _new_token()
            self._sessions[token_hash] = _Session(_digest(csrf), now, now)  # type: ignore[index,arg-type]
            return SessionReceipt(token, csrf)

    def lookup(self, token: object, *, csrf_token: object = None,
               require_csrf: bool = False) -> SessionSnapshot | None:
        """A write adapter must additionally check exact Origin and HTTP method.

        Failed lookups and failed CSRF checks never refresh idle expiry. A returned
        immutable snapshot cannot mutate stored session times or CSRF state.
        """
        if type(require_csrf) is not bool:
            raise LifecycleError("csrf_mode_invalid")
        with self._lock:
            now = self._now()
            self._expire(now)
            digest = _digest(token)
            session = self._sessions.get(digest) if digest is not None else None
            if session is None:
                return None
            if require_csrf:
                supplied = _digest(csrf_token)
                if supplied is None or not hmac.compare_digest(session.csrf_hash, supplied):
                    return None
            session.last_seen = now
            return SessionSnapshot(session.issued_at, session.last_seen)

    def revoke(self, token: object) -> None:
        with self._lock:
            self._now()
            digest = _digest(token)
            if digest is not None:
                self._sessions.pop(digest, None)

    def rotate_csrf(self, token: object) -> str | None:
        """Return a new CSRF challenge for an EXISTING valid session only.

        A same-origin, non-cacheable session/page response may deliver this value
        after a login redirect. Only its hash is retained. It cannot create or
        replace a session; older challenges stop working after a successful call.
        The HTTP adapter must prohibit cross-origin reads and require exact Origin
        plus the challenge for writes. Multiple tabs may need to reload a form.
        """
        with self._lock:
            now = self._now()
            self._expire(now)
            digest = _digest(token)
            session = self._sessions.get(digest) if digest is not None else None
            if session is None:
                return None
            csrf = _new_token()
            session.csrf_hash = _digest(csrf)  # type: ignore[assignment]
            session.last_seen = now
            return csrf

    def revoke_all(self) -> None:
        with self._lock:
            self._now()
            self._clear()


def serialize_cookie(name: str, token: str | None = None) -> str:
    """Fixed staging host-only cookies. None expires the named cookie."""
    if name not in _COOKIE_NAMES:
        raise LifecycleError("cookie_name_invalid")
    if token is not None and _digest(token) is None:
        raise LifecycleError("cookie_token_invalid")
    value = f"{name}={token or ''}; Path=/; Secure; HttpOnly; SameSite=Lax"
    return value + "; Max-Age=0" if token is None else value


def read_cookie(headers: list[str] | tuple[str, ...], name: str) -> str | None:
    """Pass ALL Cookie header values; never a last-header-only convenience value.

    Reject duplicate target cookies, quoted/invalid target tokens, controls and
    oversized input. Unrelated cookie pairs are ignored, not authorization inputs.
    """
    if name not in _COOKIE_NAMES:
        raise LifecycleError("cookie_name_invalid")
    if type(headers) not in (list, tuple) or len(headers) > 16:
        return None
    if any(not isinstance(raw, str) for raw in headers):
        return None
    if sum(len(raw) for raw in headers) > 8192:
        return None
    matches: list[str] = []
    for raw in headers:
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in raw):
            return None
        for segment in raw.split(";"):
            key, separator, value = segment.strip().partition("=")
            if key.strip() == name:
                if not separator or key != name or _digest(value) is None:
                    return None
                matches.append(value)
    return matches[0] if len(matches) == 1 else None
