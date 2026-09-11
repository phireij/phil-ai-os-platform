import assert from "node:assert/strict";
import test from "node:test";

import { buildOrderIntakeReviewState } from "../src/order-intake-review-state.mjs";

test("builds a bounded custom-cake review summary without persisting file contents", () => {
  const state = buildOrderIntakeReviewState({
    cakeType: "custom",
    customNotes: "Blue flowers, Happy Birthday, less sweet frosting",
    referenceImages: [
      { name: "front-design.jpg", type: "image/jpeg", bytes: "private-binary" },
      { name: "side-detail.webp", type: "image/webp" },
    ],
    photoTopper: true,
    edibleTopper: false,
    addons: ["candles", "candles", "message-plaque", "unsupported"],
    icingRequested: true,
  });

  assert.equal(state.cakeType, "custom");
  assert.equal(state.customNotes, "Blue flowers, Happy Birthday, less sweet frosting");
  assert.equal(state.referenceImageCount, 2);
  assert.deepEqual(state.referenceImages, [
    { name: "front-design.jpg", type: "image/jpeg" },
    { name: "side-detail.webp", type: "image/webp" },
  ]);
  assert.equal("bytes" in state.referenceImages[0], false);
  assert.equal(state.photoTopper, true);
  assert.equal(state.edibleTopper, false);
  assert.deepEqual(state.addons, ["candles", "message-plaque"]);
  assert.equal(state.icingRequested, true);
  assert.equal(state.fileContentPersisted, false);
  assert.equal(state.networkCallPerformed, false);
  assert.equal(state.orderCreationAuthorized, false);
  assert.equal(state.paymentExecutionAuthorized, false);
});

test("basic cake review suppresses custom-only fields", () => {
  const state = buildOrderIntakeReviewState({
    cakeType: "basic",
    customNotes: "should not appear",
    referenceImages: [{ name: "private.jpg", type: "image/jpeg" }],
    photoTopper: true,
    edibleTopper: true,
    addons: ["number-candle"],
    icingRequested: true,
  });

  assert.equal(state.cakeType, "basic");
  assert.equal(state.customNotes, "");
  assert.equal(state.referenceImageCount, 0);
  assert.deepEqual(state.referenceImages, []);
  assert.equal(state.photoTopper, false);
  assert.equal(state.edibleTopper, false);
  assert.deepEqual(state.addons, ["number-candle"]);
  assert.equal(state.icingRequested, true);
});

test("reference image metadata is bounded to the same eight-image intake limit", () => {
  const referenceImages = Array.from({ length: 12 }, (_, index) => ({
    name: `reference-${index + 1}.jpg`,
    type: "image/jpeg",
  }));
  const state = buildOrderIntakeReviewState({ cakeType: "custom", referenceImages });

  assert.equal(state.referenceImageCount, 8);
  assert.equal(state.referenceImages[0].name, "reference-1.jpg");
  assert.equal(state.referenceImages[7].name, "reference-8.jpg");
});

test("unknown cake types and addons fail toward the basic safe state", () => {
  const state = buildOrderIntakeReviewState({
    cakeType: "mystery",
    addons: ["unsupported"],
    photoTopper: true,
  });

  assert.equal(state.cakeType, "basic");
  assert.deepEqual(state.addons, []);
  assert.equal(state.photoTopper, false);
});
