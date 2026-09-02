import test from "node:test";
import assert from "node:assert/strict";

import { UI_STATE_KINDS, uiState } from "../src/ui-state.mjs";

test("all customer UI states remain non-authorizing", () => {
  for (const kind of UI_STATE_KINDS) {
    const state = uiState(kind, "en");
    assert.equal(state.mutation_authorized, false);
    assert.ok(state.title);
    assert.ok(state.message);
  }
});

test("loading and recovery states are bilingual", () => {
  assert.equal(uiState("loading", "en").title, "Loading products");
  assert.equal(uiState("loading", "ja").title, "商品を読み込んでいます");
  assert.equal(uiState("error", "en").retry_label, "Reload preview");
  assert.equal(uiState("error", "ja").retry_label, "プレビューを再読み込み");
});

test("missing product route guidance is customer friendly", () => {
  const en = uiState("route_missing", "en");
  const ja = uiState("route_missing", "ja");
  assert.match(en.message, /product list/i);
  assert.match(ja.message, /商品一覧/);
});

test("unsupported UI state fails closed", () => {
  assert.throws(() => uiState("success-authorized", "en"), /unsupported UI state/);
});

test("unsupported locale falls back to English", () => {
  const state = uiState("empty", "fr");
  assert.equal(state.locale, "en");
  assert.equal(state.mutation_authorized, false);
});
