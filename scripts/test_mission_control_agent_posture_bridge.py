#!/usr/bin/env python3
"""Exercise the isolated bridge with synthetic upstream content only."""

from __future__ import annotations

import importlib.util
import io
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SOURCE = Path(__file__).resolve().parents[1] / "ops/mission-control-public/read-model-bridge.py"
spec = importlib.util.spec_from_file_location("mission_control_read_model_bridge", SOURCE)
assert spec and spec.loader
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
open_local_read_model = bridge._open_local_read_model


def agent(*, grants_authority: bool = False, age: int = 30) -> dict:
    return {
        "agent_id": "synthetic-agent",
        "authority_ceiling": "A0",
        "evidence_complete": True,
        "registry": {"enabled": True, "assignable": True, "evidence_complete": True},
        "presence": {
            "state": "fresh", "identity_verified": True, "evidence_complete": True,
            "observed_at": "2026-10-13T23:59:30Z", "age_seconds": age,
        },
        "workload": {"evidence_complete": True, "active_task_count": 0},
        "readiness": {"state": "ready", "reason": "synthetic-only", "grants_authority": grants_authority},
        "task_text": "private-task-content-must-not-escape",
    }


def upstream(*, agents=None, handoffs=None, generated_at="2026-10-14T00:00:00Z") -> dict:
    return {
        "status": "ok", "generated_at": generated_at,
        "multi_agent": {"agents": [agent()] if agents is None else agents},
        "handoffs": [{"task_text": "private-handoff-content-must-not-escape"}] if handoffs is None else handoffs,
        "unregistered_secret": "private-source-content-must-not-escape",
    }


class BridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = upstream()
        self.token = self.enterContext(patch.object(bridge, "_token", return_value="synthetic-test-token"))
        self.read_model = self.enterContext(patch.object(bridge, "_open_local_read_model"))
        self.read_model.side_effect = lambda _request: io.BytesIO(json.dumps(self.source).encode("utf-8"))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}/api/agent-posture"

    def request(self, method="GET", *, authorized=True):
        headers = {"Authorization": "Bearer synthetic-test-token"} if authorized else {}
        request = Request(self.base, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read()
        except HTTPError as error:
            with error:
                return error.code, error.read()

    def test_auth_and_mutation_boundary(self):
        self.assertEqual(self.request(authorized=False)[0], 401)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual(self.request(method)[0], 405)
        self.read_model.assert_not_called()

    def test_bounded_v2_projection_excludes_private_source_fields(self):
        status, raw = self.request()
        self.assertEqual(status, 200)
        self.assertNotIn(b"private-", raw)
        response = json.loads(raw)
        self.assertEqual(response["contract_version"], 2)
        self.assertEqual(response["source_generated_at"], self.source["generated_at"])
        self.assertEqual(response["authority_effect"], "none")
        self.assertEqual(response["multi_agent"]["agents"][0]["readiness"], {
            "state": "ready", "reason": "synthetic-only", "grants_authority": False,
        })
        self.assertEqual(response["handoffs"], [{"record_present": True}])
        self.assertTrue(response["agents_available"])
        self.assertTrue(response["handoffs_available"])

    def test_upstream_authority_claim_is_rejected(self):
        self.source = upstream(agents=[agent(grants_authority=True)])
        status, raw = self.request()
        self.assertEqual(status, 200)
        readiness = json.loads(raw)["multi_agent"]["agents"][0]["readiness"]
        self.assertEqual(readiness, {
            "state": "indeterminate", "reason": "authority_claim_rejected", "grants_authority": False,
        })

    def test_unsupported_ready_evidence_is_downgraded(self):
        for generated_at, age in (("2026-10-13T23:58:00Z", 30), ("2026-10-14T00:00:00Z", 121), ("unknown", 30)):
            with self.subTest(generated_at=generated_at, age=age):
                self.source = upstream(agents=[agent(age=age)], generated_at=generated_at)
                status, raw = self.request()
                self.assertEqual(status, 200)
                readiness = json.loads(raw)["multi_agent"]["agents"][0]["readiness"]
                self.assertEqual(readiness["state"], "indeterminate")
                self.assertFalse(readiness["grants_authority"])

    def test_limits_and_unavailable_lists_are_explicit(self):
        self.source = upstream(agents=[agent() for _ in range(bridge.MAX_AGENTS + 2)], handoffs=[{} for _ in range(bridge.MAX_HANDOFFS + 2)])
        status, raw = self.request()
        self.assertEqual(status, 200)
        response = json.loads(raw)
        self.assertEqual(len(response["multi_agent"]["agents"]), bridge.MAX_AGENTS)
        self.assertEqual(len(response["handoffs"]), bridge.MAX_HANDOFFS)
        self.assertTrue(response["agents_truncated"])
        self.assertTrue(response["handoffs_truncated"])
        self.source = {"status": "unknown", "generated_at": "invalid"}
        status, raw = self.request()
        response = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertIsNone(response["source_generated_at"])
        self.assertFalse(response["agents_available"])
        self.assertFalse(response["handoffs_available"])

    def test_oversized_upstream_response_fails_closed(self):
        self.read_model.side_effect = lambda _request: io.BytesIO(b" " * (bridge.MAX_UPSTREAM_RESPONSE_BYTES + 2))
        status, raw = self.request()
        self.assertEqual(status, 502)
        self.assertEqual(json.loads(raw), {"status": "read_model_unavailable"})

    def test_upstream_transport_is_pinned_and_proxy_free(self):
        with patch.object(bridge, "UPSTREAM", "https://external.invalid/collect"):
            with self.assertRaisesRegex(ValueError, "read_model_upstream_not_allowed"):
                open_local_read_model(Request(bridge.UPSTREAM))
        with self.assertRaisesRegex(ValueError, "read_model_upstream_not_allowed"):
            open_local_read_model(Request("http://external.invalid/collect"))
        with self.assertRaisesRegex(ValueError, "read_model_upstream_not_allowed"):
            open_local_read_model(Request(bridge.UPSTREAM, method="POST"))
        with patch.object(bridge, "build_opener") as make_opener:
            open_local_read_model(Request(bridge.UPSTREAM))
        handlers = make_opener.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], bridge._NoRedirect)


if __name__ == "__main__":
    unittest.main()
