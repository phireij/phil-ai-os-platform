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
                self.assertIn("preview/PREVIEW_BOUNDARY.txt", names)
                self.assertTrue(any(name.startswith("preview/src/") and name.endswith(".mjs") for name in names))
                for target in preview_builder.ALLOWED_FETCH_TARGETS:
                    self.assertIn("preview/" + target.removeprefix("./"), names)

                landing = archive.read("preview/index.html").decode("utf-8")
                self.assertIn("Ruby's Cake Delights", landing)
                self.assertIn("ruby-storefront-progress.css", landing)
                self.assertIn("engineering-preview.html", landing)
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

    def test_preview_boundary_injection_is_idempotent(self):
        source = "<html><head><meta name=\"robots\" content=\"noindex,nofollow\"></head><body><main>Test</main></body></html>"
        once = preview_builder._inject_preview_boundary(source)
        twice = preview_builder._inject_preview_boundary(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(preview_builder.PREVIEW_MARKER), 1)
        self.assertIn("noarchive", once.lower())

    def test_only_bundled_fixture_fetches_are_allowed(self):
        for target in sorted(preview_builder.ALLOWED_FETCH_TARGETS):
            preview_builder._validate_script_network_calls(
                f'const response = await fetch("{target}", {{ cache: "no-store" }});',
                "fixture.mjs",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                'await fetch("https://example.com/catalog.json");',
                "external.mjs",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                'await fetch("./fixtures/not-bundled.json");',
                "unknown-fixture.mjs",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                "await fetch(runtimeUrl);",
                "dynamic.mjs",
            )
        with self.assertRaises(ValueError):
            preview_builder._validate_script_network_calls(
                "const xhr = new XMLHttpRequest();",
                "xhr.mjs",
            )


if __name__ == "__main__":
    unittest.main()
