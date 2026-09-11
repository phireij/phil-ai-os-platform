import assert from "node:assert/strict";
import test from "node:test";

import {
  ORDER_INTAKE_REVIEW_KEY,
  clearOrderIntakeReviewCarryover,
  loadOrderIntakeReviewCarryover,
  sanitizeOrderIntakeReviewCarryover,
  saveOrderIntakeReviewCarryover,
} from "../src/order-intake-review-continuity.mjs";
import { orderIntakeCartContextRows } from "../src/order-intake-cart-context.mjs";

function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, value); },
    removeItem(key) { values.delete(key); },
  };
}

test("review continuity stores only bounded metadata and never file contents", () => {
  const state = sanitizeOrderIntakeReviewCarryover({
    cakeType: "custom",
    customNotes: "Blue flowers",
    referenceImages: [{ name: "idea.jpg", type: "image/jpeg", bytes: "private-binary" }],
    photoTopper: true,
    addons: ["candles"],
  });

  assert.equal(state.referenceImageCount, 1);
  assert.deepEqual(state.referenceImages, [{ name: "idea.jpg", type: "image/jpeg" }]);
  assert.equal("bytes" in state.referenceImages[0], false);
  assert.equal(state.fileContentPersisted, false);
  assert.equal(state.networkCallPerformed, false);
  assert.equal(state.orderCreationAuthorized, false);
  assert.equal(state.paymentExecutionAuthorized, false);
});

test("review continuity round-trips within session storage and can be cleared", () => {
  const storage = memoryStorage();
  assert.equal(saveOrderIntakeReviewCarryover(storage, {
    cakeType: "custom",
    customNotes: "Gold accents",
    referenceImages: [{ name: "gold.png", type: "image/png" }],
    edibleTopper: true,
    icingRequested: true,
  }), true);

  const loaded = loadOrderIntakeReviewCarryover(storage);
  assert.equal(loaded.cakeType, "custom");
  assert.equal(loaded.customNotes, "Gold accents");
  assert.equal(loaded.referenceImages[0].name, "gold.png");
  assert.ok(storage.getItem(ORDER_INTAKE_REVIEW_KEY));
  assert.equal(clearOrderIntakeReviewCarryover(storage), true);
  assert.equal(loadOrderIntakeReviewCarryover(storage), null);
});

test("cart context reuses the bounded review rows without creating authority", () => {
  const storage = memoryStorage();
  saveOrderIntakeReviewCarryover(storage, {
    cakeType: "custom",
    customNotes: "Happy 18th",
    referenceImages: [{ name: "reference.webp", type: "image/webp" }],
    photoTopper: true,
    addons: ["message-plaque"],
  });

  const rows = orderIntakeCartContextRows(storage);
  assert.ok(rows.some((row) => row.label.includes("Design notes") && row.value === "Happy 18th"));
  assert.ok(rows.some((row) => row.label.includes("Reference images") && row.value.includes("reference.webp")));
  assert.ok(rows.some((row) => row.label.includes("Topper") && row.value.includes("Photo")));
});

test("unknown review versions and broken storage fail closed", () => {
  const storage = memoryStorage();
  storage.setItem(ORDER_INTAKE_REVIEW_KEY, JSON.stringify({ version: 99, cakeType: "custom" }));
  assert.equal(loadOrderIntakeReviewCarryover(storage), null);

  const broken = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
    removeItem() { throw new Error("blocked"); },
  };
  assert.equal(loadOrderIntakeReviewCarryover(broken), null);
  assert.equal(saveOrderIntakeReviewCarryover(broken, { cakeType: "custom" }), false);
  assert.equal(clearOrderIntakeReviewCarryover(broken), false);
});
