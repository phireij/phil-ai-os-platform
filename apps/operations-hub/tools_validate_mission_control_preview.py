#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREVIEW = ROOT / "mission-control"


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_MISSION_CONTROL_PREVIEW_VALIDATION_FAILED: {message}")


def main() -> None:
    html = (PREVIEW / "index.html").read_text(encoding="utf-8")
    js = (PREVIEW / "mission-control.mjs").read_text(encoding="utf-8")
    fixture = json.loads((PREVIEW / "fixture.json").read_text(encoding="utf-8"))

    if fixture.get("schema") != "phil-ai-os-mission-control-lifecycle-projection":
        fail("projection schema drift")
    if fixture.get("status") != "read_only" or fixture.get("mission_control_mode") != "read_only":
        fail("Mission Control must remain read_only")
    if fixture.get("authority_effect") != "none":
        fail("authority_effect must remain none")
    if fixture.get("automation", {}).get("simulated_only") is not True:
        fail("automation must remain simulated-only")

    authority_flags = (
        "execution_authorized",
        "channel_reply_authorized",
        "network_dispatch_authorized",
        "woo_commerce_mutation_authorized",
        "order_creation_authorized",
        "payment_execution_authorized",
        "sms_send_authorized",
        "inventory_mutation_authorized",
        "production_publish_authorized",
        "mutation_authorized",
    )
    for field in authority_flags:
        if fixture.get(field) is not False:
            fail(f"{field} must remain false")

    for field, value in fixture.get("privacy", {}).items():
        if value is not False:
            fail(f"privacy exposure must remain false: {field}")

    forbidden_html = (
        r"<form\b",
        r"<button\b",
        r"type=[\"']submit[\"']",
        r"\bapprove\b[^<]{0,30}(button|control)",
        r"\bsend\b[^<]{0,30}(button|control)",
    )
    for pattern in forbidden_html:
        if re.search(pattern, html, flags=re.IGNORECASE):
            fail(f"interactive/authorizing HTML surface found: {pattern}")

    forbidden_js = (
        r"\bPOST\b",
        r"\bPUT\b",
        r"\bPATCH\b",
        r"\bDELETE\b",
        r"XMLHttpRequest",
        r"WebSocket",
        r"navigator\.sendBeacon",
    )
    for pattern in forbidden_js:
        if re.search(pattern, js, flags=re.IGNORECASE):
            fail(f"network write capability found: {pattern}")

    if 'fetch("./fixture.json"' not in js:
        fail("preview must load only the bounded local fixture")
    if "cache: \"no-store\"" not in js:
        fail("preview fixture must avoid stale caching")
    if "assertReadOnly" not in js:
        fail("runtime fail-closed read-only assertion missing")

    print(
        "PHIL_AI_OS_MISSION_CONTROL_PREVIEW_GREEN "
        "mode=read_only simulated_only=true writes=false replies=false network_dispatch=false authority_effect=none"
    )


if __name__ == "__main__":
    main()
