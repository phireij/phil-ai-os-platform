import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const performanceCss = readFileSync(new URL("../mobile-performance.css", import.meta.url), "utf8");
const mediaCss = readFileSync(new URL("../product-media-resilience.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("mobile performance layer loads the dedicated product media contract", () => {
  assert.match(performanceCss, /@import "\.\/product-media-resilience\.css"/);
  assert.match(mediaCss, /\.product-media/);
  assert.match(mediaCss, /\.detail-media/);
});

test("product media reserves stable geometry before future images load", () => {
  assert.match(mediaCss, /aspect-ratio:\s*4\s*\/\s*3/);
  assert.match(mediaCss, /overflow:\s*hidden/);
  assert.match(mediaCss, /contain:\s*paint/);
});

test("future product images fill reserved slots without distortion", () => {
  assert.match(mediaCss, /> img/);
  assert.match(mediaCss, /width:\s*100%/);
  assert.match(mediaCss, /height:\s*100%/);
  assert.match(mediaCss, /object-fit:\s*cover/);
  assert.match(mediaCss, /object-position:\s*center/);
  assert.match(mediaCss, /img\[loading="lazy"\]/);
});

test("media resilience remains local, accessibility-friendly and PWA cached", () => {
  assert.match(mediaCss, /forced-colors:\s*active/);
  assert.doesNotMatch(mediaCss, /https?:\/\//);
  assert.doesNotMatch(mediaCss, /POST|PUT|PATCH|DELETE/);
  assert.match(sw, /\.\/product-media-resilience\.css/);
});
