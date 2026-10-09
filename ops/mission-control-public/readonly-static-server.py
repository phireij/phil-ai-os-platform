#!/usr/bin/env python3
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(os.environ.get("MISSION_CONTROL_ROOT", "/srv/mission-control")).resolve()
HOST = os.environ.get("MISSION_CONTROL_HOST", "0.0.0.0")
PORT = int(os.environ.get("MISSION_CONTROL_PORT", "8080"))

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, b'{"status":"ok","mode":"read_only"}', "application/json")
            return
        relative = unquote(self.path.split("?", 1)[0]).lstrip("/") or "index.html"
        candidate = (ROOT / relative).resolve()
        if ROOT not in candidate.parents and candidate != ROOT:
            self._send(404, b'{"status":"not_found"}', "application/json")
            return
        if not candidate.is_file():
            self._send(404, b'{"status":"not_found"}', "application/json")
            return
        content_type = "text/html; charset=utf-8" if candidate.suffix == ".html" else "application/json; charset=utf-8" if candidate.suffix == ".json" else "text/css; charset=utf-8" if candidate.suffix == ".css" else "text/javascript; charset=utf-8"
        self._send(200, candidate.read_bytes(), content_type)

    def do_POST(self):
        self._send(405, b'{"status":"read_only","message":"mutation_not_available"}', "application/json")

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
