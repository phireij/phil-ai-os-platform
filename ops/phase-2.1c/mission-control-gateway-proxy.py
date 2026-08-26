#!/usr/bin/env python3
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ['PHIL_AI_OS_MC_UPSTREAM'].rstrip('/')
HOST = os.getenv('PHIL_AI_OS_MC_PROXY_HOST', '0.0.0.0')
PORT = int(os.getenv('PHIL_AI_OS_MC_PROXY_PORT', '8080'))

class Handler(BaseHTTPRequestHandler):
    def _proxy(self):
        target = UPSTREAM + self.path
        body = None
        length = self.headers.get('Content-Length')
        if length:
            body = self.rfile.read(int(length))
        req = urllib.request.Request(target, data=body, method=self.command)
        for key in ('Content-Type', 'Accept'):
            if self.headers.get(key):
                req.add_header(key, self.headers[key])
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/octet-stream'))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            self.send_header('Content-Type', exc.headers.get('Content-Type', 'application/json'))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            payload = b'{"status":"upstream_unavailable"}'
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def do_GET(self): self._proxy()
    def do_HEAD(self): self._proxy()
    def do_POST(self): self._proxy()
    def do_PUT(self): self._proxy()
    def do_PATCH(self): self._proxy()
    def do_DELETE(self): self._proxy()

    def log_message(self, fmt, *args):
        pass

if __name__ == '__main__':
    print(f'PHIL_AI_OS_PHASE_2_1C_GATEWAY_PROXY_LISTENING host={HOST} port={PORT}', flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
