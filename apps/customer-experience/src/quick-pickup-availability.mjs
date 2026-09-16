const AUTHORITY_FLAGS = [
  "network_authorized",
  "inventory_mutation_authorized",
  "reservation_authorized",
  "order_creation_authorized",
];

function requireIsoTimestamp(value, field) {
  if (typeof value !== "string" || Number.isNaN(Date.parse(value))) {
    throw new TypeError(`${field} must be an ISO timestamp`);
  }
}

function requireNonNegativeInteger(value, field) {
  if (!Number.isInteger(value) || value < 0) {
    throw new TypeError(`${field} must be a non-negative integer`);
  }
}

/**
 * Validates a synthetic, non-authorizing availability snapshot.
 *
 * This is deliberately not an AirREGI integration or CSV importer. A real
 * provider schema, SKU mapping, credential boundary, reconciliation process,
 * and separate production acceptance remain required before activation.
 */
export function validateQuickPickupInventorySnapshot(snapshot) {
  if (snapshot?.fixture_only !== true) {
    throw new Error("Quick Pickup inventory snapshot must remain fixture_only");
  }
  if (snapshot.source_type !== "synthetic_operator_csv_snapshot") {
    throw new Error("Quick Pickup inventory snapshot source must remain synthetic");
  }
  if (snapshot.airregi_api_verified !== false || snapshot.airregi_csv_format_verified !== false) {
    throw new Error("AirREGI capability must remain unverified in fixture inventory snapshots");
  }
  if (typeof snapshot.snapshot_id !== "string" || snapshot.snapshot_id.length === 0) {
    throw new TypeError("snapshot_id must be a non-empty string");
  }
  requireIsoTimestamp(snapshot.captured_at, "captured_at");
  if (!Number.isInteger(snapshot.max_age_minutes) || snapshot.max_age_minutes < 1) {
    throw new TypeError("max_age_minutes must be a positive integer");
  }
  if (!Array.isArray(snapshot.items) || snapshot.items.length === 0) {
    throw new TypeError("items must be a non-empty array");
  }
  for (const flag of AUTHORITY_FLAGS) {
    if (snapshot[flag] !== false) throw new Error(`${flag} must remain false`);
  }

  const skus = new Set();
  for (const item of snapshot.items) {
    if (typeof item?.sku !== "string" || item.sku.length === 0) {
      throw new TypeError("inventory item sku must be a non-empty string");
    }
    if (skus.has(item.sku)) throw new Error(`duplicate inventory sku: ${item.sku}`);
    skus.add(item.sku);
    requireNonNegativeInteger(item.on_hand, `on_hand for ${item.sku}`);
    requireNonNegativeInteger(item.safety_stock, `safety_stock for ${item.sku}`);
    requireNonNegativeInteger(item.active_reservations, `active_reservations for ${item.sku}`);
  }
  return snapshot;
}

export function availableToSell(item) {
  return Math.max(0, item.on_hand - item.safety_stock - item.active_reservations);
}

/**
 * Returns a read-only availability decision. It never reserves stock, creates
 * an order, or establishes a connection to an inventory provider.
 */
export function evaluateQuickPickupAvailability(request, snapshot) {
  validateQuickPickupInventorySnapshot(snapshot);
  if (typeof request?.sku !== "string" || request.sku.length === 0) {
    throw new TypeError("sku must be a non-empty string");
  }
  if (!Number.isInteger(request.quantity) || request.quantity < 1) {
    throw new TypeError("quantity must be a positive integer");
  }
  requireIsoTimestamp(request.evaluated_at, "evaluated_at");

  const capturedAt = Date.parse(snapshot.captured_at);
  const evaluatedAt = Date.parse(request.evaluated_at);
  const stale = evaluatedAt > capturedAt + snapshot.max_age_minutes * 60_000;
  const item = snapshot.items.find((candidate) => candidate.sku === request.sku);
  const available = item ? availableToSell(item) : 0;
  const reason = stale
    ? "inventory_snapshot_stale"
    : !item
      ? "inventory_unknown"
      : available < request.quantity
        ? "insufficient_available_to_sell"
        : "availability_confirmed_by_fixture_snapshot";

  return Object.freeze({
    available: reason === "availability_confirmed_by_fixture_snapshot",
    reason,
    snapshot_id: snapshot.snapshot_id,
    available_to_sell: available,
    inventory_mutation_authorized: false,
    reservation_authorized: false,
    order_creation_authorized: false,
  });
}
