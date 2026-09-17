import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../src/quick-pickup-preview.mjs", import.meta.url);

async function source() {
  return readFile(sourceUrl, "utf8");
}

test("Quick Pickup preview consumes both fixture-only stock and slot controls", async () => {
  const text = await source();
  assert.match(text, /evaluateQuickPickupDecisionPreview/);
  assert.match(text, /quick-pickup-inventory-snapshot\.json/);
  assert.match(text, /quick-pickup-capacity-snapshot\.json/);
  assert.match(text, /buildDeterministicQuickPickupFixtureRequest/);
});

test("Quick Pickup preview applies the fixture-only operator-disable control before route exposure", async () => {
  const text = await source();
  assert.match(text, /applyQuickPickupDisableControl/);
  assert.match(text, /validateQuickPickupDisableControl/);
  assert.match(text, /quick-pickup-disable-control\.json/);
  assert.match(text, /const state = applyQuickPickupDisableControl\(upstreamState, disableControl\)/);
  assert.match(text, /Fixture operator-disable control/);
  assert.match(text, /フィクスチャ専用：運用者停止コントロール/);
});

test("customer copy makes the synthetic decision non-authorizing in English and Japanese", async () => {
  const text = await source();
  assert.match(text, /Historical test data only/);
  assert.match(text, /not live inventory, not a reservation, and not an order/);
  assert.match(text, /過去のテストデータのみです/);
  assert.match(text, /実在庫、予約、注文ではなく/);
});

test("preview technical output cannot claim live fixture sources", async () => {
  const text = await source();
  assert.match(text, /live_inventory_claimed: false/);
  assert.match(text, /live_capacity_claimed: false/);
  assert.match(text, /automatic_production_execution_authorized/);
});
