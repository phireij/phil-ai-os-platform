import assert from "node:assert/strict";
import test from "node:test";

import { buildOrderIntakeRequestEnvelope } from "../src/order-intake-request-envelope.mjs";

test("request envelope normalizes fulfillment and bounded custom request metadata", () => {
  const envelope = buildOrderIntakeRequestEnvelope({
    fulfillment: "pickup",
    requestedDate: "2026-09-20",
    pickupTime: "15:30",
    yamatoWindow: "18-20",
    cakeType: "custom",
    customNotes: "White flowers",
    referenceImages: [{ name: "idea.jpg", type: "image/jpeg", bytes: "private" }],
    photoTopper: true,
    addons: ["candles", "candles", "message-plaque", "unknown"],
    icingRequested: true,
  });

  assert.equal(envelope.schema, "rubys-order-intake-request");
  assert.equal(envelope.version, 1);
  assert.equal(envelope.state, "review_only");
  assert.deepEqual(envelope.fulfillment, {
    method: "pickup",
    requestedDate: "2026-09-20",
    pickupTime: "15:30",
    yamatoWindow: "none",
    routeOrFeeConfirmed: false,
    fulfillmentConfirmed: false,
  });
  assert.equal(envelope.customization.customNotes, "White flowers");
  assert.deepEqual(envelope.customization.referenceImages, [{ name: "idea.jpg", type: "image/jpeg" }]);
  assert.deepEqual(envelope.customization.addons, ["candles", "message-plaque"]);
  assert.equal(JSON.stringify(envelope).includes("private"), false);
});

test("basic cake suppresses custom-only metadata", () => {
  const envelope = buildOrderIntakeRequestEnvelope({
    fulfillment: "yamato",
    requestedDate: "2026-09-22",
    yamatoWindow: "14-16",
    cakeType: "basic",
    customNotes: "should disappear",
    referenceImages: [{ name: "private.png", type: "image/png" }],
    photoTopper: true,
    edibleTopper: true,
    addons: ["number-candle"],
  });

  assert.equal(envelope.fulfillment.pickupTime, "");
  assert.equal(envelope.fulfillment.yamatoWindow, "14-16");
  assert.equal(envelope.customization.customNotes, "");
  assert.equal(envelope.customization.referenceImageCount, 0);
  assert.deepEqual(envelope.customization.referenceImages, []);
  assert.equal(envelope.customization.photoTopper, false);
  assert.equal(envelope.customization.edibleTopper, false);
  assert.deepEqual(envelope.customization.addons, ["number-candle"]);
});

test("unknown enum values fail closed to safe defaults", () => {
  const envelope = buildOrderIntakeRequestEnvelope({
    fulfillment: "drone",
    yamatoWindow: "overnight",
    cakeType: "mystery",
    addons: ["fireworks"],
  });

  assert.equal(envelope.fulfillment.method, "yamato");
  assert.equal(envelope.fulfillment.yamatoWindow, "none");
  assert.equal(envelope.customization.cakeType, "basic");
  assert.deepEqual(envelope.customization.addons, []);
});

test("request envelope never grants production, order, payment, network, or upload authority", () => {
  const envelope = buildOrderIntakeRequestEnvelope({ cakeType: "custom" });

  assert.deepEqual(envelope.pricing, {
    quoteCalculated: false,
    shippingFeeCalculated: false,
    totalCalculated: false,
  });
  for (const value of Object.values(envelope.authority)) assert.equal(value, false);
  assert.equal(envelope.fulfillment.routeOrFeeConfirmed, false);
  assert.equal(envelope.fulfillment.fulfillmentConfirmed, false);
});

test("request envelope is immutable at its contract boundaries", () => {
  const envelope = buildOrderIntakeRequestEnvelope({
    cakeType: "custom",
    referenceImages: [{ name: "a.webp", type: "image/webp" }],
    addons: ["candles"],
  });

  assert.equal(Object.isFrozen(envelope), true);
  assert.equal(Object.isFrozen(envelope.fulfillment), true);
  assert.equal(Object.isFrozen(envelope.customization), true);
  assert.equal(Object.isFrozen(envelope.customization.referenceImages), true);
  assert.equal(Object.isFrozen(envelope.customization.referenceImages[0]), true);
  assert.equal(Object.isFrozen(envelope.customization.addons), true);
  assert.equal(Object.isFrozen(envelope.pricing), true);
  assert.equal(Object.isFrozen(envelope.authority), true);
});
