import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../mobile-performance.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("storefront loads dedicated mobile performance hardening", () => {
  assert.match(html, /mobile-performance\.css/);
  assert.match(css, /content-visibility:\s*auto/);
  assert.match(css, /contain-intrinsic-size/);
});

test("loading feedback reserves space and respects reduced motion", () => {
  assert.match(css, /\.cx-state-loading/);
  assert.match(css, /min-height:\s*9rem/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /animation:\s*none/);
});

test("performance asset remains available on weak connections through the PWA shell", () => {
  assert.match(sw, /phil-ai-os-cx-sprint4-v17/);
  assert.match(sw, /\.\/mobile-performance\.css/);
});

test("performance hardening adds no commerce authority or network mutation", () => {
  assert.doesNotMatch(css, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(css, /mutation_authorized/);
});
