import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const root = new URL("../", import.meta.url);
const helper = readFileSync(new URL("src/page-chrome-locale.mjs", root), "utf8");
const connectivity = readFileSync(new URL("src/connectivity-status.mjs", root), "utf8");
const pages = [
  "index.html",
  "cart-preview.html",
  "confirmation-preview.html",
  "quick-pickup-preview.html",
];

test("primary customer pages share the connectivity module that loads bilingual page chrome", () => {
  assert.match(connectivity, /import "\.\/page-chrome-locale\.mjs"/);
  for (const page of pages) {
    const html = readFileSync(new URL(page, root), "utf8");
    assert.match(html, /src\/connectivity-status\.mjs/);
  }
});

test("page chrome helper localizes keyboard and language-control labels", () => {
  assert.match(helper, /Skip to content/);
  assert.match(helper, /メインコンテンツへ移動/);
  assert.match(helper, /language: "Language"/);
  assert.match(helper, /language: "言語"/);
  assert.match(helper, /\.skip-link/);
  assert.match(helper, /aria-label/);
  assert.match(helper, /attributeFilter: \["lang"\]/);
  assert.match(helper, /typeof document !== "undefined"/);
});

test("page chrome helper localizes visible preview boundary copy for each mobile destination", () => {
  assert.match(helper, /Isolated preview · No live checkout/);
  assert.match(helper, /隔離プレビュー · ライブチェックアウトなし/);
  assert.match(helper, /Isolated preview · KOMOJU not connected/);
  assert.match(helper, /隔離プレビュー · KOMOJU未接続/);
  assert.match(helper, /Isolated synthetic preview · No order submission/);
  assert.match(helper, /隔離された合成プレビュー · 注文送信なし/);
  assert.match(helper, /Isolated preview · No external activation/);
  assert.match(helper, /隔離プレビュー · 外部有効化なし/);
  assert.match(helper, /\.status-pill/);
  assert.match(helper, /footer p/);
  assert.match(helper, /pageChromeKey/);
});

test("shared preview chrome localizes browser metadata without changing catalog SEO", () => {
  assert.match(helper, /Phil AI OS — Final Confirmation Preview/);
  assert.match(helper, /Phil AI OS — 注文最終確認プレビュー/);
  assert.match(helper, /Phil AI OS — Quick Pickup Readiness Preview/);
  assert.match(helper, /Phil AI OS — クイックピックアップ準備状況プレビュー/);
  assert.match(helper, /isolated final order confirmation compliance preview/);
  assert.match(helper, /分離された注文最終確認コンプライアンスプレビュー/);
  assert.match(helper, /isolated Air Mobile Quick Pickup readiness preview/);
  assert.match(helper, /Air モバイルオーダー・クイックピックアップ準備状況プレビュー/);
  assert.match(helper, /const metadata = localized\.metadata\?\.\[page\]/);
  assert.match(helper, /document\.title = metadata\.title/);
  assert.match(helper, /meta\[name="description"\]/);
  assert.doesNotMatch(helper, /catalog: Object\.freeze\(\{\s*title:/);
});

test("remaining cart confirmation and Quick Pickup semantic labels follow EN and JA locale", () => {
  assert.match(helper, /"← Catalog preview"/);
  assert.match(helper, /"← 商品プレビュー"/);
  assert.match(helper, /"Readiness result"/);
  assert.match(helper, /"準備状況結果"/);
  assert.match(helper, /"Final-step review"/);
  assert.match(helper, /"最終ステップ確認"/);
  assert.match(helper, /"Review before submitting"/);
  assert.match(helper, /"送信前に確認"/);
  assert.match(helper, /"This is not the actual WooCommerce final screen"/);
  assert.match(helper, /"これは実際のWooCommerce最終画面ではありません"/);
  assert.match(helper, /"External Quick Pickup"/);
  assert.match(helper, /"外部クイックピックアップ"/);
  assert.match(helper, /"Authority boundary"/);
  assert.match(helper, /"権限境界"/);
  assert.match(helper, /applySemanticCopy\(localized\.semantics\?\.\[page\]\)/);
  assert.match(helper, /document\.querySelector\(selector\)/);
});
