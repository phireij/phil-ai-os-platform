"""Optional isolated hosted-runner check; no provider, credentials or live routes."""
import argparse
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import runpy
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
WIRE = runpy.run_path(str(ROOT / "message_history_rollback_wire.py"))
FIX = runpy.run_path(str(ROOT / "integrated_message_history.py"))

@contextmanager
def facade(repo):
    assets = repo / "apps/operations-hub/mission-control"
    media = {".html":"text/html; charset=utf-8", ".css":"text/css; charset=utf-8",
             ".mjs":"text/javascript; charset=utf-8", ".json":"application/json"}
    events, port = [], [None]

    class Facade(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get("Host") != f"localhost:{self.server.server_port}":
                self.send_error(400)
                return
            u = urlsplit(self.path)
            name = "index.html" if u.path == "/" else u.path.removeprefix("/")
            if u.scheme or u.netloc or u.fragment:
                self.send_error(400)
                return
            if name in FIX["FIXTURES"] and not u.query:
                path = assets / name
                self.respond(200, media[path.suffix], path.read_bytes())
                return
            if u.path not in FIX["ROOTS"] or port[0] is None:
                self.send_error(404)
                return
            header = self.headers.get("Cookie", "")
            prefix = WIRE["COOKIE"] + "="
            if not header.startswith(prefix) or ";" in header:
                self.send_error(401)
                return
            code, payload = WIRE["fetch"](port[0], self.path, header.removeprefix(prefix))
            query = parse_qs(u.query)
            events.append((FIX["ROOTS"][u.path], code, sorted(query),
                           query.get("limit"), query.get("pagination")))
            self.respond(code, "application/json", json.dumps(payload).encode())

        def respond(self, code, content_type, raw):
            self.send_response(code)
            self.send_header("Content-Type",content_type)
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    with ThreadingHTTPServer(("127.0.0.1", 0), Facade) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port, port, events
        finally:
            server.shutdown()
            thread.join(5)

def check(repo, baseline, http_only=False):
    FIX["verify_frozen"](repo)
    candidate = repo / "ops/mission-control-identity"
    with tempfile.TemporaryDirectory() as tmp, facade(repo) as (local, backend, events):
        root = Path(tmp)
        (root / "key").write_text("47"*32)
        (root / "key").chmod(0o600)
        origin = f"http://localhost:{local}"
        if http_only:
            with WIRE["process"]("candidate", candidate, root) as (worker, port):
                backend[0] = port
                token = WIRE["issue"](worker)
                c = http.client.HTTPConnection("127.0.0.1",local,timeout=5)
                try:
                    raw = {"Host": f"localhost:{local}", "Cookie":WIRE["COOKIE"]+"="+token}
                    for path in ("/", "/mission-control.mjs", "/auth/google/session"):
                        c.request("GET",path,headers=raw)
                        r=c.getresponse()
                        assert r.status==200 and r.read()
                finally:
                    c.close()
            assert events == [("session",200,[],None,None)]
            print("PASS rollback façade static and actual handler loopback proxy")
            return
        from playwright.sync_api import expect, sync_playwright

        def intercept(route):
            u = urlsplit(route.request.url)
            if (f"{u.scheme}://{u.netloc}" == origin and route.request.method == "GET"
                and (u.path in FIX["ROOTS"] or u.path in {"/","/favicon.ico"}
                     or u.path.removeprefix("/") in FIX["FIXTURES"])):
                route.continue_()
            else:
                route.abort()
                unexpected.append("blocked request")

        def cookie(ctx, token):
            # Metadata only; Chromium treats localhost as secure for these cookies.
            ctx.add_cookies([dict(name=WIRE["COOKIE"],value=token,url=f"https://localhost:{local}/",
                                  secure=True,httpOnly=True,sameSite="Lax")])

        unexpected, page_errors = [], []
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            try:
                with browser.new_context(service_workers="block") as ctx:
                    ctx.route("**/*", intercept)
                    with WIRE["process"]("candidate",candidate,root) as (worker,port):
                        backend[0] = port
                        cookie(ctx,WIRE["issue"](worker))
                        page = ctx.new_page()
                        page.on("pageerror",lambda _: page_errors.append("page error"))
                        ready = lambda response: (urlsplit(response.url).path.endswith("/cto-handoff-results")
                                                  and response.status == 200)
                        with page.expect_response(ready):
                            page.goto(origin+"/")
                        expect(page.locator("#load-state")).to_contain_text("SYNTHETIC FIXTURE")
                        state = page.locator("#conversation-state")
                        control = page.locator("#conversation-history-more")
                        rows = page.locator("#conversation-thread .conversation-message")
                        expect(state).to_contain_text("conversation storage active")
                        expect(rows).to_have_count(100)
                        expect(rows.first).to_contain_text("Synthetic rollback row 105")
                        expect(rows.last).to_contain_text("Synthetic rollback row 204")
                        expect(control).to_have_attribute("aria-disabled","false")
                        logical = WIRE["ask"](worker,"logical","logical")
                    with WIRE["process"]("baseline",baseline,root,port) as (worker,port):
                        backend[0] = port
                        control.click()
                        expect(state).to_contain_text("session expired")
                        expect(page.locator("#conversation-thread")).not_to_contain_text("Synthetic rollback row")
                        expect(control).to_be_hidden()
                        expect(page.locator("#conversation-message")).to_be_disabled()
                        assert [e for e in events if e[0]=="messages"][-1] == (
                            "messages",401,["cursor","limit","pagination"],["100"],["keyset-v1"])
                        cookie(ctx,WIRE["issue"](worker))
                        # Reload the same tab, keeping frozen candidate UI. This models
                        # re-init after successful session issuance, not Google login.
                        with page.expect_response(ready):
                            page.reload()
                        expect(state).to_contain_text("conversation storage active")
                        expect(rows).to_have_count(100)
                        expect(rows.first).to_contain_text("Synthetic rollback row 000")
                        expect(rows.last).to_contain_text("Synthetic rollback row 099")
                        expect(control).to_be_hidden()
                        assert [e for e in events if e[0]=="messages"] == [
                            ("messages",200,["limit","pagination"],["100"],["keyset-v1"]),
                            ("messages",401,["cursor","limit","pagination"],["100"],["keyset-v1"]),
                            ("messages",200,["limit"],["100"],None),
                        ]
                        assert WIRE["ask"](worker,"logical","logical")==logical
                    assert not unexpected and not page_errors
            finally:
                browser.close()
    print("PASS candidate tab reset through real rollback and reloaded capability-free baseline (synthetic session only)")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate",type=Path)
    parser.add_argument("baseline_identity",type=Path)
    parser.add_argument("--http-only", action="store_true",
                        help="Exercise façade without importing or launching browser")
    args=parser.parse_args()
    check(args.candidate.resolve(),args.baseline_identity.resolve(),args.http_only)
