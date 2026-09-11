import {
  catalogCardViewModel,
  evaluateCheckoutReadiness,
  productDetailViewModel,
} from "./core.mjs";
import { buildCartCheckoutIntent, cartPricingSummary } from "./cart.mjs";
import { createCustomerFlow, transitionCustomerFlow } from "./flow.mjs";
import { buildPaymentHandoffIntent, validatePaymentProviderProfile } from "./payment.mjs";

const DEFAULT_PICKUP_AT = "2026-09-13T10:00:00+09:00";
const DEFAULT_EVALUATED_AT = "2026-09-12T00:00:00Z";

function requireSyntheticCatalog(catalogFixture) {
  if (catalogFixture?.fixture_only !== true) {
    throw new Error("synthetic journey requires a fixture-only catalog");
  }
  if (!Array.isArray(catalogFixture.products) || catalogFixture.products.length < 1) {
    throw new Error("synthetic journey requires catalog products");
  }
  if (typeof catalogFixture.catalog_snapshot_ref !== "string" || !catalogFixture.catalog_snapshot_ref.startsWith("fixture:")) {
    throw new Error("synthetic journey requires a fixture catalog snapshot reference");
  }
  return catalogFixture;
}

function assertNonAuthorizingEvidence({ intent, readiness, pricing, paymentHandoff }) {
  if (intent.mutation_authorized !== false || readiness.mutation_authorized !== false) {
    throw new Error("synthetic journey checkout evidence must remain non-authorizing");
  }
  if (pricing.mutation_authorized !== false) {
    throw new Error("synthetic journey pricing evidence must remain non-authorizing");
  }
  if (
    paymentHandoff.order_creation_authorized !== false ||
    paymentHandoff.payment_execution_authorized !== false ||
    paymentHandoff.live_mode_authorized !== false
  ) {
    throw new Error("synthetic journey payment handoff must remain non-authorizing");
  }
}

function buildReadyJourney({ catalogFixture, providerProfile, locale, pickupAt, evaluatedAt }) {
  const products = catalogFixture.products;
  const catalogBySku = new Map(products.map((product) => [product.sku, product]));
  const availableProducts = products.filter(
    (product) => product.availability === "in_stock" && product.pickup?.supported === true,
  );
  if (availableProducts.length < 2) {
    throw new Error("synthetic journey requires at least two in-stock pickup products");
  }

  const selectedProducts = availableProducts.slice(0, 2);
  const catalogCard = catalogCardViewModel(selectedProducts[0], locale);
  const productDetail = productDetailViewModel(selectedProducts[0], locale);

  let flow = createCustomerFlow();
  flow = transitionCustomerFlow(flow, "select_product");
  flow = transitionCustomerFlow(flow, "start_checkout");

  const intent = buildCartCheckoutIntent({
    intentId: `sprint4-synthetic-ready-${locale}`,
    locale,
    items: selectedProducts.map((product) => ({ sku: product.sku, quantity: 1 })),
    requestedPickupAt: pickupAt,
  });
  const readiness = evaluateCheckoutReadiness(intent, catalogBySku, evaluatedAt);
  if (readiness.ready !== true || readiness.blockers.length !== 0) {
    throw new Error(`synthetic ready journey unexpectedly blocked: ${readiness.blockers.join(",")}`);
  }
  flow = transitionCustomerFlow(flow, "readiness_ready");
  if (flow.state !== "ready") {
    throw new Error("synthetic ready journey did not reach ready state");
  }

  const pricing = cartPricingSummary(intent, catalogBySku);
  const paymentHandoff = buildPaymentHandoffIntent({
    checkoutIntent: intent,
    readiness,
    catalogBySku,
    providerProfile,
  });
  assertNonAuthorizingEvidence({ intent, readiness, pricing, paymentHandoff });

  return Object.freeze({
    locale,
    catalog_snapshot_ref: catalogFixture.catalog_snapshot_ref,
    selected_product_keys: selectedProducts.map((product) => product.product_key),
    selected_skus: selectedProducts.map((product) => product.sku),
    localized_catalog_name: catalogCard.name,
    localized_product_name: productDetail.name,
    checkout_state: flow.state,
    readiness_ready: readiness.ready,
    blockers: readiness.blockers,
    total_amount: pricing.total_amount,
    currency: pricing.currency,
    payment_provider: paymentHandoff.provider,
    payment_connection_state: paymentHandoff.connection_state,
    mutation_authorized: false,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    live_mode_authorized: false,
    network_call_performed: false,
  });
}

function buildBlockedJourney({ catalogFixture, providerProfile, locale, pickupAt, evaluatedAt }) {
  const products = catalogFixture.products;
  const catalogBySku = new Map(products.map((product) => [product.sku, product]));
  const unavailable = products.find(
    (product) => product.availability === "out_of_stock" && product.pickup?.supported === true,
  );
  if (!unavailable) {
    throw new Error("synthetic journey requires an out-of-stock pickup product");
  }

  let flow = createCustomerFlow();
  flow = transitionCustomerFlow(flow, "select_product");
  flow = transitionCustomerFlow(flow, "start_checkout");

  const intent = buildCartCheckoutIntent({
    intentId: `sprint4-synthetic-blocked-${locale}`,
    locale,
    items: [{ sku: unavailable.sku, quantity: 1 }],
    requestedPickupAt: pickupAt,
  });
  const readiness = evaluateCheckoutReadiness(intent, catalogBySku, evaluatedAt);
  if (readiness.ready !== false || !readiness.blockers.includes("inventory")) {
    throw new Error("synthetic blocked journey must fail closed on unavailable inventory");
  }
  flow = transitionCustomerFlow(flow, "readiness_blocked");
  if (flow.state !== "blocked") {
    throw new Error("synthetic blocked journey did not reach blocked state");
  }

  let paymentHandoffBlocked = false;
  try {
    buildPaymentHandoffIntent({
      checkoutIntent: intent,
      readiness,
      catalogBySku,
      providerProfile,
    });
  } catch (error) {
    if (!String(error?.message || error).includes("checkout readiness is GREEN")) {
      throw error;
    }
    paymentHandoffBlocked = true;
  }
  if (!paymentHandoffBlocked) {
    throw new Error("synthetic blocked journey must not prepare a payment handoff");
  }

  return Object.freeze({
    locale,
    catalog_snapshot_ref: catalogFixture.catalog_snapshot_ref,
    selected_product_key: unavailable.product_key,
    selected_sku: unavailable.sku,
    checkout_state: flow.state,
    readiness_ready: readiness.ready,
    blockers: readiness.blockers,
    payment_handoff_blocked: paymentHandoffBlocked,
    mutation_authorized: false,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    live_mode_authorized: false,
    network_call_performed: false,
  });
}

export function runSyntheticCustomerJourney({
  catalogFixture,
  providerProfile,
  locale = "en",
  pickupAt = DEFAULT_PICKUP_AT,
  evaluatedAt = DEFAULT_EVALUATED_AT,
}) {
  requireSyntheticCatalog(catalogFixture);
  validatePaymentProviderProfile(providerProfile);
  if (!new Set(["en", "ja"]).has(locale)) {
    throw new Error("synthetic journey locale must be en or ja");
  }

  const ready = buildReadyJourney({ catalogFixture, providerProfile, locale, pickupAt, evaluatedAt });
  const blocked = buildBlockedJourney({ catalogFixture, providerProfile, locale, pickupAt, evaluatedAt });

  return Object.freeze({
    smoke: "sprint4_customer_experience_end_to_end_synthetic",
    fixture_only: true,
    locale,
    ready,
    blocked,
    network_call_performed: false,
    mutation_authorized: false,
    production_authority_changed: false,
  });
}
