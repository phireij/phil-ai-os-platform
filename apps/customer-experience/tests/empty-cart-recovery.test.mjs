import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/empty-cart-recovery.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../cart-mobile-controls.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("empty cart offers an explicit bilingual return-to-catalog action", () => {
  assert.match(source, /Browse products/);
  assert.match(source, /商品を見る/);
  assert.match(source, /Your cart is empty/);
  assert.match(source, /カートは空です/);
  assert.match(source, /localeHref\("\.\/#catalog-section", lang\)/);
});

test("recovery is visible only while selected quantity is zero", () => {
  assert.match(source, /selectedQuantityTotal/);
  assert.match(source, /const isEmpty = selectedQuantityTotal\(\) === 0/);
  assert.match(source, /recovery\.hidden = !isEmpty/);
  assert.match(source, /input\.disabled/);
});

test("recovery is accessible and thumb friendly", () => {
  assert.match(source, /role", "status/);
  assert.match(source, /aria-live", "polite/);
  assert.match(source, /aria-atomic", "true/);
  assert.match(css, /empty-cart-recovery-action/);
  assert.match(css, /min-height:\s*48px/);
  assert.match(css, /focus-visible/);
  assert.match(css, /forced-colors/);
});

test("recovery remains local and non-authorizing", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /XMLHttpRequest|sendBeacon/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
  assert.doesNotMatch(source, /order_creation_authorized\s*:\s*true/);
  assert.doesNotMatch(source, /payment_execution_authorized\s*:\s*true/);
});

test("recovery module is loaded and cached", () => {
  assert.match(html, /src\/empty-cart-recovery\.mjs/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/src\/empty-cart-recovery\.mjs/);
});
