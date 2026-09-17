import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  QUICK_PICKUP_ROUTE_COPY,
  quickPickupRouteCopy,
  validateQuickPickupRouteCopy,
} from "../src/quick-pickup-route-copy.mjs";

const swUrl = new URL("../sw.js", import.meta.url);

test("Quick Pickup route copy has exact EN/JA key parity", () => {
  assert.equal(validateQuickPickupRouteCopy(), QUICK_PICKUP_ROUTE_COPY);
  assert.deepEqual(Object.keys(QUICK_PICKUP_ROUTE_COPY.en).sort(), Object.keys(QUICK_PICKUP_ROUTE_COPY.ja).sort());
});

test("Quick Pickup route copy remains explicitly non-ordering in both locales", () => {
  const en = quickPickupRouteCopy("en");
  const ja = quickPickupRouteCopy("ja");
  assert.match(en.status, /Ordering disabled/);
  assert.match(en.heroCopy, /cannot reserve stock.*create an order.*execute payment/i);
  assert.match(en.fixtureSafety, /does not hold stock.*create an order.*authorize payment.*publish this route/i);
  assert.match(ja.status, /注文無効/);
  assert.match(ja.heroCopy, /在庫確保.*注文作成.*決済実行/);
  assert.match(ja.fixtureSafety, /在庫確保.*注文作成.*決済承認.*ルート公開/);
});

test("unsupported locale falls back to English without authority", () => {
  assert.equal(quickPickupRouteCopy("fr"), QUICK_PICKUP_ROUTE_COPY.en);
  assert.match(quickPickupRouteCopy("fr").footer, /No customer order action/);
});

test("copy validator fails closed on missing translations and blank text", () => {
  const missingKey = {
    en: { language: "Language", status: "Disabled" },
    ja: { language: "言語" },
  };
  assert.throws(() => validateQuickPickupRouteCopy(missingKey), /keys must match exactly/);
  const blank = {
    en: { language: "Language" },
    ja: { language: "   " },
  };
  assert.throws(() => validateQuickPickupRouteCopy(blank), /non-empty string/);
});

test("validated Quick Pickup copy contract is cached for offline route rendering", async () => {
  const sw = await readFile(swUrl, "utf8");
  assert.match(sw, /\.\/src\/quick-pickup-route-copy\.mjs/);
  assert.match(sw, /\.\/quick-pickup\.html/);
});
