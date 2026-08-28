import { cartPricingSummary } from "./cart.mjs";

export const KOMOJU_PROVIDER_ID = "komoju";
export const KOMOJU_INTEGRATION_MODE = "woocommerce_plugin";

export function validatePaymentProviderProfile(profile) {
  if (profile?.fixture_only !== true) {
    throw new Error("payment provider profile must remain fixture_only");
  }
  if (profile.provider !== KOMOJU_PROVIDER_ID) {
    throw new Error("unsupported payment provider");
  }
  if (profile.integration_mode !== KOMOJU_INTEGRATION_MODE) {
    throw new Error("KOMOJU must use the WooCommerce plugin boundary");
  }
  if (profile.connection_mode !== "account_sign_in") {
    throw new Error("KOMOJU WooCommerce connection must use account sign-in profile");
  }
  if (profile.connection_state !== "not_configured") {
    throw new Error("Sprint 4 payment connection must remain not_configured");
  }
  if (profile.live_mode_authorized !== false || profile.payment_execution_authorized !== false) {
    throw new Error("payment provider profile must remain non-authorizing");
  }
  return profile;
}

export function buildPaymentHandoffIntent({ checkoutIntent, readiness, catalogBySku, providerProfile }) {
  validatePaymentProviderProfile(providerProfile);
  if (checkoutIntent?.mutation_authorized !== false || readiness?.mutation_authorized !== false) {
    throw new Error("checkout and readiness must remain non-authorizing");
  }
  if (readiness.intent_id !== checkoutIntent.intent_id) {
    throw new Error("readiness does not match checkout intent");
  }
  if (readiness.ready !== true || readiness.blockers?.length) {
    throw new Error("payment handoff cannot be prepared before checkout readiness is GREEN");
  }
  const pricing = cartPricingSummary(checkoutIntent, catalogBySku);
  if (pricing.currency !== "JPY") {
    throw new Error("Sprint 4 KOMOJU pilot contract is JPY only");
  }
  return Object.freeze({
    handoff_id: `payment-handoff:${checkoutIntent.intent_id}`,
    checkout_intent_id: checkoutIntent.intent_id,
    provider: KOMOJU_PROVIDER_ID,
    integration_mode: KOMOJU_INTEGRATION_MODE,
    connection_state: providerProfile.connection_state,
    locale: checkoutIntent.locale,
    amount: Object.freeze({ amount: pricing.total_amount, currency: pricing.currency }),
    line_items: pricing.lines,
    fulfillment: checkoutIntent.fulfillment,
    requested_pickup_at: checkoutIntent.requested_pickup_at,
    external_order_reference: null,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    live_mode_authorized: false,
  });
}
