import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const performanceCss = readFileSync(new URL("../mobile-performance.css", import.meta.url), "utf8");
const narrowCss = readFileSync(new URL("../mobile-narrow-screen.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("mobile performance layer loads narrow-screen resilience", () => {
  assert.match(performanceCss, /@import "\.\/mobile-narrow-screen\.css"/);
});

test("narrow screens avoid min-content overflow in major customer surfaces", () => {
  assert.match(narrowCss, /\.product-card-body/);
  assert.match(narrowCss, /\.detail-copy/);
  assert.match(narrowCss, /\.checkout-card/);
  assert.match(narrowCss, /\.mobile-action-dock a/);
  assert.match(narrowCss, /min-width:\s*0/);
  assert.match(narrowCss, /overflow-wrap:\s*anywhere/);
});

test("very small phones and landscape phones retain usable controls", () => {
  assert.match(narrowCss, /max-width:\s*360px/);
  assert.match(narrowCss, /max-height:\s*500px/);
  assert.match(narrowCss, /orientation:\s*landscape/);
  assert.match(narrowCss, /--mobile-dock-height:\s*64px/);
  assert.match(narrowCss, /min-height:\s*48px/);
});

test("narrow-screen hardening remains accessibility-friendly, local and cached", () => {
  assert.match(narrowCss, /forced-colors:\s*active/);
  assert.doesNotMatch(narrowCss, /https?:\/\//);
  assert.doesNotMatch(narrowCss, /POST|PUT|PATCH|DELETE/);
  assert.match(sw, /\.\/mobile-narrow-screen\.css/);
});
