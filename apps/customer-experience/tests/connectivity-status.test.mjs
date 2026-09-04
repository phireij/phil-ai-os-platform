import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { connectivityMessage } from "../src/connectivity-status.mjs";

const source = readFileSync(new URL("../src/connectivity-status.mjs", import.meta.url), "utf8");
const css = readFileSync(new URL("../connectivity-status.css", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");
const pages = ["index.html", "cart-preview.html", "confirmation-preview.html", "quick-pickup-preview.html"]
  .map((name) => readFileSync(new URL(`../${name}`, import.meta.url), "utf8"));

test("connectivity copy distinguishes online and offline without implying live commerce", () => {
  assert.match(connectivityMessage({ online: true, locale: "en" }), /isolated preview only/);
  assert.match(connectivityMessage({ online: false, locale: "en" }), /cached preview only/);
  assert.match(connectivityMessage({ online: false, locale: "en" }), /orders and payments cannot be submitted/);
  assert.match(connectivityMessage({ online: false, locale: "ja" }), /オフライン/);
  assert.match(connectivityMessage({ online: false, locale: "ja" }), /注文送信・決済実行はできません/);
});

test("connectivity status is accessible, bilingual and reacts locally to browser state", () => {
  assert.match(source, /aria-live/);
  assert.match(source, /aria-atomic/);
  assert.match(source, /addEventListener\("online"/);
  assert.match(source, /addEventListener\("offline"/);
  assert.match(source, /#locale-select/);
  assert.match(css, /data-connection="offline"/);
  assert.match(css, /@media \(max-width: 679px\)/);
  assert.match(css, /@media \(forced-colors: active\)/);
});

test("connectivity status remains network-inert and non-authorizing", () => {
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /XMLHttpRequest|sendBeacon/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.doesNotMatch(source, /mutation_authorized\s*:\s*true/);
  assert.doesNotMatch(source, /order_creation_authorized\s*:\s*true/);
  assert.doesNotMatch(source, /payment_execution_authorized\s*:\s*true/);
});

test("all customer preview surfaces load the connectivity status", () => {
  for (const html of pages) {
    assert.match(html, /connectivity-status\.css/);
    assert.match(html, /src\/connectivity-status\.mjs/);
  }
});

test("connectivity assets remain available through the PWA shell", () => {
  assert.match(sw, /\.\/connectivity-status\.css/);
  assert.match(sw, /\.\/src\/connectivity-status\.mjs/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v19/);
});
