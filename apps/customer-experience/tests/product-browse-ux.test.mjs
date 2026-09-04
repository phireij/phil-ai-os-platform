import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/product-browse-ux.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../product-browse-ux.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("mobile catalog supports fast all versus available-now scanning", () => {
  assert.ok(source.includes('data-filter="all"'));
  assert.ok(source.includes('data-filter="available"'));
  assert.match(source, /availability\.in_stock/);
  assert.ok(source.includes("Showing ${visible} of ${total}"));
  assert.match(source, /現在購入可能/);
});

test("available product detail offers a locale-and-product-preserving cart continuation", () => {
  assert.match(source, /mobile-detail-continuation/);
  assert.match(source, /selectedProductKey/);
  assert.match(source, /selectedDetailIsAvailable/);
  assert.match(source, /searchParams\.set\("product", productKey\)/);
  assert.match(source, /localeHref\(`\$\{cartUrl\.pathname\}\$\{cartUrl\.search\}`, lang\)/);
  assert.match(source, /Review cart/);
  assert.match(source, /カートを確認/);
});

test("unavailable product detail never presents a misleading cart continuation", () => {
  assert.match(source, /This item is currently unavailable/);
  assert.match(source, /この商品は現在購入できません/);
  assert.match(source, /See available products/);
  assert.match(source, /購入可能な商品を見る/);
  assert.match(source, /if \(!available\)/);
  assert.match(source, /is-unavailable-redirect/);
  assert.match(source, /localeHref\("\.\/#catalog-section", lang\)/);
  assert.match(source, /removeAttribute\("data-selected-product"\)/);
});

test("unavailable product detail becomes browse-only instead of showing an active checkout form", () => {
  assert.match(source, /syncDetailCheckoutAvailability/);
  assert.match(source, /checkout\.hidden = !available/);
  assert.match(source, /aria-hidden/);
  assert.match(source, /control\.disabled = !available/);
  assert.match(source, /panel\.dataset\.detailMode = "browse_only"/);
  assert.match(source, /panel\.dataset\.detailMode = "checkout_preview"/);
});

test("browsing enhancement remains non-authorizing and network inert", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("mobile browse assets are loaded and cached for weak connections", () => {
  assert.match(html, /product-browse-ux\.css/);
  assert.match(html, /src\/product-browse-ux\.mjs/);
  assert.match(css, /min-height: 48px/);
  assert.match(css, /position: sticky/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/src\/product-browse-ux\.mjs/);
  assert.match(sw, /\.\/product-browse-ux\.css/);
});
