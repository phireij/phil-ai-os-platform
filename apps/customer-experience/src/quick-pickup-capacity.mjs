const AUTHORITY_FLAGS = ["network_authorized", "capacity_mutation_authorized", "order_creation_authorized"];

function requireIsoTimestamp(value, field) {
  if (typeof value !== "string" || Number.isNaN(Date.parse(value))) {
    throw new TypeError(`${field} must be an ISO timestamp`);
  }
}

function requirePositiveInteger(value, field) {
  if (!Number.isInteger(value) || value < 1) throw new TypeError(`${field} must be a positive integer`);
}

/**
 * Validates a synthetic slot-capacity fixture. It is not an operator schedule,
 * booking calendar, or production capacity control.
 */
export function validateQuickPickupCapacitySnapshot(snapshot) {
  if (snapshot?.fixture_only !== true) throw new Error("Quick Pickup capacity snapshot must remain fixture_only");
  if (snapshot.source_type !== "synthetic_operator_capacity_snapshot") {
    throw new Error("Quick Pickup capacity snapshot source must remain synthetic");
  }
  if (typeof snapshot.snapshot_id !== "string" || snapshot.snapshot_id.length === 0) {
    throw new TypeError("snapshot_id must be a non-empty string");
  }
  if (snapshot.timezone !== "Asia/Tokyo") throw new Error("Quick Pickup capacity fixture must use Asia/Tokyo");
  if (!Array.isArray(snapshot.slots) || snapshot.slots.length === 0) {
    throw new TypeError("slots must be a non-empty array");
  }
  for (const flag of AUTHORITY_FLAGS) {
    if (snapshot[flag] !== false) throw new Error(`${flag} must remain false`);
  }
  const ids = new Set();
  for (const slot of snapshot.slots) {
    if (typeof slot?.slot_id !== "string" || slot.slot_id.length === 0) {
      throw new TypeError("slot_id must be a non-empty string");
    }
    if (ids.has(slot.slot_id)) throw new Error(`duplicate pickup slot: ${slot.slot_id}`);
    ids.add(slot.slot_id);
    requireIsoTimestamp(slot.pickup_starts_at, `pickup_starts_at for ${slot.slot_id}`);
    requireIsoTimestamp(slot.pickup_ends_at, `pickup_ends_at for ${slot.slot_id}`);
    requireIsoTimestamp(slot.order_cutoff_at, `order_cutoff_at for ${slot.slot_id}`);
    if (Date.parse(slot.pickup_starts_at) >= Date.parse(slot.pickup_ends_at)) {
      throw new Error(`pickup slot must end after it starts: ${slot.slot_id}`);
    }
    if (Date.parse(slot.order_cutoff_at) > Date.parse(slot.pickup_starts_at)) {
      throw new Error(`pickup cutoff must not be after pickup start: ${slot.slot_id}`);
    }
    requirePositiveInteger(slot.capacity, `capacity for ${slot.slot_id}`);
    if (!Number.isInteger(slot.booked) || slot.booked < 0 || slot.booked > slot.capacity) {
      throw new TypeError(`booked must be within capacity for ${slot.slot_id}`);
    }
  }
  return snapshot;
}

/** Returns a read-only decision and never books or holds a pickup slot. */
export function evaluateQuickPickupCapacity(request, snapshot) {
  validateQuickPickupCapacitySnapshot(snapshot);
  if (typeof request?.slot_id !== "string" || request.slot_id.length === 0) {
    throw new TypeError("slot_id must be a non-empty string");
  }
  requirePositiveInteger(request.quantity, "quantity");
  requireIsoTimestamp(request.evaluated_at, "evaluated_at");

  const slot = snapshot.slots.find((candidate) => candidate.slot_id === request.slot_id);
  const remaining = slot ? slot.capacity - slot.booked : 0;
  const reason = !slot
    ? "pickup_slot_unknown"
    : Date.parse(request.evaluated_at) > Date.parse(slot.order_cutoff_at)
      ? "pickup_cutoff_passed"
      : remaining < request.quantity
        ? "pickup_capacity_unavailable"
        : "pickup_capacity_confirmed_by_fixture_snapshot";
  return Object.freeze({
    available: reason === "pickup_capacity_confirmed_by_fixture_snapshot",
    reason,
    snapshot_id: snapshot.snapshot_id,
    remaining_capacity: remaining,
    capacity_mutation_authorized: false,
    order_creation_authorized: false,
  });
}
