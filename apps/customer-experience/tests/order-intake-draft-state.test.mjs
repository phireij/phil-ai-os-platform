import assert from "node:assert/strict";
import test from "node:test";

import {
  ORDER_INTAKE_DRAFT_KEY,
  clearOrderIntakeDraft,
  loadOrderIntakeDraft,
  sanitizeOrderIntakeDraft,
  saveOrderIntakeDraft,
} from "../src/order-intake-draft-state.mjs";

function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setItem(key, value) {
      values.set(key, value);
    },
    removeItem(key) {
      values.delete(key);
    },
  };
}

test("sanitizes bounded customer-editable draft fields without file metadata", () => {
  const draft = sanitizeOrderIntakeDraft({
    version: 1,
    fulfillment: "pickup",
    requestedDate: "2026-09-20",
    pickupTime: "15:30",
    yamatoWindow: "19-21",
    cakeType: "custom",
    customNotes: "Blue flowers and Happy Birthday",
    photoTopper: true,
    edibleTopper: false,
    addons: ["candles", "candles", "message-plaque", "unsupported"],
    icingRequested: true,
    referenceImages: [{ name: "private.jpg" }],
  });

  assert.deepEqual(draft, {
    version: 1,
    fulfillment: "pickup",
    requestedDate: "2026-09-20",
    pickupTime: "15:30",
    yamatoWindow: "19-21",
    cakeType: "custom",
    customNotes: "Blue flowers and Happy Birthday",
    photoTopper: true,
    edibleTopper: false,
    addons: ["candles", "message-plaque"],
    icingRequested: true,
  });
  assert.equal("referenceImages" in draft, false);
});

test("rejects unknown draft versions instead of guessing compatibility", () => {
  assert.equal(sanitizeOrderIntakeDraft({ version: 99, fulfillment: "pickup" }), null);
});

test("invalid enum values fall back to safe preview defaults", () => {
  const draft = sanitizeOrderIntakeDraft({
    version: 1,
    fulfillment: "drone",
    cakeType: "mystery",
    yamatoWindow: "midnight",
  });

  assert.equal(draft.fulfillment, "yamato");
  assert.equal(draft.cakeType, "basic");
  assert.equal(draft.yamatoWindow, "none");
});

test("session storage round-trip is fail-closed and removable", () => {
  const storage = memoryStorage();
  assert.equal(saveOrderIntakeDraft(storage, {
    fulfillment: "ruby-car",
    requestedDate: "2026-09-25",
    cakeType: "basic",
  }), true);

  const restored = loadOrderIntakeDraft(storage);
  assert.equal(restored.fulfillment, "ruby-car");
  assert.equal(restored.requestedDate, "2026-09-25");
  assert.equal(restored.cakeType, "basic");
  assert.ok(storage.getItem(ORDER_INTAKE_DRAFT_KEY));

  assert.equal(clearOrderIntakeDraft(storage), true);
  assert.equal(loadOrderIntakeDraft(storage), null);
});

test("storage failures do not break the preview", () => {
  const broken = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
    removeItem() { throw new Error("blocked"); },
  };

  assert.equal(loadOrderIntakeDraft(broken), null);
  assert.equal(saveOrderIntakeDraft(broken, { fulfillment: "yamato" }), false);
  assert.equal(clearOrderIntakeDraft(broken), false);
});
