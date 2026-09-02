import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("service worker only falls back to app shell for navigation requests", () => {
  assert.match(sw, /event\.request\.mode === "navigate"/);
  assert.match(sw, /caches\.match\("\.\/index\.html"\)/);
});

test("failed non-navigation requests fail closed instead of receiving HTML", () => {
  assert.match(sw, /new Response\("", \{ status: 503, statusText: "Offline" \}\)/);
  assert.doesNotMatch(sw, /catch\(\(\) => caches\.match\("\.\/index\.html"\)\)/);
});

test("successful same-origin responses remain cacheable", () => {
  assert.match(sw, /response\.status === 200/);
  assert.match(sw, /cache\.put\(event\.request, copy\)/);
});
