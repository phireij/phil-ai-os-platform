import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const shop = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const cart = readFileSync(new URL("../cart-preview.html", import.meta.url), "utf8");
const pickup = readFileSync(new URL("../quick-pickup-preview.html", import.meta.url), "utf8");

test("each primary mobile destination identifies its current page", () => {
  assert.match(shop, /href="#catalog-section" aria-current="page"/);
  assert.match(cart, /href="\.\/cart-preview\.html" aria-current="page"/);
  assert.match(pickup, /href="\.\/quick-pickup-preview\.html" aria-current="page"/);
});

test("mobile navigation still exposes the same three destinations", () => {
  for (const html of [shop, cart, pickup]) {
    assert.match(html, /mobile-action-dock/);
    assert.match(html, /dock-shop-label/);
    assert.match(html, /dock-cart-label/);
    assert.match(html, /dock-pickup-label/);
  }
});
