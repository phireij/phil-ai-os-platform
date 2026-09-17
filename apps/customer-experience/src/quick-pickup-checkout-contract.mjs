import { validatePaymentProviderProfile } from "./payment.mjs";

export function validateQuickPickupCheckoutContract(contract) {
  if (contract?.fixture_only !== true) throw new Error("Quick Pickup checkout contract must remain fixture_only");
  if (contract.provider !== "ruby_first_party_quick_pickup") throw new Error("Quick Pickup provider drift");
  if (contract.fulfillment !== "pickup") throw new Error("Quick Pickup checkout contract must use pickup fulfillment");
  if (contract.checkout_boundary !== "woocommerce_checkout_handoff") throw new Error("Quick Pickup must hand off at the WooCommerce checkout boundary");
  if (typeof contract.sku !== "string" || !contract.sku) throw new TypeError("Quick Pickup checkout contract requires sku");
  if (!Number.isInteger(contract.quantity) || contract.quantity < 1) throw new TypeError("Quick Pickup checkout contract requires positive quantity");
  if (typeof contract.slot_id !== "string" || !contract.slot_id) throw new TypeError("Quick Pickup checkout contract requires slot_id");
  for (const key of [
    "order_creation_authorized",
    "payment_execution_authorized",
    "live_mode_authorized",
    "inventory_mutation_authorized",
    "capacity_mutation_authorized",
    "production_publish_authorized",
  ]) {
    if (contract[key] !== false) throw new Error(`${key} must remain false`);
  }
  if (contract.external_order_reference !== null) throw new Error("external order reference must remain null before order creation");
  return contract;
}

export function buildQuickPickupCheckoutHandoff({ pickupDecision, providerProfile }) {
  validatePaymentProviderProfile(providerProfile);
  if (!pickupDecision || typeof pickupDecision !== "object") throw new TypeError("pickupDecision is required");
  if (pickupDecision.fixture_only !== true) throw new Error("Quick Pickup checkout handoff requires a fixture-only decision");
  if (pickupDecision.available !== true) throw new Error("Quick Pickup checkout handoff requires an available synthetic decision");
  if (pickupDecision.order_creation_authorized !== false || pickupDecision.payment_execution_authorized !== false) {
    throw new Error("Quick Pickup decision must remain non-authorizing");
  }

  return validateQuickPickupCheckoutContract(Object.freeze({
    fixture_only: true,
    provider: "ruby_first_party_quick_pickup",
    fulfillment: "pickup",
    checkout_boundary: "woocommerce_checkout_handoff",
    sku: pickupDecision.sku,
    quantity: pickupDecision.quantity,
    slot_id: pickupDecision.slot_id,
    external_order_reference: null,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    live_mode_authorized: false,
    inventory_mutation_authorized: false,
    capacity_mutation_authorized: false,
    production_publish_authorized: false,
  }));
}
