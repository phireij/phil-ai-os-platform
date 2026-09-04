import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  externalQuickPickupUiState,
  validateExternalQuickPickupConfig,
} from "../src/pickup.mjs";

const fixtureUrl = new URL("../fixtures/air-mobile-quick-pickup.json", import.meta.url);

async function fixture() {
  return JSON.parse(await readFile(fixtureUrl, "utf8"));
}

test("current Air Mobile fixture remains unavailable while production URL is pending", async () => {
  const config = await fixture();
  assert.equal(validateExternalQuickPickupConfig(config), config);
  assert.deepEqual(externalQuickPickupUiState(config), {
    available: false,
    href: null,
    reason: "production_url_pending",
  });
});

test("an owner-confirmed URL remains unavailable until validation and activation are separately authorized", async () => {
  const config = {
    ...(await fixture()),
    production_url: "https://example.invalid/quick-pickup",
    owner_confirmed: true,
  };
  assert.deepEqual(externalQuickPickupUiState(config), {
    available: false,
    href: null,
    reason: "activation_pending",
  });
});

test("controlled activation requires owner confirmation and completed validation", async () => {
  const config = {
    ...(await fixture()),
    production_url: "https://example.invalid/quick-pickup",
    owner_confirmed: true,
    validation_complete: true,
    activation_authorized: true,
  };
  assert.deepEqual(externalQuickPickupUiState(config), {
    available: true,
    href: "https://example.invalid/quick-pickup",
    reason: "controlled_activation_ready",
  });
});

test("unsafe URL forms and automatic publication fail closed", async () => {
  const base = await fixture();
  assert.throws(
    () => validateExternalQuickPickupConfig({ ...base, production_url: "http://example.invalid/pickup", owner_confirmed: true }),
    /must use https/,
  );
  assert.throws(
    () => validateExternalQuickPickupConfig({ ...base, production_url: "https://user:pass@example.invalid/pickup", owner_confirmed: true }),
    /must not embed credentials/,
  );
  assert.throws(
    () => validateExternalQuickPickupConfig({ ...base, automatic_publication_authorized: true }),
    /must remain disabled/,
  );
});

test("activation cannot outrun owner confirmation or validation", async () => {
  const base = await fixture();
  assert.throws(
    () => validateExternalQuickPickupConfig({ ...base, production_url: "https://example.invalid/pickup", activation_authorized: true }),
    /requires validated owner-confirmed production_url/,
  );
});
