import assert from "node:assert/strict";
import test from "node:test";

import {
  ORDER_INTAKE_REVIEW_HANDOFF_KEY,
  buildOrderIntakeReviewHandoff,
  clearOrderIntakeReviewHandoff,
  loadOrderIntakeReviewHandoff,
  saveOrderIntakeReviewHandoff,
} from "../src/order-intake-review-handoff.mjs";

function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, value); },
    removeItem(key) { values.delete(key); },
  };
}

test("review handoff keeps only bounded request data and never file contents", () => {
  const handoff = buildOrderIntakeReviewHandoff({
    fulfillment: "pickup",
    requestedDate: "2026-09-20",
    pickupTime: "15:30",
    cakeType: "custom",
    customNotes: "Blue flowers",
    referenceImages: [{ name: "idea.jpg", type: "image/jpeg", bytes: "private-binary" }],
    photoTopper: true,
    addons: ["candles"],
  });

  assert.equal(handoff.state, "prepared_for_staff_review");
  assert.equal(handoff.request.fulfillment.method, "pickup");
  assert.equal(handoff.request.fulfillment.pickupTime, "15:30");
  assert.equal(handoff.request.customization.referenceImageCount, 1);
  assert.deepEqual(handoff.request.customization.referenceImages, [{ name: "idea.jpg", type: "image/jpeg" }]);
  assert.equal(JSON.stringify(handoff).includes("private-binary"), false);
  assert.equal(handoff.authority.staffReviewOnly, true);
  assert.equal(handoff.authority.networkCallPerformed, false);
  assert.equal(handoff.authority.wooCommerceMutationAuthorized, false);
  assert.equal(handoff.authority.orderCreationAuthorized, false);
  assert.equal(handoff.authority.paymentExecutionAuthorized, false);
});

test("basic cake handoff suppresses custom-only data", () => {
  const handoff = buildOrderIntakeReviewHandoff({
    fulfillment: "yamato",
    requestedDate: "2026-09-22",
    cakeType: "basic",
    customNotes: "must disappear",
    referenceImages: [{ name: "must-disappear.png", type: "image/png" }],
    photoTopper: true,
    edibleTopper: true,
  });

  assert.equal(handoff.request.customization.cakeType, "basic");
  assert.equal(handoff.request.customization.customNotes, "");
  assert.equal(handoff.request.customization.referenceImageCount, 0);
  assert.deepEqual(handoff.request.customization.referenceImages, []);
  assert.equal(handoff.request.customization.photoTopper, false);
  assert.equal(handoff.request.customization.edibleTopper, false);
});

test("review handoff round-trips through session storage and remains non-authorizing", () => {
  const storage = memoryStorage();
  assert.equal(saveOrderIntakeReviewHandoff(storage, {
    fulfillment: "ruby-car",
    requestedDate: "2026-09-25",
    cakeType: "custom",
    customNotes: "Gold accents",
    icingRequested: true,
  }), true);

  const raw = storage.getItem(ORDER_INTAKE_REVIEW_HANDOFF_KEY);
  assert.ok(raw);
  const loaded = loadOrderIntakeReviewHandoff(storage);
  assert.equal(loaded.request.fulfillment.method, "ruby-car");
  assert.equal(loaded.request.fulfillment.requestedDate, "2026-09-25");
  assert.equal(loaded.request.customization.customNotes, "Gold accents");
  assert.equal(loaded.request.fulfillment.routeOrFeeConfirmed, false);
  assert.equal(loaded.request.pricing.totalCalculated, false);
  assert.equal(loaded.authority.productionPublishAuthorized, false);

  assert.equal(clearOrderIntakeReviewHandoff(storage), true);
  assert.equal(loadOrderIntakeReviewHandoff(storage), null);
});

test("unknown handoff versions and blocked storage fail closed", () => {
  const storage = memoryStorage();
  storage.setItem(ORDER_INTAKE_REVIEW_HANDOFF_KEY, JSON.stringify({
    schema: "rubys-order-intake-review-handoff",
    version: 99,
    state: "prepared_for_staff_review",
  }));
  assert.equal(loadOrderIntakeReviewHandoff(storage), null);

  const broken = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
    removeItem() { throw new Error("blocked"); },
  };
  assert.equal(loadOrderIntakeReviewHandoff(broken), null);
  assert.equal(saveOrderIntakeReviewHandoff(broken, {}), false);
  assert.equal(clearOrderIntakeReviewHandoff(broken), false);
});
