import { normalizeLocale } from "./core.mjs";

function normalizeItems(items) {
  if (!Array.isArray(items) || items.length === 0) {
    throw new TypeError("cart requires at least one item");
  }
  const seen = new Set();
  return items.map((item) => {
    if (typeof item?.sku !== "string" || item.sku.trim() === "") {
      throw new TypeError("cart item sku is required");
    }
    if (!Number.isInteger(item.quantity) || item.quantity < 1) {
      throw new TypeError("cart item quantity must be a positive integer");
    }
    if (seen.has(item.sku)) {
      throw new Error(`duplicate cart sku: ${item.sku}`);
    }
    seen.add(item.sku);
    return Object.freeze({ sku: item.sku, quantity: item.quantity });
  });
}

export function buildCartCheckoutIntent({ intentId, locale, items, requestedPickupAt = null }) {
  if (typeof intentId !== "string" || intentId.trim() === "") {
    throw new TypeError("intentId is required");
  }
  if (requestedPickupAt !== null && Number.isNaN(Date.parse(requestedPickupAt))) {
    throw new TypeError("requestedPickupAt must be an ISO date-time or null");
  }
  return Object.freeze({
    intent_id: intentId,
    locale: normalizeLocale(locale),
    items: normalizeItems(items),
    fulfillment: "pickup",
    requested_pickup_at: requestedPickupAt,
    mutation_authorized: false,
  });
}

export function cartPricingSummary(intent, catalogBySku) {
  if (intent?.mutation_authorized !== false) {
    throw new Error("cart intent must remain non-authorizing");
  }
  if (!(catalogBySku instanceof Map)) {
    throw new TypeError("catalogBySku must be a Map");
  }
  let currency = null;
  let total = 0;
  const lines = intent.items.map((item) => {
    const product = catalogBySku.get(item.sku);
    if (!product?.price || typeof product.price.amount !== "string") {
      throw new Error(`missing price for ${item.sku}`);
    }
    const amount = Number(product.price.amount);
    if (!Number.isFinite(amount) || amount < 0) {
      throw new Error(`invalid price for ${item.sku}`);
    }
    if (currency === null) currency = product.price.currency;
    if (product.price.currency !== currency) {
      throw new Error("mixed-currency cart is not supported");
    }
    const lineTotal = amount * item.quantity;
    total += lineTotal;
    return Object.freeze({
      sku: item.sku,
      quantity: item.quantity,
      unit_amount: String(amount),
      line_amount: String(lineTotal),
      currency,
    });
  });
  return Object.freeze({
    lines,
    total_amount: String(total),
    currency,
    mutation_authorized: false,
  });
}
