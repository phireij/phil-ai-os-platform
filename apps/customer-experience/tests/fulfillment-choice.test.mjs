import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/fulfillment-choice.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../fulfillment-choice.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("mobile cart offers pickup and delivery choices", () => {
  assert.match(source, /Store pickup/);
  assert.match(source, /Delivery/);
  assert.match(source, /店頭受取/);
  assert.match(source, /配送/);
  assert.match(source, /fulfillment-mode/);
});

test("delivery guidance preserves approved shipping wording", () => {
  assert.match(source, /Kanto: ¥1,350 flat rate/);
  assert.match(source, /Other regions: ¥1,500–¥1,800 depending on delivery area/);
  assert.match(source, /関東：一律 1,350円/);
  assert.match(source, /その他の地域：配送地域により 1,500円〜1,800円/);
  assert.match(source, /exact shipping fee will be displayed on the final order confirmation screen/);
});

test("delivery preview remains non-authorizing and blocks payment handoff", () => {
  assert.match(source, /No order or payment handoff was prepared for delivery/);
  assert.match(source, /event\.stopImmediatePropagation\(\)/);
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("fulfillment assets are mobile-ready and cached", () => {
  assert.match(html, /fulfillment-choice\.css/);
  assert.match(html, /src\/fulfillment-choice\.mjs/);
  assert.match(css, /min-height: 72px/);
  assert.match(css, /min-height: 48px/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/fulfillment-choice\.css/);
  assert.match(sw, /\.\/src\/fulfillment-choice\.mjs/);
});
