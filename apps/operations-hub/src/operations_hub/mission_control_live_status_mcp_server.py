"""Loopback-only server for the separately authorized read-only live-status MCP tool."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .mission_control_cto_auth0_verifier import verifier_from_environment
from .mission_control_live_status import collect_live_status, load_manifest
from .mission_control_live_status_mcp import CANONICAL_RESOURCE_URI, LiveStatusMcpResource


HOST = "127.0.0.1"
PORT = 8788
METADATA_URI = "https://miscon.phireij.cloud/.well-known/oauth-protected-resource/mcp/live-status"
ISSUER_ENV = "MCP_AUTHORIZATION_ISSUER"
MANIFEST_PATH_ENV = "MCP_LIVE_STATUS_MANIFEST_PATH"
DEFAULT_MANIFEST_PATH = "/srv/mission-control/live-status-manifest.json"


def _resource() -> LiveStatusMcpResource:
    return LiveStatusMcpResource(CANONICAL_RESOURCE_URI, os.environ.get(ISSUER_ENV, ""), METADATA_URI)


def _manifest_loader() -> dict[str, object]:
    return load_manifest(Path(os.environ.get(MANIFEST_PATH_ENV, DEFAULT_MANIFEST_PATH)))


def _verify_owner_credential(credential: str):
    return verifier_from_environment(CANONICAL_RESOURCE_URI)(credential)


def _bearer_credential(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.startswith("Bearer "):
        return None
    token = value.removeprefix("Bearer ")
    return token if token and token == token.strip() and " " not in token else None


class Handler(BaseHTTPRequestHandler):
    server_version = "PhilAiOsLiveStatusMcp/1"
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: object, headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        resource = _resource()
        if self.path == "/healthz":
            self._send(200, {"status": "ok", "mode": "live_status_read_only", "authority_effect": "none", "live_data": "on_demand"})
        elif self.path == "/.well-known/oauth-protected-resource/mcp/live-status":
            self._send(200, resource.protected_resource_metadata())
        else:
            self._send(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send(404, {"status": "not_found"})
            return
        try:
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            method, request_id = request["method"], request.get("id")
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
                params.get("name"), params.get("arguments"), _bearer_credential(self.headers.get("Authorization")),
                verifier=_verify_owner_credential, manifest_loader=_manifest_loader,
                collector=collect_live_status, now=datetime.now(timezone.utc),
            )
            challenge = result.get("_meta", {}).get("mcp/www_authenticate", ())
            if result.get("isError") and challenge:
                self._send(401, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": "authentication_required"}}, headers={"WWW-Authenticate": challenge[0]})
                return
        else:
            self._send(200, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method_not_found"}})
            return
        self._send(200, {"jsonrpc": "2.0", "id": request_id, "result": result})

    def do_PUT(self) -> None:  # noqa: N802
        self._send(405, {"status": "read_only"})

    do_PATCH = do_PUT  # noqa: N815
    do_DELETE = do_PUT  # noqa: N815

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    _resource()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"live_status_mcp_listening={HOST}:{PORT} authority_effect=none", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
