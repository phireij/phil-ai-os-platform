import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const mobileUx = readFileSync(new URL("../src/mobile-ux.mjs", import.meta.url), "utf8");

test("storefront shared chrome participates in EN/JA localization", () => {
  assert.match(mobileUx, /skipToContent:\s*"Skip to content"/);
  assert.match(mobileUx, /skipToContent:\s*"本文へ移動"/);
  assert.match(mobileUx, /languageLabel:\s*"言語"/);
  assert.match(mobileUx, /previewStatus:\s*"分離プレビュー · ライブチェックアウトなし"/);
  assert.match(mobileUx, /footer:\s*"Phil AI OS · Sprint 4 カスタマーエクスペリエンス · 合成フィクスチャ環境"/);
});

test("shared chrome selectors and accessibility labels are updated by locale", () => {
  assert.match(mobileUx, /"\.skip-link":\s*"skipToContent"/);
  assert.match(mobileUx, /"\.site-header \.brand":\s*"brand"/);
  assert.match(mobileUx, /"\.locale-label":\s*"languageLabel"/);
  assert.match(mobileUx, /"\.hero \.status-pill":\s*"previewStatus"/);
  assert.match(mobileUx, /"footer p":\s*"footer"/);
  assert.match(mobileUx, /heroActions\.setAttribute\("aria-label", copy\.previewActionsLabel\)/);
});
