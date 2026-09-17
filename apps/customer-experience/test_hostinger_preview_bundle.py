from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

import tools_build_hostinger_preview as preview_builder


class HostingerPreviewBundleTests(unittest.TestCase):
    def test_bundle_is_isolated_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ruby-cx-hostinger-preview.zip"
            preview_builder.build(output)
            self.assertTrue(output.exists())

            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("preview/index.html", names)
                self.assertIn("preview/engineering-preview.html", names)
                self.assertIn("preview/order-intake-preview.html", names)
                self.assertIn("preview/ruby-product-preview.html", names)
                self.assertIn("preview/ruby-product-preview.css", names)
                self.assertIn("preview/ruby-cart-preview.html", names)
                self.assertIn("preview/ruby-preview-cart.css", names)
                self.assertIn("preview/PREVIEW_BOUNDARY.txt", names)
                self.assertIn("preview/src/ruby-storefront.js", names)
                self.assertIn("preview/src/ruby-working-catalog-preview.js", names)
                self.assertIn("preview/src/ruby-working-product-detail.js", names)
                self.assertIn("preview/src/ruby-product-preview.js", names)
                self.assertIn("preview/src/ruby-preview-cart.js", names)
                self.assertIn("preview/src/ruby-cart-preview.js", names)

                # The actual first-party Quick Pickup preproduction acceptance route
                # must be present in every deployable Hostinger preview artifact.
                # This does not authorize deployment or production activation; it
                # only prevents a stale/incomplete artifact from passing CI.
                self.assertIn("preview/quick-pickup.html", names)
                self.assertIn("preview/src/quick-pickup-route.js", names)
                self.assertIn("preview/src/quick-pickup-route-copy.js", names)
                self.assertIn("preview/src/quick-pickup-checkout-contract.js", names)
                self.assertIn("preview/src/quick-pickup-disable-control.js", names)
                self.assertIn("preview/src/quick-pickup-decision-preview.js", names)
                self.assertIn("preview/src/quick-pickup-availability.js", names)
                self.assertIn("preview/src/quick-pickup-capacity.js", names)
                self.assertIn("preview/fixtures/first-party-quick-pickup.json", names)
                self.assertIn("preview/fixtures/quick-pickup-inventory-snapshot.json", names)
                self.assertIn("preview/fixtures/quick-pickup-capacity-snapshot.json", names)
                self.assertIn("preview/fixtures/quick-pickup-disable-control.json", names)

                self.assertTrue(any(name.startswith("preview/src/") and name.endswith(".js") for name in names))
                self.assertFalse(any(name.startswith("preview/src/") and name.endswith(".mjs") for name in names))
                for target in preview_builder.ALLOWED_FETCH_TARGETS:
                    self.assertIn("preview/" + target.removeprefix("./"), names)

                landing = archive.read("preview/index.html").decode("utf-8")
                self.assertIn("Ruby's Cake Delights", landing)
                self.assertIn("ruby-storefront-progress.css", landing)
                self.assertIn('id="ruby-working-products"', landing)
                self.assertIn("src/ruby-storefront.js", landing)
                self.assertNotIn(".mjs", landing)
                self.assertIn("ruby-cart-preview.html", landing)
                self.assertNotIn('href="./cart-preview.html"', landing)
                self.assertIn("engineering-preview.html", landing)
                self.assertEqual(landing.count("PRE-PRODUCTION PREVIEW"), 1)
                self.assertNotIn('class="phil-preview-boundary"', landing)

                quick_pickup = archive.read("preview/quick-pickup.html").decode("utf-8")
                self.assertIn("Ordering disabled", quick_pickup)
                self.assertIn("src/quick-pickup-route.js", quick_pickup)
                self.assertNotIn(".mjs", quick_pickup)
                self.assertIn("PRE-PRODUCTION PREVIEW", quick_pickup)
                self.assertIn('name="robots"', quick_pickup.lower())
                self.assertIn("noindex", quick_pickup.lower())

                quick_pickup_route = archive.read("preview/src/quick-pickup-route.js").decode("utf-8")
                self.assertIn("order_creation_authorized: false", quick_pickup_route)
                self.assertIn("payment_execution_authorized: false", quick_pickup_route)
                self.assertIn("production_publish_authorized: false", quick_pickup_route)
                self.assertNotIn(".mjs", quick_pickup_route)

                product_detail = archive.read("preview/ruby-product-preview.html").decode("utf-8")
                self.assertIn('id="ruby-product-detail"', product_detail)
                self.assertIn("ruby-product-preview.css", product_detail)
                self.assertIn("ruby-preview-cart.css", product_detail)
                self.assertIn("src/ruby-product-preview.js", product_detail)
                self.assertNotIn(".mjs", product_detail)
                self.assertIn("ruby-cart-preview.html", product_detail)
                self.assertNotIn('href="./cart-preview.html"', product_detail)

                branded_cart = archive.read("preview/ruby-cart-preview.html").decode("utf-8")
                self.assertIn('id="ruby-preview-cart-root"', branded_cart)
                self.assertIn("ruby-preview-cart.css", branded_cart)
                self.assertIn("src/ruby-cart-preview.js", branded_cart)
                self.assertNotIn(".mjs", branded_cart)
                self.assertNotIn("KOMOJU", branded_cart)
                self.assertNotIn('href="./cart-preview.html"', branded_cart)

                storefront_module = archive.read("preview/src/ruby-storefront.js").decode("utf-8")
                self.assertIn('./ruby-storefront-progress.js', storefront_module)
                self.assertIn('./ruby-working-catalog-preview.js', storefront_module)
                self.assertNotIn(".mjs", storefront_module)

                engineering = archive.read("preview/engineering-preview.html").decode("utf-8")
                self.assertIn("Phil AI OS · Sprint 4", engineering)
                self.assertIn("Ruby storefront", engineering)

                for name in sorted(n for n in names if n.endswith(".html")):
                    text = archive.read(name).decode("utf-8")
                    lower = text.lower()
                    self.assertIn(preview_builder.PREVIEW_MARKER, text)
                    self.assertIn('name="robots"', lower)
                    self.assertIn("noindex", lower)
                    self.assertIn("noarchive", lower)
                    self.assertNotIn("rubyscakedelights.shop", lower)
                    self.assertIn("PRE-PRODUCTION PREVIEW", text)
                    self.assertNotIn(".mjs", text)

    def test_preview_boundary_injection_is_idempotent(self):
        source = "<html><head><meta name=\"robots\" content=\"noindex,nofollow\"></head><body><main>Test</main></body></html>"
        once = preview_builder._inject_preview_boundary(source)
        twice = preview_builder._inject_preview_boundary(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(preview_builder.PREVIEW_MARKER), 1)
        self.assertIn("noarchive", once.lower())

    def test_existing_branded_preview_strip_is_not_duplicated(self):
        source = (
            "<html><head><meta name=\"robots\" content=\"noindex,nofollow\"></head><body>"
            "<div class=\"preview-strip\">PRE-PRODUCTION PREVIEW · Visual progress only</div>"
            "<main>Test</main></body></html>"
        )
        injected = preview_builder._inject_preview_boundary(source)
        self.assertEqual(injected.count("PRE-PRODUCTION PREVIEW"), 1)
        self.assertIn(preview_builder.PREVIEW_MARKER, injected)
        self.assertNotIn('class="phil-preview-boundary"', injected)

    def test_browser_module_refs_are_rewritten_for_shared_hosting(self):
        source = (
            '<script type="module" src="./src/app.mjs"></script>\n'
            'import "./core.mjs";\n'
            'export { thing } from "./thing.mjs";'
        )
        rewritten = preview_builder._rewrite_browser_module_refs(source)
        self.assertNotIn(".mjs", rewritten)
        self.assertIn("./src/app.js", rewritten)
        self.assertIn("./core.js", rewritten)
        self.assertIn("./thing.js", rewritten)

    def test_only_bundled_fixture_fetches_are_allowed(self):
        for target in sorted(preview_builder.ALLOWED_FETCH_TARGETS):
            preview_builder._validate_script_network_calls(
                f'const response = await fetch("{target}", {{ cache: "no-store" }});',
                "fixture.js",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                'await fetch("https://example.com/catalog.json");',
                "external.js",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                'await fetch("./fixtures/not-bundled.json");',
                "unknown-fixture.js",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                "await fetch(runtimeUrl);",
                "dynamic.js",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                "const xhr = new XMLHttpRequest();",
                "xhr.js",
            )


if __name__ == "__main__":
    unittest.main()
