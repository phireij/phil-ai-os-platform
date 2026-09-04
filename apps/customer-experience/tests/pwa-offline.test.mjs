import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("navigation uses network first and falls back to cached page or app shell", () => {
  assert.match(sw, /async function navigationResponse/);
  assert.match(sw, /const response = await fetch\(request\)/);
  assert.match(sw, /const exact = await caches\.match\(request\)/);
  assert.match(sw, /caches\.match\("\.\/index\.html"\)/);
});

test("failed non-navigation requests fail closed instead of receiving HTML", () => {
  assert.match(sw, /async function staticResponse/);
  assert.match(sw, /new Response\("", \{ status: 503, statusText: "Offline" \}\)/);
});

test("successful same-origin responses remain cacheable", () => {
  assert.match(sw, /response\.status === 200/);
  assert.match(sw, /cache\.put\(request, copy\)/);
});

test("PWA shell includes the mobile UX and Quick Pickup dependencies", () => {
  assert.match(sw, /\.\/src\/mobile-ux\.mjs/);
  assert.match(sw, /\.\/src\/checkout-confidence\.mjs/);
  assert.match(sw, /\.\/quick-pickup-preview\.html/);
  assert.match(sw, /\.\/src\/quick-pickup-preview\.mjs/);
  assert.match(sw, /\.\/fixtures\/air-mobile-quick-pickup\.json/);
});
