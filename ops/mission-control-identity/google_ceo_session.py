"""Inactive CEO-only Google session service; no conversation routes or storage.

The service cannot start without explicit enablement and protected files. A
reviewed deployment must replace the identity probe; this module does not
alter any existing Mission Control gateway or workload.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from google_identity_probe import (
    COOKIE_NAME as FLOW_COOKIE,
    FlowStore,
    ProbeHandler,
    _cookie_value,
    _single_query_value,
    exchange_verified_subject,
)
from google_oidc_config import GoogleOidcConfig, ISSUER


SESSION_COOKIE = "__Host-mc-ceo-session"
ORIGIN = "https://miscon.phireij.cloud"
IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 8 * 60 * 60
MAX_SESSIONS = 16


def load_ceo_subject(path: Path) -> str:
    """Read an exact issuer/subject pair from a protected configuration file."""
    parts = path.read_text(encoding="utf-8").strip().split("|")
    if len(parts) != 2 or parts[0] != ISSUER or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", parts[1]):
        raise ValueError("ceo_binding_invalid")
    return parts[1]


@dataclass
class LiveSession:
    csrf_token: str
    issued_at: float
    last_seen: float


class SessionStore:
    def __init__(self, clock: object = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[bytes, LiveSession] = {}

    def _expire(self, now: float) -> None:
        for digest, item in tuple(self._sessions.items()):
            if now - item.issued_at >= ABSOLUTE_SECONDS or now - item.last_seen >= IDLE_SECONDS:
                del self._sessions[digest]

    @staticmethod
    def _digest(token: str) -> bytes | None:
        if not isinstance(token, str) or not (32 <= len(token) <= 128) or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            return None
        return hashlib.sha256(token.encode("ascii")).digest()

    def issue(self) -> tuple[str, LiveSession] | None:
        with self._lock:
            now = self._clock()  # type: ignore[operator]
            self._expire(now)
            if len(self._sessions) >= MAX_SESSIONS:
                return None
            token = secrets.token_urlsafe(48)
            item = LiveSession(secrets.token_urlsafe(32), now, now)
            self._sessions[hashlib.sha256(token.encode("ascii")).digest()] = item
            return token, item

    def get(self, token: str) -> LiveSession | None:
        digest = self._digest(token)
        if digest is None:
            return None
        with self._lock:
            now = self._clock()  # type: ignore[operator]
            self._expire(now)
            item = self._sessions.get(digest)
            if item is not None:
                item.last_seen = now
            return item

    def revoke(self, token: str) -> None:
        digest = self._digest(token)
        if digest is not None:
            with self._lock:
                self._sessions.pop(digest, None)

    def revoke_all(self) -> None:
        with self._lock:
            self._sessions.clear()


def _session_cookie(header: str) -> str:
    matches = []
    for segment in header.split(";"):
        name, separator, value = segment.strip().partition("=")
        if separator and name == SESSION_COOKIE:
            matches.append(value)
    return matches[0] if len(matches) == 1 else ""


class SessionHandler(ProbeHandler):
    server_version = "MissionControlGoogleCeoSession/0.1"

    def _send(
        self,
        status: HTTPStatus,
        body: str,
        *,
        location: str | None = None,
        cookie: str | None = None,
        cookies: tuple[str, ...] = (),
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if location:
            self.send_header("Location", location)
        for value in ((cookie,) if cookie else ()) + cookies:
            self.send_header("Set-Cookie", value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        path = urlsplit(self.path)
        if self.headers.get("Host") != "miscon.phireij.cloud":
            self._send(HTTPStatus.BAD_REQUEST, "Invalid host")
        elif path.path == "/auth/google/start" and not path.query:
            self._start()
        elif path.path == "/auth/google/callback":
            self._callback(path.query)
        elif path.path == "/auth/google/session" and not path.query:
            self._session()
        elif path.path == "/auth/google/healthz" and not path.query:
            self._send(HTTPStatus.OK, "session_ready;conversation_authority=none")
        else:
            self._send(HTTPStatus.NOT_FOUND, "Not found")

    def _callback(self, query: str) -> None:
        state = _single_query_value(query, "state", 128)
        code = _single_query_value(query, "code", 4096)
        flow = self.server.flows.take(state) if state and code else None  # type: ignore[attr-defined]
        browser = _cookie_value(self.headers.get("Cookie", ""))
        clear_flow = f"{FLOW_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"
        if not flow or not browser or not hmac.compare_digest(
            hashlib.sha256(browser.encode("utf-8")).digest(), flow.browser_hash
        ):
            self._send(HTTPStatus.UNAUTHORIZED, "Sign-in could not be verified", cookie=clear_flow)
            return
        previous = _session_cookie(self.headers.get("Cookie", ""))
        self.server.sessions.revoke(previous)  # type: ignore[attr-defined]
        clear_session = f"{SESSION_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"
        try:
            subject = exchange_verified_subject(code, flow, self.server.secret_file)  # type: ignore[attr-defined]
        except Exception:
            self._send(HTTPStatus.BAD_GATEWAY, "Google sign-in could not be completed", cookies=(clear_flow, clear_session))
            return
        if not hmac.compare_digest(subject, self.server.ceo_subject):  # type: ignore[attr-defined]
            self._send(HTTPStatus.FORBIDDEN, "Account is not authorized", cookies=(clear_flow, clear_session))
            return
        issued = self.server.sessions.issue()  # type: ignore[attr-defined]
        if issued is None:
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "Session capacity reached", cookies=(clear_flow, clear_session))
            return
        token, _item = issued
        session_cookie = f"{SESSION_COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Lax"
        body = (
            "<!doctype html><html><head><title>CEO session</title></head><body>"
            "<h1>CEO sign-in complete</h1><p>No conversation access is active.</p>"
            "</body></html>"
        )
        self._send(HTTPStatus.OK, body, cookies=(clear_flow, session_cookie))

    def _session(self) -> None:
        token = _session_cookie(self.headers.get("Cookie", ""))
        item = self.server.sessions.get(token)  # type: ignore[attr-defined]
        if item is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"authenticated":false}', content_type="application/json; charset=utf-8")
            return
        body = json.dumps({
            "authenticated": True,
            "scope": "mission_control:session",
            "conversation_authority": False,
            "idle_seconds": IDLE_SECONDS,
            "absolute_seconds": ABSOLUTE_SECONDS,
            "csrf_token": item.csrf_token,
        }, separators=(",", ":"))
        self._send(HTTPStatus.OK, body, content_type="application/json; charset=utf-8")

    def do_POST(self) -> None:
        path = urlsplit(self.path)
        if self.headers.get("Host") != "miscon.phireij.cloud":
            self._send(HTTPStatus.BAD_REQUEST, "Invalid host")
            return
        if path.path != "/auth/google/logout" or path.query:
            self._send(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")
            return
        if self.headers.get("Origin") != ORIGIN or self.headers.get("Transfer-Encoding") or self.headers.get("Content-Length", "0") != "0":
            self._send(HTTPStatus.FORBIDDEN, "Request not authorized")
            return
        token = _session_cookie(self.headers.get("Cookie", ""))
        item = self.server.sessions.get(token)  # type: ignore[attr-defined]
        supplied = self.headers.get("X-MC-CSRF", "")
        if item is None or len(supplied) > 128 or not hmac.compare_digest(item.csrf_token, supplied):
            self._send(HTTPStatus.FORBIDDEN, "Request not authorized")
            return
        self.server.sessions.revoke(token)  # type: ignore[attr-defined]
        clear = f"{SESSION_COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"
        self._send(HTTPStatus.OK, "Signed out", cookie=clear)


def main() -> None:
    config = GoogleOidcConfig.from_environment()
    subject = load_ceo_subject(config.ceo_subject_file)
    server = ThreadingHTTPServer(("0.0.0.0", 8093), SessionHandler)
    server.flows = FlowStore()  # type: ignore[attr-defined]
    server.sessions = SessionStore()  # type: ignore[attr-defined]
    server.secret_file = config.client_secret_file  # type: ignore[attr-defined]
    server.ceo_subject = subject  # type: ignore[attr-defined]
    server.serve_forever()


if __name__ == "__main__":
    main()
