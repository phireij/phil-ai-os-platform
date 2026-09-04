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

test("product cards expose clearer bilingual details actions with price and availability context", () => {
  assert.match(source, /View details/);
  assert.match(source, /詳細を見る/);
  assert.match(source, /decorateProductCardScanability/);
  assert.match(source, /aria-describedby/);
  assert.match(source, /product-\$\{key\}-availability/);
  assert.match(source, /product-\$\{key\}-price/);
  assert.match(source, /dataset\.cardAvailability/);
  assert.match(css, /fulfillment-chip:empty/);
  assert.match(css, /data-card-availability="unavailable"/);
});

test("catalog no-results state offers a bilingual one-tap recovery", () => {
  assert.match(source, /No products match this filter/);
  assert.match(source, /この条件に一致する商品はありません/);
  assert.match(source, /Show all products/);
  assert.match(source, /すべての商品を見る/);
  assert.match(source, /visible === 0 && filterMode !== "all"/);
  assert.match(source, /data-reset-filter/);
  assert.match(source, /resetToAllProducts/);
  assert.match(source, /filterMode = "all"/);
  assert.ok(source.includes(`document.querySelector('[data-filter="all"]')?.focus();`));
  assert.match(css, /browse-no-results-action/);
  assert.match(css, /min-height: 48px/);
});

test("catalog filter context survives product-detail navigation and return", () => {
  assert.match(source, /filterFromUrl/);
  assert.match(source, /URLSearchParams\(location\.search\)\.get\("filter"\)/);
  assert.match(source, /searchParams\.set\("filter", "available"\)/);
  assert.match(source, /decorateCatalogDetailLinks/);
  assert.match(source, /catalogReturnHref/);
  assert.match(source, /syncBackLink/);
  assert.match(source, /restoreFilterFromUrl/);
  assert.match(source, /popstate/);
});

test("catalog return restores focus near the previously opened product only", () => {
  assert.match(source, /RETURN_TARGET_KEY/);
  assert.match(source, /sessionStorage\.setItem\(RETURN_TARGET_KEY, productKey\)/);
  assert.match(source, /sessionStorage\.getItem\(RETURN_TARGET_KEY\)/);
  assert.match(source, /sessionStorage\.removeItem\(RETURN_TARGET_KEY\)/);
  assert.match(source, /if \(returnFocusRestored \|\| selectedProductKey\(\)\) return/);
  assert.match(source, /targetLink\.focus\(\{ preventScroll: true \}\)/);
  assert.match(source, /scrollIntoView\(\{ block: "center", inline: "nearest" \}\)/);
  assert.doesNotMatch(source, /localStorage/);
});

test("filter controls expose target and status semantics with visible focus", () => {
  assert.match(source, /aria-controls="catalog-grid browse-no-results"/);
  assert.match(source, /role="status"/);
  assert.match(source, /aria-live="polite"/);
  assert.match(source, /aria-atomic="true"/);
  assert.match(css, /filter-chip:focus-visible/);
  assert.match(css, /browse-no-results-action:focus-visible/);
  assert.match(css, /@media \(forced-colors: active\)/);
  assert.match(css, /Highlight/);
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
  assert.match(source, /filterMode = "available"/);
  assert.match(source, /link\.href = catalogReturnHref\(lang\)/);
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
