import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/cart-form-guard.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../cart-mobile-controls.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("cart guard blocks avoidable submit attempts until visible prerequisites are met", () => {
  assert.match(source, /chooseItem/);
  assert.match(source, /choosePickup/);
  assert.match(source, /chooseArea/);
  assert.match(source, /button\.disabled = !ready/);
  assert.match(source, /aria-disabled/);
});

test("cart guard is bilingual and reacts to pickup or delivery mode", () => {
  assert.match(source, /Choose at least one available item/);
  assert.match(source, /利用可能な商品を1つ以上/);
  assert.match(source, /fulfillmentMode\(\) === "delivery"/);
  assert.match(source, /#delivery-area/);
  assert.match(source, /#pickup-at/);
});

test("blocked customers can jump directly to the required mobile field", () => {
  assert.match(source, /Go to required field/);
  assert.match(source, /必要な項目へ移動/);
  assert.match(source, /focusRequiredField/);
  assert.match(source, /scrollIntoView/);
  assert.match(source, /preventScroll: true/);
  assert.match(source, /aria-describedby/);
  assert.match(css, /cart-guidance-action/);
  assert.match(css, /min-height:\s*48px/);
});

test("cart guard remains network-inert and non-authorizing", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("cart guard is loaded, styled and cached", () => {
  assert.match(html, /src\/cart-form-guard\.mjs/);
  assert.match(css, /cart-form-guidance/);
  assert.match(css, /#evaluate-button:disabled/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/src\/cart-form-guard\.mjs/);
});
