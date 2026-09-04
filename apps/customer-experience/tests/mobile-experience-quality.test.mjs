import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const index = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");
const mobileUx = readFileSync(new URL("../src/mobile-ux.mjs", import.meta.url), "utf8");

test("mobile journey exposes clear browse, fulfillment and final-review steps", () => {
  assert.match(index, /class="journey-panel"/);
  assert.match(index, /id="journey-browse-title"/);
  assert.match(index, /id="journey-fulfillment-title"/);
  assert.match(index, /id="journey-review-title"/);
});

test("thumb-friendly mobile dock uses safe-area spacing and large targets", () => {
  assert.match(index, /class="mobile-action-dock"/);
  assert.match(styles, /--mobile-dock-height:\s*72px/);
  assert.match(styles, /env\(safe-area-inset-bottom\)/);
  assert.match(styles, /\.mobile-action-dock a\s*\{[^}]*min-height:\s*56px/s);
  assert.match(styles, /\.detail-link, \.primary-button, \.secondary-link, \.text-link\s*\{[^}]*min-height:\s*48px/s);
});

test("new mobile journey remains bilingual in English and Japanese", () => {
  assert.match(index, /src="\.\/src\/mobile-ux\.mjs"/);
  assert.match(mobileUx, /From craving to confirmation/);
  assert.match(mobileUx, /商品選びから最終確認まで/);
  assert.match(mobileUx, /店頭受取・配送/);
  assert.match(mobileUx, /モバイルプレビューナビゲーション/);
});

test("customer-flow preview remains non-authorizing and local", () => {
  assert.doesNotMatch(index, /https?:\/\//);
  assert.doesNotMatch(mobileUx, /fetch\s*\(/);
  assert.doesNotMatch(mobileUx, /POST|PUT|PATCH|DELETE/);
  assert.match(index, /No live checkout/);
});
