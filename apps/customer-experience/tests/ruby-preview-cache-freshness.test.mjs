import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const serviceWorker = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("branded Ruby preview assets are network-first", () => {
  assert.match(serviceWorker, /const CACHE_NAME = "phil-ai-os-cx-sprint4-v\d+";/);
  assert.match(serviceWorker, /function isRubyPreviewAsset\(url\)/);
  assert.match(serviceWorker, /url\.pathname\.includes\("\/src\/ruby-"\)/);
  assert.match(serviceWorker, /async function rubyPreviewStaticResponse\(request\)/);
  assert.match(serviceWorker, /fetch\(request, \{ cache: "no-store" \}\)/);
  assert.match(serviceWorker, /isRubyPreviewAsset\(url\) \? rubyPreviewStaticResponse\(event\.request\) : staticResponse\(event\.request\)/);
});
