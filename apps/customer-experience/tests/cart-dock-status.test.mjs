import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/cart-dock-status.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("mobile cart dock reports the selected quantity total", () => {
  assert.match(source, /selectedItemCount/);
  assert.match(source, /total \+ quantity/);
  assert.match(source, /data-cart-sku/);
  assert.match(source, /dataset\.cartCount/);
});

test("cart dock status is bilingual and screen-reader descriptive", () => {
  assert.match(source, /Cart, 1 item selected/);
  assert.match(source, /カート、/);
  assert.match(source, /aria-label/);
  assert.match(source, /locale-select/);
});

test("cart dock reacts locally to cart edits and DOM rendering", () => {
  assert.match(source, /addEventListener\("input"/);
  assert.match(source, /addEventListener\("change"/);
  assert.match(source, /MutationObserver/);
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
});

test("cart dock module is loaded and available through the PWA shell", () => {
  assert.match(html, /src\/cart-dock-status\.mjs/);
  assert.match(sw, /\.\/src\/cart-dock-status\.mjs/);
});
