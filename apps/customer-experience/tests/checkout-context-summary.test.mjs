import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/checkout-context-summary.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../checkout-context-summary.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("mobile checkout context mirrors running total and fulfillment mode", () => {
  assert.match(source, /#cart-summary/);
  assert.match(source, /fulfillment-mode/);
  assert.match(source, /Store pickup/);
  assert.match(source, /Delivery/);
  assert.match(source, /店頭受取/);
  assert.match(source, /配送/);
});

test("context summary is accessible and responsive to cart changes", () => {
  assert.match(source, /role", "status/);
  assert.match(source, /aria-live", "polite/);
  assert.match(source, /MutationObserver/);
  assert.match(source, /addEventListener\("input"/);
  assert.match(source, /addEventListener\("change"/);
});

test("context summary is sticky only for mobile-sized screens", () => {
  assert.match(css, /max-width:\s*760px/);
  assert.match(css, /position:\s*sticky/);
  assert.match(css, /safe-area-inset-top/);
});

test("checkout context remains local, inert, and available offline", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
  assert.match(html, /checkout-context-summary\.css/);
  assert.match(html, /src\/checkout-context-summary\.mjs/);
  assert.match(sw, /\.\/checkout-context-summary\.css/);
  assert.match(sw, /\.\/src\/checkout-context-summary\.mjs/);
});
