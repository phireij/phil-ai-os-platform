#!/usr/bin/env python3
"""Small authenticated gateway for the Mission Control MVP.

The gateway is intentionally separate from the public static preview. Its
default configuration permits reads and CEO decision requests only. Task
assignment is disabled unless the deployment explicitly enables the bounded
delegation gate.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

_container_source = Path(os.environ.get("MISSION_CONTROL_SOURCE_ROOT", "/srv/apps/operations-hub/src"))
if _container_source.exists():
    SOURCE_ROOT = _container_source
else:
    _repository_root = Path(__file__).resolve().parents[2]
    SOURCE_ROOT = _repository_root / "apps" / "operations-hub" / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from operations_hub.mission_control_control_plane import (  # noqa: E402
    MissionControlControlPlane,
    MissionControlControlPlaneError,
)

HOST = os.environ.get("MISSION_CONTROL_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("MISSION_CONTROL_GATEWAY_PORT", "8090"))
CEO_TOKEN_FILE = os.environ.get("MISSION_CONTROL_CEO_TOKEN_FILE", "/run/philaios/mission_control_ceo_token")


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _read_secret() -> str:
    try:
        return Path(CEO_TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    expected = _read_secret()
    supplied = handler.headers.get("Authorization", "")
    return bool(expected) and hmac.compare_digest(supplied, "Bearer " + expected)


class Handler(BaseHTTPRequestHandler):
    server_version = "PhilAIOSMissionControlGateway/0.1"

    def _send(self, status: int, body: dict) -> None:
        payload = _json_bytes(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            value = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _require_auth(self) -> bool:
        if _authorized(self):
            return True
        self._send(401, {"status": "unauthorized"})
        return False

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/healthz":
            self._send(200, {"status": "ok", "mode": "authenticated_control_plane", "authority_effect": "none"})
            return
        if not self._require_auth():
            return
        api = MissionControlControlPlane()
        try:
            if path == "/api/snapshot":
                self._send(200, api.snapshot())
            elif path == "/api/approvals":
                self._send(200, api.recent_approvals())
            elif path == "/api/executions":
                self._send(200, api.recent_executions())
            else:
                self._send(404, {"status": "not_found"})
        except MissionControlControlPlaneError:
            self._send(502, {"status": "control_api_unavailable"})

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        path = urlparse(self.path).path
        api = MissionControlControlPlane()
        payload = self._body()
        try:
            if path == "/api/decision-requests":
                result = api.request_ceo_decision(
                    str(payload.get("task_text") or ""),
                    str(payload.get("conversation_id") or ""),
                )
                self._send(201, result)
                return
            if path.startswith("/api/tasks/") and path.endswith("/assign"):
                if os.environ.get("MISSION_CONTROL_DELEGATION_ENABLED", "false").lower() != "true":
                    self._send(403, {"status": "delegation_gate_disabled"})
                    return
                task_id = path[len("/api/tasks/") : -len("/assign")]
                result = api.assign_task(task_id, str(payload.get("agent_id") or ""), allow_mutation=True)
                self._send(200, result)
                return
            self._send(404, {"status": "not_found"})
        except MissionControlControlPlaneError as exc:
            status = 400 if str(exc).endswith("required") else 502
            self._send(status, {"status": "request_failed", "reason": str(exc)})

    def log_message(self, _format: str, *_args) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

