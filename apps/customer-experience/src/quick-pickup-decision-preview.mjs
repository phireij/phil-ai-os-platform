import { evaluateQuickPickupAvailability } from "./quick-pickup-availability.mjs";
import { evaluateQuickPickupCapacity } from "./quick-pickup-capacity.mjs";

function requirePreviewRequest(request) {
  if (typeof request?.sku !== "string" || request.sku.length === 0) {
    throw new TypeError("preview sku must be a non-empty string");
  }
  if (typeof request?.slot_id !== "string" || request.slot_id.length === 0) {
    throw new TypeError("preview slot_id must be a non-empty string");
  }
  if (!Number.isInteger(request.quantity) || request.quantity < 1) {
    throw new TypeError("preview quantity must be a positive integer");
  }
  if (typeof request.evaluated_at !== "string" || Number.isNaN(Date.parse(request.evaluated_at))) {
    throw new TypeError("preview evaluated_at must be an ISO timestamp");
  }
}

/**
 * Combines the existing fixture-only inventory and slot checks for a customer-facing
 * preview. This is intentionally a read-only decision: it cannot reserve stock,
 * book capacity, create an order, activate payment, or authorize a production route.
 */
export function evaluateQuickPickupDecisionPreview(request, inventorySnapshot, capacitySnapshot) {
  requirePreviewRequest(request);

  const inventory = evaluateQuickPickupAvailability({
    sku: request.sku,
    quantity: request.quantity,
    evaluated_at: request.evaluated_at,
  }, inventorySnapshot);
  const capacity = evaluateQuickPickupCapacity({
    slot_id: request.slot_id,
    quantity: request.quantity,
    evaluated_at: request.evaluated_at,
  }, capacitySnapshot);

  const available = inventory.available && capacity.available;
  const reason = !inventory.available
    ? inventory.reason
    : !capacity.available
      ? capacity.reason
      : "fixture_inventory_and_capacity_confirmed";

  return Object.freeze({
    fixture_only: true,
    available,
    reason,
    sku: request.sku,
    quantity: request.quantity,
    slot_id: request.slot_id,
    evaluated_at: request.evaluated_at,
    inventory_reason: inventory.reason,
    capacity_reason: capacity.reason,
    available_to_sell: inventory.available_to_sell,
    remaining_capacity: capacity.remaining_capacity,
    route_activation_authorized: false,
    inventory_mutation_authorized: false,
    reservation_authorized: false,
    capacity_mutation_authorized: false,
    order_creation_authorized: false,
    payment_execution_authorized: false,
  });
}

/**
 * Produces one deterministic demonstration request from validated fixture snapshots.
 * The evaluation time is intentionally anchored to the fixture capture time instead
 * of wall-clock time so this preview never presents historical fixture data as live.
 */
export function buildDeterministicQuickPickupFixtureRequest(inventorySnapshot, capacitySnapshot) {
  const item = inventorySnapshot?.items?.[0];
  const slot = capacitySnapshot?.slots?.[0];
  if (!item || !slot) throw new Error("Quick Pickup decision preview fixtures must contain an item and slot");
  const capturedAt = Date.parse(inventorySnapshot.captured_at);
  if (Number.isNaN(capturedAt)) throw new TypeError("inventory fixture captured_at must be an ISO timestamp");

  return Object.freeze({
    sku: item.sku,
    quantity: 1,
    slot_id: slot.slot_id,
    evaluated_at: new Date(capturedAt + 15 * 60_000).toISOString(),
  });
}
