import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  availableToSell,
  evaluateQuickPickupAvailability,
  validateQuickPickupInventorySnapshot,
} from "../src/quick-pickup-availability.mjs";

const fixtureUrl = new URL("../fixtures/quick-pickup-inventory-snapshot.json", import.meta.url);

async function fixture() {
  return JSON.parse(await readFile(fixtureUrl, "utf8"));
}

test("fresh synthetic snapshot calculates conservative availability without authority", async () => {
  const snapshot = await fixture();
  assert.equal(validateQuickPickupInventorySnapshot(snapshot), snapshot);
  assert.equal(availableToSell(snapshot.items[2]), 3);
  assert.deepEqual(evaluateQuickPickupAvailability({
    sku: "SAMPLE-UBE-001",
    quantity: 3,
    evaluated_at: "2026-09-16T00:20:00.000Z",
  }, snapshot), {
    available: true,
    reason: "availability_confirmed_by_fixture_snapshot",
    snapshot_id: "fixture:quick-pickup-inventory-v1",
    available_to_sell: 3,
    inventory_mutation_authorized: false,
    reservation_authorized: false,
    order_creation_authorized: false,
  });
});

test("stale snapshots and unknown or insufficient stock fail closed", async () => {
  const snapshot = await fixture();
  assert.equal(evaluateQuickPickupAvailability({
    sku: "SAMPLE-CHOCO-001", quantity: 1, evaluated_at: "2026-09-16T00:31:00.000Z",
  }, snapshot).reason, "inventory_snapshot_stale");
  assert.equal(evaluateQuickPickupAvailability({
    sku: "NOT-IN-SNAPSHOT", quantity: 1, evaluated_at: "2026-09-16T00:10:00.000Z",
  }, snapshot).reason, "inventory_unknown");
  assert.equal(evaluateQuickPickupAvailability({
    sku: "SAMPLE-UBE-001", quantity: 4, evaluated_at: "2026-09-16T00:10:00.000Z",
  }, snapshot).reason, "insufficient_available_to_sell");
});

test("fixture inventory rejects production claims and invalid quantities", async () => {
  const snapshot = await fixture();
  assert.throws(() => validateQuickPickupInventorySnapshot({ ...snapshot, fixture_only: false }), /fixture_only/);
  assert.throws(() => validateQuickPickupInventorySnapshot({ ...snapshot, reservation_authorized: true }), /reservation_authorized/);
  assert.throws(() => validateQuickPickupInventorySnapshot({ ...snapshot, airregi_api_verified: true }), /unverified/);
  assert.throws(() => validateQuickPickupInventorySnapshot({ ...snapshot, items: [...snapshot.items, snapshot.items[0]] }), /duplicate/);
  assert.throws(() => evaluateQuickPickupAvailability({
    sku: "SAMPLE-UBE-001", quantity: 0, evaluated_at: "2026-09-16T00:10:00.000Z",
  }, snapshot), /positive integer/);
});
