import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const cart = readFileSync(new URL("../src/cart-preview.mjs", import.meta.url), "utf8");
const confirmation = readFileSync(new URL("../src/confirmation-preview.mjs", import.meta.url), "utf8");
const pickup = readFileSync(new URL("../src/quick-pickup-preview.mjs", import.meta.url), "utf8");

for (const [name, source] of [["cart", cart], ["confirmation", confirmation], ["quick pickup", pickup]]) {
  test(`${name} preview localizes shared chrome`, () => {
    assert.match(source, /skipToContent:\s*"本文へ移動"/);
    assert.match(source, /brand:\s*"カスタマーエクスペリエンス"/);
    assert.match(source, /languageLabel:\s*"言語"/);
    assert.match(source, /\.skip-link/);
    assert.match(source, /\.site-header \.brand/);
    assert.match(source, /\.locale-label/);
    assert.match(source, /\.hero \.status-pill/);
    assert.match(source, /footer p/);
    assert.match(source, /setAttribute\("aria-label", c\.languageLabel\)/);
  });
}

test("preview-specific Japanese status and footer copy stay distinct", () => {
  assert.match(cart, /previewStatus:\s*"分離プレビュー · KOMOJU未接続"/);
  assert.match(confirmation, /previewStatus:\s*"分離合成プレビュー · 注文送信なし"/);
  assert.match(pickup, /previewStatus:\s*"分離プレビュー · 外部有効化なし"/);
  assert.match(pickup, /フィクスチャ専用クイックピックアップ準備状況/);
});
