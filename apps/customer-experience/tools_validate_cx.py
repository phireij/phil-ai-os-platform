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


def audit_html(relative: str) -> None:
    html = (ROOT / relative).read_text(encoding="utf-8")
    audit = CXHTMLAudit()
    audit.feed(html)
    if audit.html_lang not in {"en", "ja"}:
        fail(f"{relative}: html lang baseline is required")
    if not audit.has_viewport or not audit.has_main or not audit.has_skip_link:
        fail(f"{relative}: mobile viewport, main landmark and skip link are required")
    if audit.robots_content != "noindex,nofollow":
        fail(f"{relative}: isolated preview must default to noindex,nofollow")
    if audit.buttons_without_type:
        fail(f"{relative}: all buttons require explicit type")
    if not audit.control_ids.issubset(audit.labels_for | {"locale-select"}):
        missing = sorted(audit.control_ids - (audit.labels_for | {"locale-select"}))
        fail(f"{relative}: form controls require labels: {missing}")


def main() -> None:
    required = [
        "index.html",
        "cart-preview.html",
        "confirmation-preview.html",
        "styles.css",
        "manifest.webmanifest",
        "app-icon.svg",
        "sw.js",
        "src/app.mjs",
        "src/core.mjs",
        "src/cart.mjs",
        "src/cart-preview.mjs",
        "src/confirmation-preview.mjs",
        "src/flow.mjs",
        "src/payment.mjs",
        "src/pickup.mjs",
        "src/readiness-feedback.mjs",
        "src/seo.mjs",
        "fixtures/catalog.json",
        "fixtures/final-confirmation.json",
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
    if not isinstance(products, list) or len(products) < 3:
        fail("catalog requires at least three synthetic products for catalog/cart CX testing")
    seen_keys: set[str] = set()
    seen_skus: set[str] = set()
    in_stock_count = 0
    for product in products:
        key = product.get("product_key")
        sku = product.get("sku")
        if not key or not sku or key in seen_keys or sku in seen_skus:
            fail("product keys and SKUs must be present and unique")
        seen_keys.add(key)
        seen_skus.add(sku)
        if product.get("availability") == "in_stock":
            in_stock_count += 1
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
    if in_stock_count < 2:
        fail("multi-item GREEN path requires at least two synthetic in-stock products")

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

    confirmation = json.loads((ROOT / "fixtures/final-confirmation.json").read_text(encoding="utf-8"))
    expected_confirmation_boundary = {
        "fixture_only": True,
        "preview_only": True,
        "actual_final_confirmation_screen_reviewed": False,
        "order_creation_authorized": False,
        "mutation_authorized": False,
        "payment_execution_authorized": False,
        "production_publish_authorized": False,
    }
    for key, expected in expected_confirmation_boundary.items():
        if confirmation.get(key) != expected:
            fail(f"final confirmation boundary mismatch: {key}")
    if not isinstance(confirmation.get("items"), list) or not confirmation["items"]:
        fail("final confirmation fixture requires synthetic order items")
    calculated_subtotal = 0
    confirmation_skus: set[str] = set()
    for item in confirmation["items"]:
        sku = item.get("sku")
        quantity = item.get("quantity")
        unit_price = item.get("unit_price_jpy")
        if not sku or sku in confirmation_skus:
            fail("final confirmation fixture requires unique SKUs")
        confirmation_skus.add(sku)
        if not isinstance(quantity, int) or quantity < 1 or not isinstance(unit_price, int) or unit_price < 0:
            fail(f"{sku}: final confirmation quantity/price invalid")
        for field in ("name", "option"):
            localized = item.get(field, {})
            if not localized.get("en") or not localized.get("ja"):
                fail(f"{sku}: final confirmation {field} requires en and ja")
        calculated_subtotal += quantity * unit_price
    pricing = confirmation.get("pricing", {})
    if pricing.get("subtotal_jpy") != calculated_subtotal:
        fail("final confirmation subtotal drift")
    if pricing.get("total_jpy") != pricing.get("subtotal_jpy", 0) + pricing.get("shipping_jpy", 0):
        fail("final confirmation total drift")
    if pricing.get("consumption_tax_status") != "exempt" or pricing.get("qualified_invoice_status") != "not_registered":
        fail("final confirmation tax posture drift")
    if pricing.get("woocommerce_tax_enabled") is not False or pricing.get("separate_consumption_tax_jpy") != 0:
        fail("final confirmation unexpectedly adds WooCommerce consumption tax")
    shipping = confirmation.get("shipping", {})
    if shipping.get("method") != "yamato_cool" or shipping.get("region") != "kanto" or shipping.get("rate_jpy") != 1350:
        fail("final confirmation Yamato Cool Kanto rate drift")
    if pricing.get("shipping_jpy") != shipping.get("rate_jpy"):
        fail("final confirmation shipping total mismatch")
    payment = confirmation.get("payment", {})
    if payment.get("method") not in {"credit_card", "konbini", "merpay", "paidy"} or payment.get("provider") != "komoju":
        fail("final confirmation payment method/provider drift")
    if payment.get("method") == "konbini":
        if payment.get("live_expiry_setting_verified") is not True or payment.get("expiry_days") != 3:
            fail("final confirmation Konbini expiry must remain exactly 3 days")
        if payment.get("exact_transaction_deadline_controls") is not True or payment.get("example_deadline_only") is not True:
            fail("final confirmation must defer to the exact transaction deadline")
    fulfillment = confirmation.get("fulfillment", {})
    if fulfillment.get("dispatch_window_days") != [2, 5] or fulfillment.get("starts_after_required_payment_completion") is not True:
        fail("final confirmation fulfillment timing drift")
    cancellation = confirmation.get("cancellation", {})
    if [cancellation.get("full_refund_before_hours"), cancellation.get("half_fee_from_hours"), cancellation.get("half_fee_to_hours"), cancellation.get("full_fee_under_hours")] != [48, 24, 48, 24]:
        fail("final confirmation cancellation timing drift")

    manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
    if manifest.get("display") != "standalone" or manifest.get("scope") != "./":
        fail("PWA manifest must remain local standalone scope")
    if not manifest.get("icons"):
        fail("PWA manifest requires an icon")

    audit_html("index.html")
    audit_html("cart-preview.html")
    audit_html("confirmation-preview.html")

    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    cart_html = (ROOT / "cart-preview.html").read_text(encoding="utf-8")
    confirmation_html = (ROOT / "confirmation-preview.html").read_text(encoding="utf-8")
    if "./cart-preview.html" not in index_html:
        fail("catalog preview must link the isolated cart/payment handoff preview")
    if "./confirmation-preview.html" not in index_html or "./confirmation-preview.html" not in cart_html:
        fail("isolated customer flow must link the final confirmation compliance preview")
    for phrase in (
        "No order submission",
        "disabled>Place order (preview only — disabled)</button>",
        "This is not the actual WooCommerce final screen",
        "actual WooCommerce final screen reviewed = false",
    ):
        if phrase not in confirmation_html:
            fail(f"final confirmation HTML safety marker missing: {phrase}")

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
        "authorizing order creation flag": r"order_creation_authorized\s*[:=]\s*true",
        "authorizing production publish flag": r"production_publish_authorized\s*[:=]\s*true",
        "false actual-screen acceptance": r"actual_final_confirmation_screen_reviewed\s*[:=]\s*true",
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
    cart_preview = (ROOT / "src/cart-preview.mjs").read_text(encoding="utf-8")
    confirmation_preview = (ROOT / "src/confirmation-preview.mjs").read_text(encoding="utf-8")
    readiness_feedback = (ROOT / "src/readiness-feedback.mjs").read_text(encoding="utf-8")
    if "fixture_only !== true" not in app or "fixture_only !== true" not in cart_preview or "fixture_only !== true" not in confirmation_preview:
        fail("all customer previews must refuse non-fixture data")
    if 'serviceWorker.register("./sw.js")' not in app:
        fail("PWA service worker registration missing")
    if "buildPaymentHandoffIntent" not in cart_preview:
        fail("cart preview must compose the inert payment handoff through the tested boundary")
    for phrase in (
        "isolated preview cannot claim actual final-screen acceptance",
        "order_creation_authorized",
        "payment_execution_authorized",
        "production_publish_authorized",
        "Konbini confirmation must preserve the verified 3-day Live expiry",
        "payment method is outside the approved initial subset",
    ):
        if phrase not in confirmation_preview:
            fail(f"final confirmation module safety control missing: {phrase}")
    if "readiness feedback must remain non-authorizing" not in readiness_feedback:
        fail("customer readiness feedback must preserve the non-authorizing boundary")

    service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
    for cached_path in (
        "./cart-preview.html",
        "./confirmation-preview.html",
        "./src/cart.mjs",
        "./src/cart-preview.mjs",
        "./src/confirmation-preview.mjs",
        "./src/flow.mjs",
        "./src/payment.mjs",
        "./src/pickup.mjs",
        "./src/readiness-feedback.mjs",
        "./src/seo.mjs",
        "./fixtures/final-confirmation.json",
        "./fixtures/payment-provider.json",
        "./fixtures/pickup-policy.json",
    ):
        if cached_path not in service_worker:
            fail(f"offline app shell missing {cached_path}")

    print("PHIL_AI_OS_SPRINT_4_FINAL_CONFIRMATION_PREVIEW_GREEN fixture_only=true actual_screen=false order_creation=false payment_execution=false")
    print("PHIL_AI_OS_SPRINT_4_CX_VALIDATION_GREEN")


if __name__ == "__main__":
    main()
