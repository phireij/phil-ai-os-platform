#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class CXHTMLAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang = None
        self.has_viewport = False
        self.has_main = False
        self.has_skip_link = False
        self.labels_for: set[str] = set()
        self.control_ids: set[str] = set()
        self.buttons_without_type = 0

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "html":
            self.html_lang = data.get("lang")
        if tag == "meta" and data.get("name") == "viewport":
            self.has_viewport = True
        if tag == "main":
            self.has_main = True
        if tag == "a" and data.get("href") == "#main":
            self.has_skip_link = True
        if tag == "label" and data.get("for"):
            self.labels_for.add(data["for"])
        if tag in {"input", "select", "textarea"} and data.get("id"):
            self.control_ids.add(data["id"])
        if tag == "button" and not data.get("type"):
            self.buttons_without_type += 1


def fail(message: str) -> None:
    raise SystemExit(f"PHIL_AI_OS_SPRINT_4_CX_VALIDATION_FAILED: {message}")


def main() -> None:
    required = [
        "index.html",
        "styles.css",
        "manifest.webmanifest",
        "app-icon.svg",
        "sw.js",
        "src/app.mjs",
        "src/core.mjs",
        "fixtures/catalog.json",
    ]
    for relative in required:
        if not (ROOT / relative).is_file():
            fail(f"missing required file: {relative}")

    fixture = json.loads((ROOT / "fixtures/catalog.json").read_text(encoding="utf-8"))
    if fixture.get("fixture_only") is not True:
        fail("catalog must be fixture_only")
    products = fixture.get("products")
    if not isinstance(products, list) or len(products) < 2:
        fail("catalog requires at least two synthetic products for responsive CX testing")
    seen_keys: set[str] = set()
    seen_skus: set[str] = set()
    for product in products:
        key = product.get("product_key")
        sku = product.get("sku")
        if not key or not sku or key in seen_keys or sku in seen_skus:
            fail("product keys and SKUs must be present and unique")
        seen_keys.add(key)
        seen_skus.add(sku)
        for field in ("name", "short_description", "description"):
            value = product.get(field, {})
            if not value.get("en") or not value.get("ja"):
                fail(f"{sku}: {field} requires non-empty en and ja")
        pickup = product.get("pickup", {})
        instructions = pickup.get("instructions", {})
        if pickup.get("supported") is not True or not instructions.get("en") or not instructions.get("ja"):
            fail(f"{sku}: bilingual pickup contract required")
        if not product.get("media") or product.get("primary_media_ref") != product["media"][0].get("ref"):
            fail(f"{sku}: deterministic primary media fixture required")

    manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    if manifest.get("display") != "standalone" or manifest.get("scope") != "./":
        fail("PWA manifest must remain local standalone scope")
    if not manifest.get("icons"):
        fail("PWA manifest requires an icon")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    audit = CXHTMLAudit()
    audit.feed(html)
    if audit.html_lang not in {"en", "ja"}:
        fail("html lang baseline is required")
    if not audit.has_viewport or not audit.has_main or not audit.has_skip_link:
        fail("mobile viewport, main landmark and skip link are required")
    if audit.buttons_without_type:
        fail("all buttons require explicit type")
    if not audit.control_ids.issubset(audit.labels_for | {"locale-select"}):
        fail("form controls require labels")

    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in required if path != "app-icon.svg")
    forbidden = {
        "production Ruby domain": r"rubyscakedelights\.shop",
        "WooCommerce consumer key": r"\bck_[A-Za-z0-9]{8,}",
        "WooCommerce consumer secret": r"\bcs_[A-Za-z0-9]{8,}",
        "authorizing mutation flag": r"mutation_authorized\s*[:=]\s*true",
        "external API endpoint": r"https?://(?!schema\.org|example\.invalid)",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, combined, flags=re.IGNORECASE):
            fail(f"forbidden {label} found in runtime foundation")

    app = (ROOT / "src/app.mjs").read_text(encoding="utf-8")
    if "fixture_only !== true" not in app:
        fail("app must refuse non-fixture catalog data")
    if 'serviceWorker.register("./sw.js")' not in app:
        fail("PWA service worker registration missing")

    print("PHIL_AI_OS_SPRINT_4_CX_VALIDATION_GREEN")


if __name__ == "__main__":
    main()
