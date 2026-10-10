#!/usr/bin/env python3
"""Bearer-authenticated, read-only bridge to the host-local A7 read model."""

from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOST = os.getenv("MISSION_CONTROL_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.getenv("MISSION_CONTROL_BRIDGE_PORT", "8091"))
CEO_TOKEN_FILE = os.getenv("MISSION_CONTROL_CEO_TOKEN_FILE", "/run/secrets/mission_control_ceo_token")
UPSTREAM = os.getenv("MISSION_CONTROL_READ_MODEL_URL", "http://127.0.0.1:4881/api/read-model")


def _token() -> str:
    try:
        return Path(CEO_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _json(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "PhilAIOSMissionControlReadModelBridge/0.1"

    def _send(self, status: int, body: dict) -> None:
        payload = _json(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path != "/api/agent-posture":
            self._send(404, {"status": "not_found"})
            return
        expected = _token()
        supplied = self.headers.get("Authorization", "")
        if not expected or not hmac.compare_digest(supplied, "Bearer " + expected):
            self._send(401, {"status": "unauthorized"})
            return
        try:
            with urlopen(Request(UPSTREAM, headers={"Accept": "application/json"}), timeout=10) as response:
                source = json.loads(response.read().decode("utf-8"))
            if not isinstance(source, dict):
                raise ValueError("read_model_not_object")
            self._send(200, {
                "status": source.get("status", "unknown"),
                "multi_agent": source.get("multi_agent") or {},
                "agent_runtime": source.get("agent_runtime"),
                "worker_readiness": source.get("worker_readiness"),
                "handoffs": source.get("handoffs", []),
                "governance": source.get("governance", {}),
                "authority_effect": "none",
            })
        except (OSError, ValueError, HTTPError, URLError):
            self._send(502, {"status": "read_model_unavailable"})

    def do_POST(self) -> None:
        self._send(405, {"status": "mutation_not_available"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def log_message(self, _format: str, *_args) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
