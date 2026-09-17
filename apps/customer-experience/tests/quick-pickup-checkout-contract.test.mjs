import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildQuickPickupCheckoutHandoff,
  validateQuickPickupCheckoutContract,
} from "../src/quick-pickup-checkout-contract.mjs";
import {
  buildDeterministicQuickPickupFixtureRequest,
  evaluateQuickPickupDecisionPreview,
} from "../src/quick-pickup-decision-preview.mjs";

const inventoryUrl = new URL("../fixtures/quick-pickup-inventory-snapshot.json", import.meta.url);
const capacityUrl = new URL("../fixtures/quick-pickup-capacity-snapshot.json", import.meta.url);
const providerUrl = new URL("../fixtures/payment-provider.json", import.meta.url);

async function json(url) {
  return JSON.parse(await readFile(url, "utf8"));
}

async function availableFixtureDecision() {
  const [inventory, capacity] = await Promise.all([json(inventoryUrl), json(capacityUrl)]);
  const request = buildDeterministicQuickPickupFixtureRequest(inventory, capacity);
  return evaluateQuickPickupDecisionPreview(request, inventory, capacity);
}

test("builds a non-authorizing WooCommerce checkout handoff from an available fixture decision", async () => {
  const [pickupDecision, providerProfile] = await Promise.all([availableFixtureDecision(), json(providerUrl)]);
  const handoff = buildQuickPickupCheckoutHandoff({ pickupDecision, providerProfile });
  assert.equal(validateQuickPickupCheckoutContract(handoff), handoff);
  assert.equal(handoff.fixture_only, true);
  assert.equal(handoff.fulfillment, "pickup");
  assert.equal(handoff.checkout_boundary, "woocommerce_checkout_handoff");
  assert.equal(handoff.sku, pickupDecision.sku);
  assert.equal(handoff.slot_id, pickupDecision.slot_id);
  assert.equal(handoff.external_order_reference, null);
  assert.equal(handoff.order_creation_authorized, false);
  assert.equal(handoff.payment_execution_authorized, false);
  assert.equal(handoff.live_mode_authorized, false);
  assert.equal(handoff.inventory_mutation_authorized, false);
  assert.equal(handoff.capacity_mutation_authorized, false);
  assert.equal(handoff.production_publish_authorized, false);
});

test("refuses checkout handoff when the synthetic pickup decision is unavailable", async () => {
  const [pickupDecision, providerProfile] = await Promise.all([availableFixtureDecision(), json(providerUrl)]);
  assert.throws(
    () => buildQuickPickupCheckoutHandoff({ pickupDecision: { ...pickupDecision, available: false }, providerProfile }),
    /available synthetic decision/,
  );
});

test("refuses any authority expansion in the Quick Pickup checkout contract", async () => {
  const [pickupDecision, providerProfile] = await Promise.all([availableFixtureDecision(), json(providerUrl)]);
  const base = buildQuickPickupCheckoutHandoff({ pickupDecision, providerProfile });
  for (const key of [
    "order_creation_authorized",
    "payment_execution_authorized",
    "live_mode_authorized",
    "inventory_mutation_authorized",
    "capacity_mutation_authorized",
    "production_publish_authorized",
  ]) {
    assert.throws(() => validateQuickPickupCheckoutContract({ ...base, [key]: true }), new RegExp(key));
  }
});

test("refuses a live or configured payment provider profile", async () => {
  const [pickupDecision, providerProfile] = await Promise.all([availableFixtureDecision(), json(providerUrl)]);
  assert.throws(
    () => buildQuickPickupCheckoutHandoff({ pickupDecision, providerProfile: { ...providerProfile, payment_execution_authorized: true } }),
    /non-authorizing/,
  );
});
