import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const sourceUrl = new URL("../src/product-detail-facts.mjs", import.meta.url);
const source = readFileSync(sourceUrl, "utf8");
const css = readFileSync(new URL("../product-detail-facts.css", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("product detail facts module has valid syntax", () => {
  execFileSync(process.execPath, ["--check", fileURLToPath(sourceUrl)], { stdio: "pipe" });
});

test("product detail surfaces availability price and pickup support as key facts", () => {
  assert.match(source, /product-key-facts/);
  assert.match(source, /Availability/);
  assert.match(source, /在庫状況/);
  assert.match(source, /Price/);
  assert.match(source, /価格/);
  assert.match(source, /Pickup supported/);
  assert.match(source, /店頭受取対応/);
  assert.match(source, /pickupSupported/);
});

test("product detail media uses fixture alt text and image semantics", () => {
  assert.match(source, /mediaAlt/);
  assert.match(source, /localized\(product\.media\[0\]\.alt, lang\)/);
  assert.match(source, /setAttribute\("role", "img"\)/);
  assert.match(source, /setAttribute\("aria-label", facts\.mediaAlt\)/);
});

test("mobile key facts remain scannable", () => {
  assert.match(css, /\.product-key-facts/);
  assert.match(css, /\.product-key-fact/);
  assert.match(css, /grid-template-columns/);
  assert.match(css, /@media \(max-width: 679px\)/);
});

test("detail facts remain fixture-only and non-authorizing", () => {
  assert.match(source, /fixture_only !== true/);
  assert.match(source, /\.\/fixtures\/catalog\.json/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
});

test("product detail facts are loaded and cached for weak connections", () => {
  assert.match(html, /product-detail-facts\.css/);
  assert.match(html, /src\/product-detail-facts\.mjs/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/product-detail-facts\.css/);
  assert.match(sw, /\.\/src\/product-detail-facts\.mjs/);
});
