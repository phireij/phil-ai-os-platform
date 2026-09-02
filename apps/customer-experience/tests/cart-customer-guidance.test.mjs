import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/cart-preview.mjs", import.meta.url), "utf8");

test("cart preview uses the shared bilingual readiness feedback boundary", () => {
  assert.match(source, /import \{ readinessFeedback \} from "\.\/readiness-feedback\.mjs"/);
  assert.match(source, /const feedback = readinessFeedback\(readiness, state\.locale\)/);
});

test("cart preview keeps technical payload behind a disclosure", () => {
  assert.match(source, /<details>/);
  assert.match(source, /technicalDetails/);
  assert.match(source, /customer_feedback: feedback/);
});

test("cart preview keeps production mutation authority false", () => {
  assert.match(source, /mutation_authorized: false/);
  assert.doesNotMatch(source, /mutation_authorized:\s*true/);
});
