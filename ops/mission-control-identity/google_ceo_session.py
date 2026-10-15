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
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from conversation_store import (
    ConversationConfig,
    ConversationRequestError,
    ConversationStore,
)
from notification_delivery import (
    NotificationConfigurationError,
    NotificationDeliveryWorker,
    TelegramDeliveryConfig,
    TelegramTransport,
)

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
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
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
            now = self._clock()
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
            now = self._clock()
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
            authority = "enabled" if self.server.conversations is not None else "none"  # type: ignore[attr-defined]
            self._send(HTTPStatus.OK, f"session_ready;conversation_authority={authority}")
        elif path.path == "/api/conversations":
            self._list_conversations(path.query)
        elif path.path == "/api/notifications":
            self._list_notifications(path.query)
        elif re.fullmatch(r"/api/conversations/[A-Za-z0-9_-]{16,200}/messages", path.path):
            self._list_messages(path.path.split("/")[3], path.query)
        elif re.fullmatch(r"/api/conversations/[A-Za-z0-9_-]{16,200}/task-proposals", path.path):
            self._list_task_proposals(path.path.split("/")[3], path.query)
        elif re.fullmatch(r"/api/conversations/[A-Za-z0-9_-]{16,200}/audit-timeline", path.path):
            self._list_audit_timeline(path.path.split("/")[3], path.query)
        elif re.fullmatch(r"/api/conversations/[A-Za-z0-9_-]{16,200}/responses/[A-Za-z0-9_-]{16,200}", path.path) and not path.query:
            parts = path.path.split("/")
            self._response_state(parts[3], parts[5])
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
        conversation_status = (
            "Conversation storage is available in the Mission Control window."
            if self.server.conversations is not None  # type: ignore[attr-defined]
            else "No conversation access is active."
        )
        body = (
            "<!doctype html><html><head><title>CEO session</title></head><body>"
            f"<h1>CEO sign-in complete</h1><p>{conversation_status}</p>"
            "<p>Returning to Mission Control.</p></body></html>"
        )
        # A callback is only a transient handoff.  Return the browser to the
        # same-origin control page after setting the host-only session cookie;
        # no token, subject, or authorization code is placed in the URL.
        self._send(
            HTTPStatus.SEE_OTHER,
            body,
            location="/?ceo_session=active",
            cookies=(clear_flow, session_cookie),
        )

    def _session(self) -> None:
        token = _session_cookie(self.headers.get("Cookie", ""))
        item = self.server.sessions.get(token)  # type: ignore[attr-defined]
        if item is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"authenticated":false}', content_type="application/json; charset=utf-8")
            return
        body = json.dumps({
            "authenticated": True,
            "scope": "mission_control:conversation" if self.server.conversations is not None else "mission_control:session",  # type: ignore[attr-defined]
            "conversation_authority": self.server.conversations is not None,  # type: ignore[attr-defined]
            "idle_seconds": IDLE_SECONDS,
            "absolute_seconds": ABSOLUTE_SECONDS,
            "csrf_token": item.csrf_token,
        }, separators=(",", ":"))
        self._send(HTTPStatus.OK, body, content_type="application/json; charset=utf-8")

    def _conversation_session(self) -> LiveSession | None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            return None
        token = _session_cookie(self.headers.get("Cookie", ""))
        return self.server.sessions.get(token)  # type: ignore[attr-defined]

    def _query_limit(self, query: str) -> int:
        if not query:
            return 50
        try:
            values = parse_qs(query, keep_blank_values=True, strict_parsing=True)
        except ValueError as exc:
            raise ConversationRequestError("invalid_query", 400) from exc
        if set(values) != {"limit"} or len(values["limit"]) != 1:
            raise ConversationRequestError("invalid_query", 400)
        try:
            return int(values["limit"][0])
        except ValueError as exc:
            raise ConversationRequestError("invalid_limit", 400) from exc

    def _audit_query(self, query: str) -> tuple[int, int]:
        if not query:
            return 50, 0
        try:
            values = parse_qs(query, keep_blank_values=True, strict_parsing=True)
        except ValueError as exc:
            raise ConversationRequestError("invalid_query", 400) from exc
        if not set(values).issubset({"limit", "cursor"}) or any(len(value) != 1 for value in values.values()):
            raise ConversationRequestError("invalid_query", 400)
        try:
            limit = int(values.get("limit", ["50"])[0])
            cursor = int(values.get("cursor", ["0"])[0])
        except ValueError as exc:
            raise ConversationRequestError("invalid_query", 400) from exc
        if limit < 1 or limit > 100 or cursor < 0 or cursor > 100_000:
            raise ConversationRequestError("invalid_query", 400)
        return limit, cursor

    def _conversation_error(self, error: ConversationRequestError) -> None:
        self._send(
            HTTPStatus(error.status),
            json.dumps({"error": error.code}, separators=(",", ":")),
            content_type="application/json; charset=utf-8",
        )

    def _list_conversations(self, query: str) -> None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            self._send(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self._conversation_session() is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"error":"unauthorized"}', content_type="application/json; charset=utf-8")
            return
        try:
            conversations = self.server.conversations.list_conversations(self._query_limit(query))  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        body = json.dumps({"conversations": conversations, "next_cursor": None}, separators=(",", ":"))
        self._send(HTTPStatus.OK, body, content_type="application/json; charset=utf-8")

    def _list_messages(self, conversation_id: str, query: str) -> None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            self._send(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self._conversation_session() is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"error":"unauthorized"}', content_type="application/json; charset=utf-8")
            return
        try:
            messages = self.server.conversations.list_messages(conversation_id, self._query_limit(query))  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        body = json.dumps({"conversation_id": conversation_id, "messages": messages, "next_cursor": None}, separators=(",", ":"))
        self._send(HTTPStatus.OK, body, content_type="application/json; charset=utf-8")

    def _response_state(self, conversation_id: str, message_id: str) -> None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            self._send(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self._conversation_session() is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"error":"unauthorized"}', content_type="application/json; charset=utf-8")
            return
        try:
            result = self.server.conversations.get_response_state(conversation_id, message_id)  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        self._send(HTTPStatus.OK, json.dumps(result, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def _list_task_proposals(self, conversation_id: str, query: str) -> None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            self._send(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self._conversation_session() is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"error":"unauthorized"}', content_type="application/json; charset=utf-8")
            return
        try:
            proposals = self.server.conversations.list_task_proposals(conversation_id, self._query_limit(query))  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error); return
        self._send(HTTPStatus.OK, json.dumps({"proposals": proposals, "next_cursor": None, "authority_effect": "none"}, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def _list_audit_timeline(self, conversation_id: str, query: str) -> None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            self._send(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self._conversation_session() is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"error":"unauthorized"}', content_type="application/json; charset=utf-8")
            return
        try:
            result = self.server.conversations.list_audit_timeline(conversation_id, *self._audit_query(query))  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        self._send(HTTPStatus.OK, json.dumps(result, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def _list_notifications(self, query: str) -> None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            self._send(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self._conversation_session() is None:
            self._send(HTTPStatus.UNAUTHORIZED, '{"error":"unauthorized"}', content_type="application/json; charset=utf-8")
            return
        try:
            result = self.server.conversations.list_notifications(*self._audit_query(query))  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        self._send(HTTPStatus.OK, json.dumps(result, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def do_POST(self) -> None:
        path = urlsplit(self.path)
        if self.headers.get("Host") != "miscon.phireij.cloud":
            self._send(HTTPStatus.BAD_REQUEST, "Invalid host")
            return
        if path.path == "/auth/google/logout" and not path.query:
            self._logout()
            return
        if path.path == "/api/conversations" and not path.query:
            self._create_conversation()
            return
        match = re.fullmatch(r"/api/conversations/([A-Za-z0-9_-]{16,200})/messages", path.path)
        if match and not path.query:
            self._submit_message(match.group(1))
            return
        match = re.fullmatch(r"/api/conversations/([A-Za-z0-9_-]{16,200})/task-proposals", path.path)
        if match and not path.query:
            self._create_task_proposal(match.group(1)); return
        match = re.fullmatch(r"/api/task-proposals/([A-Za-z0-9_-]{16,200})/decisions", path.path)
        if match and not path.query:
            self._record_task_decision(match.group(1)); return
        self._send(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")

    def _authorized_write(self, maximum_body: int) -> tuple[LiveSession, bytes] | None:
        if self.server.conversations is None:  # type: ignore[attr-defined]
            self._send(HTTPStatus.NOT_FOUND, "Not found")
            return None
        if self.headers.get("Origin") != ORIGIN or self.headers.get("Transfer-Encoding"):
            self._send(HTTPStatus.FORBIDDEN, "Request not authorized")
            return None
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send(HTTPStatus.BAD_REQUEST, "Invalid request")
            return None
        if content_length < 0 or content_length > maximum_body:
            self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request too large")
            return None
        if content_length and self.headers.get("Content-Type") != "application/json":
            self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Unsupported media type")
            return None
        token = _session_cookie(self.headers.get("Cookie", ""))
        item = self.server.sessions.get(token)  # type: ignore[attr-defined]
        supplied = self.headers.get("X-MC-CSRF", "")
        if item is None or len(supplied) > 128 or not hmac.compare_digest(item.csrf_token, supplied):
            self._send(HTTPStatus.FORBIDDEN, "Request not authorized")
            return None
        return item, self.rfile.read(content_length)

    def _create_conversation(self) -> None:
        authorized = self._authorized_write(2)
        if authorized is None:
            return
        _item, body = authorized
        try:
            result = self.server.conversations.create_conversation(self.headers.get("Idempotency-Key", ""), body)  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        self._send(HTTPStatus.CREATED, json.dumps(result, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def _submit_message(self, conversation_id: str) -> None:
        authorized = self._authorized_write(80_000)
        if authorized is None:
            return
        _item, body = authorized
        try:
            result = self.server.conversations.submit_message(  # type: ignore[attr-defined]
                conversation_id, self.headers.get("Idempotency-Key", ""), body
            )
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        self._send(HTTPStatus.ACCEPTED, json.dumps(result, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def _create_task_proposal(self, conversation_id: str) -> None:
        authorized = self._authorized_write(30_000)
        if authorized is None: return
        _item, body = authorized
        try:
            result = self.server.conversations.create_task_proposal(conversation_id, self.headers.get("Idempotency-Key", ""), body)  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error); return
        self._send(HTTPStatus.CREATED, json.dumps(result, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def _record_task_decision(self, proposal_id: str) -> None:
        authorized = self._authorized_write(8_000)
        if authorized is None: return
        _item, body = authorized
        try:
            result = self.server.conversations.record_task_decision(proposal_id, self.headers.get("Idempotency-Key", ""), body)  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error); return
        self._send(HTTPStatus.CREATED, json.dumps(result, separators=(",", ":")), content_type="application/json; charset=utf-8")

    def _logout(self) -> None:
        path = urlsplit(self.path)
        if path.query:
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

    def do_DELETE(self) -> None:
        path = urlsplit(self.path)
        if self.headers.get("Host") != "miscon.phireij.cloud":
            self._send(HTTPStatus.BAD_REQUEST, "Invalid host")
            return
        match = re.fullmatch(r"/api/conversations/([A-Za-z0-9_-]{16,200})", path.path)
        if not match or path.query:
            self._send(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")
            return
        authorized = self._authorized_write(0)
        if authorized is None:
            return
        try:
            self.server.conversations.delete_conversation(match.group(1))  # type: ignore[attr-defined]
        except ConversationRequestError as error:
            self._conversation_error(error)
            return
        self._send(HTTPStatus.NO_CONTENT, "")


def main() -> None:
    config = GoogleOidcConfig.from_environment()
    subject = load_ceo_subject(config.ceo_subject_file)
    conversation_config = ConversationConfig.from_environment()
    try:
        delivery_config = TelegramDeliveryConfig.from_environment()
    except NotificationConfigurationError as exc:
        raise ValueError(str(exc)) from exc
    if delivery_config is not None and conversation_config is None:
        raise ValueError("telegram_delivery_requires_conversation_storage")
    server = ThreadingHTTPServer(("0.0.0.0", 8093), SessionHandler)
    server.flows = FlowStore()  # type: ignore[attr-defined]
    server.sessions = SessionStore()  # type: ignore[attr-defined]
    server.secret_file = config.client_secret_file  # type: ignore[attr-defined]
    server.ceo_subject = subject  # type: ignore[attr-defined]
    server.conversations = (  # type: ignore[attr-defined]
        ConversationStore(
            conversation_config,
            config.issuer,
            subject,
            notification_delivery_enabled=delivery_config is not None,
        )
        if conversation_config is not None
        else None
    )
    worker = None
    if delivery_config is not None and conversation_config is not None and not server.conversations._readonly_preflight:  # type: ignore[attr-defined]
        worker = NotificationDeliveryWorker(
            server.conversations,  # type: ignore[arg-type]
            TelegramTransport(delivery_config),
            retry_seconds=delivery_config.retry_seconds,
            poll_seconds=delivery_config.poll_seconds,
        )
        worker.start()
    try:
        server.serve_forever()
    finally:
        if worker is not None:
            worker.stop()


if __name__ == "__main__":
    main()
