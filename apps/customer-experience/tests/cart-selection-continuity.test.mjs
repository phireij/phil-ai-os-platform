import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/cart-selection-continuity.mjs", import.meta.url), "utf8");
const browse = readFileSync(new URL("../src/product-browse-ux.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("product detail continuation carries explicit product identity into cart", () => {
  assert.match(browse, /searchParams\.set\("product", productKey\)/);
  assert.match(browse, /selectedProductKey/);
  assert.match(browse, /selected product/);
});

test("cart defaults to only the explicitly requested available product", () => {
  assert.match(source, /for \(const input of inputs\) input\.value = "0"/);
  assert.match(source, /product_key === requestedProductKey/);
  assert.match(source, /input\.value = "1"/);
  assert.match(source, /input && !input\.disabled/);
});

test("missing or unavailable carried product fails visibly without execution", () => {
  assert.match(source, /selected product is not currently available in the cart/);
  assert.match(source, /選択した商品は現在カートで利用できません/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /payment|order.*create/i);
});

test("continuity module is loaded and cached", () => {
  assert.match(html, /src\/cart-selection-continuity\.mjs/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v12/);
  assert.match(sw, /\.\/src\/cart-selection-continuity\.mjs/);
});
