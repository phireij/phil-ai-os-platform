"""Isolated HTTP checks for the explicit same-process Ruby synthetic topology."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from google_ceo_session import IDLE_SECONDS, ORIGIN, SESSION_COOKIE, SessionHandler, SessionStore
from google_identity_probe import FlowStore
from http.server import ThreadingHTTPServer
from ruby_review_synthetic_harness import HARNESS_OPT_IN
from ruby_review_synthetic_topology import (
    LoopbackRubySyntheticTopology,
    RubySyntheticTopologyError,
)


HOST = "miscon.phireij.cloud"
OWNER = "synthetic-ceo-subject"
ISSUER = "https://accounts.google.com"


class RubySyntheticTopologyHttpChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = [100.0]
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SessionHandler)
        self.server.flows = FlowStore()  # type: ignore[attr-defined]
        self.server.sessions = SessionStore(clock=lambda: self.clock[0])  # type: ignore[attr-defined]
        self.server.secret_file = Path("/unused-synthetic-secret")  # type: ignore[attr-defined]
        self.server.ceo_subject = OWNER  # type: ignore[attr-defined]
        self.server.conversations = None  # type: ignore[attr-defined]
        self.server.ruby_review_synthetic_surface_enabled = False  # type: ignore[attr-defined]
        self.server.ruby_review_transport_binding = None  # type: ignore[attr-defined]
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.scope = Path(self.temp.name) / "ruby-synthetic-scope"
        self.scope.mkdir()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def compose(self) -> LoopbackRubySyntheticTopology:
        topology = LoopbackRubySyntheticTopology.create_and_bind(
            server=self.server,
            storage_scope=self.scope,
            opt_in=HARNESS_OPT_IN,
            owner_subject=OWNER,
            issuer=ISSUER,
        )
        self.addCleanup(topology.close)
        return topology

    def issue_cookie(self) -> tuple[str, str]:
        token, item = self.server.sessions.issue()  # type: ignore[attr-defined]
        self.assertIsNotNone(token)
        return f"{SESSION_COOKIE}={token}", item.csrf_token

    def request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        host: str = HOST,
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body=body, headers={"Host": host, **(headers or {})})
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    def raw_request(
        self, method: str, path: str, headers: list[tuple[str, str]], body: bytes = b""
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        connection.putheader("Host", HOST)
        for name, value in headers:
            connection.putheader(name, value)
        connection.endheaders(body)
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    def test_default_off_then_exact_loopback_paths_with_unchanged_auth_routes(self) -> None:
        self.assertEqual(404, self.request("GET", "/api/ruby-review-synthetic/records")[0])
        topology = self.compose()
        self.assertEqual(self.scope.resolve(), topology.harness.run_directory.parent)
        cookie, _csrf = self.issue_cookie()
        self.assertEqual(200, self.request("GET", "/auth/google/healthz")[0])
        self.assertEqual(302, self.request("GET", "/auth/google/start")[0])
        status, _, session = self.request("GET", "/auth/google/session", {"Cookie": cookie})
        self.assertEqual(200, status)
        self.assertTrue(json.loads(session)["authenticated"])
        self.assertFalse(json.loads(session)["conversation_authority"])
        status, _headers, body = self.request("GET", "/api/ruby-review-synthetic/records", {"Cookie": cookie})
        self.assertEqual(200, status)
        records = json.loads(body)["records"]
        record_id = records[0]["record_id"]
        self.assertEqual(200, self.request("GET", f"/api/ruby-review-synthetic/records/{record_id}", {"Cookie": cookie})[0])
        self.assertEqual(200, self.request("GET", f"/api/ruby-review-synthetic/records/{record_id}/audit", {"Cookie": cookie})[0])
        for path in (
            "/api/ruby-review-synthetic",
            "/api/ruby-review-synthetic/records/",
            "/api/ruby-review-synthetic/records?export=1",
            f"/api/ruby-review-synthetic/records/{record_id}/audit/extra",
            "/api/ruby-review-synthetic/other-service",
        ):
            self.assertEqual(404, self.request("GET", path, {"Cookie": cookie})[0])
        self.assertEqual(405, self.request("POST", "/api/ruby-review-synthetic/records", {"Cookie": cookie}, b"{}")[0])
        self.assertEqual(404, self.request("GET", "/api/conversations", {"Cookie": cookie})[0])

    def test_session_owner_host_origin_and_framing_guards(self) -> None:
        self.compose()
        cookie, _csrf = self.issue_cookie()
        records_path = "/api/ruby-review-synthetic/records"
        self.assertEqual(401, self.request("GET", records_path)[0])
        self.assertEqual(400, self.request("GET", records_path, host="ruby.example")[0])
        self.assertEqual(403, self.request("GET", records_path, {"Cookie": cookie, "Origin": "https://evil.example"})[0])
        self.assertEqual(403, self.request("GET", records_path, {"Cookie": cookie, "Sec-Fetch-Site": "cross-site"})[0])
        with self.subTest("wrong owner"):
            self.server.ceo_subject = "different-owner"  # type: ignore[attr-defined]
            self.assertEqual(404, self.request("GET", records_path, {"Cookie": cookie})[0])
            self.server.ceo_subject = OWNER  # type: ignore[attr-defined]
        self.assertEqual(400, self.raw_request("GET", records_path, [("Cookie", cookie), ("Origin", ORIGIN), ("Origin", ORIGIN)])[0])
        self.assertEqual(400, self.raw_request("GET", records_path, [("Cookie", cookie), ("Content-Length", "2")], b"{}")[0])
        self.clock[0] += IDLE_SECONDS + 1
        self.assertEqual(401, self.request("GET", records_path, {"Cookie": cookie})[0])

    def test_receipt_history_is_original_read_only_and_csrf_framed(self) -> None:
        topology = self.compose()
        cookie, csrf = self.issue_cookie()
        before = topology.harness.config.state_file.read_bytes()
        headers = {"Cookie": cookie, "Origin": ORIGIN, "X-MC-CSRF": csrf, "Content-Type": "application/json"}
        _status, _, listed = self.request("GET", "/api/ruby-review-synthetic/records", {"Cookie": cookie})
        pickup_id = next(record["record_id"] for record in json.loads(listed)["records"] if record["fulfillment_preference"] == "store pickup")
        _status, _, current = self.request("GET", f"/api/ruby-review-synthetic/records/{pickup_id}", {"Cookie": cookie})
        self.assertEqual(3, json.loads(current)["revision_number"])
        self.assertEqual(403, self.request("POST", "/api/ruby-review-synthetic/receipts/create-pickup", {"Cookie": cookie}, b"{}")[0])
        self.assertEqual(403, self.request("POST", "/api/ruby-review-synthetic/receipts/create-pickup", {**headers, "X-MC-CSRF": "wrong"}, b"{}")[0])
        self.assertEqual(400, self.raw_request("POST", "/api/ruby-review-synthetic/receipts/create-pickup", [("Cookie", cookie), ("Origin", ORIGIN), ("Content-Type", "application/json"), ("Content-Length", "2"), ("X-MC-CSRF", csrf), ("X-MC-CSRF", csrf)], b"{}")[0])
        create_status, _, create = self.request("POST", "/api/ruby-review-synthetic/receipts/create-pickup", headers, b"{}")
        revise_status, _, revise = self.request("POST", "/api/ruby-review-synthetic/receipts/revise-pickup", headers, b"{}")
        self.assertEqual((200, 200), (create_status, revise_status))
        self.assertEqual(("committed", 1), (json.loads(create)["state"], json.loads(create)["receipt"]["revision_number"]))
        self.assertEqual(("committed", 2), (json.loads(revise)["state"], json.loads(revise)["receipt"]["revision_number"]))
        self.assertEqual(404, self.request("POST", "/api/ruby-review-synthetic/receipts/unknown", headers, b"{}")[0])
        self.assertEqual(before, topology.harness.config.state_file.read_bytes())
        self.assertFalse(json.loads(create)["retry_authorized"])
        self.assertEqual(405, self.request("PUT", "/api/ruby-review-synthetic/records", {"Cookie": cookie})[0])

    def test_composition_refuses_non_loopback_wrong_owner_and_existing_binding(self) -> None:
        self.assertEqual("127.0.0.1", self.server.server_address[0])
        original_address = self.server.server_address
        self.server.server_address = ("192.0.2.1", 8093)
        with self.assertRaisesRegex(RubySyntheticTopologyError, "loopback_required"):
            self.compose()
        self.server.server_address = original_address
        self.server.ceo_subject = "different-owner"  # type: ignore[attr-defined]
        with self.assertRaisesRegex(RubySyntheticTopologyError, "owner_mismatch"):
            self.compose()
        self.server.ceo_subject = OWNER  # type: ignore[attr-defined]
        self.server.ruby_review_transport_binding = object()  # type: ignore[attr-defined]
        with self.assertRaisesRegex(RubySyntheticTopologyError, "binding_already_set"):
            self.compose()


if __name__ == "__main__":
    unittest.main()
