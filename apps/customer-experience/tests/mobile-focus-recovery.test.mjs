import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const guard = readFileSync(new URL("../src/cart-form-guard.mjs", import.meta.url), "utf8");
const css = readFileSync(new URL("../cart-mobile-controls.css", import.meta.url), "utf8");

test("mobile recovery action points customers at visible missing prerequisites", () => {
  assert.match(guard, /targetFor/);
  assert.match(guard, /chooseItem/);
  assert.match(guard, /choosePickup/);
  assert.match(guard, /chooseArea/);
  assert.match(guard, /scrollIntoView/);
  assert.match(guard, /\.focus\(/);
});

test("recovery remains accessible and touch friendly", () => {
  assert.match(guard, /aria-atomic/);
  assert.match(guard, /aria-describedby/);
  assert.match(css, /\.cart-guidance-action/);
  assert.match(css, /min-height:\s*48px/);
});

test("recovery does not introduce network execution", () => {
  assert.doesNotMatch(guard, /fetch\s*\(/);
  assert.doesNotMatch(guard, /POST|PUT|PATCH|DELETE/);
});
