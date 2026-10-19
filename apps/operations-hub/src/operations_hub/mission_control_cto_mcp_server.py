"""Loopback-only MCP fixture server with fail-closed Auth0 JWT verification.

This process deliberately exposes no live source, credential issuer, OAuth flow,
or tunnel connection.  Its only possible tool output is a committed synthetic
fixture, and it remains non-callable until a later approved owner-subject map.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .mission_control_cto_auth0_verifier import verifier_from_environment
from .mission_control_cto_mcp_fixture import (
    CANONICAL_RESOURCE_URI,
    OfflineMcpFixtureResource,
)


HOST = "127.0.0.1"
PORT = 8787
METADATA_URI = "https://miscon.phireij.cloud/.well-known/oauth-protected-resource/mcp"
ISSUER_ENV = "MCP_AUTHORIZATION_ISSUER"
FIXTURE_PATH_ENV = "MCP_SYNTHETIC_FIXTURE_PATH"
DEFAULT_FIXTURE_PATH = "/srv/mission-control/project-readiness.json"


def _resource() -> OfflineMcpFixtureResource:
    issuer = os.environ.get(ISSUER_ENV, "")
    return OfflineMcpFixtureResource(CANONICAL_RESOURCE_URI, issuer, METADATA_URI)


def _fixture_loader() -> tuple[dict[str, object], None]:
    """Read only the committed image fixture, and only after token verification."""

    path = Path(os.environ.get(FIXTURE_PATH_ENV, DEFAULT_FIXTURE_PATH))
    return json.loads(path.read_text(encoding="utf-8")), None


def _bearer_credential(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.startswith("Bearer "):
        return None
    token = value.removeprefix("Bearer ")
    return token if token and token == token.strip() and " " not in token else None


class Handler(BaseHTTPRequestHandler):
    server_version = "PhilAiOsOfflineMcpFixture/1"

    def _send(self, code: int, body: object) -> None:
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        resource = _resource()
        if self.path == "/healthz":
            self._send(200, {
                "status": "ok", "mode": "offline_fixture", "authority_effect": "none",
                "live_data": False,
            })
        elif self.path == "/.well-known/oauth-protected-resource/mcp":
            self._send(200, resource.protected_resource_metadata())
        else:
            self._send(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send(404, {"status": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            method = request["method"]
            request_id = request.get("id")
        except (UnicodeDecodeError, ValueError, KeyError, TypeError):
            self._send(400, {"error": "invalid_request"})
            return
        resource = _resource()
        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}}
        elif method == "tools/list":
            result = resource.list_tools()
        elif method == "tools/call":
            params = request.get("params", {})
            result = resource.call_tool(
                params.get("name"), params.get("arguments"),
                _bearer_credential(self.headers.get("Authorization")),
                verifier=verifier_from_environment(CANONICAL_RESOURCE_URI),
                fixture_loader=_fixture_loader,
                now=_utc_now(),
            )
        else:
            self._send(200, {"jsonrpc": "2.0", "id": request_id,
                             "error": {"code": -32601, "message": "method_not_found"}})
            return
        self._send(200, {"jsonrpc": "2.0", "id": request_id, "result": result})

    def do_PUT(self) -> None:  # noqa: N802
        self._send(405, {"status": "read_only"})

    do_PATCH = do_PUT  # noqa: N815
    do_DELETE = do_PUT  # noqa: N815

    def log_message(self, format: str, *args: object) -> None:
        pass


def _utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def main() -> None:
    _resource()  # Fail closed if the configured issuer is absent or invalid.
    verifier_from_environment(CANONICAL_RESOURCE_URI)  # Validate issuer/JWKS config; no token or network use.
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"offline_mcp_fixture_listening={HOST}:{PORT} authority_effect=none", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
