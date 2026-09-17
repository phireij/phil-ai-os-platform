import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { firstPartyQuickPickupUiState } from "../src/pickup.mjs";
import {
  applyQuickPickupDisableControl,
  validateQuickPickupDisableControl,
} from "../src/quick-pickup-disable-control.mjs";

const configUrl = new URL("../fixtures/first-party-quick-pickup.json", import.meta.url);
const controlUrl = new URL("../fixtures/quick-pickup-disable-control.json", import.meta.url);

async function fixture(url) {
  return JSON.parse(await readFile(url, "utf8"));
}

function fullyReadyConfig(base) {
  return {
    ...base,
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
}

test("engaged operator disable vetoes an otherwise ready synthetic route", async () => {
  const [base, control] = await Promise.all([fixture(configUrl), fixture(controlUrl)]);
  assert.equal(validateQuickPickupDisableControl(control), control);
  const upstream = firstPartyQuickPickupUiState(fullyReadyConfig(base));
  assert.equal(upstream.available, true);
  assert.equal(upstream.href, "/quick-pickup");

  assert.deepEqual(applyQuickPickupDisableControl(upstream, control), {
    available: false,
    href: null,
    reason: "operator_disable_engaged",
    upstream_reason: "controlled_activation_ready",
    disable_control_id: "fixture:quick-pickup-disable-v1",
    disable_reason: "preproduction_not_ready",
    route_activation_authorized: false,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    production_publish_authorized: false,
  });
});

test("disengaged fixture control does not make an unready route available", async () => {
  const [base, control] = await Promise.all([fixture(configUrl), fixture(controlUrl)]);
  const upstream = firstPartyQuickPickupUiState(base);
  const result = applyQuickPickupDisableControl(upstream, { ...control, disable_engaged: false });
  assert.equal(result.available, false);
  assert.equal(result.href, null);
  assert.equal(result.reason, "implementation_pending");
  assert.equal(result.route_activation_authorized, false);
});

test("disable fixture rejects any production-side authority", async () => {
  const control = await fixture(controlUrl);
  for (const key of [
    "network_authorized",
    "route_mutation_authorized",
    "inventory_mutation_authorized",
    "capacity_mutation_authorized",
    "order_creation_authorized",
    "payment_execution_authorized",
    "production_publish_authorized",
  ]) {
    assert.throws(() => validateQuickPickupDisableControl({ ...control, [key]: true }), new RegExp(key));
  }
  assert.throws(() => validateQuickPickupDisableControl({ ...control, fixture_only: false }), /fixture_only/);
  assert.throws(() => validateQuickPickupDisableControl({ ...control, control_id: "production:disable" }), /fixture-scoped/);
});
