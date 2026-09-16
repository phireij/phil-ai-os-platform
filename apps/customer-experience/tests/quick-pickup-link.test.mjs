import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  firstPartyQuickPickupUiState,
  validateFirstPartyQuickPickupConfig,
} from "../src/pickup.mjs";

const fixtureUrl = new URL("../fixtures/first-party-quick-pickup.json", import.meta.url);

async function fixture() {
  return JSON.parse(await readFile(fixtureUrl, "utf8"));
}

test("first-party Quick Pickup remains unavailable until implemented", async () => {
  const config = await fixture();
  assert.equal(validateFirstPartyQuickPickupConfig(config), config);
  assert.deepEqual(firstPartyQuickPickupUiState(config), {
    available: false,
    href: null,
    reason: "implementation_pending",
  });
});

test("implemented route remains unavailable until every readiness gate is green", async () => {
  const config = {
    ...(await fixture()),
    route_implemented: true,
    customer_route: "/quick-pickup",
  };
  assert.deepEqual(firstPartyQuickPickupUiState(config), {
    available: false,
    href: null,
    reason: "readiness_pending",
  });
});

test("controlled activation requires all first-party readiness gates", async () => {
  const config = {
    ...(await fixture()),
    route_implemented: true,
    customer_route: "/quick-pickup",
    eligible_catalog_confirmed: true,
    inventory_freshness_control_green: true,
    capacity_and_cutoff_control_green: true,
    checkout_and_payment_contract_green: true,
    bilingual_customer_copy_green: true,
    controlled_handset_and_operator_acceptance_green: true,
    rollback_disable_path_green: true,
    activation_authorized: true,
  };
  assert.deepEqual(firstPartyQuickPickupUiState(config), {
    available: true,
    href: "/quick-pickup",
    reason: "controlled_activation_ready",
  });
});

test("Air Mobile and automatic execution fail closed", async () => {
  const base = await fixture();
  assert.throws(
    () => validateFirstPartyQuickPickupConfig({ ...base, air_mobile_order_required_for_v1: true }),
    /must not be a V1 Quick Pickup dependency/,
  );
  assert.throws(
    () => validateFirstPartyQuickPickupConfig({ ...base, automatic_production_execution_authorized: true }),
    /must remain disabled/,
  );
  assert.throws(
    () => validateFirstPartyQuickPickupConfig({ ...base, customer_route: "https://example.invalid/pickup" }),
    /site-relative path/,
  );
});

test("activation cannot outrun the first-party readiness gates", async () => {
  const base = await fixture();
  assert.throws(
    () => validateFirstPartyQuickPickupConfig({ ...base, activation_authorized: true }),
    /requires every first-party readiness gate/,
  );
});
