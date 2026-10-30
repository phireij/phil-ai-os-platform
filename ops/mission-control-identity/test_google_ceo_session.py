"""Offline checks for the inactive, CEO-bound session boundary."""

from __future__ import annotations

import http.client
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from conversation_store import ConversationConfig, ConversationStore
from google_ceo_session import (
    ABSOLUTE_SECONDS,
    IDLE_SECONDS,
    SESSION_COOKIE,
    SessionHandler,
    SessionStore,
    load_ceo_subject,
)
from google_identity_probe import FlowStore
from http.server import ThreadingHTTPServer


HOST = "miscon.phireij.cloud"


class SessionStoreChecks(unittest.TestCase):
    def test_idle_absolute_expiry_and_revocation(self) -> None:
        now = [100.0]
        store = SessionStore(clock=lambda: now[0])
        token, _item = store.issue()  # type: ignore[misc]
        self.assertIsNotNone(store.get(token))
        now[0] += IDLE_SECONDS + 1
        self.assertIsNone(store.get(token))

        token, _item = store.issue()  # type: ignore[misc]
        now[0] += IDLE_SECONDS - 1
        self.assertIsNotNone(store.get(token))
        now[0] += IDLE_SECONDS - 1
        self.assertIsNotNone(store.get(token))
        now[0] += ABSOLUTE_SECONDS
        self.assertIsNone(store.get(token))

        token, _item = store.issue()  # type: ignore[misc]
        store.revoke(token)
        self.assertIsNone(store.get(token))
        token, _item = store.issue()  # type: ignore[misc]
        store.revoke_all()
        self.assertIsNone(store.get(token))

    def test_binding_requires_exact_issuer_and_subject(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "binding"
            path.write_text("https://accounts.google.com|123456789012345678901\n", encoding="utf-8")
            self.assertEqual(load_ceo_subject(path), "123456789012345678901")
            for value in ("https://evil.example|123456789012345678901", "https://accounts.google.com|", "https://accounts.google.com|abc|extra"):
                path.write_text(value, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_ceo_subject(path)


class SessionHttpChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SessionHandler)
        self.server.flows = FlowStore()  # type: ignore[attr-defined]
        self.server.sessions = SessionStore()  # type: ignore[attr-defined]
        self.server.secret_file = Path("/unused-synthetic-secret")  # type: ignore[attr-defined]
        self.server.ceo_subject = "synthetic-ceo-subject"  # type: ignore[attr-defined]
        self.server.conversations = None  # type: ignore[attr-defined]
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body=body, headers={"Host": HOST, **(headers or {})})
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    def start_flow(self) -> tuple[str, str]:
        status, headers, _ = self.request("GET", "/auth/google/start")
        self.assertEqual(status, 302)
        location = dict(headers)["Location"]
        state = parse_qs(urlsplit(location).query)["state"][0]
        flow_cookie = next(value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie")
        return state, flow_cookie

    def sign_in(self, subject: str = "synthetic-ceo-subject") -> tuple[int, list[tuple[str, str]], bytes]:
        state, flow_cookie = self.start_flow()
        with patch("google_ceo_session.exchange_verified_subject", return_value=subject):
            return self.request("GET", f"/auth/google/callback?state={state}&code=synthetic-code", {"Cookie": flow_cookie})

    def test_exact_subject_issues_hardened_cookie_without_conversation_authority(self) -> None:
        denied, headers, body = self.sign_in("different-subject")
        self.assertEqual(denied, 403)
        self.assertNotIn(SESSION_COOKIE.encode(), body)
        self.assertTrue(any(value.startswith(SESSION_COOKIE + "=; ") and "Max-Age=0" in value for key, value in headers if key.lower() == "set-cookie"))

        status, headers, body = self.sign_in()
        self.assertEqual(status, 303)
        self.assertIn(b"No conversation access is active", body)
        self.assertEqual(dict(headers)["Location"], "/?ceo_session=active")
        cookies = [value for key, value in headers if key.lower() == "set-cookie"]
        session_cookie = next(value for value in cookies if value.startswith(SESSION_COOKIE + "="))
        self.assertIn("; Path=/; Secure; HttpOnly; SameSite=Lax", session_cookie)
        self.assertNotIn("Domain=", session_cookie)
        self.assertNotIn("Max-Age=", session_cookie)
        token_cookie = session_cookie.split(";", 1)[0]

        status, _, body = self.request("GET", "/auth/google/session", {"Cookie": token_cookie})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["authenticated"])
        self.assertFalse(payload["conversation_authority"])
        self.assertEqual(payload["scope"], "mission_control:session")
        self.assertGreater(len(payload["csrf_token"]), 32)

    def test_logout_requires_exact_origin_and_csrf_then_revokes(self) -> None:
        status, headers, _ = self.sign_in()
        self.assertEqual(status, 303)
        cookie = next(value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie" and value.startswith(SESSION_COOKIE + "="))
        status, _, body = self.request("GET", "/auth/google/session", {"Cookie": cookie})
        self.assertEqual(status, 200)
        csrf = json.loads(body)["csrf_token"]
        self.assertEqual(self.request("POST", "/auth/google/logout", {"Cookie": cookie, "X-MC-CSRF": csrf})[0], 403)
        self.assertEqual(self.request("POST", "/auth/google/logout", {"Cookie": cookie, "Origin": "https://evil.example", "X-MC-CSRF": csrf})[0], 403)
        self.assertEqual(self.request("POST", "/auth/google/logout", {"Cookie": cookie, "Origin": "https://miscon.phireij.cloud", "X-MC-CSRF": "wrong"})[0], 403)
        self.assertEqual(self.request("GET", "/auth/google/session", {"Cookie": cookie})[0], 200)
        status, headers, _ = self.request("POST", "/auth/google/logout", {"Cookie": cookie, "Origin": "https://miscon.phireij.cloud", "X-MC-CSRF": csrf})
        self.assertEqual(status, 200)
        self.assertTrue(any("Max-Age=0" in value for key, value in headers if key.lower() == "set-cookie"))
        self.assertEqual(self.request("GET", "/auth/google/session", {"Cookie": cookie})[0], 401)

    def test_new_sign_in_with_wrong_account_revokes_previous_session(self) -> None:
        status, headers, _ = self.sign_in()
        self.assertEqual(status, 303)
        cookie = next(value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie" and value.startswith(SESSION_COOKIE + "="))
        state, flow_cookie = self.start_flow()
        with patch("google_ceo_session.exchange_verified_subject", return_value="different-subject"):
            status, headers, _ = self.request("GET", f"/auth/google/callback?state={state}&code=synthetic-code", {"Cookie": flow_cookie + "; " + cookie})
        self.assertEqual(status, 403)
        self.assertTrue(any(value.startswith(SESSION_COOKIE + "=;") for key, value in headers if key.lower() == "set-cookie"))
        self.assertEqual(self.request("GET", "/auth/google/session", {"Cookie": cookie})[0], 401)

    def test_replay_host_methods_and_errors_fail_closed(self) -> None:
        state, flow_cookie = self.start_flow()
        with patch("google_ceo_session.exchange_verified_subject", return_value="synthetic-ceo-subject"):
            self.assertEqual(self.request("GET", f"/auth/google/callback?state={state}&code=synthetic-code", {"Cookie": flow_cookie})[0], 303)
            self.assertEqual(self.request("GET", f"/auth/google/callback?state={state}&code=synthetic-code", {"Cookie": flow_cookie})[0], 401)
        self.assertEqual(self.request("GET", "/auth/google/session", {"Host": "evil.example"})[0], 400)
        self.assertEqual(self.request("POST", "/auth/google/session")[0], 405)
        self.assertEqual(self.request("PUT", "/auth/google/logout")[0], 405)

        state, flow_cookie = self.start_flow()
        captured = io.StringIO()
        with redirect_stderr(captured), patch("google_ceo_session.exchange_verified_subject", side_effect=RuntimeError("sensitive-test-marker")):
            status, _headers, body = self.request("GET", f"/auth/google/callback?state={state}&code=sensitive-test-code", {"Cookie": flow_cookie})
        self.assertEqual(status, 502)
        self.assertNotIn(b"sensitive-test-marker", body)
        self.assertNotIn(b"sensitive-test-code", body)
        self.assertNotIn("sensitive-test-marker", captured.getvalue())
        self.assertNotIn("sensitive-test-code", captured.getvalue())

    def test_conversation_routes_are_disabled_then_require_session_origin_and_csrf(self) -> None:
        self.assertEqual(self.request("GET", "/api/conversations")[0], 404)
        root = Path(self.temp.name)
        key = root / "key"
        key.write_text("11" * 32, encoding="ascii")
        self.server.conversations = ConversationStore(  # type: ignore[attr-defined]
            ConversationConfig(root / "state", root / "ledger", key),
            "https://accounts.google.com",
            "synthetic-ceo-subject",
        )
        status, headers, _ = self.sign_in()
        self.assertEqual(status, 303)
        cookie = next(
            value.split(";", 1)[0]
            for name, value in headers
            if name.lower() == "set-cookie" and value.startswith(SESSION_COOKIE + "=")
        )
        status, _, body = self.request("GET", "/auth/google/session", {"Cookie": cookie})
        session = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(session["conversation_authority"])
        self.assertEqual(session["scope"], "mission_control:conversation")
        status, _, callback_body = self.sign_in()
        self.assertEqual(status, 303)
        self.assertIn(b"Conversation storage is available", callback_body)
        csrf = session["csrf_token"]

        request_headers = {
            "Cookie": cookie,
            "Content-Type": "application/json",
            "Idempotency-Key": "create-conversation-0001",
            "X-MC-CSRF": csrf,
        }
        self.assertEqual(self.request("POST", "/api/conversations", request_headers, b"{}")[0], 403)
        request_headers["Origin"] = "https://miscon.phireij.cloud"
        status, _, body = self.request("POST", "/api/conversations", request_headers, b"{}")
        self.assertEqual(status, 201)
        conversation_id = json.loads(body)["conversation_id"]

        message_headers = {
            **request_headers,
            "Idempotency-Key": "submit-conversation-0001",
        }
        status, _, body = self.request(
            "POST",
            f"/api/conversations/{conversation_id}/messages",
            message_headers,
            b'{"body":"synthetic confidential marker"}',
        )
        self.assertEqual(status, 202)
        self.assertEqual(json.loads(body)["error_code"], "runtime_unavailable")
        status, _, body = self.request(
            "GET", f"/api/conversations/{conversation_id}/messages", {"Cookie": cookie}
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["messages"][0]["body"], "synthetic confidential marker")
        proposal_headers = {
            **request_headers,
            "Idempotency-Key": "proposal-conversation-0001",
        }
        status, _, body = self.request(
            "POST",
            f"/api/conversations/{conversation_id}/task-proposals",
            proposal_headers,
            json.dumps({
                "source_message_id": json.loads(body)["messages"][0]["message_id"],
                "project_id": "phil-ai-os",
                "task_class": "general",
                "scope": "Review one bounded artifact.",
                "expected_result": "A review note.",
                "required_authority": "A1",
                "source_evidence_refs": [],
            }).encode(),
        )
        self.assertEqual(status, 201)
        proposal_id = json.loads(body)["proposal_id"]
        decision_headers = {
            **request_headers,
            "Idempotency-Key": "decision-proposal-0001",
        }
        status, _, body = self.request(
            "POST",
            f"/api/task-proposals/{proposal_id}/decisions",
            decision_headers,
            b'{"decision":"approved","rationale":"Bounded handoff only.","expires_at":"2030-01-01T00:00:00Z"}',
        )
        self.assertEqual(status, 201)
        handoff_headers = {
            **request_headers,
            "Idempotency-Key": "handoff-proposal-0001",
        }
        status, _, body = self.request(
            "POST", f"/api/task-proposals/{proposal_id}/cto-handoffs", handoff_headers, b"{}"
        )
        self.assertEqual(status, 201)
        self.assertEqual("awaiting_connector", json.loads(body)["state"])
        self.assertFalse(json.loads(body)["dispatch_authorized"])
        status, _, body = self.request(
            "GET", f"/api/conversations/{conversation_id}/cto-handoffs", {"Cookie": cookie}
        )
        self.assertEqual(status, 200)
        self.assertEqual(1, len(json.loads(body)))
        status, _, body = self.request(
            "GET", f"/api/conversations/{conversation_id}/audit-timeline?limit=100", {"Cookie": cookie}
        )
        self.assertEqual(status, 200)
        timeline = json.loads(body)
        self.assertEqual("none", timeline["authority_effect"])
        self.assertNotIn("synthetic confidential marker", body.decode())
        self.assertEqual("available", {item["source"]: item["status"] for item in timeline["source_coverage"]}["notification_outbox"])
        self.assertEqual("awaiting_connector", {item["source"]: item["status"] for item in timeline["source_coverage"]}["task_assignment"])
        status, _, body = self.request("GET", "/api/notifications?limit=100", {"Cookie": cookie})
        self.assertEqual(status, 200)
        notifications = json.loads(body)
        self.assertEqual("not_configured", notifications["transport_status"])
        self.assertEqual(1, len(notifications["notifications"]))
        self.assertEqual("ceo_decision_recorded", notifications["notifications"][0]["kind"])
        self.assertEqual("not_configured", notifications["notifications"][0]["delivery_state"])
        self.assertEqual(
            self.request(
                "DELETE",
                f"/api/conversations/{conversation_id}",
                {**request_headers, "X-MC-CSRF": "wrong"},
            )[0],
            403,
        )
        self.assertEqual(
            self.request(
                "DELETE", f"/api/conversations/{conversation_id}", request_headers
            )[0],
            204,
        )
        self.assertEqual(
            self.request(
                "GET", f"/api/conversations/{conversation_id}/messages", {"Cookie": cookie}
            )[0],
            404,
        )


if __name__ == "__main__":
    unittest.main()
