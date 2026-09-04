import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/cart-session-recovery.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("cart recovery is session-scoped and stores only checkout choices", () => {
  assert.match(source, /sessionStorage/);
  assert.match(source, /quantities/);
  assert.match(source, /pickupAt/);
  assert.match(source, /deliveryArea/);
  assert.doesNotMatch(source, /localStorage/);
  assert.doesNotMatch(source, /email|phone|address|card|payment_token|customer_id/i);
});

test("explicit product navigation wins over stale session recovery", () => {
  assert.match(source, /explicitProductSelectionPresent/);
  assert.match(source, /URLSearchParams\(location\.search\)\.get\("product"\)/);
  assert.match(source, /if \(!saved \|\| explicitProductSelectionPresent\(\)\) return false/);
});

test("restored choices are clamped and re-run local readiness guards", () => {
  assert.match(source, /MAX_QUANTITY = 99/);
  assert.match(source, /dispatchEvent\(new Event\("input"/);
  assert.match(source, /dispatchEvent\(new Event\("change"/);
});

test("session recovery remains network-inert and non-authorizing", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /XMLHttpRequest|sendBeacon/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("session recovery is loaded and available in the PWA shell", () => {
  assert.match(html, /src\/cart-session-recovery\.mjs/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v19/);
  assert.match(sw, /\.\/src\/cart-session-recovery\.mjs/);
});
