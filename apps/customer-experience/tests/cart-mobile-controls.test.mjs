import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/cart-mobile-controls.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../cart-mobile-controls.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("quantity controls support thumb-friendly decrement and increment", () => {
  assert.match(source, /data-delta="-1"/);
  assert.match(source, /data-delta="1"/);
  assert.match(source, /Decrease quantity/);
  assert.match(source, /数量を減らす/);
  assert.match(css, /min-width: 48px/);
  assert.match(css, /min-height: 48px/);
});

test("line totals update locally with bilingual labels", () => {
  assert.match(source, /Item total/);
  assert.match(source, /商品小計/);
  assert.match(source, /formatYen/);
  assert.match(source, /numericUnitPrice/);
});

test("cart controls remain network-inert and non-authorizing", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("mobile cart assets are loaded and cached", () => {
  assert.match(html, /cart-mobile-controls\.css/);
  assert.match(html, /src\/cart-mobile-controls\.mjs/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v14/);
  assert.match(sw, /\.\/cart-mobile-controls\.css/);
  assert.match(sw, /\.\/src\/cart-mobile-controls\.mjs/);
});
