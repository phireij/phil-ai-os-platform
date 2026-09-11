import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { saveOrderIntakeReviewCarryover } from "../src/order-intake-review-continuity.mjs";
import {
  orderIntakeFinalReviewCorrectionHref,
  orderIntakeFinalReviewRows,
} from "../src/order-intake-final-review.mjs";

function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, value); },
    removeItem(key) { values.delete(key); },
  };
}

test("final review carries bounded custom request details without creating authority", () => {
  const storage = memoryStorage();
  saveOrderIntakeReviewCarryover(storage, {
    cakeType: "custom",
    customNotes: "Soft pink flowers",
    referenceImages: [{ name: "flower-reference.jpg", type: "image/jpeg", bytes: "never-store" }],
    photoTopper: true,
    addons: ["candles", "message-plaque"],
    icingRequested: true,
  });

  const rows = orderIntakeFinalReviewRows(storage);
  assert.ok(rows.some((row) => row.label.includes("Design notes") && row.value === "Soft pink flowers"));
  assert.ok(rows.some((row) => row.label.includes("Reference images") && row.value.includes("flower-reference.jpg")));
  assert.ok(rows.some((row) => row.label.includes("Topper") && row.value.includes("Photo")));
  assert.ok(rows.some((row) => row.label.includes("Add-ons") && row.value.includes("Candles")));
  assert.ok(rows.some((row) => row.label.includes("Icing")));
  assert.equal(JSON.stringify(rows).includes("never-store"), false);
});

test("final review correction route preserves only the supported Japanese locale", () => {
  assert.equal(orderIntakeFinalReviewCorrectionHref("?lang=ja"), "./order-intake-preview.html?lang=ja");
  assert.equal(orderIntakeFinalReviewCorrectionHref("?lang=en"), "./order-intake-preview.html");
  assert.equal(orderIntakeFinalReviewCorrectionHref("?lang=fr&next=https://example.com"), "./order-intake-preview.html");
});

test("final confirmation page exposes the carried custom-request review surface", () => {
  const html = readFileSync(new URL("../confirmation-preview.html", import.meta.url), "utf8");
  assert.match(html, /id="order-intake-final-review"/);
  assert.match(html, /src="\.\/src\/order-intake-final-review\.mjs"/);
  assert.match(html, /place-order-preview[^>]*disabled/);
});

test("PWA shell caches the order-intake continuity chain used by cart and final review", () => {
  const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");
  for (const asset of [
    "./src/order-intake-draft-state.mjs",
    "./src/order-intake-review-state.mjs",
    "./src/order-intake-review-summary.mjs",
    "./src/order-intake-review-continuity.mjs",
    "./src/order-intake-cart-context.mjs",
    "./src/order-intake-final-review.mjs",
  ]) {
    assert.ok(sw.includes(`\"${asset}\"`), `missing ${asset} from app shell`);
  }
});
