import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function text(path) {
  return readFile(new URL(path, root), "utf8");
}

test("Quick Pickup route is isolated, noindex and exposes no ordering form", async () => {
  const html = await text("quick-pickup.html");
  assert.match(html, /meta name="robots" content="noindex,nofollow"/);
  assert.match(html, /Ordering disabled/);
  assert.match(html, /No customer order action/);
  assert.doesNotMatch(html, /<form\b/i);
  assert.doesNotMatch(html, /<button\b/i);
});

test("Quick Pickup route runtime remains fixture-only and non-authorizing", async () => {
  const source = await text("src/quick-pickup-route.mjs");
  for (const fixture of [
    "first-party-quick-pickup.json",
    "quick-pickup-inventory-snapshot.json",
    "quick-pickup-capacity-snapshot.json",
    "quick-pickup-disable-control.json",
  ]) {
    assert.match(source, new RegExp(`fixtures/${fixture.replaceAll(".", "\\.")}`));
  }
  assert.match(source, /order_creation_authorized:\s*false/);
  assert.match(source, /payment_execution_authorized:\s*false/);
  assert.match(source, /production_publish_authorized:\s*false/);
  assert.doesNotMatch(source, /fetch\(["']https?:\/\//);
});

test("Quick Pickup route and runtime are cached in the offline app shell", async () => {
  const serviceWorker = await text("sw.js");
  assert.match(serviceWorker, /"\.\/quick-pickup\.html"/);
  assert.match(serviceWorker, /"\.\/src\/quick-pickup-route\.mjs"/);
  assert.match(serviceWorker, /"\.\/fixtures\/first-party-quick-pickup\.json"/);
  assert.match(serviceWorker, /"\.\/fixtures\/quick-pickup-disable-control\.json"/);
});

test("offline hardening does not promote Quick Pickup production readiness", async () => {
  const readiness = JSON.parse(await text("../../ops/readiness/ruby-first-party-quick-pickup-readiness.json"));
  assert.equal(readiness.production_readiness.first_party_pickup_route_implemented, true);
  assert.equal(readiness.production_readiness.production_activation_ready, false);
  assert.equal(readiness.production_readiness.controlled_handset_and_operator_acceptance_green, false);
  assert.equal(readiness.production_readiness.rollback_disable_path_green, false);
  for (const value of Object.values(readiness.authority)) assert.equal(value, false);
});
