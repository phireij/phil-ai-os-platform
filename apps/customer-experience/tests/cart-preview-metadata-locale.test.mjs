import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/cart-preview.mjs", import.meta.url), "utf8");

test("cart preview localizes browser metadata with locale changes", () => {
  assert.match(source, /pageTitle: "Phil AI OS — Cart & KOMOJU Handoff Preview"/);
  assert.match(source, /pageTitle: "Phil AI OS — カート・KOMOJU引継ぎプレビュー"/);
  assert.match(source, /metaDescription: "Phil AI OS isolated multi-item checkout and KOMOJU handoff preview"/);
  assert.match(source, /metaDescription: "Phil AI OS の分離された複数商品チェックアウトとKOMOJU引継ぎプレビュー"/);
  assert.match(source, /document\.title = c\.pageTitle/);
  assert.ok(source.includes("document.querySelector('meta[name=\"description\"]')"));
  assert.match(source, /setAttribute\("content", c\.metaDescription\)/);
});
