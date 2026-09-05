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
