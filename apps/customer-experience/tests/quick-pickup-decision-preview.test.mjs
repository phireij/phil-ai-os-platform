import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildDeterministicQuickPickupFixtureRequest,
  evaluateQuickPickupDecisionPreview,
} from "../src/quick-pickup-decision-preview.mjs";

const inventoryUrl = new URL("../fixtures/quick-pickup-inventory-snapshot.json", import.meta.url);
const capacityUrl = new URL("../fixtures/quick-pickup-capacity-snapshot.json", import.meta.url);

async function fixtures() {
  const [inventory, capacity] = await Promise.all([
    readFile(inventoryUrl, "utf8").then(JSON.parse),
    readFile(capacityUrl, "utf8").then(JSON.parse),
  ]);
  return { inventory, capacity };
}

test("deterministic fixture decision combines stock and slot availability without authority", async () => {
  const { inventory, capacity } = await fixtures();
  const request = buildDeterministicQuickPickupFixtureRequest(inventory, capacity);
  assert.deepEqual(request, {
    sku: "SAMPLE-CHOCO-001",
    quantity: 1,
    slot_id: "fixture-2026-09-16-1400",
    evaluated_at: "2026-09-16T00:15:00.000Z",
  });

  const result = evaluateQuickPickupDecisionPreview(request, inventory, capacity);
  assert.equal(result.fixture_only, true);
  assert.equal(result.available, true);
  assert.equal(result.reason, "fixture_inventory_and_capacity_confirmed");
  assert.equal(result.available_to_sell, 10);
  assert.equal(result.remaining_capacity, 3);
  for (const key of [
    "route_activation_authorized",
    "inventory_mutation_authorized",
    "reservation_authorized",
    "capacity_mutation_authorized",
    "order_creation_authorized",
    "payment_execution_authorized",
  ]) {
    assert.equal(result[key], false, `${key} must remain false`);
  }
});

test("inventory freshness failure keeps the combined preview fail closed", async () => {
  const { inventory, capacity } = await fixtures();
  const result = evaluateQuickPickupDecisionPreview({
    sku: "SAMPLE-CHOCO-001",
    quantity: 1,
    slot_id: "fixture-2026-09-16-1400",
    evaluated_at: "2026-09-16T00:31:00.000Z",
  }, inventory, capacity);
  assert.equal(result.available, false);
  assert.equal(result.reason, "inventory_snapshot_stale");
  assert.equal(result.order_creation_authorized, false);
});

test("stock and capacity constraints remain independently fail closed", async () => {
  const { inventory, capacity } = await fixtures();
  const noStock = evaluateQuickPickupDecisionPreview({
    sku: "SAMPLE-CARROT-001",
    quantity: 1,
    slot_id: "fixture-2026-09-16-1400",
    evaluated_at: "2026-09-16T00:15:00.000Z",
  }, inventory, capacity);
  assert.equal(noStock.available, false);
  assert.equal(noStock.reason, "insufficient_available_to_sell");

  const noCapacity = evaluateQuickPickupDecisionPreview({
    sku: "SAMPLE-CHOCO-001",
    quantity: 4,
    slot_id: "fixture-2026-09-16-1400",
    evaluated_at: "2026-09-16T00:15:00.000Z",
  }, inventory, capacity);
  assert.equal(noCapacity.available, false);
  assert.equal(noCapacity.reason, "pickup_capacity_unavailable");
});

test("decision preview validates the synthetic request shape", async () => {
  const { inventory, capacity } = await fixtures();
  assert.throws(
    () => evaluateQuickPickupDecisionPreview({ sku: "", quantity: 1, slot_id: "slot", evaluated_at: "2026-09-16T00:15:00Z" }, inventory, capacity),
    /sku/,
  );
  assert.throws(
    () => evaluateQuickPickupDecisionPreview({ sku: "SAMPLE-CHOCO-001", quantity: 0, slot_id: "slot", evaluated_at: "2026-09-16T00:15:00Z" }, inventory, capacity),
    /positive integer/,
  );
});
