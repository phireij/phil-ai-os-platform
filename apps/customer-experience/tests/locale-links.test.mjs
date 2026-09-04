import test from "node:test";
import assert from "node:assert/strict";
import { localizedRelativeHref } from "../src/locale-links.mjs";

test("relative customer-flow links preserve Japanese locale", () => {
  assert.equal(localizedRelativeHref("./cart-preview.html", "ja"), "./cart-preview.html?lang=ja");
  assert.equal(localizedRelativeHref("./quick-pickup-preview.html#main", "ja"), "./quick-pickup-preview.html?lang=ja#main");
});

test("existing query parameters are preserved while locale is replaced", () => {
  assert.equal(localizedRelativeHref("./?product=ube&lang=en", "ja"), "./?product=ube&lang=ja");
  assert.equal(localizedRelativeHref("./confirmation-preview.html?lang=ja", "en"), "./confirmation-preview.html?lang=en");
});

test("fragment-only and non-relative links are not rewritten", () => {
  assert.equal(localizedRelativeHref("#catalog-section", "ja"), "#catalog-section");
  assert.equal(localizedRelativeHref("https://example.com", "ja"), "https://example.com");
});
