import test from "node:test";
import assert from "node:assert/strict";
import {
  buildCheckoutIntent,
  catalogCardViewModel,
  evaluateCheckoutReadiness,
  formatMoney,
  localized,
  normalizeLocale,
  productDetailViewModel,
  productStructuredData,
} from "../src/core.mjs";

const product = {
  product_key: "sample-product",
  sku: "SAMPLE-001",
  name: { en: "Sample Cake", ja: "サンプルケーキ" },
  short_description: { en: "Short", ja: "短い説明" },
  description: { en: "Synthetic description", ja: "合成説明" },
  price: { amount: "500", currency: "JPY" },
  availability: "in_stock",
  primary_media_ref: "fixture://media/primary.svg",
  media: [
    { ref: "fixture://media/second.svg", alt: { en: "Second", ja: "二番目" }, position: 1 },
    { ref: "fixture://media/primary.svg", alt: { en: "Primary", ja: "メイン" }, position: 0 },
  ],
  pickup: { supported: true, instructions: { en: "Pickup instructions", ja: "受取案内" } },
};

test("normalizes only supported locales", () => {
  assert.equal(normalizeLocale("ja"), "ja");
  assert.equal(normalizeLocale("fr"), "en");
});

test("localized selection is explicit", () => {
  assert.equal(localized({ en: "Cake", ja: "ケーキ" }, "ja"), "ケーキ");
});

test("missing required translation fails closed", () => {
  assert.throws(() => localized({ en: "Cake", ja: "" }, "ja"), /missing required ja translation/);
});

test("formats JPY without fractional digits", () => {
  assert.match(formatMoney({ amount: "500", currency: "JPY" }, "ja"), /500/);
});

test("catalog card keeps locale in detail route", () => {
  const vm = catalogCardViewModel(product, "ja");
  assert.equal(vm.name, "サンプルケーキ");
  assert.equal(vm.detailHref, "?product=sample-product&lang=ja");
});

test("product detail media is sorted deterministically", () => {
  const vm = productDetailViewModel(product, "en");
  assert.deepEqual(vm.media.map((item) => item.ref), ["fixture://media/primary.svg", "fixture://media/second.svg"]);
});

test("checkout intent is always non-authorizing pickup", () => {
  const intent = buildCheckoutIntent({
    intentId: "intent-1",
    locale: "en",
    sku: "SAMPLE-001",
    quantity: 2,
    requestedPickupAt: "2026-09-01T02:00:00.000Z",
  });
  assert.equal(intent.fulfillment, "pickup");
  assert.equal(intent.mutation_authorized, false);
});

test("invalid checkout quantity is rejected", () => {
  assert.throws(() => buildCheckoutIntent({ intentId: "intent-1", locale: "en", sku: "SAMPLE-001", quantity: 0 }), /positive integer/);
});

test("checkout readiness blocks missing pickup time", () => {
  const intent = buildCheckoutIntent({ intentId: "intent-1", locale: "en", sku: "SAMPLE-001", quantity: 1 });
  const readiness = evaluateCheckoutReadiness(intent, new Map([[product.sku, product]]), "2026-08-28T10:00:00Z");
  assert.equal(readiness.ready, false);
  assert.deepEqual(readiness.blockers, ["pickup_time"]);
  assert.equal(readiness.mutation_authorized, false);
});

test("checkout readiness blocks unavailable inventory", () => {
  const unavailable = { ...product, availability: "out_of_stock" };
  const intent = buildCheckoutIntent({
    intentId: "intent-2",
    locale: "ja",
    sku: unavailable.sku,
    quantity: 1,
    requestedPickupAt: "2026-09-01T02:00:00Z",
  });
  const readiness = evaluateCheckoutReadiness(intent, new Map([[unavailable.sku, unavailable]]), "2026-08-28T10:00:00Z");
  assert.equal(readiness.ready, false);
  assert.deepEqual(readiness.blockers, ["inventory"]);
});

test("checkout readiness can become ready without creating authority", () => {
  const intent = buildCheckoutIntent({
    intentId: "intent-3",
    locale: "en",
    sku: product.sku,
    quantity: 1,
    requestedPickupAt: "2026-09-01T02:00:00Z",
  });
  const readiness = evaluateCheckoutReadiness(intent, new Map([[product.sku, product]]), "2026-08-28T10:00:00Z");
  assert.equal(readiness.ready, true);
  assert.deepEqual(readiness.blockers, []);
  assert.equal(readiness.mutation_authorized, false);
});

test("structured data is locale-aware and read-only", () => {
  const data = productStructuredData(product, "ja");
  assert.equal(data["@type"], "Product");
  assert.equal(data.name, "サンプルケーキ");
  assert.equal(data.offers.priceCurrency, "JPY");
  assert.match(data.url, /lang=ja/);
});
