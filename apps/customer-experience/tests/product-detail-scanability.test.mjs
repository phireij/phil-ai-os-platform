import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../src/app.mjs", import.meta.url), "utf8");
const css = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("product detail surfaces availability price and pickup support as key facts", () => {
  assert.match(app, /product-key-facts/);
  assert.match(app, /Availability/);
  assert.match(app, /在庫状況/);
  assert.match(app, /Price/);
  assert.match(app, /価格/);
  assert.match(app, /Pickup available/);
  assert.match(app, /店頭受取対応/);
  assert.match(app, /pickupSupported/);
});

test("product detail media exposes image semantics without inventing production media", () => {
  assert.match(app, /role="img"/);
  assert.match(app, /vm\.media\[0\]\?\.alt/);
  assert.doesNotMatch(app, /mutation_authorized\s*:\s*true/);
});

test("mobile key facts remain scannable", () => {
  assert.match(css, /\.product-key-facts/);
  assert.match(css, /\.product-key-fact/);
  assert.match(css, /grid-template-columns/);
  assert.match(css, /@media \(max-width: 679px\)/);
});

test("updated product detail ships through the current PWA shell", () => {
  assert.match(sw, /phil-ai-os-cx-sprint4-v23/);
  assert.match(sw, /\.\/src\/app\.mjs/);
  assert.match(sw, /\.\/styles\.css/);
});
