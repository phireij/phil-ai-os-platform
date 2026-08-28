import test from "node:test";
import assert from "node:assert/strict";
import { evaluateCheckoutReadiness } from "../src/core.mjs";
import { buildCartCheckoutIntent, cartPricingSummary } from "../src/cart.mjs";
import { buildPaymentHandoffIntent, validatePaymentProviderProfile } from "../src/payment.mjs";

const cake = {
  sku: "SAMPLE-CAKE-001",
  price: { amount: "500", currency: "JPY" },
  availability: "in_stock",
};
const cookie = {
  sku: "SAMPLE-COOKIE-001",
  price: { amount: "300", currency: "JPY" },
  availability: "in_stock",
};
const catalog = new Map([[cake.sku, cake], [cookie.sku, cookie]]);
const provider = {
  fixture_only: true,
  provider: "komoju",
  integration_mode: "woocommerce_plugin",
  connection_mode: "account_sign_in",
  connection_state: "not_configured",
  test_mode_required_before_live: true,
  live_mode_authorized: false,
  payment_execution_authorized: false,
};

function cartIntent(items = [{ sku: cake.sku, quantity: 2 }, { sku: cookie.sku, quantity: 1 }]) {
  return buildCartCheckoutIntent({
    intentId: "cart-intent-001",
    locale: "ja",
    items,
    requestedPickupAt: "2026-09-01T03:00:00Z",
  });
}

function readinessFor(intent, catalogBySku = catalog) {
  return evaluateCheckoutReadiness(intent, catalogBySku, "2026-08-28T12:00:00Z");
}

test("multi-item cart intent remains non-authorizing", () => {
  const intent = cartIntent();
  assert.equal(intent.items.length, 2);
  assert.equal(intent.fulfillment, "pickup");
  assert.equal(intent.locale, "ja");
  assert.equal(intent.mutation_authorized, false);
});

test("duplicate cart SKU is rejected", () => {
  assert.throws(
    () => cartIntent([{ sku: cake.sku, quantity: 1 }, { sku: cake.sku, quantity: 2 }]),
    /duplicate cart sku/,
  );
});

test("invalid cart quantity is rejected", () => {
  assert.throws(() => cartIntent([{ sku: cake.sku, quantity: 0 }]), /positive integer/);
});

test("cart pricing totals multiple JPY lines deterministically", () => {
  const pricing = cartPricingSummary(cartIntent(), catalog);
  assert.equal(pricing.total_amount, "1300");
  assert.equal(pricing.currency, "JPY");
  assert.deepEqual(pricing.lines.map((line) => line.line_amount), ["1000", "300"]);
  assert.equal(pricing.mutation_authorized, false);
});

test("cart pricing rejects mixed currencies", () => {
  const mixed = new Map(catalog);
  mixed.set(cookie.sku, { ...cookie, price: { amount: "300", currency: "USD" } });
  assert.throws(() => cartPricingSummary(cartIntent(), mixed), /mixed-currency/);
});

test("KOMOJU provider profile must be fixture-only", () => {
  assert.throws(() => validatePaymentProviderProfile({ ...provider, fixture_only: false }), /fixture_only/);
});

test("KOMOJU provider profile rejects a different provider", () => {
  assert.throws(() => validatePaymentProviderProfile({ ...provider, provider: "other" }), /unsupported payment provider/);
});

test("KOMOJU provider profile rejects configured connectivity during bounded Sprint 4", () => {
  assert.throws(() => validatePaymentProviderProfile({ ...provider, connection_state: "test_connected" }), /not_configured/);
});

test("payment handoff is blocked when checkout readiness is not GREEN", () => {
  const intent = cartIntent();
  const blocked = { ...readinessFor(intent), ready: false, blockers: ["inventory"] };
  assert.throws(
    () => buildPaymentHandoffIntent({ checkoutIntent: intent, readiness: blocked, catalogBySku: catalog, providerProfile: provider }),
    /readiness is GREEN/,
  );
});

test("payment handoff rejects mismatched checkout/readiness identity", () => {
  const intent = cartIntent();
  const readiness = { ...readinessFor(intent), intent_id: "different-intent" };
  assert.throws(
    () => buildPaymentHandoffIntent({ checkoutIntent: intent, readiness, catalogBySku: catalog, providerProfile: provider }),
    /does not match/,
  );
});

test("KOMOJU handoff can be prepared without creating payment authority", () => {
  const intent = cartIntent();
  const readiness = readinessFor(intent);
  assert.equal(readiness.ready, true);
  const handoff = buildPaymentHandoffIntent({ checkoutIntent: intent, readiness, catalogBySku: catalog, providerProfile: provider });
  assert.equal(handoff.provider, "komoju");
  assert.equal(handoff.integration_mode, "woocommerce_plugin");
  assert.equal(handoff.connection_state, "not_configured");
  assert.deepEqual(handoff.amount, { amount: "1300", currency: "JPY" });
  assert.equal(handoff.line_items.length, 2);
  assert.equal(handoff.external_order_reference, null);
  assert.equal(handoff.order_creation_authorized, false);
  assert.equal(handoff.payment_execution_authorized, false);
  assert.equal(handoff.live_mode_authorized, false);
});

test("Sprint 4 KOMOJU handoff rejects non-JPY pricing", () => {
  const usdProduct = { ...cake, price: { amount: "5", currency: "USD" } };
  const usdCatalog = new Map([[cake.sku, usdProduct]]);
  const intent = cartIntent([{ sku: cake.sku, quantity: 1 }]);
  const readiness = readinessFor(intent, usdCatalog);
  assert.throws(
    () => buildPaymentHandoffIntent({ checkoutIntent: intent, readiness, catalogBySku: usdCatalog, providerProfile: provider }),
    /JPY only/,
  );
});
