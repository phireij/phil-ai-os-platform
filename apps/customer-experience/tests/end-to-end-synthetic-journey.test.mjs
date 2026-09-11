import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runSyntheticCustomerJourney } from "../src/synthetic-journey-smoke.mjs";

const catalogFixture = JSON.parse(
  readFileSync(new URL("../fixtures/catalog.json", import.meta.url), "utf8"),
);
const providerProfile = JSON.parse(
  readFileSync(new URL("../fixtures/payment-provider.json", import.meta.url), "utf8"),
);

test("end-to-end synthetic customer journey reaches ready payment handoff without authority", () => {
  const evidence = runSyntheticCustomerJourney({
    catalogFixture,
    providerProfile,
    locale: "en",
  });

  assert.equal(evidence.smoke, "sprint4_customer_experience_end_to_end_synthetic");
  assert.equal(evidence.fixture_only, true);
  assert.equal(evidence.network_call_performed, false);
  assert.equal(evidence.mutation_authorized, false);
  assert.equal(evidence.production_authority_changed, false);

  assert.equal(evidence.ready.checkout_state, "ready");
  assert.equal(evidence.ready.readiness_ready, true);
  assert.deepEqual(evidence.ready.blockers, []);
  assert.deepEqual(evidence.ready.selected_skus, ["SAMPLE-CHOCO-001", "SAMPLE-UBE-001"]);
  assert.equal(evidence.ready.total_amount, "950");
  assert.equal(evidence.ready.currency, "JPY");
  assert.equal(evidence.ready.payment_provider, "komoju");
  assert.equal(evidence.ready.payment_connection_state, "not_configured");
  assert.equal(evidence.ready.order_creation_authorized, false);
  assert.equal(evidence.ready.payment_execution_authorized, false);
  assert.equal(evidence.ready.live_mode_authorized, false);
});

test("end-to-end synthetic customer journey proves blocked inventory cannot reach payment handoff", () => {
  const evidence = runSyntheticCustomerJourney({
    catalogFixture,
    providerProfile,
    locale: "ja",
  });

  assert.equal(evidence.blocked.checkout_state, "blocked");
  assert.equal(evidence.blocked.readiness_ready, false);
  assert.deepEqual(evidence.blocked.blockers, ["inventory"]);
  assert.equal(evidence.blocked.selected_sku, "SAMPLE-CARROT-001");
  assert.equal(evidence.blocked.payment_handoff_blocked, true);
  assert.equal(evidence.blocked.network_call_performed, false);
  assert.equal(evidence.blocked.mutation_authorized, false);
  assert.equal(evidence.blocked.payment_execution_authorized, false);
});

test("synthetic journey exercises bilingual catalog and product detail contracts", () => {
  const english = runSyntheticCustomerJourney({ catalogFixture, providerProfile, locale: "en" });
  const japanese = runSyntheticCustomerJourney({ catalogFixture, providerProfile, locale: "ja" });

  assert.equal(english.ready.localized_catalog_name, "Sample Chocolate Cupcake");
  assert.equal(japanese.ready.localized_catalog_name, "サンプル・チョコレートカップケーキ");
  assert.equal(english.ready.localized_product_name, "Sample Chocolate Cupcake");
  assert.equal(japanese.ready.localized_product_name, "サンプル・チョコレートカップケーキ");
  assert.equal(english.ready.catalog_snapshot_ref, catalogFixture.catalog_snapshot_ref);
  assert.equal(japanese.ready.catalog_snapshot_ref, catalogFixture.catalog_snapshot_ref);
});

test("synthetic journey rejects any fixture or payment profile that could imply live authority", () => {
  assert.throws(
    () => runSyntheticCustomerJourney({ catalogFixture: { ...catalogFixture, fixture_only: false }, providerProfile }),
    /fixture-only catalog/,
  );
  assert.throws(
    () => runSyntheticCustomerJourney({
      catalogFixture,
      providerProfile: { ...providerProfile, connection_state: "connected" },
    }),
    /connection must remain not_configured/,
  );
  assert.throws(
    () => runSyntheticCustomerJourney({
      catalogFixture,
      providerProfile: { ...providerProfile, payment_execution_authorized: true },
    }),
    /non-authorizing/,
  );
});
