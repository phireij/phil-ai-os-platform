import test from "node:test";
import assert from "node:assert/strict";
import { createCustomerFlow, transitionCustomerFlow } from "../src/flow.mjs";
import { evaluatePickupSelection, validatePickupPolicy } from "../src/pickup.mjs";
import { catalogMetadata, productMetadata } from "../src/seo.mjs";

const product = {
  product_key: "sample-product",
  sku: "SAMPLE-001",
  name: { en: "Sample Cake", ja: "サンプルケーキ" },
  description: { en: "Synthetic description", ja: "合成説明" },
  price: { amount: "500", currency: "JPY" },
  availability: "in_stock",
  media: [],
  pickup: { supported: true, instructions: { en: "Pickup", ja: "受取" } },
  seo: {
    title: { en: "Sample SEO", ja: "サンプルSEO" },
    description: { en: "SEO fixture", ja: "SEOフィクスチャ" },
  },
};

const pickupPolicy = { fixture_only: true, min_lead_minutes: 60, max_advance_days: 14 };

test("preview catalog metadata is noindex with no canonical", () => {
  const metadata = catalogMetadata("en");
  assert.equal(metadata.robots, "noindex,nofollow");
  assert.equal(metadata.canonical, null);
});

test("preview product metadata is localized and noindex", () => {
  const metadata = productMetadata(product, "ja");
  assert.equal(metadata.title, "サンプルSEO");
  assert.equal(metadata.robots, "noindex,nofollow");
  assert.equal(metadata.canonical, null);
});

test("deployment metadata requires explicit HTTPS canonical base", () => {
  assert.throws(() => productMetadata(product, "en", "deployment", "http://shop.invalid"), /explicit HTTPS/);
});

test("deployment product metadata creates deterministic localized canonical", () => {
  const metadata = productMetadata(product, "ja", "deployment", "https://shop.invalid");
  assert.equal(metadata.robots, "index,follow");
  assert.equal(metadata.canonical, "https://shop.invalid/?product=sample-product&lang=ja");
});

test("pickup policy must be explicitly fixture-only", () => {
  assert.throws(() => validatePickupPolicy({ min_lead_minutes: 60, max_advance_days: 14 }), /fixture_only/);
});

test("pickup selection blocks missing time", () => {
  assert.deepEqual(
    evaluatePickupSelection(null, "2026-08-28T10:00:00Z", pickupPolicy),
    { valid: false, blocker: "pickup_time", reason: "missing" },
  );
});

test("pickup selection blocks insufficient lead time", () => {
  const result = evaluatePickupSelection("2026-08-28T10:30:00Z", "2026-08-28T10:00:00Z", pickupPolicy);
  assert.equal(result.valid, false);
  assert.equal(result.reason, "lead_time");
});

test("pickup selection blocks requests too far ahead", () => {
  const result = evaluatePickupSelection("2026-09-20T10:00:00Z", "2026-08-28T10:00:00Z", pickupPolicy);
  assert.equal(result.valid, false);
  assert.equal(result.reason, "too_far_ahead");
});

test("pickup selection accepts time inside synthetic policy window", () => {
  const result = evaluatePickupSelection("2026-08-29T10:00:00Z", "2026-08-28T10:00:00Z", pickupPolicy);
  assert.equal(result.valid, true);
});

test("customer flow starts at catalog with no mutation authority", () => {
  const flow = createCustomerFlow();
  assert.equal(flow.state, "catalog");
  assert.equal(flow.mutation_authorized, false);
});

test("customer flow rejects impossible transitions", () => {
  assert.throws(() => transitionCustomerFlow(createCustomerFlow(), "readiness_ready"), /invalid customer flow transition/);
});

test("customer flow reaches ready without gaining authority", () => {
  let flow = createCustomerFlow();
  flow = transitionCustomerFlow(flow, "select_product");
  flow = transitionCustomerFlow(flow, "start_checkout");
  flow = transitionCustomerFlow(flow, "readiness_ready");
  assert.equal(flow.state, "ready");
  assert.equal(flow.mutation_authorized, false);
  assert.equal(flow.revision, 3);
});
