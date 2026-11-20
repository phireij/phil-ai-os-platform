"""Playwright acceptance against exact static frontend; synthetic API only."""
import argparse
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

args = argparse.ArgumentParser(description=__doc__)
args.add_argument("frontend", type=Path)
args.add_argument("--browser", default=None, help="Installed Chromium path, if not using Playwright's bundled Chromium")
args.add_argument("--legacy-frontend", type=Path, help="Exact baseline frontend (optional legacy UI/new API check)")
config = args.parse_args()
www = config.frontend.resolve()
origin = "http://mission-control.test"
conv = "conv_0000000000000001"

def row(n):
    return dict(conversation_id=conv, message_id=f"message_{n:016d}", sender="ceo",
                body=f"Synthetic row {n:03d}", created_at="2026-11-20T00:00:00Z",
                authority_effect="none")

def replay(browser, mode, frontend=www):
    page = browser.new_page(viewport={"width": 390 if mode == "mobile" else 1280, "height": 840})
    seen = []
    fail_once = mode == "retry"
    expiry = mode == "expiry"
    captured_errors = []
    unexpected = []
    held = []
    page.on("pageerror", lambda error: captured_errors.append(str(error)))

    def route(r):
        req = r.request
        u = urlparse(req.url)
        if not req.url.startswith(origin + "/") or req.method != "GET":
            unexpected.append((req.method, u.path))
            r.abort()
            return
        if u.path == "/auth/google/session":
            if mode == "signedout":
                return r.fulfill(status=401, json={"error": "unauthorized"})
            session = dict(authenticated=True, conversation_authority=True, csrf_token="synthetic")
            if mode == "inactive":
                session["conversation_authority"] = False
            elif mode != "legacy_api":
                session["message_history_pagination"] = "keyset-v1"
            r.fulfill(json=session)
        elif u.path == "/api/conversations":
            r.fulfill(json={"conversations": [{"conversation_id": conv}]})
        elif u.path == f"/api/conversations/{conv}/messages":
            nonlocal fail_once, expiry
            q = parse_qs(u.query)
            if mode in {"legacy_api", "legacy_ui"}:
                assert q == {"limit": ["100"]}, q
                seen.append("legacy")
                return r.fulfill(json={"conversation_id": conv,
                    "messages": [row(n) for n in range(5, 105)], "next_cursor": None})
            assert q.get("pagination") == ["keyset-v1"] and q.get("limit") == ["100"], q
            cursor = q.get("cursor", [None])[0]
            seen.append(cursor)
            if cursor and fail_once:
                fail_once = False
                return r.fulfill(status=503, json={"error": "synthetic_retry"})
            if cursor and expiry:
                expiry = False
                return r.fulfill(status=400, json={"error": "invalid_cursor"})
            if cursor == "synthetic-older":
                rows, next_cursor = range(0, 5), None
            else:
                assert cursor is None
                rows, next_cursor = range(5, 105), "synthetic-older"
            payload = {"conversation_id": conv, "messages": [row(n) for n in rows], "next_cursor": next_cursor}
            if mode == "scroll" and cursor:
                held.append((r, payload))
                return
            r.fulfill(json=payload)
        elif u.path == f"/api/conversations/{conv}/task-proposals":
            r.fulfill(json={"proposals": [], "authority_effect": "none"})
        elif u.path == f"/api/conversations/{conv}/audit-timeline":
            r.fulfill(json={"conversation_id": conv, "events": [],
                            "source_coverage": [], "authority_effect": "none"})
        elif u.path == "/api/notifications":
            r.fulfill(json={"notifications": [], "transport_status": "not_configured",
                            "authority_effect": "none"})
        elif u.path.startswith(("/api/", "/auth/")):
            unexpected.append((req.method, u.path))
            r.fulfill(status=404)
        else:
            name = u.path.strip("/") or "index.html"
            f = frontend / name
            if "/" not in name and f.is_file():
                ctype = {".mjs": "text/javascript", ".css": "text/css", ".html": "text/html",
                         ".json": "application/json"}.get(f.suffix, "application/octet-stream")
                r.fulfill(path=str(f), content_type=ctype)
            else:
                if name != 'favicon.ico':
                    unexpected.append((req.method, u.path))
                r.fulfill(status=404)

    page.route("**/*", route)
    page.goto(origin + "/")
    expect(page.locator("#load-state")).to_contain_text("SYNTHETIC FIXTURE")
    control = page.locator("#conversation-history-more")
    status = page.locator("#conversation-history-status")
    rows = page.locator("#conversation-thread .conversation-message")
    if mode in {"signedout", "inactive"}:
        expect(page.locator("#conversation-state")).to_contain_text(
            "sign-in available" if mode == "signedout" else "storage inactive")
        expect(control).to_be_hidden()
        expect(page.locator("#conversation-message")).to_be_disabled()
        assert not seen and not unexpected and not captured_errors
        page.close()
        return
    expect(page.locator("#conversation-lifecycle-state")).to_contain_text("0 audit events")
    expect(page.locator("#conversation-state")).to_contain_text("conversation storage active")
    expect(rows).to_have_count(100)
    expect(rows.first).to_contain_text("Synthetic row 005")
    expect(rows.last).to_contain_text("Synthetic row 104")
    if mode in {"legacy_api", "legacy_ui"}:
        expect(control).to_be_hidden()  # Includes a legacy UI without this element.
        assert seen == ["legacy"] and not unexpected and not captured_errors
        page.close()
        return
    expect(control).to_have_attribute("aria-disabled", "false")
    control.focus()
    control.press("Enter")
    if mode == "retry":
        expect(status).to_contain_text("Try again")
        expect(rows).to_have_count(100)
        control.press("Space")
    if mode == "expiry":
        expect(control).to_have_text("Refresh latest messages")
        control.press("Enter")
        expect(control).to_have_text("Load earlier messages")
        expect(rows).to_have_count(100)
        control.press("Enter")
    anchor_top = None
    if mode == "scroll":
        # Let the user move into the transcript while the network is pending.
        expect(status).to_contain_text("Loading earlier")
        assert len(held) == 1, held
        anchor = rows.filter(has_text="Synthetic row 030")
        anchor_top = anchor.evaluate("""row => {
            row.scrollIntoView({block: "center"});
            return row.getBoundingClientRect().top;
        }""")
        r, payload = held.pop()
        r.fulfill(json=payload)
    expect(rows).to_have_count(105)
    for n, item in enumerate(rows.all()):
        expect(item).to_contain_text(f"Synthetic row {n:03d}")
    expect(status).to_contain_text("No earlier messages remain")
    if anchor_top is not None:
        after = rows.filter(has_text="Synthetic row 030").evaluate(
            "row => row.getBoundingClientRect().top")
        assert abs(after - anchor_top) <= 3, (anchor_top, after)
    expect(control).to_be_focused()
    expect(control).to_have_attribute("aria-disabled", "true")
    assert seen == {
        "desktop": [None, "synthetic-older"], "mobile": [None, "synthetic-older"],
        "retry": [None, "synthetic-older", "synthetic-older"],
        "expiry": [None, "synthetic-older", None, "synthetic-older"],
        "scroll": [None, "synthetic-older"],
    }[mode], seen
    assert not unexpected and not captured_errors, (unexpected, captured_errors)
    page.close()

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=config.browser, headless=True)
    for mode in ("desktop", "mobile", "retry", "expiry", "scroll", "signedout", "inactive", "legacy_api"):
        replay(browser, mode)
        print(f"PASS {mode}")
    if config.legacy_frontend:
        replay(browser, "legacy_ui", config.legacy_frontend.resolve())
        print("PASS legacy_ui")
    browser.close()
