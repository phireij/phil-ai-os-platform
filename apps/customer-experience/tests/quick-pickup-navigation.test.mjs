import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/quick-pickup-preview.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../quick-pickup-preview.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("Quick Pickup exposes consistent mobile Shop Cart Pickup navigation", () => {
  assert.match(html, /mobile-action-dock/);
  assert.match(html, /\.\/#catalog-section/);
  assert.match(html, /\.\/cart-preview\.html/);
  assert.match(html, /\.\/quick-pickup-preview\.html/);
  assert.match(html, /aria-current="page"/);
});

test("Quick Pickup navigation stays bilingual and locale preserving", () => {
  assert.match(source, /syncMobileNavigation/);
  assert.match(source, /syncLocaleLinks\(locale\)/);
  assert.match(source, /shop: "Shop"/);
  assert.match(source, /cart: "Cart"/);
  assert.match(source, /pickup: "Pickup"/);
  assert.match(source, /shop: "商品"/);
  assert.match(source, /cart: "カート"/);
  assert.match(source, /pickup: "受取"/);
  assert.match(source, /navLabel/);
});

test("navigation addition does not expand Quick Pickup authority", () => {
  assert.doesNotMatch(source, /automatic_publication_authorized\s*:\s*true/);
  assert.doesNotMatch(source, /activation_authorized\s*:\s*true/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
});

test("Quick Pickup remains available through the offline app shell", () => {
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/quick-pickup-preview\.html/);
  assert.match(sw, /\.\/src\/quick-pickup-preview\.mjs/);
});
