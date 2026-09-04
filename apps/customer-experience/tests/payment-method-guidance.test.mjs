import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/payment-method-guidance.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../payment-method-guidance.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");
const fixture = JSON.parse(readFileSync(new URL("../fixtures/final-confirmation.json", import.meta.url), "utf8"));

test("Konbini guidance mirrors governed preview deadline evidence", () => {
  assert.equal(fixture.payment.method, "konbini");
  assert.equal(fixture.payment.expiry_days, 3);
  assert.equal(fixture.payment.exact_transaction_deadline_controls, true);
  assert.match(source, /Pay within 3 days/);
  assert.match(source, /KOMOJU/);
  assert.match(source, /3日以内にお支払いください/);
  assert.match(source, /注文ごとに表示する期限が優先/);
});

test("payment guidance fails closed and remains non-authorizing", () => {
  assert.match(source, /fixture_only !== true/);
  assert.match(source, /preview_only !== true/);
  assert.match(source, /payment_execution_authorized !== false/);
  assert.match(source, /order_creation_authorized !== false/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
});

test("mobile payment guidance is bilingual, accessible and PWA-cached", () => {
  assert.match(html, /payment-method-guidance\.css/);
  assert.match(html, /src\/payment-method-guidance\.mjs/);
  assert.match(source, /aria-labelledby/);
  assert.match(css, /@media \(max-width: 679px\)/);
  assert.match(css, /@media \(forced-colors: active\)/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/src\/payment-method-guidance\.mjs/);
  assert.match(sw, /\.\/payment-method-guidance\.css/);
});
