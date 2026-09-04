import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const cart = readFileSync(new URL("../src/cart-preview.mjs", import.meta.url), "utf8");
const continuity = readFileSync(new URL("../src/cart-selection-continuity.mjs", import.meta.url), "utf8");

test("direct cart visits start empty instead of preselecting products", () => {
  assert.match(cart, /function defaultQuantity\(\) \{\s*return 0;\s*\}/);
  assert.doesNotMatch(cart, /index < 3 \? 1 : 0/);
  assert.match(cart, /Your cart is empty\. Choose a product to continue\./);
  assert.match(cart, /カートは空です。商品を選択して続行してください。/);
});

test("explicit product carryover can still select one intended product", () => {
  assert.match(continuity, /requestedProductKey/);
  assert.match(continuity, /input\.value = "1"/);
  assert.match(continuity, /explicitSelectionApplied/);
});

test("empty-cart behavior adds no network mutation or authority", () => {
  assert.doesNotMatch(cart, /mutation_authorized\s*:\s*true/);
  assert.doesNotMatch(continuity, /POST|PUT|PATCH|DELETE/);
});
