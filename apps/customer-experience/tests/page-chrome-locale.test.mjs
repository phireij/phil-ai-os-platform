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
