import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/final-review-summary.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../confirmation-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../final-review-summary.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");
const fixture = JSON.parse(readFileSync(new URL("../fixtures/final-confirmation.json", import.meta.url), "utf8"));

test("mobile final review summarizes total, fulfillment, payment and policies", () => {
  assert.match(source, /Final review at a glance/);
  assert.match(source, /最終確認の要点/);
  assert.match(source, /pricing\.total_jpy/);
  assert.match(source, /fulfillment\.summary/);
  assert.match(source, /cancellation\.summary/);
  assert.match(source, /returns\.summary/);
});

test("Konbini deadline guidance remains aligned with fixture evidence", () => {
  assert.equal(fixture.payment.method, "konbini");
  assert.equal(fixture.payment.expiry_days, 3);
  assert.match(source, /transaction-specific KOMOJU deadline controls/);
  assert.match(source, /KOMOJUが注文ごとに表示する期限が優先/);
});

test("final review fails closed on authority flags", () => {
  assert.match(source, /order_creation_authorized !== false/);
  assert.match(source, /payment_execution_authorized !== false/);
  assert.match(source, /production_publish_authorized !== false/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("final review is mobile-readable, accessible and cached", () => {
  assert.match(html, /final-review-summary\.css/);
  assert.match(html, /src\/final-review-summary\.mjs/);
  assert.match(source, /aria-labelledby/);
  assert.match(css, /max-width: 679px/);
  assert.match(css, /position: sticky/);
  assert.match(css, /safe-area-inset-top/);
  assert.match(css, /forced-colors: active/);
  assert.match(sw, /\.\/final-review-summary\.css/);
  assert.match(sw, /\.\/src\/final-review-summary\.mjs/);
});
