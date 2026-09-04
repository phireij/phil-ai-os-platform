import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const source = readFileSync(new URL("../src/checkout-confidence.mjs", import.meta.url), "utf8");

test("checkout preview explains order, fulfillment and payment review before final action", () => {
  assert.match(html, /id="confidence-order-title"/);
  assert.match(html, /id="confidence-fulfillment-title"/);
  assert.match(html, /id="confidence-payment-title"/);
  assert.match(html, /shipping fee before order submission/);
  assert.match(html, /review the final information before any order-submission action/);
});

test("checkout confidence guidance is bilingual", () => {
  assert.match(source, /You stay in control before the final action/);
  assert.match(source, /最終操作の前に、内容を確認できます/);
  assert.match(source, /商品・数量・合計金額/);
  assert.match(source, /支払方法と支払時期/);
});

test("mobile cart navigation is thumb-friendly and does not add execution", () => {
  assert.match(html, /class="mobile-action-dock"/);
  assert.match(html, /aria-current="page"/);
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
});
