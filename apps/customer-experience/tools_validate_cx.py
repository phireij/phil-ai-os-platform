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
        self.robots_content = None
        self.labels_for: set[str] = set()
        self.control_ids: set[str] = set()
        self.buttons_without_type = 0

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "html":
            self.html_lang = data.get("lang")
        if tag == "meta" and data.get("name") == "viewport":
            self.has_viewport = True
        if tag == "meta" and data.get("name") == "robots":
            self.robots_content = data.get("content")
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
        "src/cart.mjs",
        "src/flow.mjs",
        "src/payment.mjs",
        "src/pickup.mjs",
        "src/seo.mjs",
        "fixtures/catalog.json",
        "fixtures/payment-provider.json",
        "fixtures/pickup-policy.json",
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
        for seo_field in ("title", "description"):
            value = product.get("seo", {}).get(seo_field, {})
            if not value.get("en") or not value.get("ja"):
                fail(f"{sku}: seo.{seo_field} requires non-empty en and ja")
        pickup = product.get("pickup", {})
        instructions = pickup.get("instructions", {})
        if pickup.get("supported") is not True or not instructions.get("en") or not instructions.get("ja"):
            fail(f"{sku}: bilingual pickup contract required")
        if not product.get("media") or product.get("primary_media_ref") != product["media"][0].get("ref"):
            fail(f"{sku}: deterministic primary media fixture required")

    pickup_policy = json.loads((ROOT / "fixtures/pickup-policy.json").read_text(encoding="utf-8"))
    if pickup_policy.get("fixture_only") is not True:
        fail("pickup policy must be fixture_only")
    if not isinstance(pickup_policy.get("min_lead_minutes"), int) or pickup_policy["min_lead_minutes"] < 0:
        fail("pickup policy requires non-negative min_lead_minutes")
    if not isinstance(pickup_policy.get("max_advance_days"), int) or pickup_policy["max_advance_days"] < 1:
        fail("pickup policy requires positive max_advance_days")

    payment_provider = json.loads((ROOT / "fixtures/payment-provider.json").read_text(encoding="utf-8"))
    expected_payment_boundary = {
        "fixture_only": True,
        "provider": "komoju",
        "integration_mode": "woocommerce_plugin",
        "connection_mode": "account_sign_in",
        "connection_state": "not_configured",
        "test_mode_required_before_live": True,
        "live_mode_authorized": False,
        "payment_execution_authorized": False,
    }
    for key, expected in expected_payment_boundary.items():
        if payment_provider.get(key) != expected:
            fail(f"payment provider boundary mismatch: {key}")

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
    if audit.robots_content != "noindex,nofollow":
        fail("isolated preview must default to noindex,nofollow")
    if audit.buttons_without_type:
        fail("all buttons require explicit type")
    if not audit.control_ids.issubset(audit.labels_for | {"locale-select"}):
        fail("form controls require labels")

    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in required if path != "app-icon.svg")
    forbidden = {
        "production Ruby domain": r"rubyscakedelights\.shop",
        "WooCommerce consumer key": r"\bck_[A-Za-z0-9]{8,}",
        "WooCommerce consumer secret": r"\bcs_[A-Za-z0-9]{8,}",
        "KOMOJU live secret": r"\bsk_live_[A-Za-z0-9_-]{6,}",
        "KOMOJU test secret": r"\bsk_test_[A-Za-z0-9_-]{6,}",
        "KOMOJU live publishable key": r"\bpk_live_[A-Za-z0-9_-]{6,}",
        "KOMOJU test publishable key": r"\bpk_test_[A-Za-z0-9_-]{6,}",
        "authorizing mutation flag": r"mutation_authorized\s*[:=]\s*true",
        "authorizing payment flag": r"payment_execution_authorized\s*[:=]\s*true",
        "authorizing live mode flag": r"live_mode_authorized\s*[:=]\s*true",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, combined, flags=re.IGNORECASE):
            fail(f"forbidden {label} found in runtime foundation")

    allowed_url_prefixes = {"https://schema.org", "https://example.invalid"}
    urls = set(re.findall(r"https?://[A-Za-z0-9.-]+", combined))
    unexpected_urls = sorted(url for url in urls if url not in allowed_url_prefixes)
    if unexpected_urls:
        fail(f"unexpected external URL in runtime foundation: {unexpected_urls[0]}")

    app = (ROOT / "src/app.mjs").read_text(encoding="utf-8")
    if "fixture_only !== true" not in app:
        fail("app must refuse non-fixture data")
    if 'serviceWorker.register("./sw.js")' not in app:
        fail("PWA service worker registration missing")

    service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
    for cached_path in (
        "./src/cart.mjs",
        "./src/flow.mjs",
        "./src/payment.mjs",
        "./src/pickup.mjs",
        "./src/seo.mjs",
        "./fixtures/payment-provider.json",
        "./fixtures/pickup-policy.json",
    ):
        if cached_path not in service_worker:
            fail(f"offline app shell missing {cached_path}")

    print("PHIL_AI_OS_SPRINT_4_CX_VALIDATION_GREEN")


if __name__ == "__main__":
    main()
