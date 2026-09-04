import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const EXPECTED_HOST = "darkgreen-wallaby-680439.hostingersite.com";
const baseUrl = (process.env.RUBY_WOO_PREPRODUCTION_BASE_URL || "").replace(/\/$/, "");
const outputDir = process.env.RUBY_FINAL_SCREEN_CAPTURE_OUTPUT || "/tmp/philaios-ruby-final-screen";

if (!baseUrl) throw new Error("RUBY_WOO_PREPRODUCTION_BASE_URL is required");
const target = new URL(baseUrl);
if (target.protocol !== "https:" || target.hostname !== EXPECTED_HOST) {
  throw new Error(`probe target must remain locked to https://${EXPECTED_HOST}`);
}

await mkdir(outputDir, { recursive: true });

const endpoint = `${baseUrl}/wp-json/wc/store/v1/products?per_page=100`;
const response = await fetch(endpoint, {
  method: "GET",
  redirect: "error",
  headers: {
    Accept: "application/json",
    "User-Agent": "PhilAIOS-Preproduction-Catalog-Probe/1.0",
  },
});

if (!response.ok) {
  const payload = {
    version: "ruby-preproduction-public-catalog-probe-v1",
    environment: "preproduction",
    endpoint_class: "woocommerce_store_api_products_get_only",
    network_read_only: true,
    http_status: response.status,
    products_returned: 0,
    purchasable_candidates: 0,
    first_candidate_product_id: null,
    checkout_ready_for_non_submitted_screen_capture: false,
    mutation_authorized: false,
    order_creation_authorized: false,
    payment_execution_authorized: false,
    production_publish_authorized: false,
    decision: "STORE_API_GET_FAILED_FAIL_CLOSED",
  };
  await writeFile(path.join(outputDir, "catalog-probe.json"), `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  throw new Error(`preproduction Store API products GET failed: ${response.status}`);
}

const products = await response.json();
if (!Array.isArray(products)) {
  throw new Error("preproduction Store API products payload is not an array");
}

const candidates = products.filter(
  (item) => item?.id && item?.is_purchasable !== false && item?.is_in_stock !== false
);
const firstCandidate = candidates[0] || null;

const payload = {
  version: "ruby-preproduction-public-catalog-probe-v1",
  environment: "preproduction",
  endpoint_class: "woocommerce_store_api_products_get_only",
  network_read_only: true,
  http_status: response.status,
  products_returned: products.length,
  purchasable_candidates: candidates.length,
  first_candidate_product_id: firstCandidate?.id ?? null,
  checkout_ready_for_non_submitted_screen_capture: Boolean(firstCandidate),
  mutation_authorized: false,
  order_creation_authorized: false,
  payment_execution_authorized: false,
  production_publish_authorized: false,
  decision: firstCandidate
    ? "PURCHASABLE_PREPRODUCTION_PRODUCT_AVAILABLE_FOR_NON_SUBMITTED_SCREEN_CAPTURE"
    : "NO_PURCHASABLE_PREPRODUCTION_PRODUCT_FAIL_CLOSED",
};

await writeFile(path.join(outputDir, "catalog-probe.json"), `${JSON.stringify(payload, null, 2)}\n`, "utf8");

if (!firstCandidate) {
  console.error(
    `PHIL_AI_OS_RUBY_PREPRODUCTION_CATALOG_PROBE_BLOCKED products=${products.length} candidates=0 mutation=false order_creation=false payment_execution=false`
  );
  process.exitCode = 3;
} else {
  console.log(
    `PHIL_AI_OS_RUBY_PREPRODUCTION_CATALOG_PROBE_GREEN products=${products.length} candidates=${candidates.length} candidate_id=${firstCandidate.id} mutation=false order_creation=false payment_execution=false`
  );
}
