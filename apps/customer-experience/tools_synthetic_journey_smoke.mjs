import { readFileSync } from "node:fs";
import { runSyntheticCustomerJourney } from "./src/synthetic-journey-smoke.mjs";

function loadJson(relativePath) {
  return JSON.parse(readFileSync(new URL(relativePath, import.meta.url), "utf8"));
}

const catalogFixture = loadJson("./fixtures/catalog.json");
const providerProfile = loadJson("./fixtures/payment-provider.json");

const evidence = ["en", "ja"].map((locale) =>
  runSyntheticCustomerJourney({ catalogFixture, providerProfile, locale }),
);

for (const item of evidence) {
  if (
    item.ready.checkout_state !== "ready" ||
    item.blocked.checkout_state !== "blocked" ||
    item.blocked.payment_handoff_blocked !== true ||
    item.network_call_performed !== false ||
    item.mutation_authorized !== false ||
    item.production_authority_changed !== false
  ) {
    throw new Error(`Sprint 4 synthetic journey smoke failed for locale=${item.locale}`);
  }
}

console.log(
  "PHIL_AI_OS_SPRINT_4_END_TO_END_SYNTHETIC_GREEN " +
    "locales=en,ja ready_path=true blocked_path=true " +
    "komoju_connection=not_configured network_call=false mutation=false " +
    "order_creation=false payment_execution=false live_mode=false",
);
