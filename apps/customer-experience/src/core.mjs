export const SUPPORTED_LOCALES = Object.freeze(["en", "ja"]);

export function normalizeLocale(value, fallback = "en") {
  return SUPPORTED_LOCALES.includes(value) ? value : fallback;
}

export function localized(value, locale) {
  const selected = normalizeLocale(locale);
  if (!value || typeof value !== "object") {
    throw new TypeError("localized value must be an object");
  }
  const text = value[selected];
  if (typeof text !== "string" || text.trim() === "") {
    throw new Error(`missing required ${selected} translation`);
  }
  return text;
}

export function formatMoney(price, locale) {
  if (!price || typeof price.amount !== "string" || !/^[A-Z]{3}$/.test(price.currency || "")) {
    throw new TypeError("invalid price contract");
  }
  const amount = Number(price.amount);
  if (!Number.isFinite(amount) || amount < 0) {
    throw new TypeError("invalid price amount");
  }
  return new Intl.NumberFormat(locale === "ja" ? "ja-JP" : "en-US", {
    style: "currency",
    currency: price.currency,
    maximumFractionDigits: price.currency === "JPY" ? 0 : 2,
  }).format(amount);
}

export function catalogCardViewModel(product, locale) {
  if (!product?.product_key || !product?.sku) {
    throw new TypeError("product identity is required");
  }
  return Object.freeze({
    productKey: product.product_key,
    sku: product.sku,
    name: localized(product.name, locale),
    shortDescription: product.short_description ? localized(product.short_description, locale) : "",
    formattedPrice: formatMoney(product.price, locale),
    availability: product.availability,
    primaryMediaRef: product.primary_media_ref,
    detailHref: `?product=${encodeURIComponent(product.product_key)}&lang=${normalizeLocale(locale)}`,
  });
}

export function productDetailViewModel(product, locale) {
  if (!product?.product_key || !product?.sku) {
    throw new TypeError("product identity is required");
  }
  const media = [...(product.media || [])]
    .sort((a, b) => a.position - b.position)
    .map((item) => ({
      ref: item.ref,
      alt: localized(item.alt, locale),
      position: item.position,
    }));
  return Object.freeze({
    productKey: product.product_key,
    sku: product.sku,
    name: localized(product.name, locale),
    description: localized(product.description, locale),
    formattedPrice: formatMoney(product.price, locale),
    availability: product.availability,
    media,
    pickupSupported: Boolean(product.pickup?.supported),
    pickupInstructions: localized(product.pickup?.instructions, locale),
  });
}

export function buildCheckoutIntent({ intentId, locale, sku, quantity, requestedPickupAt = null }) {
  if (typeof intentId !== "string" || intentId.trim() === "") {
    throw new TypeError("intentId is required");
  }
  if (typeof sku !== "string" || sku.trim() === "") {
    throw new TypeError("sku is required");
  }
  if (!Number.isInteger(quantity) || quantity < 1) {
    throw new TypeError("quantity must be a positive integer");
  }
  if (requestedPickupAt !== null && Number.isNaN(Date.parse(requestedPickupAt))) {
    throw new TypeError("requestedPickupAt must be an ISO date-time or null");
  }
  return Object.freeze({
    intent_id: intentId,
    locale: normalizeLocale(locale),
    items: [{ sku, quantity }],
    fulfillment: "pickup",
    requested_pickup_at: requestedPickupAt,
    mutation_authorized: false,
  });
}

export function evaluateCheckoutReadiness(intent, catalogBySku, evaluatedAt) {
  if (intent?.mutation_authorized !== false) {
    throw new Error("checkout intent must remain non-authorizing");
  }
  const blockers = new Set();
  const items = intent.items.map((item) => {
    const product = catalogBySku.get(item.sku);
    let availability = "unknown";
    let availableQuantity = null;
    if (!product) {
      blockers.add("inventory");
    } else if (product.availability === "in_stock") {
      availability = "available";
    } else if (product.availability === "out_of_stock") {
      availability = "unavailable";
      blockers.add("inventory");
    } else if (product.availability === "backorder") {
      availability = "unknown";
      blockers.add("inventory");
    } else {
      blockers.add("inventory");
    }
    return {
      sku: item.sku,
      requested_quantity: item.quantity,
      availability,
      available_quantity: availableQuantity,
    };
  });
  if (!intent.requested_pickup_at) {
    blockers.add("pickup_time");
  }
  return Object.freeze({
    intent_id: intent.intent_id,
    evaluated_at: evaluatedAt,
    catalog_snapshot_ref: "fixture:cx/synthetic-catalog-v1",
    items,
    ready: blockers.size === 0,
    blockers: [...blockers].sort(),
    customer_action_required: blockers.has("pickup_time") ? ["select_pickup_time"] : [],
    mutation_authorized: false,
  });
}

export function productStructuredData(product, locale, canonicalBase = "https://example.invalid") {
  const vm = productDetailViewModel(product, locale);
  const availabilityMap = {
    in_stock: "https://schema.org/InStock",
    out_of_stock: "https://schema.org/OutOfStock",
    backorder: "https://schema.org/BackOrder",
    unknown: "https://schema.org/PreOrder",
  };
  return Object.freeze({
    "@context": "https://schema.org",
    "@type": "Product",
    name: vm.name,
    description: vm.description,
    sku: vm.sku,
    url: `${canonicalBase.replace(/\/$/, "")}/?product=${encodeURIComponent(vm.productKey)}&lang=${normalizeLocale(locale)}`,
    offers: {
      "@type": "Offer",
      priceCurrency: product.price.currency,
      price: product.price.amount,
      availability: availabilityMap[product.availability] || availabilityMap.unknown,
    },
  });
}
