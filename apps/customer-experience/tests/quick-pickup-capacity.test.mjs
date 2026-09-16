import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { evaluateQuickPickupCapacity, validateQuickPickupCapacitySnapshot } from "../src/quick-pickup-capacity.mjs";

const fixtureUrl = new URL("../fixtures/quick-pickup-capacity-snapshot.json", import.meta.url);
async function fixture() { return JSON.parse(await readFile(fixtureUrl, "utf8")); }

test("synthetic pickup capacity remains read-only and honors remaining capacity", async () => {
  const snapshot = await fixture();
  assert.equal(validateQuickPickupCapacitySnapshot(snapshot), snapshot);
  assert.deepEqual(evaluateQuickPickupCapacity({
    slot_id: "fixture-2026-09-16-1400", quantity: 3, evaluated_at: "2026-09-16T03:30:00.000Z",
  }, snapshot), {
    available: true,
    reason: "pickup_capacity_confirmed_by_fixture_snapshot",
    snapshot_id: "fixture:quick-pickup-capacity-v1",
    remaining_capacity: 3,
    capacity_mutation_authorized: false,
    order_creation_authorized: false,
  });
});

test("unknown, past-cutoff, and full capacity requests fail closed", async () => {
  const snapshot = await fixture();
  assert.equal(evaluateQuickPickupCapacity({
    slot_id: "unknown", quantity: 1, evaluated_at: "2026-09-16T03:30:00.000Z",
  }, snapshot).reason, "pickup_slot_unknown");
  assert.equal(evaluateQuickPickupCapacity({
    slot_id: "fixture-2026-09-16-1400", quantity: 1, evaluated_at: "2026-09-16T04:00:01.000Z",
  }, snapshot).reason, "pickup_cutoff_passed");
  assert.equal(evaluateQuickPickupCapacity({
    slot_id: "fixture-2026-09-16-1400", quantity: 4, evaluated_at: "2026-09-16T03:30:00.000Z",
  }, snapshot).reason, "pickup_capacity_unavailable");
});

test("capacity fixture rejects production authority and invalid slot data", async () => {
  const snapshot = await fixture();
  assert.throws(() => validateQuickPickupCapacitySnapshot({ ...snapshot, capacity_mutation_authorized: true }), /must remain false/);
  assert.throws(() => validateQuickPickupCapacitySnapshot({ ...snapshot, timezone: "UTC" }), /Asia\/Tokyo/);
  assert.throws(() => validateQuickPickupCapacitySnapshot({
    ...snapshot, slots: [{ ...snapshot.slots[0], booked: 9 }],
  }), /within capacity/);
});
