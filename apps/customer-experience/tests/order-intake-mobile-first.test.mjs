import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../order-intake-preview.html", import.meta.url), "utf8");
const css = readFileSync(new URL("../order-intake-preview.css", import.meta.url), "utf8");
const source = readFileSync(new URL("../src/order-intake-preview.mjs", import.meta.url), "utf8");
const index = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const sw = readFileSync(new URL("../sw.js", import.meta.url), "utf8");

test("order intake is mobile-first with safe-area support and 48px controls", () => {
  assert.match(html, /width=device-width,initial-scale=1,viewport-fit=cover/);
  assert.match(css, /env\(safe-area-inset-bottom\)/);
  assert.match(css, /min-height: 48px/);
  assert.match(css, /font-size: 16px/);
  assert.match(css, /grid-template-columns: minmax\(0, 1fr\)/);
});

test("desktop remains explicitly supported with a wider responsive layout", () => {
  assert.match(css, /@media \(min-width: 900px\)/);
  assert.match(css, /grid-template-columns: minmax\(0, 1\.7fr\) minmax\(18rem, \.8fr\)/);
  assert.match(css, /position: sticky/);
});

test("requested delivery is clearly non-guaranteed before payment", () => {
  assert.match(html, /requested delivery date and time are not guaranteed yet/i);
  assert.match(html, /This is a request, not a confirmed date/);
  assert.match(html, /Payment<\/dt><dd>Not requested/);
  assert.match(source, /Delivery and final quote still require confirmation before payment/);
});

test("Ruby car guidance mirrors the approved provisional route policy without live calculation", () => {
  assert.match(html, /up to 10 km ¥2,500/);
  assert.match(html, /over 10–30 km \+¥150 per started km/);
  assert.match(html, /over 30–50 km \+¥200 per started km/);
  assert.match(html, /over 50–80 km manual quote/);
  assert.match(html, /over 80 km unavailable/);
  assert.match(html, /Tolls are separate/);
  assert.match(html, /routes over 75 minutes one-way require review/);
  assert.match(source, /Pending route review — no live calculation/);
  assert.match(source, /rubyCarRouteGuidance\.hidden = !isRubyCar/);
});

test("custom cake flow accepts only private image-oriented references and no standalone topper", () => {
  assert.match(html, /accept="image\/jpeg,image\/png,image\/webp"/);
  assert.match(html, /multiple/);
  assert.match(html, /Up to 8 reference images/);
  assert.match(html, /private order inputs/);
  assert.match(html, /Photo topper[\s\S]*available only as part of a cake order/);
  assert.match(html, /Edible topper[\s\S]*available only as part of a cake order/);
  assert.match(source, /files\.length > 8/);
});

test("icing captures preference but leaves unapproved color pricing inactive", () => {
  assert.match(html, /White is the working default/);
  assert.match(html, /Additional-color pricing is still pending Ruby’s business confirmation/);
  const icingSection = html.match(/<fieldset class="choice-list intake-field">\s*<legend>Icing \/ アイシング<\/legend>[\s\S]*?<\/fieldset>/)?.[0] || "";
  assert.ok(icingSection, "icing section must remain present");
  assert.doesNotMatch(icingSection, /¥200/);
  assert.doesNotMatch(source, /200/);
});

test("preview behavior is local and non-authorizing", () => {
  assert.match(source, /event\.preventDefault\(\)/);
  assert.doesNotMatch(source, /fetch\s*\(/);
  assert.doesNotMatch(source, /XMLHttpRequest|WebSocket|sendBeacon/);
  assert.doesNotMatch(source, /POST|PUT|PATCH|DELETE/);
  assert.match(html, /never creates an order, uploads a file, calculates a live route, charges a payment, or mutates WooCommerce/);
});

test("order intake preview is discoverable and cached in the isolated shell", () => {
  assert.match(index, /\.\/order-intake-preview\.html/);
  assert.match(sw, /phil-ai-os-cx-sprint4-v\d+/);
  assert.match(sw, /\.\/order-intake-preview\.html/);
  assert.match(sw, /\.\/order-intake-preview\.css/);
  assert.match(sw, /\.\/src\/order-intake-preview\.mjs/);
});