"""Loopback-only tests with a synthetic owner, store and session."""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

from conversation_store import MAGIC, ConversationConfig, ConversationStore
from google_ceo_session import SESSION_COOKIE, SessionHandler, SessionStore


class MessageHistoryHttpTests(unittest.TestCase):
    def test_synthetic_owner_full_wire_traversal_without_store_format_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = root / "key"
            key.write_text("47" * 32, encoding="ascii")
            key.chmod(0o600)
            config = ConversationConfig(root / "store.enc", root / "ledger.enc", key)
            issuer = "https://accounts.google.com"
            subject = "synthetic-history-owner"
            store = ConversationStore(config, issuer, subject)
            self.addCleanup(store.close)
            server = ThreadingHTTPServer(("127.0.0.1", 0), SessionHandler)
            self.addCleanup(server.server_close)
            server.sessions = SessionStore()
            server.conversations = store
            server.ruby_review_synthetic_surface_enabled = False
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 5)
            self.addCleanup(server.shutdown)
            token, _ = server.sessions.issue()

            def read(path: str, *, authenticated: bool = True) -> tuple[int, dict[str, object]]:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                headers = {"Host": "miscon.phireij.cloud", "Accept": "application/json"}
                if authenticated:
                    headers["Cookie"] = f"{SESSION_COOKIE}={token}"
                try:
                    connection.request("GET", path, headers=headers)
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    connection.close()

            session, payload = read("/auth/google/session", authenticated=False)
            self.assertEqual(session, 401)
            self.assertNotIn("message_history_pagination", payload)
            session, payload = read("/auth/google/session")
            self.assertEqual(session, 200)
            self.assertEqual(payload["message_history_pagination"], "keyset-v1")

            parent = "conv_0000000000000001"
            now = int(time.time())
            store._live.connection.execute("INSERT INTO conversations VALUES (?,?,?,?)",
                                           (parent, store._owner, now, now))
            identifiers = [f"message_{i:016d}" for i in range(205)]
            # A single shared timestamp forces stable identifier ties across
            # both boundaries while inserts are deliberately nonchronological.
            for identifier in identifiers[::2] + identifiers[1::2][::-1]:
                store._live.connection.execute("INSERT INTO messages VALUES (?,?,'ceo',?,?)",
                                               (identifier, parent, "Synthetic history row", now))
            store._live.persist()
            snapshot = (root / "store.enc").read_bytes()
            self.assertEqual(MAGIC, b"PHIL-MC-CONVERSATION-STATE-V1\x00")
            self.assertTrue(snapshot.startswith(MAGIC))
            base_path = f"/api/conversations/{parent}/messages"
            self.assertEqual(read(f"{base_path}?pagination=keyset-v1", authenticated=False)[0], 401)
            status, data = read(f"{base_path}?limit=100")
            self.assertEqual(status, 200)
            self.assertEqual([row["message_id"] for row in data["messages"]], identifiers[-100:])
            self.assertIsNone(data["next_cursor"])
            obtained: list[str] = []
            cursor = None
            page_size = []
            for _ in range(3):
                query = {"pagination": "keyset-v1", "limit": "100"}
                if cursor:
                    query["cursor"] = cursor
                status, data = read(f"{base_path}?{urlencode(query)}")
                self.assertEqual(status, 200)
                self.assertEqual(data["conversation_id"], parent)
                ids = [row["message_id"] for row in data["messages"]]
                page_size.append(len(ids))
                self.assertTrue(all(row["authority_effect"] == "none" for row in data["messages"]))
                obtained = ids + obtained
                cursor = data["next_cursor"]
            self.assertIsNone(cursor)
            self.assertEqual(page_size, [100, 100, 5])
            self.assertEqual(obtained, identifiers)
            self.assertEqual((root / "store.enc").read_bytes(), snapshot)


if __name__ == "__main__":
    unittest.main()
