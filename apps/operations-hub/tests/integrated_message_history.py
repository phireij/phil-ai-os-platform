"""Exact static Mission Control UI + actual loopback SessionHandler (synthetic only)."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

BIND = "127.0.0.1"
BROWSER_HOST = "localhost"
# Handler's fixed virtual-host check. Header only; never resolved or connected to.
VIRTUAL_HOST = "miscon.phireij.cloud"
CONV = "conv_0000000000000001"
IDS = [f"message_{i:016d}" for i in range(205)]
FIXTURES = {
    "index.html", "mission-control.mjs", "mission-control.css", "fixture.json",
    "channel-readiness.json", "conversation.json", "project-readiness.json",
    "notification-read-model.json", "governed-proposals.json", "operator-read-model.json",
}
ROOTS = {
    "/auth/google/session": "session",
    "/api/conversations": "conversations",
    "/api/notifications": "notifications",
    **{f"/api/conversations/{CONV}/{suffix}": suffix for suffix in (
        "messages", "task-proposals", "audit-timeline", "cto-handoffs", "cto-handoff-results"
    )},
}
MAX_BODY = 4 * 1024 * 1024
FROZEN_BLOBS = {
    "apps/operations-hub/mission-control/index.html": "d708c09de0f3ff60a26e1999d81f9de9d7b65714",
    "apps/operations-hub/mission-control/mission-control.css": "344f3285eab5ecce27424eb7d0b4e1c916e8c4d6",
    "apps/operations-hub/mission-control/mission-control.mjs": "1a7c556c4f7c8303c778862163b92e345c48339e",
    "ops/mission-control-identity/conversation_store.py": "e212a037059c8e50c763e5a93a80219f16c0c032",
    "ops/mission-control-identity/google_ceo_session.py": "ce219aaec1d4f3fa20d383494c38ee22ce88cfcc",
}


def verify_frozen(repo):
    for path, expected in FROZEN_BLOBS.items():
        body = (repo / path).read_bytes()
        prefix = f"blob {len(body)}\0".encode("ascii")
        assert hashlib.sha1(prefix + body, usedforsecurity=False).hexdigest() == expected, path


@contextmanager
def serve(server_type, handler):
    server = server_type((BIND, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    try:
        yield server, thread
    finally:
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=5)
        server.server_close()
        if thread.is_alive():
            raise RuntimeError("test listener did not stop")


def seed(store, folder: Path):
    now = int(time.time())
    db = store._live.connection
    db.execute("INSERT INTO conversations VALUES (?,?,?,?)", (CONV, store._owner, now, now))
    for identifier in IDS[::2] + IDS[1::2][::-1]:
        ordinal = int(identifier.rsplit("_", 1)[1])
        db.execute("INSERT INTO messages VALUES (?,?,'ceo',?,?)",
                   (identifier, CONV, f"Synthetic row {ordinal:03d}", now))
    store._live.persist()
    return (folder / "store.enc").read_bytes()


@contextmanager
def setup(repo: Path):
    ops = repo / "ops/mission-control-identity"
    sys.path.insert(0, str(ops))
    from conversation_store import ConversationConfig, ConversationStore, MAGIC
    from google_ceo_session import SessionHandler, SessionStore, SESSION_COOKIE

    assets = repo / "apps/operations-hub/mission-control"
    static = {name: (assets / name).read_bytes() for name in FIXTURES}
    assert all(len(body) <= MAX_BODY for body in static.values())

    class QuietHandler(SessionHandler):
        # Disable synthetic cookie/query/data and route logging; leave application dispatch intact.
        def log_message(self, *_):
            pass

    with TemporaryDirectory(prefix="mc-history-loopback-") as tmp:
        folder = Path(tmp)
        key = folder / "key"
        key.write_text("47" * 32, encoding="ascii")
        key.chmod(0o600)
        store = ConversationStore(ConversationConfig(folder / "store.enc", folder / "ledger.enc", key),
                                  "https://accounts.google.com", "synthetic-history-owner")
        try:
            snapshot = seed(store, folder)
            assert snapshot.startswith(MAGIC)
            with serve(ThreadingHTTPServer, QuietHandler) as (backend, backend_thread):
                backend.sessions = SessionStore()
                backend.conversations = store
                backend.ruby_review_synthetic_surface_enabled = False
                # No Google configuration, gateway, provider, delivery, or product startup.
                token, _ = backend.sessions.issue()
                cookie = f"{SESSION_COOKIE}={token}"
                expected_host = ""
                events = []
                state_lock = threading.Lock()
                pause = threading.Event()
                entered = threading.Event()
                release = threading.Event()

                class Facade(BaseHTTPRequestHandler):
                    def log_message(self, *_):
                        pass

                    def send_body(self, status, body=b"", content_type="text/plain; charset=utf-8"):
                        self.send_response(status)
                        self.send_header("Content-Type", content_type)
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)

                    def deny_method(self):
                        self.send_body(405)

                    do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_CONNECT = do_OPTIONS = deny_method

                    def do_GET(self):
                        route = urlsplit(self.path)
                        if self.headers.get_all("Host") != [expected_host] or route.netloc or route.scheme:
                            self.send_body(400)
                            return
                        if len(self.path) > 8192 or route.fragment or re.search(r"[\\%]", route.path):
                            self.send_body(400)
                            return
                        if route.path == "/favicon.ico" and not route.query:
                            self.send_body(404)
                            return
                        name = route.path[1:] if route.path != "/" else "index.html"
                        if name in static and not route.query:
                            content_type = ("text/javascript" if name.endswith(".mjs") else
                                            mimetypes.guess_type(name)[0] or "application/octet-stream")
                            self.send_body(200, static[name], content_type)
                            return
                        label = ROOTS.get(route.path)
                        if label is None:
                            with state_lock:
                                events.append(("denied", 404, False))
                            self.send_body(404)
                            return
                        if self.headers.get_all("Cookie") not in (None, [cookie]):
                            self.send_body(400)
                            return
                        headers = {"Host": VIRTUAL_HOST, "Accept": "application/json"}
                        if self.headers.get("Cookie"):
                            headers["Cookie"] = cookie
                        older = label == "messages" and bool(parse_qs(route.query).get("cursor"))
                        if older and pause.is_set():
                            entered.set()
                            if not release.wait(timeout=10):
                                self.send_body(504)
                                return
                        conn = HTTPConnection(BIND, backend.server_port, timeout=5)
                        try:
                            conn.request("GET", self.path, headers=headers)
                            response = conn.getresponse()
                            body = response.read(MAX_BODY + 1)
                            content_type = response.getheader("Content-Type", "")
                            if (len(body) > MAX_BODY or not content_type.startswith("application/json")
                                    or response.getheader("Location") or response.getheader("Set-Cookie")):
                                self.send_body(502)
                                return
                            with state_lock:
                                events.append((label, response.status, older))
                            self.send_body(response.status, body, content_type)
                        finally:
                            conn.close()

                backend_thread.start()
                with serve(ThreadingHTTPServer, Facade) as (facade, facade_thread):
                    expected_host = f"{BROWSER_HOST}:{facade.server_port}"
                    facade_thread.start()
                    try:
                        yield (facade.server_port, cookie, token, SESSION_COOKIE, events, pause,
                               entered, release, folder, snapshot)
                    finally:
                        release.set()
                        assert (folder / "store.enc").read_bytes() == snapshot
        finally:
            store.close()


def http_smoke(port, cookie):
    def get(path, status, signed=False, method="GET", valid_host=True):
        c = HTTPConnection(BIND, port, timeout=6)
        h = {"Host": f"{BROWSER_HOST}:{port}" if valid_host else "unapproved.invalid"}
        if signed:
            h["Cookie"] = cookie
        try:
            c.request(method, path, headers=h)
            r = c.getresponse()
            body = r.read()
            assert r.status == status, (path.split("?")[0], status, r.status)
            return json.loads(body) if r.getheader("Content-Type").startswith("application/json") else body
        finally:
            c.close()

    get("/", 200)
    get("/mission-control.mjs", 200)
    get("/", 400, valid_host=False)
    get("/auth/google/start", 404)
    get("/auth/google/callback", 404)
    get("/api/conversations", 405, signed=True, method="POST")
    get("/auth/google/session", 401)
    get(f"/api/conversations/{CONV}/messages?pagination=keyset-v1", 401)
    assert get("/auth/google/session", 200, signed=True)["message_history_pagination"] == "keyset-v1"
    for suffix in ("task-proposals", "cto-handoffs", "cto-handoff-results"):
        get(f"/api/conversations/{CONV}/{suffix}?limit=100", 200, signed=True)
    audit = get(f"/api/conversations/{CONV}/audit-timeline?limit=100", 200, signed=True)
    assert audit["authority_effect"] == "none" and len(audit["events"]) == 100
    assert all(event["authority_effect"] == "none" and "body" not in event and "rationale" not in event
               for event in audit["events"])
    notifications = get("/api/notifications?limit=100", 200, signed=True)
    assert notifications["transport_status"] == "not_configured" and notifications["notifications"] == []
    cursor = None
    combined = []
    sizes = []
    for count in (100, 100, 5):
        q = {"pagination": "keyset-v1", "limit": "100"}
        if cursor:
            q["cursor"] = cursor
        page = get(f"/api/conversations/{CONV}/messages?{urlencode(q)}", 200, signed=True)
        current = [row["message_id"] for row in page["messages"]]
        assert len(current) == count
        assert all(row["authority_effect"] == "none" for row in page["messages"])
        cursor = page["next_cursor"]
        combined = current + combined
        sizes.append(count)
    assert cursor is None and combined == IDS
    print(f"PASS real HTTP facade and backend: 401, 200, scope denial, ordered pages {sizes}", flush=True)


def browser_check(port, token, name, events, pause, entered, release):
    from playwright.sync_api import sync_playwright, expect

    origin = f"http://{BROWSER_HOST}:{port}"
    unexpected = []
    errors = []

    def intercept(route):
        u = urlsplit(route.request.url)
        allowed = (f"{u.scheme}://{u.netloc}" == origin and route.request.method == "GET"
                   and (u.path in ROOTS or u.path == "/favicon.ico" or u.path == "/"
                        or u.path.lstrip("/") in FIXTURES))
        if allowed:
            route.continue_()
        else:
            unexpected.append(route.request.method)
            route.abort()

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        print(f"Chromium version={browser.version}", flush=True)
        try:
            before = len(events)
            with browser.new_context(service_workers="block") as ctx:
                ctx.route("**/*", intercept)
                page = ctx.new_page()
                page.on("pageerror", lambda _: errors.append("page-error"))
                page.goto(origin + "/")
                expect(page.locator("#conversation-state")).to_contain_text("sign-in available")
                expect(page.locator("#conversation-history-more")).to_be_hidden()
                expect(page.locator("#conversation-message")).to_be_disabled()
            assert events[before:] == [("session", 401, False)]
            before = len(events)
            with browser.new_context(service_workers="block", viewport={"width": 1280, "height": 840}) as ctx:
                ctx.route("**/*", intercept)
                ctx.add_cookies([dict(name=name, value=token, url=origin, secure=True,
                                      httpOnly=True, sameSite="Lax")])
                assert any(c["name"] == name and c["secure"] and c["httpOnly"]
                           for c in ctx.cookies([origin])), "loopback browser did not accept the synthetic cookie"
                page = ctx.new_page()
                page.on("pageerror", lambda _: errors.append("page-error"))
                page.goto(origin + "/")
                expect(page.locator("#load-state")).to_contain_text("SYNTHETIC FIXTURE")
                expect(page.locator("#conversation-state")).to_contain_text("conversation storage active")
                expect(page.locator("#conversation-lifecycle-state")).to_have_text("100 audit events · 0 local notifications · no authority")
                rows = page.locator("#conversation-thread .conversation-message")
                control = page.locator("#conversation-history-more")
                status = page.locator("#conversation-history-status")
                expect(rows).to_have_count(100)
                expect(rows.first).to_contain_text("Synthetic row 105")
                expect(rows.last).to_contain_text("Synthetic row 204")
                expect(control).to_have_attribute("aria-disabled", "false")
                pause.set()
                control.focus()
                control.press("Enter")
                expect(status).to_contain_text("Loading earlier")
                deadline = time.monotonic() + 3
                while not entered.is_set() and time.monotonic() < deadline:
                    # Let Playwright dispatch the route.continue_ callback.
                    page.wait_for_timeout(20)
                assert entered.is_set(), "real older-page request did not arrive"
                anchor = rows.get_by_text("Synthetic row 130", exact=True)
                y = anchor.evaluate('el => {el.scrollIntoView({block: "center"}); return el.getBoundingClientRect().top;}')
                pause.clear()
                release.set()
                expect(rows).to_have_count(200)
                expect(control).to_have_attribute("aria-disabled", "false")
                after = anchor.evaluate("el => el.getBoundingClientRect().top")
                assert abs(after - y) <= 3, "scroll position did not survive real prepend"
                expect(control).to_be_focused()
                control.press("Enter")
                expect(rows).to_have_count(205)
                expect(status).to_contain_text("No earlier messages remain")
                expect(control).to_be_focused()
                expect(control).to_have_attribute("aria-disabled", "true")
                dom = rows.evaluate_all('(nodes) => nodes.map(row => Number(row.textContent.match(/Synthetic row (\\d{3})/)[1]))')
                assert dom == list(range(205)), "DOM IDs are not complete and ordered"
                expect(page.locator("#conversation-lifecycle-state")).to_have_text("100 audit events · 0 local notifications · no authority")
                expected_requests = [("messages", 200, False), ("messages", 200, True), ("messages", 200, True)]
                assert [e for e in events[before:] if e[0] == "messages"] == expected_requests
                assert ("session", 200, False) in events[before:]
                assert all(label != "denied" and status_code == 200
                           for label, status_code, _ in events[before:])
            assert not unexpected and not errors, "unexpected browser request or page error"
        finally:
            release.set()
            browser.close()
    print("PASS Chromium integrated synthetic session, 100→200→205 records, no gaps, focus and scroll", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--http-only", action="store_true", help="No browser launch")
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    verify_frozen(checkout)
    with setup(checkout) as data:
        port, cookie, token, name, events, pause, entered, release, _, _ = data
        http_smoke(port, cookie)
        if not args.http_only:
            browser_check(port, token, name, events, pause, entered, release)
    print("PASS V1 encrypted snapshot unchanged", flush=True)


if __name__ == "__main__":
    main()
