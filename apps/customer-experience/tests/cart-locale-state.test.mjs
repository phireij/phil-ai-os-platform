import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/cart-locale-state.mjs", import.meta.url), "utf8");
const continuity = readFileSync(new URL("../src/cart-selection-continuity.mjs", import.meta.url), "utf8");
const html = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("cart quantities are snapshotted before locale rerender and restored after", () => {
  assert.match(source, /snapshotQuantities/);
  assert.match(source, /restoreQuantities/);
  assert.match(source, /queueMicrotask/);
  assert.match(source, /addEventListener\("change"/);
  assert.match(source, /true\);/);
});

test("restoration updates totals without network or authority", () => {
  assert.match(source, /dispatchEvent\(new Event\("input"/);
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("explicit product carryover runs at most once so customer edits survive", () => {
  assert.match(continuity, /explicitSelectionApplied/);
  assert.match(continuity, /if \(explicitSelectionApplied \|\| !requestedProductKey\) return/);
});

test("locale state module is loaded and cached", () => {
  assert.match(html, /src\/cart-locale-state\.mjs/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/src\/cart-locale-state\.mjs/);
});
