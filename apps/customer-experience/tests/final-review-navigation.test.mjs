import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/final-review-navigation.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../confirmation-preview.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("final review exposes thumb-friendly correction navigation", () => {
  assert.match(html, /id="final-review-mobile-nav"/);
  assert.match(html, /href="\.\/cart-preview\.html"/);
  assert.match(html, /aria-current="page"/);
  assert.match(source, /Edit cart/);
  assert.match(source, /カート修正/);
});

test("final review navigation preserves locale across relative links", () => {
  assert.match(source, /syncLocaleLinks/);
  assert.match(source, /queueMicrotask\(updateFinalReviewNavigation\)/);
  assert.match(source, /Final review navigation/);
  assert.match(source, /最終確認ナビゲーション/);
});

test("correction navigation remains local and non-authorizing", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
  assert.match(sw, /\.\/src\/final-review-navigation\.mjs/);
});

await import("../src/final-review-navigation.mjs");
